"""Regression tests for core/mcp_server.py stdio transport.

These would have caught the Content-Length read(4096) deadlock: each request is
sent as ONE small ndjson line and the client then blocks waiting for the reply,
sending no further bytes. A hard queue.get(timeout=...) makes a regressed server
FAIL FAST instead of hanging the suite forever.
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


class _Client:
    def __init__(self):
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            env={**os.environ, "PYTHONPATH": str(REPO)},
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
    brief = (
        "Task: t\nOwner: o\nScope: s\nDoD: d\nDo not: x\nStop if: y\nReturn: r\n"
    )
    resp = client.request("tools/call", {"name": "check_contract", "arguments": {"brief": brief}}, req_id=3)
    assert resp["id"] == 3
    assert resp["result"]["ok"] is True


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
    assert call["result"]["ok"] is True
