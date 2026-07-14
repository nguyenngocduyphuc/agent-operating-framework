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
    {"name":"verify_gate","description":"Run quality gate (ruff|pytest|quality|custom) with optional multi-trial","inputSchema":{"type":"object","properties":{
        "gate_type":{"type":"string"},"cwd":{"type":"string"},
        "extra_args":{"type":"array","items":{"type":"string"}},
        "trials":{"type":"integer","minimum":1}}},
     "required":["gate_type"]},
    {"name":"audit_scope","description":"Check files against scope globs","inputSchema":{"type":"object","properties":{
        "scope":{"type":"array","items":{"type":"string"}},
        "changed_files":{"type":"array","items":{"type":"string"}}},"required":["scope","changed_files"]}},
    {"name":"session_log","description":"Append event to ~/.npflight/audit.jsonl","inputSchema":{"type":"object","properties":{
        "event":{"type":"string","description":"goal|decision|dead-end|file|question"},
        "data":{"type":"object"}},"required":["event","data"]}},
    {"name":"post_evidence","description":"Post closeout evidence (adapter provides tracker token)","inputSchema":{"type":"object","properties":{
        "task_gid":{"type":"string"},"summary":{"type":"string"},
        "exit_code":{"type":"integer"},"artifacts":{"type":"array","items":{"type":"string"}},
        "references":{"type":"array","items":{"type":"string"}},
        "duration_s":{"type":"number"}},"required":["task_gid","summary"]}},
]

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
SESSION_ID = str(uuid.uuid4())
_state = {"session_id":SESSION_ID,"preflight_ok":False,"contract_ok":False,
          "last_verify_status":None,"last_preflight":None}
AUDIT_LOG = Path.home()/".npflight"/"audit.jsonl"

def _ensure_audit(): Path.home().joinpath(".npflight").mkdir(parents=True, exist_ok=True)
def _audit(entry):
    _ensure_audit()
    entry["_session"]=SESSION_ID; entry["_ts"]=time.time()
    try:
        with open(AUDIT_LOG,"a",encoding="utf-8") as f:
            f.write(json.dumps(entry,ensure_ascii=False)+"\n")
    except OSError: pass

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
        with open(p,encoding="utf-8") as f: return f.read()
    except Exception: return None

# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------
def _run_preflight(cwd,task,bootstrap):
    cmd=[sys.executable,"-m","core.preflight","--json"]
    if task: cmd+=["--task",task]
    if bootstrap: cmd.append("--bootstrap")
    try:
        r=subprocess.run(cmd,cwd=cwd or os.getcwd(),capture_output=True,text=True,timeout=30)
        p=json.loads(r.stdout); p["exit_code"]=r.returncode; return p
    except Exception as e: return {"error":str(e),"exit_code":2}

def _check_contract(brief):
    required=["Task","Owner","Scope","DoD","Do not","Stop if","Return"]
    found=[f for f in required if f.lower() in brief.lower() or f in brief]
    missing=[f for f in required if f not in found]
    return {"ok":len(missing)==0,"found":found,"missing_required":missing}

def _verify_gate(gate_type,cwd,extra_args,trials):
    cwd=cwd or os.getcwd(); extra=extra_args or []; trials=trials or 1
    builtins={"ruff":[sys.executable,"-m","ruff","check","."],
              "pytest":[sys.executable,"-m","pytest","-x"],
              "quality":[sys.executable,"-m","compileall","-q","core"]}
    results,passes=[],0
    for i in range(trials):
        cmd=(builtins.get(gate_type) or [gate_type])+extra
        try:
            r=subprocess.run(cmd,cwd=cwd,capture_output=True,text=True,timeout=120)
            ok=r.returncode==0
            results.append({"trial":i+1,"exit_code":r.returncode,"ok":ok})
            if ok: passes+=1
        except subprocess.TimeoutExpired:
            results.append({"trial":i+1,"exit_code":-1,"ok":False,"error":"timeout"})
        except Exception as e:
            results.append({"trial":i+1,"exit_code":-1,"ok":False,"error":str(e)})
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
            r=_run_preflight(a.get("cwd"),a.get("task"),a.get("bootstrap"))
            _state["preflight_ok"]=r.get("status")=="clear" and r.get("exit_code")==0
            _state["last_preflight"]=r; return _rsp(rid,r)
        if n=="check_contract":
            r=_check_contract(a.get("brief",""))
            _state["contract_ok"]=r["ok"]; _audit({"event":"check_contract","ok":r["ok"]})
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
            _state["last_verify_status"]="passed" if r["passed"] else "failed"
            _audit({"event":"verify_gate","gate_type":a["gate_type"],"passed":r["passed"]})
            return _rsp(rid,r)
        if n=="audit_scope":
            if not _state["preflight_ok"]: return _err(rid,-32000,"Preflight not passed")
            if not _state["contract_ok"]: return _err(rid,-32001,"Contract not checked")
            r=_audit_scope(a.get("scope",[]),a.get("changed_files",[]))
            _audit({"event":"audit_scope","ok":r["ok"]}); return _rsp(rid,r)
        if n=="session_log":
            _audit({"event":a.get("event"),"data":a.get("data")}); return _rsp(rid,{"ok":True})
        if n=="post_evidence":
            if not _state["preflight_ok"]: return _err(rid,-32000,"Preflight not passed")
            if not _state["contract_ok"]: return _err(rid,-32001,"Contract not checked")
            if _state["last_verify_status"] != "passed":
                return _err(rid,-32002,"A passing verify_gate is required before post_evidence")
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
