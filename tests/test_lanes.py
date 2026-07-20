"""GO-RISK-LANE (CAUSAL-VERDICT 2026-07-16, preregistered decision rule).

The verdict: gates prove causal value on risky work (scope-block 100% vs 43%,
p<0.05, replicated) but cost +35% wall time — so the full chain is mandatory
ONLY on the risk lane, and routine work runs lite (preflight + evidence).
These tests pin the fail-closed half: lite is opt-in twice (policy AND caller),
and the server escalates on evidence — a worker can never talk its way into
lite for risky work.
"""
import json
import subprocess

import pytest

from tests.test_mcp_server import _Client, envelope, payload

GOOD_BRIEF = "Task: t\nOwner: o\nScope: s\nDoD: d\nDo not: x\nStop if: y\nReturn: r\n"


def _repo(tmp_path, lanes_enabled=True):
    """Realistic layout: policy committed in-repo, audit dir OUTSIDE the repo.

    The lite file-count uses the real git inventory, so stray untracked files
    (like an in-repo audit dir) legitimately count against the budget — tests
    must model a clean deployment, not fight the fail-closed counter.
    """
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "base.txt").write_text("x")
    (repo / ".aof_policy.json").write_text(
        json.dumps({"require_task": False, "lanes_enabled": lanes_enabled}), encoding="utf-8"
    )
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=repo, check=True,
    )
    subprocess.run(["git", "checkout", "-qb", "feat/T-7"], cwd=repo, check=True)
    env = {
        "AOF_WORKSPACE": str(repo),
        "AOF_AUDIT_DIR": str(tmp_path / "aofhome"),
    }
    return repo, env


@pytest.fixture()
def lite_client(tmp_path):
    repo, env = _repo(tmp_path)
    c = _Client(extra_env=env)
    c.request("initialize", req_id=1)
    yield c, repo
    c.close()


def _preflight(c, tmp_path, lane="lite", task="T-7"):
    return c.request(
        "tools/call",
        {"name": "preflight", "arguments": {"cwd": str(tmp_path), "task": task, "lane": lane}},
        req_id=2,
    )


def test_lite_lane_small_change_posts_evidence_without_contract(lite_client):
    c, tmp_path = lite_client
    r = _preflight(c, tmp_path)
    assert payload(r)["lane"] == "lite"
    (tmp_path / "note.txt").write_text("small change")
    ev = c.request(
        "tools/call",
        {"name": "post_evidence", "arguments": {"task_gid": "T-7", "summary": "s", "exit_code": 0}},
        req_id=3,
    )
    assert envelope(ev)["isError"] is False, payload(ev)
    body = payload(ev)
    assert body["ok"] is True and body["lane"] == "lite" and body["resolution"] == "Done"


def test_lite_escalates_on_multi_file(lite_client):
    """More files than lite_max_files -> the server refuses lite. Fail closed."""
    c, tmp_path = lite_client
    _preflight(c, tmp_path)
    for i in range(5):
        (tmp_path / f"f{i}.txt").write_text("x")
    ev = c.request(
        "tools/call",
        {"name": "post_evidence", "arguments": {"task_gid": "T-7", "summary": "s", "exit_code": 0}},
        req_id=3,
    )
    assert envelope(ev)["isError"] is True
    body = payload(ev)
    assert body["error_code"] == -32012
    assert "RISK" in body["error"]
    assert "check_contract" in body["fix"], "escalation must name the full chain"


def test_lite_escalates_on_risky_path(lite_client):
    """One touched risk glob (.github/**) is enough to force the full chain."""
    c, tmp_path = lite_client
    _preflight(c, tmp_path)
    wf = tmp_path / ".github" / "workflows"
    wf.mkdir(parents=True)
    (wf / "deploy.yml").write_text("on: push")
    ev = c.request(
        "tools/call",
        {"name": "post_evidence", "arguments": {"task_gid": "T-7", "summary": "s", "exit_code": 0}},
        req_id=3,
    )
    assert envelope(ev)["isError"] is True
    assert "risk paths" in payload(ev)["error"]


def test_lite_requires_policy_opt_in(tmp_path):
    """Caller asking for lite WITHOUT lanes_enabled stays on risk. Opt-in twice."""
    repo, env = _repo(tmp_path, lanes_enabled=False)
    c = _Client(extra_env=env)
    try:
        c.request("initialize", req_id=1)
        r = _preflight(c, repo, lane="lite")
        assert payload(r).get("lane") == "risk"
        ev = c.request(
            "tools/call",
            {"name": "post_evidence", "arguments": {"task_gid": "T-7", "summary": "s", "exit_code": 0}},
            req_id=3,
        )
        assert envelope(ev)["isError"] is True
        assert payload(ev)["error_code"] == -32001, "risk lane must still demand the contract"
    finally:
        c.close()


def test_risk_lane_default_unchanged(lite_client):
    """No lane argument -> risk, full chain enforced exactly as before."""
    c, tmp_path = lite_client
    r = _preflight(c, tmp_path, lane=None)
    assert payload(r)["lane"] == "risk"
    ev = c.request(
        "tools/call",
        {"name": "post_evidence", "arguments": {"task_gid": "T-7", "summary": "s", "exit_code": 0}},
        req_id=3,
    )
    assert payload(ev)["error_code"] == -32001


def test_needs_approval_state_flow(lite_client):
    """wave2 states: needs_approval shows first and clears on 'approved'."""
    c, tmp_path = lite_client
    _preflight(c, tmp_path)
    c.request("tools/call", {"name": "session_log",
                             "arguments": {"event": "needs_approval"}}, req_id=3)
    rep = c.request("tools/call", {"name": "status_report",
                                   "arguments": {"lang": "vi"}}, req_id=4)
    text = envelope(rep)["content"][0]["text"]
    assert "CHỜ DUYỆT" in text and "Làn" in text
    c.request("tools/call", {"name": "session_log",
                             "arguments": {"event": "approved"}}, req_id=5)
    rep2 = c.request("tools/call", {"name": "status_report",
                                    "arguments": {"lang": "vi"}}, req_id=6)
    assert "CHỜ DUYỆT" not in envelope(rep2)["content"][0]["text"]
