"""Tests for policy flag `require_karpathy`.

The flag turns four Karpathy principles into contract checks that a gate can
actually run. Each test below pins one check AND its escape hatch, because the
checks are structural: they prove a claim was made, not that the claim is true.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core import check_contract

REPO = Path(__file__).resolve().parents[1]

BASE = (
    "Task: Add a health endpoint\n"
    "Owner: worker\n"
    "Scope: src/api/health.py\n"
    "DoD: GET /health returns 200\n"
    "Do not: touch deploy config\n"
    "Stop if: the fix needs a router change\n"
    "Return: diff + test output\n"
)
THINKING = (
    "Assumptions: the router already mounts /api; if not, this needs a router change first.\n"
    "DoD-cmd: python -m pytest tests/test_health.py\n"
)
KARPATHY_BRIEF = BASE + THINKING


def principles(result):
    return {f["principle"].split(".")[0] for f in result["karpathy_findings"]}


# --- flag off: behaviour is exactly what it was -----------------------------

def test_flag_off_leaves_validation_unchanged():
    off = check_contract.validate(BASE)
    assert off["ok"] is True
    assert off["karpathy_required"] is False
    assert "karpathy_findings" not in off, "checks must not run when the flag is off"


def test_flag_off_is_the_product_default():
    example = json.loads((REPO / ".aof_policy.example.json").read_text())
    assert example["require_karpathy"] is False, "shipping default must be opt-in"


# --- flag on: each principle blocks -----------------------------------------

def test_thinking_free_brief_is_blocked():
    r = check_contract.validate(BASE, require_karpathy=True)
    assert r["ok"] is False, "a brief with all 7 fields but no thinking must not pass"
    assert r["karpathy_ok"] is False
    assert principles(r) == {"1", "4"}, r["karpathy_findings"]


def test_brief_with_thinking_passes():
    r = check_contract.validate(KARPATHY_BRIEF, require_karpathy=True)
    assert r["ok"] is True, r.get("hint")
    assert r["karpathy_ok"] is True
    assert r["karpathy_findings"] == []
    assert r["dod_cmd"] == "python -m pytest tests/test_health.py"


@pytest.mark.parametrize("field", ["Assumptions", "Tradeoffs"])
def test_either_thinking_field_satisfies_principle_one(field):
    brief = BASE + f"{field}: chose the boring option; it costs an extra round trip.\n" \
                   "DoD-cmd: python -m pytest tests/test_health.py\n"
    assert check_contract.validate(brief, require_karpathy=True)["ok"] is True


def test_placeholder_assumption_is_rejected():
    brief = BASE + "Assumptions: none\nDoD-cmd: python -m pytest tests/test_health.py\n"
    r = check_contract.validate(brief, require_karpathy=True)
    assert r["ok"] is False
    assert principles(r) == {"1"}


@pytest.mark.parametrize("cmd", ["true", ":", "echo ok", "EXIT 0"])
def test_noop_dod_cmd_is_rejected(cmd):
    brief = BASE + THINKING.splitlines()[0] + f"\nDoD-cmd: {cmd}\n"
    r = check_contract.validate(brief, require_karpathy=True)
    assert r["ok"] is False
    assert principles(r) == {"4"}


@pytest.mark.parametrize("scope", ["*", "**", "**/*", ".", "./**", "src/api/health.py, **"])
def test_unbounded_scope_is_rejected(scope):
    brief = KARPATHY_BRIEF.replace("Scope: src/api/health.py", f"Scope: {scope}")
    r = check_contract.validate(brief, require_karpathy=True)
    assert r["ok"] is False
    assert "2/3" in " ".join(f["principle"] for f in r["karpathy_findings"])


@pytest.mark.parametrize("scope", ["src/**", "core/mcp_server.py, tests/*.py", "docs/*.md"])
def test_bounded_scope_globs_still_pass(scope):
    brief = KARPATHY_BRIEF.replace("Scope: src/api/health.py", f"Scope: {scope}")
    assert check_contract.validate(brief, require_karpathy=True)["ok"] is True


# --- the block message has to teach ----------------------------------------

def test_block_message_names_problem_fix_and_its_own_limits():
    r = check_contract.validate(BASE, require_karpathy=True)
    hint = r["hint"]
    assert "require_karpathy" in hint, "say WHY it blocked"
    for f in r["karpathy_findings"]:
        assert f["problem"] in hint and f["fix"] in hint
    assert "Assumptions: " in hint and "DoD-cmd: " in hint, "show the exact line to add"
    assert "Limits of this check" in hint, "a heuristic must disclose its own gaps"
    assert r["karpathy_limits"] == check_contract.KARPATHY_LIMITS


def test_documented_escape_hatch_really_works():
    """Honest limits: structure is checkable, sincerity is not. Pin the gap."""
    gamed = BASE + (
        "Assumptions: none that matter for this change\n"
        "DoD-cmd: python -c pass\n"
    )
    assert check_contract.validate(gamed, require_karpathy=True)["ok"] is True, (
        "if this ever fails, the README's stated limits are out of date"
    )


# --- wired into the MCP tool via workspace policy ---------------------------

def _policy_workspace(tmp_path, require_karpathy):
    (tmp_path / ".aof_policy.json").write_text(json.dumps({"require_karpathy": require_karpathy}))
    return tmp_path


def test_mcp_check_contract_honours_policy_flag(tmp_path, monkeypatch):
    import core.mcp_server as mcp

    ws = _policy_workspace(tmp_path, True)
    monkeypatch.setenv("AOF_POLICY_FILE", str(ws / ".aof_policy.json"))
    monkeypatch.setitem(mcp._state, "bound_workspace", str(ws))

    blocked = mcp._call(1, {"name": "check_contract", "arguments": {"brief": BASE}})
    body = json.loads(blocked["result"]["content"][0]["text"])
    assert body["ok"] is False and body["karpathy_required"] is True
    assert mcp._state["contract_ok"] is False, "a blocked contract must not unlock later gates"

    passing = mcp._call(2, {"name": "check_contract", "arguments": {"brief": KARPATHY_BRIEF}})
    assert json.loads(passing["result"]["content"][0]["text"])["ok"] is True
    assert mcp._state["contract_ok"] is True


def test_mcp_client_can_read_the_karpathy_hint(tmp_path):
    """End to end over stdio: the refusal must arrive as readable text."""
    ws = _policy_workspace(tmp_path, True)
    req = json.dumps({"jsonrpc": "2.0", "id": 1, "method": "tools/call",
                      "params": {"name": "check_contract", "arguments": {"brief": BASE}}})
    r = subprocess.run(
        [sys.executable, str(REPO / "core" / "mcp_server.py")],
        input=req + "\n", capture_output=True, text=True, timeout=20,
        env={**os.environ, "PYTHONPATH": str(REPO),
             "AOF_POLICY_FILE": str(ws / ".aof_policy.json"), "AOF_WORKSPACE": str(ws)},
    )
    resp = json.loads(r.stdout.strip().splitlines()[-1])
    text = resp["result"]["content"][0]["text"]
    assert "require_karpathy" in text and "DoD-cmd" in text, text
