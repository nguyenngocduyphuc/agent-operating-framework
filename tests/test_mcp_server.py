"""Regression tests for core/mcp_server.py stdio transport and result envelope.

These would have caught the Content-Length read(4096) deadlock: each request is
sent as ONE small ndjson line and the client then blocks waiting for the reply,
sending no further bytes. A hard queue.get(timeout=...) makes a regressed server
FAIL FAST instead of hanging the suite forever.

They would ALSO have caught the empty-tool-output bug: the server answered
tools/call with a bare business dict as `result`. The server looked healthy from
raw JSON-RPC, but every MCP host reads `result.content` and rendered "The tool
returned no output" — i.e. the product was unusable from any client. Asserting
the envelope, not just the business keys, is what makes that visible in CI.
"""
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "core" / "mcp_server.py"
TIMEOUT_S = 5.0

GOOD_BRIEF = "Task: t\nOwner: o\nScope: s\nDoD: d\nDo not: x\nStop if: y\nReturn: r\n"


def envelope(resp):
    """Assert the MCP tool-result envelope and return it."""
    result = resp["result"]
    assert "content" in result, (
        f"tools/call result has no 'content' -- every MCP host renders this as "
        f"EMPTY output. Got keys: {sorted(result)}"
    )
    assert isinstance(result["content"], list) and result["content"], "content must be a non-empty list"
    block = result["content"][0]
    assert block["type"] == "text", f"expected a text block, got {block.get('type')!r}"
    assert isinstance(block["text"], str) and block["text"].strip(), "text block must be non-empty"
    assert isinstance(result["isError"], bool), "isError must be present and boolean"
    return result


def payload(resp):
    """Decode the JSON business payload carried in the envelope's text block."""
    return json.loads(envelope(resp)["content"][0]["text"])


class _Client:
    def __init__(self, extra_env=None):
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONPATH": str(REPO), **(extra_env or {})},
        )
        self._q: queue.Queue = queue.Queue()
        self._t = threading.Thread(target=self._reader, daemon=True)
        self._t.start()

    def _reader(self):
        for line in self.proc.stdout:
            self._q.put(line)
        self._q.put(None)

    def request(self, method, params=None, req_id=None):
        msg = {"jsonrpc": "2.0", "method": method}
        if req_id is not None:
            msg["id"] = req_id
        if params is not None:
            msg["params"] = params
        self.proc.stdin.write(json.dumps(msg) + "\n")
        self.proc.stdin.flush()
        try:
            line = self._q.get(timeout=TIMEOUT_S)
        except queue.Empty:
            self.proc.kill()
            raise AssertionError(
                f"MCP server did not respond to {method!r} within {TIMEOUT_S}s "
                "— stdio transport deadlock regression"
            )
        if line is None:
            raise AssertionError(f"MCP server closed stdout without answering {method!r}")
        return json.loads(line)

    def close(self):
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        try:
            self.proc.wait(timeout=TIMEOUT_S)
        except Exception:
            self.proc.kill()


@pytest.fixture()
def client():
    c = _Client()
    yield c
    c.close()


def test_initialize_responds_fast(client):
    resp = client.request("initialize", req_id=1)
    assert resp["id"] == 1
    assert resp["result"]["serverInfo"]["name"] == "aof-mcp-server"


def test_tools_list_after_initialize(client):
    client.request("initialize", req_id=1)
    resp = client.request("tools/list", req_id=2)
    names = {t["name"] for t in resp["result"]["tools"]}
    assert {"preflight", "check_contract", "post_evidence"} <= names


def test_one_tools_call_roundtrip(client):
    client.request("initialize", req_id=1)
    resp = client.request("tools/call", {"name": "check_contract", "arguments": {"brief": GOOD_BRIEF}}, req_id=3)
    assert resp["id"] == 3
    assert envelope(resp)["isError"] is False
    assert payload(resp)["ok"] is True


def test_tools_call_result_uses_mcp_content_envelope(client):
    """A bare business dict as `result` makes every MCP host show empty output."""
    client.request("initialize", req_id=1)
    resp = client.request("tools/call", {"name": "check_contract", "arguments": {"brief": GOOD_BRIEF}}, req_id=2)
    result = envelope(resp)
    assert set(result) >= {"content", "isError"}
    assert "ok" not in result, "business keys must live inside content[0].text, not on result"


def test_every_tool_answers_with_the_envelope(tmp_path):
    """Every catalog tool, success or refusal, must be readable by a client."""
    # F1 (v0.4): preflight against a real repo distinct from AOF_WORKSPACE, so
    # this test also proves recap/handoff land next to THAT repo, not the
    # workspace -- the exact bug F1 fixes. Preflighting against the real
    # agent-operating-framework checkout here would write test artifacts into
    # the actual repo once that fix lands, so use an isolated git repo instead.
    work_repo = tmp_path / "workrepo"
    work_repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=work_repo, check=True)
    # preflight only binds bound_cwd on status=="clear"; staying on main/master
    # triggers a warn and leaves bound_cwd unset, so use a feature branch.
    subprocess.run(["git", "checkout", "-q", "-b", "feat/fixture"], cwd=work_repo, check=True)
    client = _Client(extra_env={"AOF_WORKSPACE": str(tmp_path),
                                "AOF_AUDIT_DIR": str(tmp_path / "aofhome")})
    try:
        client.request("initialize", req_id=1)
        tools = client.request("tools/list", req_id=2)["result"]["tools"]
        from core.mcp_server import TOOLS
        assert len(tools) == len(TOOLS), f"expected {len(TOOLS)} tools, got {len(tools)}"
        args = {
            "check_contract": {"brief": GOOD_BRIEF},
            "verify_gate": {"gate_type": "ruff"},
            "audit_scope": {"scope": ["core/**"]},
            "session_log": {"event": "goal"},
            "post_evidence": {"task_gid": "T-1", "summary": "s"},
            "operating_protocol": {"workspace": str(REPO)},
            "preflight": {"cwd": str(work_repo)},
            "status_report": {"lang": "en"},
            "op_log": {"since_hours": 1},
            "session_recap": {"since_hours": 1},
            "session_handoff": {"since_hours": 1},
            "worker_watch": {"path": str(tmp_path / "nope.log")},
            "aof_resume": {},
        }
        for i, tool in enumerate(tools):
            resp = client.request(
                "tools/call", {"name": tool["name"], "arguments": args[tool["name"]]},
                req_id=100 + i,
            )
            envelope(resp)  # raises with a readable message if the envelope is wrong
        # F1: recap/handoff must land next to the bound repo (work_repo), not
        # the parent AOF_WORKSPACE (tmp_path) -- proves nearest_repo() wiring.
        sessions = work_repo / "docs" / "sessions"
        assert sessions.is_dir(), "recap/handoff did not land next to the bound repo"
        assert any(p.suffix == ".html" for p in sessions.iterdir())
        assert any(p.suffix == ".md" for p in sessions.iterdir())
        assert not (tmp_path / "docs" / "sessions").exists(), (
            "recap/handoff leaked into AOF_WORKSPACE instead of the bound repo"
        )
    finally:
        client.close()


def test_refusal_is_a_readable_iserror_result_not_a_protocol_error(client):
    """Gate refusals must reach the model as text it can act on."""
    client.request("initialize", req_id=1)
    resp = client.request("tools/call", {"name": "audit_scope", "arguments": {"scope": ["x/**"]}}, req_id=3)
    assert "error" not in resp, "a gate refusal is a tool result, not a JSON-RPC protocol error"
    assert envelope(resp)["isError"] is True
    body = payload(resp)
    assert body["error_code"] == -32000
    assert "reflight" in body["error"], body
    assert "preflight" in body["fix"], "the refusal must name the tool to call next"


def test_unknown_tool_is_readable_and_lists_valid_tools(client):
    client.request("initialize", req_id=1)
    resp = client.request("tools/call", {"name": "nope", "arguments": {}}, req_id=3)
    assert envelope(resp)["isError"] is True
    body = payload(resp)
    assert body["error_code"] == -32602
    assert "check_contract" in body["fix"]


def test_operating_protocol_returns_markdown_verbatim(client):
    """Document tool: JSON-escaping a protocol doc costs tokens and readability."""
    client.request("initialize", req_id=1)
    resp = client.request(
        "tools/call", {"name": "operating_protocol", "arguments": {"workspace": str(REPO)}}, req_id=3
    )
    text = envelope(resp)["content"][0]["text"]
    assert envelope(resp)["isError"] is False
    assert text.lstrip().startswith("#"), "expected raw markdown, not a JSON blob"


def test_status_report_is_plain_text_and_never_gated(client):
    """A blocked non-technical operator most needs to see WHY — no preconditions."""
    client.request("initialize", req_id=1)
    resp = client.request(
        "tools/call", {"name": "status_report", "arguments": {"lang": "en"}}, req_id=2
    )
    result = envelope(resp)
    assert result["isError"] is False
    text = result["content"][0]["text"]
    assert "Next step" in text, "report must always tell the operator what to do next"
    assert "{" not in text.split("\n")[0], "header must be plain language, not JSON"


def test_status_report_vietnamese_default(client):
    client.request("initialize", req_id=1)
    resp = client.request("tools/call", {"name": "status_report", "arguments": {}}, req_id=2)
    text = envelope(resp)["content"][0]["text"]
    assert "Bước tiếp theo" in text


def _git_repo_with_policy(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=tmp_path, check=True,
    )
    subprocess.run(["git", "checkout", "-qb", "feat/T-9"], cwd=tmp_path, check=True)
    (tmp_path / ".aof_policy.json").write_text(
        json.dumps({"require_task": False}), encoding="utf-8"
    )
    return tmp_path


def test_second_session_on_same_task_is_refused(tmp_path):
    """C2 end to end: two servers, one task, one repo -> second preflight refused."""
    env = {
        "AOF_WORKSPACE": str(tmp_path),
        "AOF_AUDIT_DIR": str(tmp_path / "aofhome"),
    }
    _git_repo_with_policy(tmp_path)
    a, b = _Client(extra_env=env), _Client(extra_env=env)
    try:
        a.request("initialize", req_id=1)
        b.request("initialize", req_id=1)
        r1 = a.request(
            "tools/call",
            {"name": "preflight", "arguments": {"cwd": str(tmp_path), "task": "T-9"}},
            req_id=2,
        )
        assert envelope(r1)["isError"] is False
        assert payload(r1)["lease"]["status"] == "acquired"
        r2 = b.request(
            "tools/call",
            {"name": "preflight", "arguments": {"cwd": str(tmp_path), "task": "T-9"}},
            req_id=2,
        )
        assert envelope(r2)["isError"] is True, "second live session must be refused"
        body = payload(r2)
        assert body["error_code"] == -32011
        assert "LIVE" in body["error"]
    finally:
        a.close()
        b.close()


def test_lease_released_when_session_ends(tmp_path):
    """A crashed/closed session must never brick the task for the next one."""
    env = {
        "AOF_WORKSPACE": str(tmp_path),
        "AOF_AUDIT_DIR": str(tmp_path / "aofhome"),
    }
    _git_repo_with_policy(tmp_path)
    a = _Client(extra_env=env)
    a.request("initialize", req_id=1)
    r1 = a.request(
        "tools/call",
        {"name": "preflight", "arguments": {"cwd": str(tmp_path), "task": "T-9"}},
        req_id=2,
    )
    assert payload(r1)["lease"]["status"] == "acquired"
    a.close()  # graceful end -> release on stdin EOF

    b = _Client(extra_env=env)
    try:
        b.request("initialize", req_id=1)
        r2 = b.request(
            "tools/call",
            {"name": "preflight", "arguments": {"cwd": str(tmp_path), "task": "T-9"}},
            req_id=2,
        )
        assert envelope(r2)["isError"] is False
        assert payload(r2)["lease"]["status"] in ("acquired", "takeover")
    finally:
        b.close()


def test_full_oneshot_sequence(client):
    """initialize -> tools/list -> tools/call, each a single blocking round-trip."""
    init = client.request("initialize", req_id=1)
    assert "result" in init
    tools = client.request("tools/list", req_id=2)
    assert tools["result"]["tools"]
    call = client.request(
        "tools/call",
        {"name": "check_contract", "arguments": {"brief": "Task: add health\nOwner: worker\nScope: api/\nDoD: tests pass\nDo not: change db\nStop if: out of scope\nReturn: diff\n"}},
        req_id=3,
    )
    assert payload(call)["ok"] is True
