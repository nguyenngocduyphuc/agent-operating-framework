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
    from core.mcp_server import _verify_gate

    r = _verify_gate("true", os.getcwd(), [], 1)
    assert not r.get("passed", True), "gate 'true' must be blocked"
    assert "not allowed" in r.get("error", "").lower(), "error must mention not allowed"

    r = _verify_gate("rm", os.getcwd(), ["-rf", "/"], 1)
    assert not r.get("passed", True), "gate 'rm' must be blocked"


def test_allowed_gate_checks_runtime():
    """verify_gate with allowed gate_type returns a result (not blocked)."""
    from core.mcp_server import _verify_gate

    r = _verify_gate("quality", os.getcwd(), [], 1)
    # 'quality' is allowed; result should have 'gate_type' key, not an error
    assert "error" not in r, f"quality gate must not error: {r.get('error')}"
    assert r["gate_type"] == "quality"


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


def test_gate_cwd_inside_workspace_allowed():
    """verify_gate with cwd inside preflight workspace must NOT block cwd."""
    import core.mcp_server as mcp
    from core.mcp_server import _verify_gate
    mcp._state["bound_workspace"] = "/tmp/aof-workspace"
    mcp._state["bound_cwd"] = "/tmp/aof-workspace/sub"

    r = _verify_gate("quality", "/tmp/aof-workspace/sub/project", [], 1)
    assert "error" not in r, (
        f"gate with cwd inside workspace should not block: {r.get('error')}"
    )

    mcp._state["bound_workspace"] = None
    mcp._state["bound_cwd"] = None


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
    from core.mcp_server import _call, _state

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "-C", tmp_path, "checkout", "-b", "fix/TASK-123-test"], check=True)

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
    _state["preflight_ok"] = True
    _state["bound_workspace"] = pf_data.get("workspace")
    _state["bound_cwd"] = str(tmp_path)
    _state["bound_task"] = "TASK-123"

    # check_contract
    cc_req = {"id": 2, "name": "check_contract", "arguments": {"brief": GOOD_CONTRACT}}
    cc_r = _call(2, cc_req)
    assert cc_r["result"]["ok"], f"contract failed: {cc_r}"

    # verify_gate (quality = compileall, no deps)
    vg_req = {"id": 3, "name": "verify_gate", "arguments": {"gate_type": "quality", "cwd": str(tmp_path)}}
    vg_r = _call(3, vg_req)
    assert vg_r["result"].get("passed", False), f"verify gate failed: {vg_r}"

    # audit_scope
    as_req = {"id": 4, "name": "audit_scope", "arguments": {
        "scope": ["src/api/**"],
        "changed_files": ["src/api/health.py"],
    }}
    as_r = _call(4, as_req)
    assert as_r["result"]["ok"], f"scope audit failed: {as_r}"

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
