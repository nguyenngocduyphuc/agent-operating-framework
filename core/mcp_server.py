#!/usr/bin/env python3
"""AOF MCP Server — stdio JSON-RPC 2.0 server for AOF framework tools.

No private paths, no project IDs, no secrets. Credentials checked for PRESENCE only.
Transport: newline-delimited JSON (one JSON-RPC message per line). Stdlib only.

Every ``tools/call`` reply is wrapped in the MCP result envelope
``{"content": [{"type": "text", "text": ...}], "isError": bool}``. A bare business
dict as ``result`` is not a valid tool result: hosts read ``content`` and show the
call as EMPTY, which silently disables the whole server.

Preconditions are ALWAYS ON and are reported as ``isError: true`` tool results,
not JSON-RPC protocol errors: the refusal has to reach the model as readable text
with a fix, and MCP reserves protocol errors for protocol faults (bad method, bad
JSON). The refusal still carries its stable numeric code in ``error_code``, so a
naive client can never mistake a refusal for a result.
"""
import fnmatch
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
import uuid
from pathlib import Path

from core import heartbeat as heartbeat_mod
from core import lease as lease_mod
from core import oplog as oplog_mod
from core.check_contract import validate as validate_contract
from core.enforcement import (
    audit_file,
    ensure_audit_dir,
    with_stall_warning,
    write_decision,
)
from core.preflight import load_policy, nearest_repo, workspace_root

# Gate timeout bounds. A caller may raise the per-command timeout for slow suites,
# but never past the ceiling -- an unbounded gate is a hung server.
DEFAULT_GATE_TIMEOUT_S = 120
MAX_GATE_TIMEOUT_S = 1800

# ---------------------------------------------------------------------------
# TOOLS catalog
# ---------------------------------------------------------------------------
TOOLS = [
    {"name":"preflight","description":"Run AOF preflight gate","inputSchema":{"type":"object","properties":{
        "cwd":{"type":"string"},"task":{"type":"string","description":"Task ID to bind"},
        "bootstrap":{"type":"boolean"},
        "lane":{"type":"string","enum":["lite","risk"],
                "description":"lite = preflight+evidence only (needs lanes_enabled policy; "
                              "auto-escalates to risk on multi-file or risky paths). Default risk."}}}},
    {"name":"check_contract","description":"Validate 7 contract fields + References","inputSchema":{"type":"object","properties":{
        "brief":{"type":"string"}},"required":["brief"]}},
    {"name":"operating_protocol","description":"Return OPERATING_PROTOCOL.md","inputSchema":{"type":"object","properties":{
        "workspace":{"type":"string"}}}},
    {"name":"verify_gate","description":"Run quality gate (ruff|pytest|quality) with optional multi-trial","inputSchema":{"type":"object","properties":{
        "gate_type":{"type":"string"},"cwd":{"type":"string"},
        "extra_args":{"type":"array","items":{"type":"string"}},
        "timeout_s":{"type":"integer","minimum":1,"maximum":MAX_GATE_TIMEOUT_S,
                     "description":f"per-command timeout in seconds (default {DEFAULT_GATE_TIMEOUT_S}, max {MAX_GATE_TIMEOUT_S})"},
        "trials":{"type":"integer","minimum":1,"maximum":10}},
     "required":["gate_type"]}},
    {"name":"audit_scope","description":"Check git-derived changed paths against contract scope globs","inputSchema":{"type":"object","properties":{
        "scope":{"type":"array","items":{"type":"string"},
                 "description":"glob patterns; a comma/newline separated string is also accepted"},
        "changed_files":{"type":"array","items":{"type":"string"}}},"required":["scope"]}},
    {"name":"session_log","description":"Append a named event to the audit log","inputSchema":{"type":"object","properties":{
        "event":{"type":"string","description":"goal|decision|dead-end|file|question"},
        "data":{"type":"object"}},"required":["event"]}},
    {"name":"post_evidence","description":"Post closeout evidence (adapter provides tracker token)","inputSchema":{"type":"object","properties":{
        "task_gid":{"type":"string"},"summary":{"type":"string"},
        "exit_code":{"type":"integer"},"artifacts":{"type":"array","items":{"type":"string"}},
        "references":{"type":"array","items":{"type":"string"}},
        "duration_s":{"type":"number"}},"required":["task_gid","summary"]}},
    {"name":"status_report",
     "description":"Plain-language session status for non-technical operators (vi/en). "
                   "No git/test jargon: what is done, what is missing, what to do next.",
     "inputSchema":{"type":"object","properties":{
        "lang":{"type":"string","enum":["vi","en"],
                "description":"report language (default: policy report_language, else vi)"}}}},
    {"name":"op_log",
     "description":"Plain-language operations ledger digest (host-side ~/.aof): sessions, "
                   "done-with-proof, blocked, lock collisions, failed verifications.",
     "inputSchema":{"type":"object","properties":{
        "since_hours":{"type":"number","minimum":0.1,"maximum":720},
        "task":{"type":"string"},
        "lang":{"type":"string","enum":["vi","en"]}}}},
    {"name":"session_recap",
     "description":"Write a self-contained HTML session recap into <workspace>/docs/sessions/ "
                   "and return its path. Per-session docs that update themselves.",
     "inputSchema":{"type":"object","properties":{
        "since_hours":{"type":"number","minimum":0.1,"maximum":720},
        "lang":{"type":"string","enum":["vi","en"]}}}},
    {"name":"session_handoff",
     "description":"Write a markdown session handoff (Done/Blocked/Open + next-session "
                   "checklist) into <workspace>/docs/sessions/ and return its path.",
     "inputSchema":{"type":"object","properties":{
        "since_hours":{"type":"number","minimum":0.1,"maximum":720},
        "lang":{"type":"string","enum":["vi","en"]}}}},
    {"name":"worker_watch",
     "description":"Judge a worker by its OUTPUT file mtime/size, never by 'session alive'. "
                   "fresh | stale | missing.",
     "inputSchema":{"type":"object","properties":{
        "path":{"type":"string"},
        "stale_after_s":{"type":"integer","minimum":10,"maximum":86400},
        "lang":{"type":"string","enum":["vi","en"]}},"required":["path"]}},
    {"name":"aof_resume",
     "description":"Load the newest matching handoff from the host index "
                   "(~/.aof/handoffs/index.jsonl or $AOF_AUDIT_DIR) and return a "
                   "RESUME BRIEF (content + required rules + next commands). "
                   "Filter by task and/or repo path; default = newest overall.",
     "inputSchema":{"type":"object","properties":{
        "task":{"type":"string"},
        "repo":{"type":"string","description":"working-tree path or repo_key"},
        "lang":{"type":"string","enum":["vi","en"]}}}},
]

# Explicit gate allowlist — unknown gates never execute as commands
ALLOWED_GATES = frozenset({"ruff", "pytest", "quality", "dod"})

# (message, fix) pairs for the two preconditions every gated tool shares.
_FIX_PREFLIGHT = ("Preflight not passed",
                  "Call the 'preflight' tool first (arguments: cwd, and task if your "
                  "policy requires one). It must return status 'clear'; clear any "
                  "blockers it lists, then retry this tool.")
_FIX_CONTRACT = ("Contract not checked",
                 "Call 'check_contract' with the full brief (line-start fields "
                 "Task/Owner/Scope/DoD/Do not/Stop if/Return) and get ok=true, then retry.")

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
SESSION_ID = str(uuid.uuid4())
_state = {
    "session_id": SESSION_ID,
    "preflight_ok": False,
    "contract_ok": False,
    "last_verify_status": None,
    "last_preflight": None,
    "bound_workspace": None,
    "bound_cwd": None,
    "bound_task": None,
    "contract_scope_parsed": None,
    "scope_audit_ok": False,
    "scope_audit_task": None,
    "scope_audit_cwd": None,
    "scope_audit_sig": None,
    "contract_dod_cmd": None,
    "lease_task": None,
    "lease_cwd": None,
    "lease_info": None,
    "bound_lane": "risk",
    "approval_pending": False,
}

# Lite lane may NEVER touch these paths without the full chain. Escalate-only:
# the server upgrades lite -> risk on evidence, it never downgrades.
DEFAULT_RISK_GLOBS = [".github/**", "**/Dockerfile", "deploy/**", "**/deploy/**", "**/*.pem", "**/*.key"]
DEFAULT_LITE_MAX_FILES = 3
def _ensure_audit():
    ensure_audit_dir()

def _audit(entry):
    _ensure_audit()
    entry["_session"] = SESSION_ID
    entry["_ts"] = time.time()
    try:
        with open(audit_file(), "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError:
        pass

def _ssl_context():
    """Certifi-based SSL context with lazy fallback."""
    try:
        import ssl as _s

        import certifi
        return _s.create_default_context(cafile=certifi.where())
    except Exception:
        import ssl as _s
        return _s.create_default_context()

def _rfile(p):
    try:
        with open(p, encoding="utf-8") as f:
            return f.read()
    except OSError:
        return None

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
def _run_preflight(cwd,task,bootstrap):
    # ABSOLUTE file path, never `-m core.preflight`: with -m, sys.path[0] is the
    # server's cwd, so a stale `core/` copy in the host workspace root silently
    # shadows this package — observed live 2026-07-21 as a fail-open preflight
    # (legacy hard-mode policy ignored, status "clear" with no task). The gate
    # must run the preflight that shipped WITH this server, unconditionally.
    _preflight_file = str(Path(__file__).resolve().parent / "preflight.py")
    cmd=[sys.executable,_preflight_file,"--json"]
    if task:
        cmd+=["--task",task]
    if bootstrap:
        cmd.append("--bootstrap")
    try:
        r=subprocess.run(cmd,cwd=cwd or os.getcwd(),capture_output=True,text=True,timeout=30)
        p=json.loads(r.stdout)
        p["exit_code"]=r.returncode
        return p
    except Exception as e:
        return {"error":str(e),"exit_code":2}

def _workspace_policy():
    """Policy for the bound workspace (preflight) or the server's own cwd.

    ponytail: one resolution path, no caching. load_policy already honours
    AOF_POLICY_FILE, and a policy file is a few hundred bytes read once per
    check_contract call.
    """
    return load_policy(_state.get("bound_workspace") or workspace_root(os.getcwd()))


def _check_contract(brief):
    return validate_contract(brief, require_karpathy=bool(_workspace_policy().get("require_karpathy")))

def _git_run(args, cwd, timeout=15):
    """Fixed-argv git helper. Returns (ok, stdout_str, returncode). Never shell."""
    try:
        r = subprocess.run(
            ["git", *args], cwd=cwd, capture_output=True, text=True,
            timeout=timeout, shell=False,
        )
        return r.returncode == 0, (r.stdout or ""), r.returncode
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False, "", -1

def _normalize_path(p: str) -> str:
    s = (p or "").strip().replace("\\", "/")
    while s.startswith("./"):
        s = s[2:]
    return s

def _git_inventory(cwd: str) -> list:
    """Changed-file inventory from trusted git state (staged/unstaged/untracked + base diff)."""
    if not cwd or not os.path.isdir(cwd):
        raise RuntimeError("bound_cwd missing or not a directory")
    ok, out, _ = _git_run(["rev-parse", "--is-inside-work-tree"], cwd)
    if not ok or out.strip() != "true":
        raise RuntimeError("not a git repository")

    files = set()

    # Resolve a committed diff base. Only a REMOTE ref is a trustworthy divergence
    # point; a local main/master on a solo repo is often == HEAD (empty diff), so
    # committed out-of-scope work would vanish. When no remote base resolves (or its
    # merge-base fails), fall back to the repo root commit(s) and diff root..HEAD so
    # EVERY committed change on the branch stays in the inventory (fail-closed superset).
    base_ref = None
    for ref in ("origin/HEAD", "origin/main", "origin/master"):
        ok_r, _, _ = _git_run(["rev-parse", "--verify", ref], cwd)
        if ok_r:
            base_ref = ref
            break

    committed_base = None
    if base_ref:
        ok_mb, mb_out, _ = _git_run(["merge-base", "HEAD", base_ref], cwd)
        mb = mb_out.strip() if ok_mb else ""
        if mb:
            committed_base = mb

    def _add_committed_diff(base):
        ok_d, diff_out, _ = _git_run(["diff", "--name-only", f"{base}...HEAD"], cwd)
        if not ok_d:
            ok_d, diff_out, _ = _git_run(["diff", "--name-only", base, "HEAD"], cwd)
        if not ok_d:
            raise RuntimeError("git committed diff failed")
        for line in diff_out.splitlines():
            n = _normalize_path(line)
            if n:
                files.add(n)

    if committed_base is not None:
        _add_committed_diff(committed_base)
    else:
        # No remote base_ref (or merge-base failed). Diff from root commit(s).
        # A merged history can have >1 root — union each root..HEAD to stay a superset.
        ok_root, root_out, _ = _git_run(["rev-list", "--max-parents=0", "HEAD"], cwd)
        roots = [r.strip() for r in root_out.splitlines() if r.strip()] if ok_root else []
        for root in roots:
            _add_committed_diff(root)
        # If no root resolves (repo has no commits / unborn HEAD), fall through to
        # the working-tree union below — never crash.

    ok_s, staged, _ = _git_run(["diff", "--name-only", "--cached"], cwd)
    if not ok_s:
        raise RuntimeError("git staged diff failed")
    for line in staged.splitlines():
        n = _normalize_path(line)
        if n:
            files.add(n)

    ok_u, unstaged, _ = _git_run(["diff", "--name-only"], cwd)
    if not ok_u:
        raise RuntimeError("git unstaged diff failed")
    for line in unstaged.splitlines():
        n = _normalize_path(line)
        if n:
            files.add(n)

    ok_t, untracked, _ = _git_run(["ls-files", "--others", "--exclude-standard"], cwd)
    if not ok_t:
        raise RuntimeError("git untracked listing failed")
    for line in untracked.splitlines():
        n = _normalize_path(line)
        if n:
            files.add(n)

    return sorted(files)

def _inventory_sig(files) -> str:
    """Stable signature of a trusted inventory. Input is already sorted+normalized
    by _git_inventory, so ordering cannot cause a false mismatch."""
    joined = "\n".join(files)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()

def _gate_python(cwd):
    """Python of the PROJECT under test, not aof's own interpreter.

    Gate runs the project's tests/lint, so it must use an interpreter that sees
    that project's dependencies. sys.executable is aof's python — in a project
    with its own venv it lacks those deps and makes the gate always red for
    environment reasons rather than code defects.
    """
    for rel in (".venv/bin/python", ".venv/Scripts/python.exe"):
        candidate = Path(cwd) / rel
        if candidate.is_file():
            return str(candidate)
    return sys.executable

def _gate_commands(gate_type, cwd, extra):
    """Resolve allowlisted gate to fixed argv list(s). Never shell; never use gate_type as cmd."""
    extra = list(extra or [])
    py = _gate_python(cwd)
    if gate_type == "ruff":
        return [[py, "-m", "ruff", "check", "."] + extra]
    if gate_type == "pytest":
        return [[py, "-m", "pytest", "-x"] + extra]
    if gate_type == "quality":
        # Meaningful portable proof: project lint + tests when present.
        # Never treat byte-compilation alone as quality evidence.
        cmds = [[py, "-m", "ruff", "check", "."] + extra]
        # Avoid re-entrant full suite when already under pytest.
        if (Path(cwd) / "tests").is_dir() and not os.environ.get("PYTEST_CURRENT_TEST"):
            cmds.append([py, "-m", "pytest", "-x", "tests"] + extra)
        return cmds
    return None

def _resolve_timeout(timeout_s):
    """Clamp a caller timeout into [1, MAX_GATE_TIMEOUT_S]; non-numeric falls back to default."""
    try:
        t = int(timeout_s)
    except (TypeError, ValueError):
        return DEFAULT_GATE_TIMEOUT_S
    return max(1, min(t, MAX_GATE_TIMEOUT_S))

def _verify_gate(gate_type,cwd,extra_args,trials,timeout_s=None):
    # P0: restrict gate names, cwd, and trials — unknown never executes
    if gate_type not in ALLOWED_GATES:
        return {"gate_type":gate_type,"error":f"Gate '{gate_type}' not allowed. Use one of: {', '.join(sorted(ALLOWED_GATES))}",
                "passed":False,"results":[]}
    cwd=os.path.realpath(cwd or os.getcwd()); extra=extra_args or []; trials=min(trials or 1, 10)
    timeout=_resolve_timeout(timeout_s)
    # cwd must be under the preflight workspace
    ws = _state.get("bound_workspace")
    if ws and os.path.commonpath([os.path.realpath(ws)]) != os.path.commonpath([os.path.realpath(ws), cwd]):
        return {"gate_type":gate_type,"error":"cwd must be under the preflight workspace","passed":False,"results":[]}
    bound_cwd = _state.get("bound_cwd")
    if bound_cwd and cwd != os.path.realpath(bound_cwd):
        return {"gate_type":gate_type,"error":"cwd must match the preflight cwd","passed":False,"results":[]}
    if gate_type == "dod":
        # P2: run ONLY the DoD-cmd bound from the checked contract. Never a
        # caller-supplied command; never fall back to quality. Fail closed.
        dod = _state.get("contract_dod_cmd")
        if not dod:
            return {"gate_type":gate_type,"error":"No DoD-cmd bound from contract; cannot run 'dod' gate",
                    "passed":False,"results":[]}
        # Reject shell control metacharacters — argv is executed shell=False, this is
        # defense-in-depth so a DoD-cmd can never be crafted to inject via a shell.
        if any(ch in dod for ch in ";|&$`<>()\n\r\\"):
            return {"gate_type":gate_type,"error":"DoD-cmd contains shell metacharacters; refused",
                    "passed":False,"results":[]}
        try:
            argv = shlex.split(dod)
        except ValueError as e:
            return {"gate_type":gate_type,"error":f"DoD-cmd could not be parsed: {e}",
                    "passed":False,"results":[]}
        if not argv:
            return {"gate_type":gate_type,"error":"DoD-cmd is empty after parsing",
                    "passed":False,"results":[]}
        cmds = [argv]
    else:
        cmds = _gate_commands(gate_type, cwd, extra)
    if not cmds:
        return {"gate_type":gate_type,"error":f"Gate '{gate_type}' has no resolvable command",
                "passed":False,"results":[]}
    results,passes=[],0
    for i in range(trials):
        trial_ok = True
        trial_detail = []
        for cmd in cmds:
            try:
                r=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=timeout,shell=False)
                step_ok=r.returncode==0
                trial_detail.append({"cmd":cmd,"exit_code":r.returncode,"ok":step_ok})
                if not step_ok:
                    trial_ok = False
            except subprocess.TimeoutExpired:
                trial_detail.append({"cmd":cmd,"exit_code":-1,"ok":False,"error":"timeout"})
                trial_ok = False
            except Exception as e:
                trial_detail.append({"cmd":cmd,"exit_code":-1,"ok":False,"error":str(e)})
                trial_ok = False
        results.append({"trial":i+1,"ok":trial_ok,"steps":trial_detail,
                        "exit_code":0 if trial_ok else 1})
        if trial_ok: passes+=1
    pr=passes/max(trials,1)*100
    return {"gate_type":gate_type,"trials":trials,"passes":passes,"timeout_s":timeout,
            "pass_rate":round(pr,1),"passed":pr>=80.0 if trials>=3 else passes==trials,
            "results":results}

# ---------------------------------------------------------------------------
# Plain-language status report (no-code operators)
# ---------------------------------------------------------------------------
_REPORT = {
    "vi": {
        "steps": [
            ("preflight", "Kiểm tra môi trường làm việc"),
            ("contract", "Hợp đồng công việc (mục tiêu, phạm vi, tiêu chí xong)"),
            ("verify", "Kiểm chứng chất lượng"),
            ("scope", "Soát phạm vi thay đổi"),
        ],
        "blocked": "⛔ BỊ CHẶN — chưa được phép làm việc",
        "planning": "🟡 ĐANG LÀM — theo kế hoạch",
        "needs_approval": "🖐 CHỜ DUYỆT — cần anh gật đầu trước bước rủi ro",
        "done": "✅ XONG — CÓ BẰNG CHỨNG",
        "task": "Nhiệm vụ",
        "lane": "Làn",
        "lane_lite": "nhẹ (preflight + bằng chứng)",
        "lane_risk": "rủi ro (đủ chuỗi kiểm)",
        "approval_hint": "Duyệt xong thì ghi 'approved' vào session_log để mở khoá.",
        "place": "Nơi làm việc",
        "lease": "Quyền làm việc: phiên này đang giữ nhiệm vụ — không phiên nào khác chen vào được.",
        "why": "Lý do",
        "next": "Bước tiếp theo",
        "next_map": {
            "preflight": "Chạy 'preflight' để kiểm tra môi trường trước khi làm bất cứ việc gì.",
            "contract": "Khai hợp đồng công việc bằng 'check_contract' (nói rõ làm gì, ở đâu, khi nào là xong).",
            "verify": "Chạy 'verify_gate' để máy tự kiểm chứng chất lượng — không tự tin lời khai.",
            "scope": "Chạy 'audit_scope' để chắc chắn không sửa lan ra ngoài phạm vi.",
            "done": "Chạy 'post_evidence' để chốt việc kèm bằng chứng.",
        },
    },
    "en": {
        "steps": [
            ("preflight", "Workspace safety check"),
            ("contract", "Work contract (goal, scope, definition of done)"),
            ("verify", "Quality verification"),
            ("scope", "Change-scope audit"),
        ],
        "blocked": "⛔ BLOCKED — not cleared to work",
        "planning": "🟡 PLANNING — work in progress",
        "needs_approval": "🖐 NEEDS APPROVAL — waiting for a human before a risky step",
        "done": "✅ DONE — WITH PROOF",
        "task": "Task",
        "lane": "Lane",
        "lane_lite": "lite (preflight + evidence)",
        "lane_risk": "risk (full chain)",
        "approval_hint": "After approving, log 'approved' via session_log to unblock.",
        "place": "Working in",
        "lease": "Work lock: this session holds the task — no other session can cut in.",
        "why": "Why",
        "next": "Next step",
        "next_map": {
            "preflight": "Run 'preflight' to check the environment before doing anything.",
            "contract": "Declare the work contract with 'check_contract' (what, where, when it counts as done).",
            "verify": "Run 'verify_gate' so the machine verifies quality — never trust a claim.",
            "scope": "Run 'audit_scope' to prove no changes leaked outside the scope.",
            "done": "Run 'post_evidence' to close the work with proof.",
        },
    },
}


def _status_report(lang=None):
    """Render session state as plain language a non-technical operator can act on."""
    policy = _workspace_policy()
    if lang not in ("vi", "en"):
        lang = policy.get("report_language") if policy.get("report_language") in ("vi", "en") else "vi"
    t = _REPORT[lang]
    flags = {
        "preflight": bool(_state["preflight_ok"]),
        "contract": bool(_state["contract_ok"]),
        "verify": _state["last_verify_status"] == "passed",
        "scope": bool(_state["scope_audit_ok"]),
    }
    pf = _state.get("last_preflight") or {}
    lines = []
    # Wave2 canonical states (2026-07-14): Planning / Needs approval / Blocked / Done.
    if not flags["preflight"]:
        header = t["blocked"] if pf else t["planning"]
    elif _state.get("approval_pending"):
        header = t["needs_approval"]
    elif all(flags.values()):
        header = t["done"]
    else:
        header = t["planning"]
    lines.append(header)
    lines.append("")
    if _state.get("bound_task"):
        lines.append(f"{t['task']}: {_state['bound_task']}")
    if pf.get("repo") and pf.get("branch"):
        lines.append(f"{t['place']}: {pf.get('repo')} @ {pf.get('branch')}")
    if flags["preflight"]:
        lane_key = "lane_lite" if _state.get("bound_lane") == "lite" else "lane_risk"
        lines.append(f"{t['lane']}: {t[lane_key]}")
    if _state.get("lease_task"):
        lines.append(t["lease"])
    if _state.get("approval_pending"):
        lines.append(t["approval_hint"])
    lines.append("")
    for key, label in t["steps"]:
        mark = "✔" if flags[key] else "✘"
        lines.append(f"  {mark} {label}")
    blockers = pf.get("blockers") or []
    if blockers and not flags["preflight"]:
        lines.append("")
        lines.append(f"{t['why']}:")
        for b in blockers[:5]:
            lines.append(f"  - {b}")
    nxt = next((k for k, _label in t["steps"] if not flags[k]), "done")
    lines.append("")
    lines.append(f"{t['next']}: {t['next_map'][nxt]}")
    return "\n".join(lines)


def _coerce_scope(scope):
    """Accept a glob list, or a comma/newline separated string, and return a list.

    The declared schema is an array: a glob may legitimately contain a comma, which
    a delimited string cannot represent. The string form is accepted only for
    backward compatibility with older clients.
    """
    if isinstance(scope, str):
        return [s.strip() for s in scope.replace("\n", ",").split(",") if s.strip()]
    if isinstance(scope, list):
        return [str(s).strip() for s in scope if str(s).strip()]
    return []

def _audit_scope(scope,files):
    ok=[f for f in files if any(fnmatch.fnmatch(f,g) for g in scope)]
    violations=[f for f in files if f not in ok]
    return {"scope":scope,"total_files":len(files),"in_scope":ok,
            "out_of_scope":violations,"ok":len(violations)==0}

# ---------------------------------------------------------------------------
# Tracker adapter integration (additive — local audit is the source of truth)
# ---------------------------------------------------------------------------
def _load_asana_adapter():
    """Import the generic Asana adapter, whether run as a package or a bare script."""
    try:
        from adapters import asana_adapter
        return asana_adapter
    except Exception:
        import importlib.util
        p=Path(__file__).resolve().parent.parent/"adapters"/"asana_adapter.py"
        spec=importlib.util.spec_from_file_location("asana_adapter",p)
        mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
        return mod

def _post_tracker(task_gid,summary,resolution,exit_code,artifacts,references,duration_s):
    """Post evidence to a real tracker when configured. Returns None if not configured,
    else a result dict. Never raises — network failures are returned, not crashed on."""
    if os.environ.get("TRACKER_TYPE","").lower()!="asana": return None
    token=os.environ.get("TRACKER_TOKEN")
    if not token: return None
    try:
        adapter=_load_asana_adapter()
    except Exception as e:
        return {"posted":False,"error":f"adapter import failed: {e}"}
    lines=[f"AOF Evidence [session={SESSION_ID}]",
           f"Resolution: {resolution}",
           f"Summary: {summary}",
           f"Exit code: {exit_code} | Duration: {(duration_s or 0):.1f}s"]
    if artifacts:
        lines.append("Artifacts:"); lines+=[f"- {x}" for x in artifacts[:10]]
    if references:
        lines.append("References:"); lines+=[f"- {x}" for x in references[:10]]
    try:
        out=adapter.post_comment(task_gid,"\n".join(lines),token)
    except Exception as e:
        return {"posted":False,"error":f"post_comment raised: {e}"}
    result={"posted":bool(out.get("ok")),"comment":out}
    if out.get("ok") and exit_code==0:
        try:
            result["complete"]=adapter.complete_task(task_gid,token)
        except Exception as e:
            result["complete"]={"ok":False,"error":f"complete_task raised: {e}"}
    return result

# ---------------------------------------------------------------------------
# JSON-RPC handlers
# ---------------------------------------------------------------------------
def _handle(req):
    rid,method,params=req.get("id"),req.get("method",""),(req.get("params") or {}) or {}
    if method=="initialize": return _rsp(rid,{"protocolVersion":"2025-03-26",
        "capabilities":{"tools":{}},"serverInfo":{"name":"aof-mcp-server","version":"1.0.0"}})
    if method in ("notifications/initialized","ping"): return _rsp(rid,{})
    if method=="tools/list": return _rsp(rid,{"tools":TOOLS})
    if method=="tools/call": return _call(rid,params)
    return _err(rid,-32601,f"Method not found: {method}")

def _call(rid,p):
    n=p.get("name",""); a=p.get("arguments",{}) or {}
    try:
        if n=="preflight":
            _state.update({"contract_ok": False, "last_verify_status": None,
                           "contract_scope_parsed": None, "scope_audit_ok": False,
                           "scope_audit_task": None, "scope_audit_cwd": None,
                           "scope_audit_sig": None, "contract_dod_cmd": None,
                           "approval_pending": False})
            r=_run_preflight(a.get("cwd"),a.get("task"),a.get("bootstrap"))
            _state["preflight_ok"]=r.get("status")=="clear" and r.get("exit_code")==0
            _state["last_preflight"]=r
            if _state["preflight_ok"]:
                _state["bound_workspace"] = r.get("workspace")
                _state["bound_cwd"] = os.path.realpath(a.get("cwd") or os.getcwd())
                _state["bound_task"] = r.get("task")
                # GO-RISK-LANE (CAUSAL-VERDICT 2026-07-16, preregistered rule):
                # full chain is mandatory only for the risk lane; the lite lane
                # (preflight + evidence) exists because the +35% gate tax on
                # routine work is exactly why gates get bypassed. Lite is
                # OPT-IN via policy AND caller, and only ever escalates.
                lane = "risk"
                if a.get("lane") == "lite" and _workspace_policy().get("lanes_enabled"):
                    lane = "lite"
                _state["bound_lane"] = lane
                r["lane"] = lane
            else:
                _state["bound_workspace"] = None
                _state["bound_cwd"] = None
                _state["bound_task"] = None
                _state["bound_lane"] = "risk"
            # C2: exclusive task lease — a second live session on the same
            # (repo, task) is refused BEFORE any gate opens. Fail closed.
            if _state["preflight_ok"]:
                task = _state["bound_task"]
                prev = _state.get("lease_task")
                if prev and prev != task:
                    lease_mod.release(prev, _state.get("lease_cwd") or os.getcwd(), SESSION_ID)
                    _state.update({"lease_task": None, "lease_cwd": None, "lease_info": None})
                if task:
                    lr = lease_mod.acquire(task, _state["bound_cwd"], SESSION_ID)
                    if not lr.get("ok"):
                        _state.update({"preflight_ok": False, "bound_workspace": None,
                                       "bound_cwd": None, "bound_task": None})
                        _audit({"event": "lease_conflict", "task": task,
                                "holder": lr.get("holder"), "status": lr.get("status")})
                        return _tool_err(rid, -32011,
                                         lr.get("detail") or lr.get("error") or "task lease unavailable",
                                         "Another LIVE session holds this task. Wait for it, stop it, "
                                         "or preflight a different task. Never work the same task from "
                                         "two sessions at once.")
                    _state.update({"lease_task": task, "lease_cwd": _state["bound_cwd"],
                                   "lease_info": lr})
                    r["lease"] = {"status": lr.get("status")}
                    _audit({"event": "lease", "task": task, "status": lr.get("status")})
            # Estate telemetry: always record preflight outcome + bound identity.
            _audit({
                "event": "preflight",
                "status": r.get("status"),
                "workspace": r.get("workspace"),
                "repo": r.get("repo"),
                "branch": r.get("branch"),
                "task": r.get("task") or a.get("task"),
                "cwd": _state.get("bound_cwd") or a.get("cwd"),
                "lane": r.get("lane") or _state.get("bound_lane"),
                "exit_code": r.get("exit_code"),
            })
            return _tool_ok(rid,r)
        if n=="check_contract":
            _state["last_verify_status"] = None
            _state["contract_scope_parsed"] = None
            _state["scope_audit_ok"] = False
            _state["scope_audit_task"] = None
            _state["scope_audit_cwd"] = None
            _state["scope_audit_sig"] = None
            _state["contract_dod_cmd"] = None
            r=_check_contract(a.get("brief",""))
            _state["contract_ok"]=r["ok"]
            # P2: bind optional DoD-cmd to session (opt-in verify target)
            _state["contract_dod_cmd"] = r.get("dod_cmd") if r["ok"] else None
            # Parse scope from contract when it passes
            if r["ok"]:
                for line in (a.get("brief","") or "").split("\n"):
                    if line.startswith("Scope:") or line.startswith("Scope :"):
                        scope_val = line.split(":", 1)[1].strip()
                        if scope_val:
                            _state["contract_scope_parsed"] = [s.strip() for s in scope_val.split(",")]
                        break
            _audit({"event":"check_contract","ok":r["ok"],
                    "karpathy_required":r.get("karpathy_required"),
                    "karpathy_ok":r.get("karpathy_ok")})
            write_decision({
                "session": SESSION_ID, "decision": "check_contract",
                "ok": bool(r["ok"]),
                "missing_required": r.get("missing_required"),
                "task": _state.get("bound_task"),
                "karpathy_required": r.get("karpathy_required"),
                "karpathy_ok": r.get("karpathy_ok"),
                "hint": r.get("hint"),
            })
            return _tool_ok(rid,with_stall_warning(r,SESSION_ID,"check_contract"))
        if n=="operating_protocol":
            ws=a.get("workspace") or os.environ.get("AOF_WORKSPACE") or os.getcwd()
            c=_rfile(os.path.join(ws,"OPERATING_PROTOCOL.md"))
            if not c: c=_rfile(os.path.join(ws,"core","operating_protocol.md"))
            if not c:
                return _tool_err(rid,-32010,f"No OPERATING_PROTOCOL.md under workspace '{ws}'",
                                 "Pass the workspace containing OPERATING_PROTOCOL.md, or set AOF_WORKSPACE.")
            # Document tool: return the markdown verbatim. JSON-escaping a protocol
            # doc into one \n-laden line costs tokens and readability for no gain.
            return _tool_ok(rid,None,text=c)
        if n=="verify_gate":
            if not _state["preflight_ok"]: return _tool_err(rid,-32000,*_FIX_PREFLIGHT)
            if not _state["contract_ok"]: return _tool_err(rid,-32001,*_FIX_CONTRACT)
            r=_verify_gate(a["gate_type"],a.get("cwd"),a.get("extra_args"),a.get("trials"),a.get("timeout_s"))
            _state["last_verify_status"]="passed" if r.get("passed") else "failed"
            _audit({"event":"verify_gate","gate_type":a["gate_type"],"passed":r.get("passed")})
            write_decision({"session":SESSION_ID,"decision":"verify_gate","gate_type":a["gate_type"],
                            "passed":bool(r.get("passed")),"task":_state.get("bound_task")})
            return _tool_ok(rid,with_stall_warning(r,SESSION_ID,"verify_gate"))
        if n=="audit_scope":
            if not _state["preflight_ok"]: return _tool_err(rid,-32000,*_FIX_PREFLIGHT)
            if not _state["contract_ok"]: return _tool_err(rid,-32001,*_FIX_CONTRACT)
            scope = _state.get("contract_scope_parsed")
            if not scope:
                _state["scope_audit_ok"] = False
                _state["scope_audit_task"] = None
                _state["scope_audit_cwd"] = None
                return _tool_err(rid,-32005,"Contract scope is not available",
                                 "Add a line-start 'Scope: <comma-separated globs>' to the brief "
                                 "and re-run check_contract before audit_scope.")
            if a.get("scope") is not None and _coerce_scope(a["scope"]) != scope:
                _state["scope_audit_ok"] = False
                _state["scope_audit_task"] = None
                _state["scope_audit_cwd"] = None
                return _tool_err(rid,-32006,"scope must match the checked contract",
                                 f"Omit the 'scope' argument (the server uses the contract scope) "
                                 f"or pass exactly: {scope}")
            # Trusted inventory only — never use caller changed_files as evidence
            cwd = _state.get("bound_cwd") or os.getcwd()
            try:
                git_files = _git_inventory(cwd)
            except Exception as e:
                _state["scope_audit_ok"] = False
                _state["scope_audit_task"] = None
                _state["scope_audit_cwd"] = None
                _audit({"event":"audit_scope","ok":False,"error":str(e)})
                return _tool_err(rid,-32007,f"git inventory failed (fail closed): {e}",
                                 "audit_scope derives changed files from git only. Run the tools "
                                 "from inside the git repository you preflighted.")
            r=_audit_scope(scope, git_files)
            r["git_files"] = list(git_files)
            r["scope_source"] = "git+contract"
            r["caller_changed_files_ignored"] = True
            _state["scope_audit_ok"] = r["ok"]
            if r["ok"]:
                _state["scope_audit_task"] = _state.get("bound_task")
                _state["scope_audit_cwd"] = os.path.realpath(cwd)
                # P1: snapshot the audited git state for TOCTOU re-check at closeout
                _state["scope_audit_sig"] = _inventory_sig(git_files)
            else:
                _state["scope_audit_task"] = None
                _state["scope_audit_cwd"] = None
                _state["scope_audit_sig"] = None
            _audit({"event":"audit_scope","ok":r["ok"],"git_files":git_files})
            return _tool_ok(rid,r)
        if n=="session_log":
            ev = a.get("event")
            # Human-in-the-loop marker (wave2 state "Needs approval"): the agent
            # logs needs_approval before a risky step; an explicit approval or a
            # closed evidence clears it. status_report surfaces it first.
            if ev == "needs_approval":
                _state["approval_pending"] = True
            elif ev in ("approved", "approval_granted"):
                _state["approval_pending"] = False
            data = a.get("data") or {}
            # F3-1/F3-3: error ledger via session_log event=error (no new tool).
            if ev == "error":
                from core.errors_ledger import record_error
                er = record_error(data if isinstance(data, dict) else {},
                                  session=_state.get("session_id") or SESSION_ID)
                _audit({"event": ev, "data": data, "error_ledger": er})
                if er.get("refused"):
                    return _tool_ok(rid, er, text=er.get("reason"))
                return _tool_ok(rid, er)
            _audit({"event":ev,"data":data}); return _tool_ok(rid,{"ok":True})
        if n=="status_report":
            # Deliberately NOT gated: a blocked operator most needs to see why.
            return _tool_ok(rid,None,text=_status_report(a.get("lang")))
        if n in ("op_log","session_recap","session_handoff"):
            # Report tools, host-side: this is what makes Cowork/Claude Code
            # equals — one server, one ledger, every environment. Never gated.
            sh=a.get("since_hours")
            since=(time.time()-float(sh)*3600) if sh else None
            report=oplog_mod.build_digest(since_ts=since,
                                          task=a.get("task") if n=="op_log" else None)
            lang=a.get("lang")
            if n=="op_log":
                return _tool_ok(rid,None,text=oplog_mod.format_digest(report,lang))
            # F1 (v0.4): recap/handoff must land next to the repo being worked
            # on, not the parent AOF_WORKSPACE — a session in a sub-repo/worktree
            # used to write into the wrong place. nearest_repo() resolves the
            # working-tree root for bound_cwd (the checkout you can actually see
            # docs/sessions/ in) — NOT lease_mod.repo_identity(), which resolves
            # to the .git directory itself (right for lease hashing, wrong as a
            # file-write base: it would put docs/sessions/ inside .git/).
            bound_cwd=_state.get("bound_cwd") or os.getcwd()
            ws=nearest_repo(bound_cwd) or bound_cwd
            outdir=oplog_mod.default_session_dir(ws)
            summary={"sessions":report["sessions"],"done":report["done"],
                     "blocked":report["blocked"],"collisions":report["collisions"]}
            if n=="session_recap":
                stamp=time.strftime("%Y%m%d_%H%M%S")
                os.makedirs(outdir,exist_ok=True)
                fpath=os.path.join(outdir,f"RECAP_{stamp}.html")
                with open(fpath,"w",encoding="utf-8") as fh:
                    fh.write(oplog_mod.render_html(report,lang))
                _audit({"event":n,"path":fpath})
                return _tool_ok(rid,{"ok":True,"path":fpath,"summary":summary})
            # session_handoff (F2): one call writes handoff + recap, cross-linked,
            # sharing one stamp -- never a lone .md with no recap to point to.
            bundle=oplog_mod.write_session_bundle(outdir,report,lang)
            # F1-2: central index pointer (identity for keys; nearest_repo for files).
            try:
                ident_path, ident_key = lease_mod.repo_identity(bound_cwd)
            except Exception:
                ident_path, ident_key = bound_cwd, ""
            try:
                br = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=bound_cwd, capture_output=True, text=True, timeout=10,
                )
                branch = br.stdout.strip() if br.returncode == 0 else ""
            except (OSError, subprocess.TimeoutExpired):
                branch = ""
            idx = oplog_mod.append_handoff_index(
                ident_path, ident_key, branch, _state.get("bound_task"), bundle, summary,
            )
            _audit({"event":n,"path":bundle["handoff_path"],"recap_path":bundle["recap_path"],
                    "index":idx})
            return _tool_ok(rid,{"ok":True,"path":bundle["handoff_path"],
                                 "recap_path":bundle["recap_path"],"index":idx,
                                 "summary":summary})
        if n=="aof_resume":
            # Never gated: the next session must load context even when blocked.
            brief=oplog_mod.format_resume_brief(
                task=a.get("task"), repo=a.get("repo"), lang=a.get("lang"),
            )
            _audit({"event":"aof_resume","task":a.get("task"),"repo":a.get("repo")})
            return _tool_ok(rid,{"ok":True,"task":a.get("task"),"repo":a.get("repo")},
                            text=brief)
        if n=="worker_watch":
            pol=_workspace_policy()
            try:
                pol_stale=int(pol.get("worker_stale_after_s") or heartbeat_mod.DEFAULT_STALE_AFTER_S)
            except (TypeError, ValueError):
                pol_stale=heartbeat_mod.DEFAULT_STALE_AFTER_S
            stale=a.get("stale_after_s")
            stale_s=int(stale) if stale is not None else pol_stale
            r=heartbeat_mod.check(a["path"], stale_s)
            r["ok"]=r["status"]=="fresh"
            r["message"]=heartbeat_mod.format_check(r,a.get("lang"))
            return _tool_ok(rid,r)
        if n=="post_evidence":
            if not _state["preflight_ok"]: return _tool_err(rid,-32000,*_FIX_PREFLIGHT)
            if _state.get("bound_lane") == "lite":
                # Lite lane (preregistered GO-RISK-LANE): preflight + evidence.
                # Fail closed: the server re-derives the git inventory and
                # ESCALATES to risk on multi-file or risky paths — a worker
                # cannot talk its way into lite for risky work.
                lite_cwd = _state.get("bound_cwd") or os.getcwd()
                try:
                    lite_files = _git_inventory(lite_cwd)
                except Exception as e:
                    return _tool_err(rid,-32012,f"lite lane requires readable git state ({e})",
                                     "Run from the preflighted git repository, or use the full "
                                     "chain (check_contract -> verify_gate -> audit_scope).")
                policy=_workspace_policy()
                try:
                    max_files=int(policy.get("lite_max_files", DEFAULT_LITE_MAX_FILES))
                except (TypeError, ValueError):
                    max_files=DEFAULT_LITE_MAX_FILES
                globs=policy.get("risk_globs") or DEFAULT_RISK_GLOBS
                hits=[f for f in lite_files if any(fnmatch.fnmatch(f,g) for g in globs)]
                if len(lite_files)>max_files or hits:
                    reason=(f"risk paths touched: {', '.join(hits[:3])}" if hits
                            else f"{len(lite_files)} files changed (lite max {max_files})")
                    return _tool_err(rid,-32012,f"Lane escalated to RISK — {reason}",
                                     "This work is not lite. Run the full chain: check_contract, "
                                     "verify_gate, audit_scope, then post_evidence.")
                if _state["bound_task"] and a.get("task_gid") and a["task_gid"] != _state["bound_task"]:
                    return _tool_err(rid,-32004,
                                     f"task_gid '{a['task_gid']}' does not match preflighted task "
                                     f"'{_state['bound_task']}'",
                                     f"Post evidence for '{_state['bound_task']}', or re-run "
                                     f"preflight with the task you mean to close.")
                resolution="Done" if a.get("exit_code",-1)==0 else "Blocked"
                _state["approval_pending"] = False
                _audit({"event":"post_evidence","task_gid":a["task_gid"],"summary":a.get("summary"),
                        "resolution":resolution,"exit_code":a.get("exit_code"),"lane":"lite",
                        "files":lite_files,"artifacts":a.get("artifacts",[]),
                        "references":a.get("references",[]),"duration_s":a.get("duration_s")})
                write_decision({"session":SESSION_ID,"decision":"post_evidence","task":a["task_gid"],
                                "resolution":resolution,"exit_code":a.get("exit_code"),"lane":"lite"})
                result={"ok":True,"resolution":resolution,"lane":"lite",
                        "message":"Evidence logged (lite lane: preflight + evidence). "
                                  "Risky or multi-file work auto-escalates to the full chain."}
                tracker=_post_tracker(a["task_gid"],a.get("summary"),resolution,a.get("exit_code",-1),
                                      a.get("artifacts",[]),a.get("references",[]),a.get("duration_s"))
                if tracker is not None:
                    result["tracker"]=tracker
                return _tool_ok(rid,result)
            if not _state["contract_ok"]: return _tool_err(rid,-32001,*_FIX_CONTRACT)
            if _state["last_verify_status"] != "passed":
                return _tool_err(rid,-32002,"A passing verify_gate is required before post_evidence",
                                 "Run verify_gate (e.g. gate_type 'pytest') and get passed=true, then retry.")
            if not _state["scope_audit_ok"]:
                return _tool_err(rid,-32003,"A passing audit_scope is required before post_evidence",
                                 "Run audit_scope and get ok=true (no out_of_scope files), then retry.")
            # Trusted scope audit must be for the currently bound task/workspace
            bound_task = _state.get("bound_task")
            bound_cwd = _state.get("bound_cwd")
            if bound_task is not None and _state.get("scope_audit_task") != bound_task:
                return _tool_err(rid,-32003,"scope audit is not bound to the current task",
                                 "Re-run audit_scope for the task you preflighted, then retry.")
            if bound_cwd and _state.get("scope_audit_cwd") != os.path.realpath(bound_cwd):
                return _tool_err(rid,-32003,"scope audit is not bound to the current workspace",
                                 "Re-run audit_scope from the preflighted cwd, then retry.")
            # P0-3: enforce task binding — reject cross-task evidence
            if _state["bound_task"] and a.get("task_gid") and a["task_gid"] != _state["bound_task"]:
                return _tool_err(rid,-32004,
                                 f"task_gid '{a['task_gid']}' does not match preflighted task '{_state['bound_task']}'",
                                 f"Post evidence for '{_state['bound_task']}', or re-run preflight with "
                                 f"task '{a['task_gid']}' if that is the task you mean to close.")
            # P1: TOCTOU — re-derive the trusted inventory for the bound cwd and
            # compare against the snapshot taken at audit_scope. Any drift (new
            # commit / staged / untracked change) invalidates the audit. Fail closed.
            try:
                current_files = _git_inventory(bound_cwd or os.getcwd())
            except Exception as e:
                return _tool_err(rid,-32009,f"git state changed since scope audit; re-run audit_scope ({e})",
                                 "Call audit_scope again to re-snapshot git state, then retry post_evidence.")
            if _inventory_sig(current_files) != _state.get("scope_audit_sig"):
                return _tool_err(rid,-32009,"git state changed since scope audit; re-run audit_scope",
                                 "Files changed after the audit. Call audit_scope again, then retry post_evidence.")
            resolution="Done" if a.get("exit_code",-1)==0 else "Blocked"
            _state["approval_pending"] = False
            # Local audit is UNCONDITIONAL and the source of truth.
            _audit({"event":"post_evidence","task_gid":a["task_gid"],"summary":a.get("summary"),
                    "resolution":resolution,"exit_code":a.get("exit_code"),
                    "artifacts":a.get("artifacts",[]),"references":a.get("references",[]),
                    "duration_s":a.get("duration_s")})
            write_decision({"session":SESSION_ID,"decision":"post_evidence","task":a["task_gid"],
                            "resolution":resolution,"exit_code":a.get("exit_code")})
            result={"ok":True,"resolution":resolution,
                "message":"Evidence logged to audit. Set TRACKER_TYPE=asana + TRACKER_TOKEN to also post to the tracker."}
            # Additive: post to the real tracker if configured (fail-soft on network).
            tracker=_post_tracker(a["task_gid"],a.get("summary"),resolution,a.get("exit_code",-1),
                                  a.get("artifacts",[]),a.get("references",[]),a.get("duration_s"))
            if tracker is not None:
                result["tracker"]=tracker
            return _tool_ok(rid,result)
        return _tool_err(rid,-32602,f"Unknown tool: {n}",
                         f"Use one of: {', '.join(t['name'] for t in TOOLS)}")
    except Exception as e:
        return _tool_err(rid,-32603,f"{type(e).__name__}: {e}",
                         "Unexpected server-side failure. Check the tool arguments against tools/list.")

def _rsp(rid,r): b={"jsonrpc":"2.0","result":r}; return b if rid is None else {**b,"id":rid}
# _err stays for PROTOCOL faults only (unknown method, parse error). Tool-level
# failures go through _tool_err so the model can read and act on them.
def _err(rid,c,m): b={"jsonrpc":"2.0","error":{"code":c,"message":m}}; return b if rid is None else {**b,"id":rid}

def _tool_ok(rid,payload,text=None):
    """MCP tool result. `text` overrides the JSON rendering for document tools."""
    body=text if text is not None else json.dumps(payload,ensure_ascii=False,indent=2)
    return _rsp(rid,{"content":[{"type":"text","text":body}],"isError":False})

def _tool_err(rid,code,message,fix=None):
    """Refusal the model can read AND act on. Stable numeric code kept in-band."""
    payload={"ok":False,"error_code":code,"error":message}
    if fix: payload["fix"]=fix
    return _rsp(rid,{"content":[{"type":"text","text":json.dumps(payload,ensure_ascii=False,indent=2)}],
                     "isError":True})

def _send(m):
    if m is None: return
    sys.stdout.write(json.dumps(m,ensure_ascii=False)+"\n")
    sys.stdout.flush()

def main():
    _ensure_audit(); _audit({"event":"session_start","session_id":SESSION_ID})
    for raw in sys.stdin:
        raw=raw.strip()
        if not raw:
            continue
        try:
            req=json.loads(raw)
        except json.JSONDecodeError as e:
            _send(_err(None,-32700,f"Parse error: {e}"))
            continue
        _send(_handle(req))
    # Session over: give the task back so the next session is never blocked
    # by a lease whose holder simply exited.
    if _state.get("lease_task"):
        lease_mod.release(_state["lease_task"], _state.get("lease_cwd") or os.getcwd(), SESSION_ID)
    _audit({"event":"session_end"})

if __name__=="__main__":
    main()
