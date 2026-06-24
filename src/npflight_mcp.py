#!/usr/bin/env python3
"""agent-operating-framework MCP server — portable, stdlib-only, zero external deps.

Exposes 8 tools that wire an AI agent into a structured execution loop:
  preflight       → git drift-safety checks, returns {status, checks[]}
  check_contract  → validate task brief has required scope-lock fields
  operating_protocol → return configured operating rules text
  post_evidence   → post execution evidence to Asana (requires ASANA_TOKEN)
  verify_gate     → run a configured quality gate (ruff, pytest, custom)
  audit_scope     → check changed files against contract Scope globs
  session_log     → append named event to session audit trail
  query_audit     → query ~/.npflight/audit.jsonl with filters

Configuration: ~/.npflight/config.json (all optional — works with sensible defaults)
Audit trail:   ~/.npflight/audit.jsonl     (one JSON line per tool call)
Decisions:     ~/.npflight/decisions.jsonl  (check_contract verdicts)
Debug mode:    MCP_DEBUG=true → include tracebacks in error responses

Register in Claude Code:
  Add to .mcp.json → {"command":"python3","args":["/path/to/src/npflight_mcp.py"]}
"""
import datetime
import fnmatch
import json
import os
import re
import subprocess
import sys
import time
import traceback
import urllib.error
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
PROTO_VERSION = "2025-06-18"
SERVER_VERSION = "2.1.0"

AUDIT_DIR = os.path.expanduser("~/.npflight")
AUDIT_FILE = os.path.join(AUDIT_DIR, "audit.jsonl")
DECISION_FILE = os.path.join(AUDIT_DIR, "decisions.jsonl")
CONFIG_FILE = os.path.join(AUDIT_DIR, "config.json")
SESSION_ID = uuid.uuid4().hex[:8]
DEBUG = os.environ.get("MCP_DEBUG", "").lower() == "true"

_CFG: dict | None = None


def _cfg() -> dict:
    global _CFG
    if _CFG is None:
        try:
            _CFG = json.loads(open(CONFIG_FILE, encoding="utf-8").read()) if os.path.exists(CONFIG_FILE) else {}
        except Exception:
            _CFG = {}
    return _CFG


def _contract_fields() -> list[str]:
    return _cfg().get("contract_fields",
                      ["Task", "Owner", "Scope", "DoD", "Do not", "Stop if", "Return"])


def _gates() -> dict:
    defaults = {
        "ruff": ["ruff", "check", "."],
        "pytest": ["python", "-m", "pytest", "tests/", "-x", "-q", "--tb=short"],
    }
    return {**defaults, **_cfg().get("gates", {})}


def _protocol_path() -> str | None:
    configured = _cfg().get("operating_protocol_path")
    if configured and os.path.exists(configured):
        return configured
    for base in (os.getcwd(), os.path.dirname(HERE), HERE):
        p = os.path.join(base, "OPERATING_PROTOCOL.md")
        if os.path.exists(p):
            return p
    return None


TOOLS = [
    {
        "name": "preflight",
        "description": (
            "Run FIRST every task. Resolves which git repo/branch the agent is in and "
            "runs drift-safety checks. Returns {status, checks[], blockers[], warnings[]}. "
            "status=blocked → stop; status=warn → proceed with caution; status=clear → proceed."
        ),
        "inputSchema": {"type": "object", "properties": {
            "cwd": {"type": "string", "description": "absolute working directory of the agent"},
            "task": {"type": "string", "description": "task id this session is bound to (optional)"},
        }},
    },
    {
        "name": "check_contract",
        "description": (
            "Validate that a task brief contains all required scope-lock fields. "
            "Fields are configurable in ~/.npflight/config.json (default: Task/Owner/Scope/DoD/Do not/Stop if/Return). "
            "Writes a tamper-evident decision record to ~/.npflight/decisions.jsonl before returning. "
            "Returns {ok, missing[], found{}, decision_id, suggestions{}, verdict}."
        ),
        "inputSchema": {"type": "object", "required": ["brief"], "properties": {
            "brief": {"type": "string", "description": "full task brief text to validate"},
        }},
    },
    {
        "name": "operating_protocol",
        "description": (
            "Return the operating protocol rules text. Reads from operating_protocol_path in config, "
            "or searches for OPERATING_PROTOCOL.md in CWD / project root. "
            "Returns the text (up to 6000 chars) or a built-in fallback."
        ),
        "inputSchema": {"type": "object", "properties": {}},
    },
    {
        "name": "post_evidence",
        "description": (
            "Post agent execution evidence as a comment on an Asana task. "
            "Requires ASANA_TOKEN environment variable. Call when DoD is met or Stop-if fires. "
            "Returns {ok, story_gid} on success, {ok: false, error} on failure."
        ),
        "inputSchema": {"type": "object", "required": ["task_gid", "summary"], "properties": {
            "task_gid": {"type": "string", "description": "Asana task GID (numeric string)"},
            "summary": {"type": "string", "description": "1-3 sentence evidence summary"},
            "exit_code": {"type": "integer", "default": 0,
                          "description": "0 = success, non-zero = failure/blocked"},
            "artifacts": {"type": "array", "items": {"type": "string"},
                          "description": "artifact paths or URLs produced"},
            "duration_s": {"type": "number", "default": 0,
                           "description": "wall-clock execution time in seconds"},
        }},
    },
    {
        "name": "verify_gate",
        "description": (
            "Run a quality gate and return structured results. "
            "Built-in gates: ruff, pytest. Custom gates configurable in ~/.npflight/config.json. "
            "Returns {gate, status, exit_code, output, duration_s}. "
            "status values: pass | fail | timeout | error."
        ),
        "inputSchema": {"type": "object", "properties": {
            "gate_type": {"type": "string", "description": "gate name (ruff, pytest, or custom from config)"},
            "cwd": {"type": "string", "description": "working directory (default: current directory)"},
            "extra_args": {"type": "array", "items": {"type": "string"},
                           "description": "extra arguments appended to the gate command"},
        }},
    },
    {
        "name": "audit_scope",
        "description": (
            "Check whether changed files are within the contract Scope. "
            "Scope is a comma or newline separated list of glob patterns. "
            "Returns {ok, in_scope[], out_of_scope[], verdict}."
        ),
        "inputSchema": {"type": "object", "required": ["scope", "changed_files"], "properties": {
            "scope": {"type": "string",
                      "description": "contract Scope field — comma or newline separated glob patterns"},
            "changed_files": {"type": "array", "items": {"type": "string"},
                              "description": "list of changed file paths"},
        }},
    },
    {
        "name": "session_log",
        "description": (
            "Append a named event to the session audit log (~/.npflight/audit.jsonl). "
            "Use at key decision points: dod_met, blocker_hit, scope_check, stop_if_fired, evidence_posted."
        ),
        "inputSchema": {"type": "object", "required": ["event"], "properties": {
            "event": {"type": "string",
                      "description": "event name e.g. dod_met, blocker_hit, scope_check"},
            "data": {"type": "object", "description": "key-value context for this event"},
        }},
    },
    {
        "name": "query_audit",
        "description": (
            "Query the session audit log (~/.npflight/audit.jsonl). "
            "Returns recent entries, summary stats, and per-tool counts. "
            "Useful for understanding agent activity patterns and debugging sessions."
        ),
        "inputSchema": {"type": "object", "properties": {
            "limit": {"type": "integer", "default": 20,
                      "description": "max number of recent entries to return"},
            "tool": {"type": "string",
                     "description": "filter by tool name (optional)"},
            "session_id": {"type": "string",
                           "description": "filter by session id (optional)"},
        }},
    },
]


# ── Audit helpers ────────────────────────────────────────────────────────────

def _now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def _audit(tool: str, args_summary: dict, result_summary: str, duration_ms: int = 0) -> None:
    os.makedirs(AUDIT_DIR, exist_ok=True)
    entry = {
        "ts": _now(), "session_id": SESSION_ID, "tool": tool,
        "args": {k: str(v)[:120] for k, v in args_summary.items()},
        "result": result_summary[:200], "duration_ms": duration_ms,
    }
    try:
        with open(AUDIT_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _write_decision(record: dict) -> None:
    os.makedirs(AUDIT_DIR, exist_ok=True)
    try:
        with open(DECISION_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception:
        pass


# ── Tool implementations ─────────────────────────────────────────────────────

def t_preflight(a: dict) -> str:
    cwd = a.get("cwd") or os.getcwd()
    script = os.path.join(HERE, "npflight.py")
    cmd = [sys.executable, script, "--json"]
    if a.get("task"):
        cmd += ["--task", str(a["task"])]

    t0 = time.monotonic()
    if os.path.exists(script):
        run_cwd = cwd if os.path.isdir(cwd) else None
        r = subprocess.run(cmd, cwd=run_cwd, capture_output=True, text=True)
        try:
            card = json.loads(r.stdout)
        except Exception:
            card = {"raw": (r.stdout or r.stderr or "(no output)")[:500], "parse_error": True}
    else:
        card = {"status": "warn", "note": "npflight.py not found — install the full package",
                "checks": [], "blockers": [], "warnings": []}

    duration_ms = round((time.monotonic() - t0) * 1000)
    card.update({"session_id": SESSION_ID, "duration_ms": duration_ms})
    _audit("preflight", {"cwd": cwd, "task": a.get("task", "")},
           card.get("status", "unknown"), duration_ms)
    return json.dumps(card, ensure_ascii=False)


def t_check_contract(a: dict) -> str:
    brief = a.get("brief", "")
    fields = _contract_fields()
    missing, found = [], {}
    suggestions = {
        "DoD": "DoD: all tests pass, gate clean, evidence posted",
        "Stop if": "Stop if: any file outside Scope is needed, or DoD cannot be met",
        "Return": "Return: diff summary + gate results + evidence URL (or blocker + next owner)",
    }

    for field in fields:
        pattern = r"(?m)^\s*[\*\-]*\s*" + re.escape(field) + r"\s*[\*\-]*\s*:\s*(.+)"
        m = re.search(pattern, brief, re.IGNORECASE)
        if m:
            found[field] = m.group(1).strip()[:120]
        else:
            missing.append(field)

    ok = len(missing) == 0
    decision_id = uuid.uuid4().hex[:8]

    # Write tamper-evident decision record BEFORE returning
    _write_decision({
        "ts": _now(), "session_id": SESSION_ID, "decision_id": decision_id,
        "verdict": "CONTRACT_OK" if ok else "CONTRACT_INCOMPLETE",
        "missing_fields": missing, "found_fields": list(found.keys()),
    })

    verdict = ("CONTRACT OK — all scope-lock fields present." if ok
               else f"CONTRACT INCOMPLETE — missing: {', '.join(missing)}")
    result = {
        "ok": ok, "missing": missing, "found": found, "decision_id": decision_id,
        "suggestions": {f: suggestions[f] for f in missing if f in suggestions},
        "verdict": verdict,
    }
    _audit("check_contract", {"brief_len": str(len(brief))}, verdict)
    return json.dumps(result, ensure_ascii=False)


def t_operating_protocol(a: dict) -> str:
    path = _protocol_path()
    if path:
        content = open(path, encoding="utf-8").read()[:6000]
        _audit("operating_protocol", {}, f"returned {len(content)} chars from {path}")
        return content
    fallback = (
        "LOOP: preflight → check_contract → branch → plan → work → verify_gate → "
        "audit_scope → post_evidence → Done|Blocked.\n"
        "CONTRACT: Task/Owner/Scope/DoD/Do-not/Stop-if/Return. "
        "Stop at scope boundary — return blocker, never self-expand.\n"
        "Configure: create ~/.npflight/config.json with operating_protocol_path."
    )
    _audit("operating_protocol", {}, "returned built-in fallback")
    return fallback


def t_post_evidence(a: dict) -> str:
    task_gid = a.get("task_gid", "").strip()
    summary = a.get("summary", "").strip()
    exit_code = int(a.get("exit_code", 0))
    artifacts = a.get("artifacts") or []
    duration_s = float(a.get("duration_s", 0))

    if not task_gid:
        return json.dumps({"ok": False, "error": "task_gid is required"})
    if not summary:
        return json.dumps({"ok": False, "error": "summary is required"})
    token = os.environ.get("ASANA_TOKEN", "")
    if not token:
        return json.dumps({"ok": False, "error": "ASANA_TOKEN env var not set"})

    icon = "✅" if exit_code == 0 else "❌"
    lines = [
        f"{icon} Agent Evidence [session={SESSION_ID}]",
        f"Summary: {summary}",
        f"Exit code: {exit_code} | Duration: {duration_s:.1f}s",
    ]
    if artifacts:
        lines += ["Artifacts:"] + [f"  - {art}" for art in artifacts[:10]]

    payload = json.dumps({"data": {"text": "\n".join(lines)}}).encode()
    url = f"https://app.asana.com/api/1.0/tasks/{task_gid}/stories"
    req = urllib.request.Request(url, data=payload, method="POST", headers={
        "Authorization": f"Bearer {token}", "Content-Type": "application/json",
    })
    t0 = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read())
            story_gid = body.get("data", {}).get("gid", "")
            result = {"ok": True, "story_gid": story_gid, "task_gid": task_gid}
            _audit("post_evidence", {"task_gid": task_gid, "exit_code": str(exit_code)},
                   f"posted story {story_gid}", round((time.monotonic() - t0) * 1000))
            return json.dumps(result)
    except urllib.error.HTTPError as e:
        err = e.read().decode()[:200]
        result = {"ok": False, "error": f"HTTP {e.code}: {err}"}
        _audit("post_evidence", {"task_gid": task_gid}, f"HTTP {e.code}")
        return json.dumps(result)
    except Exception as e:
        result = {"ok": False, "error": str(e)}
        _audit("post_evidence", {"task_gid": task_gid}, f"error: {e}")
        return json.dumps(result)


def t_verify_gate(a: dict) -> str:
    gate = a.get("gate_type", "ruff")
    cwd = a.get("cwd") or os.getcwd()
    extra = a.get("extra_args") or []
    gates = _gates()

    if gate not in gates:
        result = {"ok": False, "error": f"unknown gate '{gate}'. Available: {list(gates.keys())}"}
        return json.dumps(result)

    cmd = gates[gate] + list(extra)
    run_cwd = cwd if os.path.isdir(cwd) else os.getcwd()
    t0 = time.monotonic()
    try:
        r = subprocess.run(cmd, cwd=run_cwd, capture_output=True, text=True, timeout=120)
        duration_s = round(time.monotonic() - t0, 2)
        status = "pass" if r.returncode == 0 else "fail"
        result = {"gate": gate, "status": status, "exit_code": r.returncode,
                  "output": (r.stdout + r.stderr).strip()[:1500], "duration_s": duration_s}
        _audit("verify_gate", {"gate": gate}, f"{status} exit={r.returncode}",
               round(duration_s * 1000))
        return json.dumps(result)
    except subprocess.TimeoutExpired:
        result = {"gate": gate, "status": "timeout", "exit_code": -1,
                  "output": "timed out after 120s", "duration_s": 120.0}
        _audit("verify_gate", {"gate": gate}, "timeout")
        return json.dumps(result)
    except Exception as e:
        result = {"gate": gate, "status": "error", "exit_code": -1, "error": str(e)}
        _audit("verify_gate", {"gate": gate}, f"error: {e}")
        return json.dumps(result)


def t_audit_scope(a: dict) -> str:
    scope_raw = a.get("scope", "")
    changed_files = a.get("changed_files") or []
    patterns = [s.strip() for s in re.split(r"[,\n]", scope_raw) if s.strip()]
    in_scope, out_of_scope = [], []

    for f in changed_files:
        matched = any(
            fnmatch.fnmatch(f, pat)
            or fnmatch.fnmatch(os.path.basename(f), pat)
            or f.startswith(pat.rstrip("/*"))
            for pat in patterns
        )
        (in_scope if matched else out_of_scope).append(f)

    ok = len(out_of_scope) == 0
    verdict = ("SCOPE OK — all changed files within contract scope." if ok
               else f"SCOPE VIOLATION — {len(out_of_scope)} file(s) outside scope: {out_of_scope}")
    result = {"ok": ok, "in_scope": in_scope, "out_of_scope": out_of_scope, "verdict": verdict}
    _audit("audit_scope", {"n_files": str(len(changed_files))}, verdict)
    return json.dumps(result, ensure_ascii=False)


def t_session_log(a: dict) -> str:
    event = a.get("event", "custom")
    data = a.get("data") or {}
    entry = {"ts": _now(), "session_id": SESSION_ID, "event": event, "data": data}
    _audit("session_log", {"event": event}, f"logged: {event}")
    return json.dumps({"ok": True, "logged": entry}, ensure_ascii=False)


def t_query_audit(a: dict) -> str:
    limit = max(1, min(int(a.get("limit", 20)), 200))
    tool_filter = a.get("tool")
    session_filter = a.get("session_id")

    if not os.path.exists(AUDIT_FILE):
        return json.dumps({"ok": True, "entries": [], "total": 0,
                           "note": "No audit log yet — run some tools first."})

    all_entries, tool_counts, sessions_seen = [], {}, set()
    try:
        with open(AUDIT_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    e = json.loads(line)
                    tool_counts[e.get("tool", "?")] = tool_counts.get(e.get("tool", "?"), 0) + 1
                    sessions_seen.add(e.get("session_id", ""))
                    if tool_filter and e.get("tool") != tool_filter:
                        continue
                    if session_filter and e.get("session_id") != session_filter:
                        continue
                    all_entries.append(e)
                except Exception:
                    pass
    except Exception as e:
        return json.dumps({"ok": False, "error": str(e)})

    result = {
        "ok": True,
        "total_unfiltered": sum(tool_counts.values()),
        "total_filtered": len(all_entries),
        "entries": all_entries[-limit:],
        "summary": {
            "tool_counts": tool_counts,
            "unique_sessions": len(sessions_seen),
            "current_session": SESSION_ID,
        },
    }
    _audit("query_audit", {"limit": str(limit), "tool": tool_filter or ""}, f"returned {len(all_entries[-limit:])} entries")
    return json.dumps(result, ensure_ascii=False)


# ── MCP dispatch ─────────────────────────────────────────────────────────────

HANDLERS = {
    "preflight": t_preflight, "check_contract": t_check_contract,
    "operating_protocol": t_operating_protocol, "post_evidence": t_post_evidence,
    "verify_gate": t_verify_gate, "audit_scope": t_audit_scope,
    "session_log": t_session_log, "query_audit": t_query_audit,
}


def send(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def _error_text(e: Exception) -> str:
    return f"error: {e}\n{traceback.format_exc()}" if DEBUG else f"error: {e}"


def main() -> None:
    for raw in sys.stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except Exception:
            continue
        mid = msg.get("id")
        method = msg.get("method", "")

        if method == "initialize":
            send({"jsonrpc": "2.0", "id": mid, "result": {
                "protocolVersion": msg.get("params", {}).get("protocolVersion", PROTO_VERSION),
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "agent-operating-framework", "version": SERVER_VERSION},
                "instructions": (
                    "Execution loop: preflight → check_contract → work → "
                    "audit_scope → verify_gate → post_evidence → Done|Blocked. "
                    "Stop at contract scope boundary. Never self-expand scope."
                ),
            }})
        elif method in ("notifications/initialized", "notifications/cancelled"):
            pass
        elif method == "ping":
            send({"jsonrpc": "2.0", "id": mid, "result": {}})
        elif method == "tools/list":
            send({"jsonrpc": "2.0", "id": mid, "result": {"tools": TOOLS}})
        elif method == "tools/call":
            p = msg.get("params", {})
            name = p.get("name", "")
            fn = HANDLERS.get(name)
            try:
                text = fn(p.get("arguments", {})) if fn else json.dumps({"error": f"unknown tool: {name}"})
                send({"jsonrpc": "2.0", "id": mid,
                      "result": {"content": [{"type": "text", "text": text}], "isError": fn is None}})
            except Exception as e:
                send({"jsonrpc": "2.0", "id": mid,
                      "result": {"content": [{"type": "text", "text": _error_text(e)}], "isError": True}})
        elif mid is not None:
            send({"jsonrpc": "2.0", "id": mid,
                  "error": {"code": -32601, "message": f"method not found: {method}"}})


if __name__ == "__main__":
    main()
