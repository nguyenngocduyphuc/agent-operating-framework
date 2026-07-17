"""Adversarial checks for AOF P0 security fixes.

Each check maps to one of the 8 proven scenarios from Wave 1 handoff.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from core import check_contract

REPO = Path(__file__).resolve().parents[1]
CORE = REPO / "core"
GOOD_POLICY = {
    "require_task": True,
    "require_contract": True,
    "require_evidence": True,
    "require_handoff": True,
    "allow_bootstrap_without_task": False,
}

GOOD_CONTRACT = (
    "Task: Add a health endpoint\n"
    "Owner: codex-worker\n"
    "Scope: src/api/health.py\n"
    "DoD: GET /health returns 200\n"
    "Do not: touch deploy config\n"
    "Stop if: scope outside src/api/\n"
    "Return: diff + test results\n"
)

PROSE_ONLY_CONTRACT = (
    "Task Owner Scope DoD Do not Stop if Return are words in prose not headers.\n"
    "This paragraph mentions all fields but none is a proper header.\n"
)


# ===================================================================
# 1. Invalid policy → fail closed (exit 2, not silent exit 0)
# ===================================================================

def test_invalid_policy_fails_closed(tmp_path):
    """A corrupt/unparseable policy file must produce a blocker, not a silent pass."""
    (tmp_path / ".aof_policy.json").write_text("not valid json {{{")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    env = {**os.environ, "AOF_WORKSPACE": str(tmp_path), "PYTHONPATH": str(REPO)}
    r = subprocess.run(
        [sys.executable, "-m", "core.preflight", "--task", "TASK-1"],
        cwd=str(CORE),
        capture_output=True, text=True, timeout=15, env=env,
    )

    assert r.returncode == 2, f"expected exit 2, got {r.returncode}"
    assert "policy" in r.stdout.lower() or "policy" in r.stderr.lower(), (
        "blocker must mention policy"
    )


# ===================================================================
# 2. Prose-only contract → fail (no line-start Field: value)
# ===================================================================

def test_prose_contract_fails():
    """Contract containing only prose (no line-start header fields) must fail."""
    r = check_contract.validate(PROSE_ONLY_CONTRACT)
    assert not r["ok"], "prose-only contract must not pass"
    assert len(r["missing_required"]) == 7, "all 7 fields should be missing"
    assert r["found"] == [], "no fields should be found from prose"


def test_valid_contract_passes():
    """A properly formatted contract with line-start fields must pass."""
    r = check_contract.validate(GOOD_CONTRACT)
    assert r["ok"], "valid contract must pass"
    assert len(r["missing_required"]) == 0


# ===================================================================
# 3. Wrong task/branch → block (exit 2)
# ===================================================================

def test_wrong_branch_blocks(tmp_path):
    """Branch naming a different task than the supplied --task must block."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    # An initial commit is needed so `git rev-parse --abbrev-ref HEAD` resolves
    # the branch name instead of returning HEAD in a commit-less repo.
    (tmp_path / "README.md").write_text("# test")
    subprocess.run(["git", "-C", tmp_path, "add", "-A"], check=True)
    subprocess.run(["git", "-C", tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "initial"], check=True)
    subprocess.run(["git", "-C", tmp_path, "checkout", "-b", "fix/ASANA-9999999999-other"], check=True)

    env = {**os.environ, "AOF_WORKSPACE": str(tmp_path), "PYTHONPATH": str(REPO)}
    r = subprocess.run(
        [sys.executable, "-m", "core.preflight", "--task", "0000000000"],
        cwd=tmp_path,
        capture_output=True, text=True, timeout=15, env=env,
    )

    assert r.returncode == 2, (
        f"expected exit 2 for wrong-task branch, got {r.returncode}\nstdout: {r.stdout}"
    )


def test_matching_branch_passes(tmp_path):
    """Branch containing the supplied --task must NOT block."""
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "README.md").write_text("# test")
    subprocess.run(["git", "-C", tmp_path, "add", "-A"], check=True)
    subprocess.run(["git", "-C", tmp_path, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "initial"], check=True)
    subprocess.run(["git", "-C", tmp_path, "checkout", "-b", "fix/ASANA-0000000000-feat"], check=True)

    env = {**os.environ, "AOF_WORKSPACE": str(tmp_path), "PYTHONPATH": str(REPO)}
    r = subprocess.run(
        [sys.executable, "-m", "core.preflight", "--task", "0000000000"],
        cwd=tmp_path,
        capture_output=True, text=True, timeout=15, env=env,
    )

    # On main/master, preflight warns but doesn't block.
    # On a non-default branch with matching task, should pass (no task mismatch).
    assert r.returncode == 0, (
        f"expected exit 0 for matching branch, got {r.returncode}\n{r.stdout}"
    )


# ===================================================================
# 4. Gate outside allowlist → block
# ===================================================================

def test_disallowed_gate_blocked():
    """verify_gate with a gate_type not in {ruff, pytest, quality} must block."""
    # Direct unit test on _verify_gate logic via MCP server import
    from unittest import mock

    from core.mcp_server import _verify_gate

    with mock.patch("core.mcp_server.subprocess.run") as run:
        r = _verify_gate("true", os.getcwd(), [], 1)
        run.assert_not_called()
    assert not r.get("passed", True), "gate 'true' must be blocked"
    assert "not allowed" in r.get("error", "").lower(), "error must mention not allowed"

    with mock.patch("core.mcp_server.subprocess.run") as run:
        r = _verify_gate("rm", os.getcwd(), ["-rf", "/"], 1)
        run.assert_not_called()
    assert not r.get("passed", True), "gate 'rm' must be blocked"


def test_allowed_gate_checks_runtime():
    """verify_gate with allowed gate_type returns a result (not blocked)."""
    from core.mcp_server import _verify_gate

    r = _verify_gate("quality", os.getcwd(), [], 1)
    # 'quality' is allowed; result should have 'gate_type' key, not an error
    assert "error" not in r, f"quality gate must not error: {r.get('error')}"
    assert r["gate_type"] == "quality"


def test_quality_gate_not_compileall_only():
    """quality must not use compileall-only as a false evidence proof."""
    from unittest import mock

    from core.mcp_server import _gate_commands

    cmds = _gate_commands("quality", str(REPO), [])
    assert cmds, "quality must resolve to at least one command"
    flat = " ".join(" ".join(c) for c in cmds)
    assert "compileall" not in flat, "quality must not be compileall-only"
    # Must reuse project lint and/or tests
    assert "ruff" in flat or "pytest" in flat

    # Unknown gate never reaches subprocess
    import core.mcp_server as mcp
    with mock.patch.object(mcp.subprocess, "run") as run:
        r = mcp._verify_gate("echo", str(REPO), ["pwned"], 1)
    run.assert_not_called()
    assert r["passed"] is False


# ===================================================================
# 5. Gate cwd outside workspace → block
# ===================================================================

def test_gate_cwd_outside_workspace_blocked():
    """verify_gate with cwd outside the preflight workspace must block."""
    # Simulate a bound workspace
    import core.mcp_server as mcp
    from core.mcp_server import _verify_gate
    mcp._state["bound_workspace"] = "/tmp/aof-workspace"
    mcp._state["bound_cwd"] = "/tmp/aof-workspace/sub"

    r = _verify_gate("ruff", "/etc", [], 1)
    assert not r.get("passed", True), "gate with cwd outside workspace must block"
    assert "cwd must be under" in r.get("error", "").lower(), (
        f"unexpected error: {r.get('error')}"
    )

    # Reset state
    mcp._state["bound_workspace"] = None
    mcp._state["bound_cwd"] = None


def test_gate_cwd_mismatch_blocked():
    """A gate cannot move to another directory after preflight."""
    import core.mcp_server as mcp
    from core.mcp_server import _verify_gate
    mcp._state["bound_workspace"] = "/tmp/aof-workspace"
    mcp._state["bound_cwd"] = "/tmp/aof-workspace/sub"

    r = _verify_gate("quality", "/tmp/aof-workspace/sub/project", [], 1)
    assert not r.get("passed", True), "gate cwd must match the preflight cwd"
    assert "preflight cwd" in r.get("error", "").lower()

    mcp._state["bound_workspace"] = None
    mcp._state["bound_cwd"] = None


def test_scope_mismatch_blocked():
    """audit_scope must use the checked contract, not a caller-supplied glob."""
    from core.mcp_server import _call, _state

    _state.update({"preflight_ok": True, "contract_ok": False,
                   "last_verify_status": None, "scope_audit_ok": False,
                   "contract_scope_parsed": None,
                   "scope_audit_task": None, "scope_audit_cwd": None})
    contract = _call(20, {"id": 20, "name": "check_contract", "arguments": {
        "brief": GOOD_CONTRACT,
    }})
    assert contract["result"]["ok"]

    result = _call(21, {"id": 21, "name": "audit_scope", "arguments": {
        "scope": ["**"],
        "changed_files": ["out-of-scope/secrets.py"],
    }})
    assert "error" in result, "caller must not widen contract scope"
    assert result["error"]["code"] == -32006

    _state.update({"preflight_ok": False, "contract_ok": False,
                   "last_verify_status": None, "scope_audit_ok": False,
                   "contract_scope_parsed": None,
                   "scope_audit_task": None, "scope_audit_cwd": None})


def test_caller_changed_files_cannot_hide_out_of_scope_git(tmp_path):
    """Caller-supplied changed_files is not evidence; git inventory is trusted."""
    from unittest import mock

    from core.mcp_server import _call, _state

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "src" / "api").mkdir(parents=True)
    (tmp_path / "src" / "api" / "health.py").write_text("ok = True\n")
    (tmp_path / "evil_out_of_scope.py").write_text("x = 1\n")

    _state.update({
        "preflight_ok": True, "contract_ok": True,
        "last_verify_status": "passed", "scope_audit_ok": False,
        "contract_scope_parsed": ["src/api/health.py"],
        "bound_cwd": str(tmp_path), "bound_task": "TASK-SCOPE",
        "scope_audit_task": None, "scope_audit_cwd": None,
    })
    # Adversary claims only the in-scope file; untracked evil still in git truth
    result = _call(30, {"id": 30, "name": "audit_scope", "arguments": {
        "scope": ["src/api/health.py"],
        "changed_files": ["src/api/health.py"],
    }})
    assert "result" in result, f"expected result, got {result}"
    assert result["result"]["ok"] is False
    assert "evil_out_of_scope.py" in result["result"]["out_of_scope"]
    assert result["result"].get("caller_changed_files_ignored") is True
    assert _state["scope_audit_ok"] is False

    # Honest git inventory with only in-scope file may pass
    with mock.patch("core.mcp_server._git_inventory", return_value=["src/api/health.py"]):
        result2 = _call(31, {"id": 31, "name": "audit_scope", "arguments": {
            "scope": ["src/api/health.py"],
            "changed_files": ["forged-only.py"],  # ignored
        }})
    assert result2["result"]["ok"] is True
    assert _state["scope_audit_ok"] is True
    assert _state["scope_audit_task"] == "TASK-SCOPE"

    _state.update({"preflight_ok": False, "contract_ok": False,
                   "last_verify_status": None, "scope_audit_ok": False,
                   "contract_scope_parsed": None, "bound_cwd": None,
                   "bound_task": None, "scope_audit_task": None,
                   "scope_audit_cwd": None})


def test_git_inventory_includes_untracked(tmp_path):
    """Untracked paths must appear in trusted scope inventory."""
    from core.mcp_server import _git_inventory

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "scratch").mkdir()
    (tmp_path / "scratch" / "untracked_evil.py").write_text("pass\n")
    files = _git_inventory(str(tmp_path))
    assert "scratch/untracked_evil.py" in files


def test_new_preflight_resets_prior_gate_state(monkeypatch):
    """A new task cannot inherit completed gates from the previous task."""
    import core.mcp_server as mcp

    monkeypatch.setattr(mcp, "_run_preflight", lambda *_: {
        "status": "clear", "exit_code": 0, "workspace": "/tmp/aof", "task": "TASK-B",
    })
    mcp._state.update({"preflight_ok": True, "contract_ok": True,
                       "last_verify_status": "passed", "scope_audit_ok": True,
                       "contract_scope_parsed": ["src/**"]})

    result = mcp._call(22, {"id": 22, "name": "preflight", "arguments": {
        "cwd": "/tmp/aof", "task": "TASK-B",
    }})
    assert result["result"]["status"] == "clear"
    assert not mcp._state["contract_ok"]
    assert mcp._state["last_verify_status"] is None
    assert not mcp._state["scope_audit_ok"]
    assert mcp._state["contract_scope_parsed"] is None


# ===================================================================
# 6. Cross-task evidence → block
# ===================================================================

def test_cross_task_evidence_blocked():
    """post_evidence must reject task_gid different from the preflighted task."""
    from core.mcp_server import _call, _state

    # Simulate session bound to task "TASK-A"
    _state["preflight_ok"] = True
    _state["contract_ok"] = True
    _state["last_verify_status"] = "passed"
    _state["scope_audit_ok"] = True
    _state["bound_task"] = "TASK-A"
    _state["bound_cwd"] = "/tmp/aof-workspace"
    _state["scope_audit_task"] = "TASK-A"
    _state["scope_audit_cwd"] = os.path.realpath("/tmp/aof-workspace")

    # Try posting evidence for "TASK-B"
    req = {"id": 10, "name": "post_evidence", "arguments": {
        "task_gid": "TASK-B",
        "summary": "cross-task evidence attempt",
        "exit_code": 0,
    }}
    r = _call(10, req)
    assert "error" in r, "expected error for cross-task evidence"
    assert r["error"]["code"] == -32004, f"expected error code -32004, got {r['error']['code']}"
    assert "TASK-A" in r["error"]["message"], "error must mention bound task"
    assert "TASK-B" in r["error"]["message"], "error must mention submitted task"

    # Cleanup
    _state["preflight_ok"] = False
    _state["contract_ok"] = False
    _state["last_verify_status"] = None
    _state["scope_audit_ok"] = False
    _state["bound_task"] = None
    _state["bound_cwd"] = None
    _state["scope_audit_task"] = None
    _state["scope_audit_cwd"] = None


def test_post_evidence_requires_bound_scope_audit():
    """post_evidence rejects scope_audit_ok that is not bound to current task/cwd."""
    from core.mcp_server import _call, _state

    _state.update({
        "preflight_ok": True, "contract_ok": True,
        "last_verify_status": "passed", "scope_audit_ok": True,
        "bound_task": "TASK-X", "bound_cwd": "/tmp/ws-a",
        "scope_audit_task": "TASK-OLD",  # stale binding
        "scope_audit_cwd": os.path.realpath("/tmp/ws-a"),
    })
    r = _call(13, {"id": 13, "name": "post_evidence", "arguments": {
        "task_gid": "TASK-X", "summary": "stale scope", "exit_code": 0,
    }})
    assert "error" in r
    assert r["error"]["code"] == -32003

    _state.update({
        "scope_audit_task": "TASK-X",
        "scope_audit_cwd": os.path.realpath("/tmp/ws-other"),
    })
    r2 = _call(14, {"id": 14, "name": "post_evidence", "arguments": {
        "task_gid": "TASK-X", "summary": "wrong cwd", "exit_code": 0,
    }})
    assert "error" in r2
    assert r2["error"]["code"] == -32003

    _state.update({
        "preflight_ok": False, "contract_ok": False,
        "last_verify_status": None, "scope_audit_ok": False,
        "bound_task": None, "bound_cwd": None,
        "scope_audit_task": None, "scope_audit_cwd": None,
    })


# ===================================================================
# 7. Done evidence requires verify AND scope-audit
# ===================================================================

def test_evidence_needs_verify():
    """post_evidence must reject if verify_gate has not passed."""
    from core.mcp_server import _call, _state

    _state["preflight_ok"] = True
    _state["contract_ok"] = True
    _state["last_verify_status"] = None   # never verified
    _state["scope_audit_ok"] = True

    req = {"id": 11, "name": "post_evidence", "arguments": {
        "task_gid": "TASK-X", "summary": "no verify", "exit_code": 0,
    }}
    r = _call(11, req)
    assert "error" in r, "expected error when verify not passed"
    assert -32002 in (r["error"]["code"], r.get("error", {}).get("code", 0)), (
        "expected verify gate error code"
    )

    _state["preflight_ok"] = False
    _state["contract_ok"] = False
    _state["last_verify_status"] = None
    _state["scope_audit_ok"] = False


def test_evidence_needs_scope_audit():
    """post_evidence must reject if audit_scope has not passed."""
    from core.mcp_server import _call, _state

    _state["preflight_ok"] = True
    _state["contract_ok"] = True
    _state["last_verify_status"] = "passed"
    _state["scope_audit_ok"] = False   # never scoped-audited

    req = {"id": 12, "name": "post_evidence", "arguments": {
        "task_gid": "TASK-X", "summary": "no scope audit", "exit_code": 0,
    }}
    r = _call(12, req)
    assert "error" in r, "expected error when scope audit not passed"
    assert -32003 in (r["error"]["code"], r.get("error", {}).get("code", 0)), (
        "expected scope audit error code"
    )

    _state["preflight_ok"] = False
    _state["contract_ok"] = False
    _state["last_verify_status"] = None
    _state["scope_audit_ok"] = False


# ===================================================================
# 8. Full MCP sequence for valid task → pass
# ===================================================================

def test_full_mcp_sequence_passes(tmp_path):
    """preflight → check_contract → verify_gate → audit_scope → post_evidence
    must all pass for a valid task with matching branch."""
    from unittest import mock

    from core.mcp_server import _call, _state

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-C", tmp_path, "checkout", "-b", "fix/TASK-123-test"], check=True)
    (tmp_path / "src" / "api").mkdir(parents=True)
    (tmp_path / "src" / "api" / "health.py").write_text("ok = True\n")
    # In-scope untracked file becomes trusted inventory

    # preflight
    _state.clear()
    _state.update({"session_id": "test-session"})
    env = {**os.environ, "AOF_WORKSPACE": str(tmp_path), "PYTHONPATH": str(REPO)}
    # Run actual preflight via subprocess to get real workspace binding
    pf_cmd = [sys.executable, "-m", "core.preflight", "--task", "TASK-123", "--json"]
    pf_r = subprocess.run(pf_cmd, cwd=tmp_path, capture_output=True, text=True, timeout=15, env=env)
    pf_data = json.loads(pf_r.stdout)
    assert pf_r.returncode == 0, f"preflight failed: {pf_data}"

    # Now drive the rest through MCP _call with proper state
    bound = os.path.realpath(str(tmp_path))
    _state["preflight_ok"] = True
    _state["bound_workspace"] = pf_data.get("workspace")
    _state["bound_cwd"] = bound
    _state["bound_task"] = "TASK-123"
    _state["scope_audit_ok"] = False
    _state["scope_audit_task"] = None
    _state["scope_audit_cwd"] = None

    # check_contract
    cc_req = {"id": 2, "name": "check_contract", "arguments": {"brief": GOOD_CONTRACT}}
    cc_r = _call(2, cc_req)
    assert cc_r["result"]["ok"], f"contract failed: {cc_r}"

    # verify_gate (quality = ruff, and pytest only when not already under pytest)
    with mock.patch("core.mcp_server.subprocess.run") as run:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        vg_req = {"id": 3, "name": "verify_gate", "arguments": {"gate_type": "quality", "cwd": bound}}
        vg_r = _call(3, vg_req)
    assert vg_r["result"].get("passed", False), f"verify gate failed: {vg_r}"
    # Must not invoke compileall
    for call in run.call_args_list:
        cmd = call.args[0] if call.args else call.kwargs.get("args")
        assert "compileall" not in " ".join(str(x) for x in (cmd or [])), call

    # audit_scope uses git truth (in-scope untracked health.py)
    as_req = {"id": 4, "name": "audit_scope", "arguments": {
        "scope": ["src/api/health.py"],
        "changed_files": [],  # ignored; must not be required as evidence
    }}
    as_r = _call(4, as_req)
    assert as_r["result"]["ok"], f"scope audit failed: {as_r}"
    assert "src/api/health.py" in as_r["result"]["git_files"]
    assert _state["scope_audit_task"] == "TASK-123"
    assert _state["scope_audit_cwd"] == bound

    # post_evidence
    pe_req = {"id": 5, "name": "post_evidence", "arguments": {
        "task_gid": "TASK-123",
        "summary": "Added health endpoint",
        "exit_code": 0,
    }}
    pe_r = _call(5, pe_req)
    assert pe_r["result"]["ok"], f"post_evidence failed: {pe_r}"
    assert pe_r["result"]["resolution"] == "Done"

    # Cleanup
    _state.clear()
