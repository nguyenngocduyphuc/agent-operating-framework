"""END-TO-END: the full no-code journey, exactly as a real deployment runs it.

No mocks. A real git workspace, the real MCP server over real stdio, the real
policy written by `aof init` (Karpathy ON), the real gates. This is the
9-step loop from docs/VONG_LAP_NO_CODE_VI.md executed start to finish:

  init -> preflight(+lease) -> contract (Karpathy REFUSES thoughtless brief,
  then accepts a real one) -> DoD gate FAILS before the work exists ->
  do the work -> DoD gate passes -> scope audit -> evidence (Done) ->
  status_report says DONE -> recap HTML + handoff written under docs/sessions/.

If any single link weakens (a gate that stops failing-first, a state that
lies, a recap that hides), this test is designed to break.
"""
import subprocess
import sys
from pathlib import Path

import pytest

from core.doctor import run_init
from tests.test_mcp_server import _Client, envelope, payload

REPO = Path(__file__).resolve().parents[1]

THOUGHTLESS_BRIEF = (
    "Task: tao file done.txt\n"
    "Owner: agent\n"
    "Scope: done.txt\n"
    "DoD: file ton tai\n"
    "Do not: dung file khac\n"
    "Stop if: khong tao duoc\n"
    "Return: duong dan file\n"
)

REAL_BRIEF = THOUGHTLESS_BRIEF + (
    "Assumptions: workspace chi co mot nhanh lam viec, khong ai khac ghi done.txt\n"
    "DoD-cmd: test -f done.txt\n"
)


@pytest.fixture()
def journey(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    # Step 0 — the operator's one-time setup, via the REAL init.
    run_init(str(ws))
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    subprocess.run(["git", "add", "."], cwd=ws, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=ws, check=True,
    )
    subprocess.run(["git", "checkout", "-qb", "feat/T-1"], cwd=ws, check=True)
    env = {
        "AOF_WORKSPACE": str(ws),
        "AOF_AUDIT_DIR": str(tmp_path / "aofhome"),
    }
    c = _Client(extra_env=env)
    c.request("initialize", req_id=1)
    yield c, ws, env
    c.close()


def test_full_no_code_journey(journey):
    c, ws, env = journey

    # 1. Preflight: clear, lease acquired.
    r = c.request("tools/call", {"name": "preflight",
                                 "arguments": {"cwd": str(ws), "task": "T-1"}}, req_id=10)
    body = payload(r)
    assert body["status"] == "clear", body
    assert body["lease"]["status"] == "acquired"

    # 2a. Karpathy gate REFUSES a contract with no auditable thinking.
    r = c.request("tools/call", {"name": "check_contract",
                                 "arguments": {"brief": THOUGHTLESS_BRIEF}}, req_id=11)
    body = payload(r)
    assert body["ok"] is False, "a brief without Assumptions/DoD-cmd must be refused"
    assert body["karpathy_ok"] is False
    assert "hint" in body and "Think before coding" in body["hint"]

    # 2b. The same task with real thinking passes and binds the DoD command.
    r = c.request("tools/call", {"name": "check_contract",
                                 "arguments": {"brief": REAL_BRIEF}}, req_id=12)
    body = payload(r)
    assert body["ok"] is True, body
    assert body["dod_cmd"] == "test -f done.txt"

    # 3. DoD gate must FAIL while the work does not exist — goal-driven proof.
    r = c.request("tools/call", {"name": "verify_gate",
                                 "arguments": {"gate_type": "dod", "cwd": str(ws)}}, req_id=13)
    assert payload(r)["passed"] is False, "DoD passing before the work exists = fake DoD"

    # 4. Do the work (inside Scope).
    (ws / "done.txt").write_text("ket qua\n")

    # 5. Now the same DoD gate passes.
    r = c.request("tools/call", {"name": "verify_gate",
                                 "arguments": {"gate_type": "dod", "cwd": str(ws)}}, req_id=14)
    assert payload(r)["passed"] is True

    # 6. Scope audit: only done.txt changed -> ok.
    r = c.request("tools/call", {"name": "audit_scope", "arguments": {}}, req_id=15)
    body = payload(r)
    assert body["ok"] is True, body
    assert body["git_files"] == ["done.txt"]

    # 7. Evidence: Done.
    r = c.request("tools/call", {"name": "post_evidence",
                                 "arguments": {"task_gid": "T-1", "summary": "tao done.txt",
                                               "exit_code": 0}}, req_id=16)
    body = payload(r)
    assert body["ok"] is True and body["resolution"] == "Done"

    # 8. Plain-language status agrees: DONE, in Vietnamese.
    r = c.request("tools/call", {"name": "status_report",
                                 "arguments": {"lang": "vi"}}, req_id=17)
    text = envelope(r)["content"][0]["text"]
    assert "XONG" in text and "BẰNG CHỨNG" in text

    # 9. Recap + handoff: per-session docs update under the workspace.
    for cmd, needle in (("recap", "<!DOCTYPE html>"), ("handoff", "BÀN GIAO")):
        pr = subprocess.run(
            [sys.executable, str(REPO / "core" / "cli.py"), cmd, "--since-hours", "1"],
            capture_output=True, text=True, cwd=ws, timeout=60,
            env={**env, "PYTHONPATH": str(REPO), "PATH": "/usr/bin:/bin"},
        )
        assert pr.returncode == 0, pr.stderr
        out = Path(pr.stdout.strip())
        assert out.exists() and str(out.parent).endswith("docs/sessions")
        content = out.read_text(encoding="utf-8")
        assert needle in content
        assert "T-1" in content, f"{cmd} must show the task that was closed"


def test_journey_evidence_refused_without_verify(journey):
    """The acceptance condition is real: skipping verify blocks evidence."""
    c, ws, _ = journey
    c.request("tools/call", {"name": "preflight",
                             "arguments": {"cwd": str(ws), "task": "T-1"}}, req_id=10)
    c.request("tools/call", {"name": "check_contract",
                             "arguments": {"brief": REAL_BRIEF}}, req_id=11)
    r = c.request("tools/call", {"name": "post_evidence",
                                 "arguments": {"task_gid": "T-1", "summary": "s",
                                               "exit_code": 0}}, req_id=12)
    assert envelope(r)["isError"] is True
    assert payload(r)["error_code"] == -32002


def test_journey_second_session_cannot_steal_the_task(journey, tmp_path):
    c, ws, env = journey
    c.request("tools/call", {"name": "preflight",
                             "arguments": {"cwd": str(ws), "task": "T-1"}}, req_id=10)
    intruder = _Client(extra_env=env)
    try:
        intruder.request("initialize", req_id=1)
        r = intruder.request("tools/call", {"name": "preflight",
                                            "arguments": {"cwd": str(ws), "task": "T-1"}}, req_id=2)
        assert envelope(r)["isError"] is True
        assert payload(r)["error_code"] == -32011
    finally:
        intruder.close()
