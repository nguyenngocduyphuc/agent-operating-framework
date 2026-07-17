#!/usr/bin/env python3
"""AOF MCP Server — stdio JSON-RPC 2.0 server for AOF framework tools.

No private paths, no project IDs, no secrets. Credentials checked for PRESENCE only.
Transport: newline-delimited JSON (one JSON-RPC message per line), matching the
proven-in-production pattern in scripts/npflight_mcp.py. Stdlib only.
"""
import fnmatch
import json
import os
import subprocess
import sys
import time
import uuid
from pathlib import Path

from core.check_contract import validate as validate_contract

# ---------------------------------------------------------------------------
# TOOLS catalog
# ---------------------------------------------------------------------------
TOOLS = [
    {"name":"preflight","description":"Run AOF preflight gate","inputSchema":{"type":"object","properties":{
        "cwd":{"type":"string"},"task":{"type":"string","description":"Task ID to bind"},
        "bootstrap":{"type":"boolean"}}}},
    {"name":"check_contract","description":"Validate 7 contract fields + References","inputSchema":{"type":"object","properties":{
        "brief":{"type":"string"}},"required":["brief"]}},
    {"name":"operating_protocol","description":"Return OPERATING_PROTOCOL.md","inputSchema":{"type":"object","properties":{
        "workspace":{"type":"string"}}}},
    {"name":"verify_gate","description":"Run quality gate (ruff|pytest|quality) with optional multi-trial","inputSchema":{"type":"object","properties":{
        "gate_type":{"type":"string"},"cwd":{"type":"string"},
        "extra_args":{"type":"array","items":{"type":"string"}},
        "trials":{"type":"integer","minimum":1,"maximum":10}}},
     "required":["gate_type"]},
    {"name":"audit_scope","description":"Check git-derived changed paths against contract scope globs","inputSchema":{"type":"object","properties":{
        "scope":{"type":"array","items":{"type":"string"}},
        "changed_files":{"type":"array","items":{"type":"string"}}},"required":["scope"]}},
    {"name":"session_log","description":"Append event to ~/.npflight/audit.jsonl","inputSchema":{"type":"object","properties":{
        "event":{"type":"string","description":"goal|decision|dead-end|file|question"},
        "data":{"type":"object"}},"required":["event","data"]}},
    {"name":"post_evidence","description":"Post closeout evidence (adapter provides tracker token)","inputSchema":{"type":"object","properties":{
        "task_gid":{"type":"string"},"summary":{"type":"string"},
        "exit_code":{"type":"integer"},"artifacts":{"type":"array","items":{"type":"string"}},
        "references":{"type":"array","items":{"type":"string"}},
        "duration_s":{"type":"number"}},"required":["task_gid","summary"]}},
]

# Explicit gate allowlist — unknown gates never execute as commands
ALLOWED_GATES = frozenset({"ruff", "pytest", "quality"})

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
}
AUDIT_LOG = Path.home()/".npflight"/"audit.jsonl"

def _ensure_audit():
    Path.home().joinpath(".npflight").mkdir(parents=True, exist_ok=True)

def _audit(entry):
    _ensure_audit()
    entry["_session"] = SESSION_ID
    entry["_ts"] = time.time()
    try:
        with open(AUDIT_LOG, "a", encoding="utf-8") as f:
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
    cmd=[sys.executable,"-m","core.preflight","--json"]
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

def _check_contract(brief):
    return validate_contract(brief)

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

    base_ref = None
    for ref in ("origin/HEAD", "origin/main", "origin/master", "main", "master"):
        ok_r, _, _ = _git_run(["rev-parse", "--verify", ref], cwd)
        if ok_r:
            base_ref = ref
            break
    if base_ref:
        ok_mb, mb_out, _ = _git_run(["merge-base", "HEAD", base_ref], cwd)
        mb = mb_out.strip() if ok_mb else ""
        if mb:
            ok_d, diff_out, _ = _git_run(["diff", "--name-only", f"{mb}...HEAD"], cwd)
            if not ok_d:
                ok_d, diff_out, _ = _git_run(["diff", "--name-only", mb, "HEAD"], cwd)
            if not ok_d:
                raise RuntimeError("git merge-base committed diff failed")
            for line in diff_out.splitlines():
                n = _normalize_path(line)
                if n:
                    files.add(n)

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

def _gate_commands(gate_type, cwd, extra):
    """Resolve allowlisted gate to fixed argv list(s). Never shell; never use gate_type as cmd."""
    extra = list(extra or [])
    if gate_type == "ruff":
        return [[sys.executable, "-m", "ruff", "check", "."] + extra]
    if gate_type == "pytest":
        return [[sys.executable, "-m", "pytest", "-x"] + extra]
    if gate_type == "quality":
        # Meaningful portable proof: project lint + tests when present.
        # Never treat byte-compilation alone as quality evidence.
        cmds = [[sys.executable, "-m", "ruff", "check", "."] + extra]
        # Avoid re-entrant full suite when already under pytest.
        if (Path(cwd) / "tests").is_dir() and not os.environ.get("PYTEST_CURRENT_TEST"):
            cmds.append([sys.executable, "-m", "pytest", "-x", "tests"] + extra)
        return cmds
    return None

def _verify_gate(gate_type,cwd,extra_args,trials):
    # P0: restrict gate names, cwd, and trials — unknown never executes
    if gate_type not in ALLOWED_GATES:
        return {"gate_type":gate_type,"error":f"Gate '{gate_type}' not allowed. Use one of: {', '.join(sorted(ALLOWED_GATES))}",
                "passed":False,"results":[]}
    cwd=os.path.realpath(cwd or os.getcwd()); extra=extra_args or []; trials=min(trials or 1, 10)
    # cwd must be under the preflight workspace
    ws = _state.get("bound_workspace")
    if ws and os.path.commonpath([os.path.realpath(ws)]) != os.path.commonpath([os.path.realpath(ws), cwd]):
        return {"gate_type":gate_type,"error":"cwd must be under the preflight workspace","passed":False,"results":[]}
    bound_cwd = _state.get("bound_cwd")
    if bound_cwd and cwd != os.path.realpath(bound_cwd):
        return {"gate_type":gate_type,"error":"cwd must match the preflight cwd","passed":False,"results":[]}
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
                r=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=120,shell=False)
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
    return {"gate_type":gate_type,"trials":trials,"passes":passes,
            "pass_rate":round(pr,1),"passed":pr>=80.0 if trials>=3 else passes==trials,
            "results":results}

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
                           "scope_audit_task": None, "scope_audit_cwd": None})
            r=_run_preflight(a.get("cwd"),a.get("task"),a.get("bootstrap"))
            _state["preflight_ok"]=r.get("status")=="clear" and r.get("exit_code")==0
            _state["last_preflight"]=r
            if _state["preflight_ok"]:
                _state["bound_workspace"] = r.get("workspace")
                _state["bound_cwd"] = os.path.realpath(a.get("cwd") or os.getcwd())
                _state["bound_task"] = r.get("task")
            else:
                _state["bound_workspace"] = None
                _state["bound_cwd"] = None
                _state["bound_task"] = None
            return _rsp(rid,r)
        if n=="check_contract":
            _state["last_verify_status"] = None
            _state["contract_scope_parsed"] = None
            _state["scope_audit_ok"] = False
            _state["scope_audit_task"] = None
            _state["scope_audit_cwd"] = None
            r=_check_contract(a.get("brief",""))
            _state["contract_ok"]=r["ok"]
            # Parse scope from contract when it passes
            if r["ok"]:
                for line in (a.get("brief","") or "").split("\n"):
                    if line.startswith("Scope:") or line.startswith("Scope :"):
                        scope_val = line.split(":", 1)[1].strip()
                        if scope_val:
                            _state["contract_scope_parsed"] = [s.strip() for s in scope_val.split(",")]
                        break
            _audit({"event":"check_contract","ok":r["ok"]})
            return _rsp(rid,r)
        if n=="operating_protocol":
            ws=a.get("workspace") or os.environ.get("AOF_WORKSPACE") or os.getcwd()
            c=_rfile(os.path.join(ws,"OPERATING_PROTOCOL.md"))
            if not c: c=_rfile(os.path.join(ws,"core","operating_protocol.md"))
            return _rsp(rid,{"content":c or "OPERATING_PROTOCOL.md not found","workspace":ws})
        if n=="verify_gate":
            if not _state["preflight_ok"]: return _err(rid,-32000,"Preflight not passed")
            if not _state["contract_ok"]: return _err(rid,-32001,"Contract not checked")
            r=_verify_gate(a["gate_type"],a.get("cwd"),a.get("extra_args"),a.get("trials"))
            _state["last_verify_status"]="passed" if r.get("passed") else "failed"
            _audit({"event":"verify_gate","gate_type":a["gate_type"],"passed":r.get("passed")})
            return _rsp(rid,r)
        if n=="audit_scope":
            if not _state["preflight_ok"]: return _err(rid,-32000,"Preflight not passed")
            if not _state["contract_ok"]: return _err(rid,-32001,"Contract not checked")
            scope = _state.get("contract_scope_parsed")
            if not scope:
                _state["scope_audit_ok"] = False
                _state["scope_audit_task"] = None
                _state["scope_audit_cwd"] = None
                return _err(rid,-32005,"Contract scope is not available")
            if a.get("scope") is not None and a["scope"] != scope:
                _state["scope_audit_ok"] = False
                _state["scope_audit_task"] = None
                _state["scope_audit_cwd"] = None
                return _err(rid,-32006,"scope must match the checked contract")
            # Trusted inventory only — never use caller changed_files as evidence
            cwd = _state.get("bound_cwd") or os.getcwd()
            try:
                git_files = _git_inventory(cwd)
            except Exception as e:
                _state["scope_audit_ok"] = False
                _state["scope_audit_task"] = None
                _state["scope_audit_cwd"] = None
                _audit({"event":"audit_scope","ok":False,"error":str(e)})
                return _err(rid,-32007,f"git inventory failed (fail closed): {e}")
            r=_audit_scope(scope, git_files)
            r["git_files"] = list(git_files)
            r["scope_source"] = "git+contract"
            r["caller_changed_files_ignored"] = True
            _state["scope_audit_ok"] = r["ok"]
            if r["ok"]:
                _state["scope_audit_task"] = _state.get("bound_task")
                _state["scope_audit_cwd"] = os.path.realpath(cwd)
            else:
                _state["scope_audit_task"] = None
                _state["scope_audit_cwd"] = None
            _audit({"event":"audit_scope","ok":r["ok"],"git_files":git_files})
            return _rsp(rid,r)
        if n=="session_log":
            _audit({"event":a.get("event"),"data":a.get("data")}); return _rsp(rid,{"ok":True})
        if n=="post_evidence":
            if not _state["preflight_ok"]: return _err(rid,-32000,"Preflight not passed")
            if not _state["contract_ok"]: return _err(rid,-32001,"Contract not checked")
            if _state["last_verify_status"] != "passed":
                return _err(rid,-32002,"A passing verify_gate is required before post_evidence")
            if not _state["scope_audit_ok"]:
                return _err(rid,-32003,"A passing audit_scope is required before post_evidence")
            # Trusted scope audit must be for the currently bound task/workspace
            bound_task = _state.get("bound_task")
            bound_cwd = _state.get("bound_cwd")
            if bound_task is not None and _state.get("scope_audit_task") != bound_task:
                return _err(rid,-32003,"scope audit is not bound to the current task")
            if bound_cwd and _state.get("scope_audit_cwd") != os.path.realpath(bound_cwd):
                return _err(rid,-32003,"scope audit is not bound to the current workspace")
            # P0-3: enforce task binding — reject cross-task evidence
            if _state["bound_task"] and a.get("task_gid") and a["task_gid"] != _state["bound_task"]:
                return _err(rid,-32004,f"task_gid '{a['task_gid']}' does not match preflighted task '{_state['bound_task']}'")
            resolution="Done" if a.get("exit_code",-1)==0 else "Blocked"
            # Local audit is UNCONDITIONAL and the source of truth.
            _audit({"event":"post_evidence","task_gid":a["task_gid"],"summary":a.get("summary"),
                    "resolution":resolution,"exit_code":a.get("exit_code"),
                    "artifacts":a.get("artifacts",[]),"references":a.get("references",[]),
                    "duration_s":a.get("duration_s")})
            result={"ok":True,"resolution":resolution,
                "message":"Evidence logged to audit. Set TRACKER_TYPE=asana + TRACKER_TOKEN to also post to the tracker."}
            # Additive: post to the real tracker if configured (fail-soft on network).
            tracker=_post_tracker(a["task_gid"],a.get("summary"),resolution,a.get("exit_code",-1),
                                  a.get("artifacts",[]),a.get("references",[]),a.get("duration_s"))
            if tracker is not None:
                result["tracker"]=tracker
            return _rsp(rid,result)
        return _err(rid,-32602,f"Unknown tool: {n}")
    except Exception as e: return _err(rid,-32603,str(e))

def _rsp(rid,r): b={"jsonrpc":"2.0","result":r}; return b if rid is None else {**b,"id":rid}
def _err(rid,c,m): b={"jsonrpc":"2.0","error":{"code":c,"message":m}}; return b if rid is None else {**b,"id":rid}

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
    _audit({"event":"session_end"})

if __name__=="__main__":
    main()
