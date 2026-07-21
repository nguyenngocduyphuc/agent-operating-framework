"""F1 (v0.4): recap/handoff must land next to the repo actually being worked
on, not a single fixed AOF_WORKSPACE. Two sessions bound to two different
repos must never write into each other's docs/sessions/ -- that was exactly
the observed bug (see docs/plans/AOF_V04_AUTOHANDOFF_EXECPLAN_20260721.md,
task F1-1): a live session in this repo wrote its handoff into the parent
NP_AI_macos workspace instead of vendors/agent-operating-framework.
"""
import json
import os
import queue
import subprocess
import sys
import threading
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "core" / "mcp_server.py"
TIMEOUT_S = 5.0


class _Client:
    """Minimal stdio JSON-RPC client -- mirrors tests/test_mcp_server.py::_Client."""

    def __init__(self, extra_env=None):
        self.proc = subprocess.Popen(
            [sys.executable, str(SERVER)],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            text=True, bufsize=1,
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
            raise AssertionError(f"MCP server did not respond to {method!r} within {TIMEOUT_S}s")
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


def _init_repo(path: Path) -> None:
    path.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    # preflight only binds bound_cwd on status=="clear"; being on main/master
    # triggers a warn ("create a feature branch per task"), which is enough to
    # keep status=="warn" and bound_cwd unset. Use a feature branch so these
    # fixture repos exercise the same clear-status path a real session would.
    subprocess.run(["git", "checkout", "-q", "-b", "feat/fixture"], cwd=path, check=True)


def _handoff_via_mcp(repo: Path, workspace: Path, aof_home: Path) -> None:
    client = _Client(extra_env={"AOF_WORKSPACE": str(workspace), "AOF_AUDIT_DIR": str(aof_home)})
    try:
        client.request("initialize", req_id=1)
        client.request("tools/call", {"name": "preflight", "arguments": {"cwd": str(repo)}}, req_id=2)
        resp = client.request(
            "tools/call", {"name": "session_handoff", "arguments": {"since_hours": 1}}, req_id=3,
        )
        result = resp["result"]
        assert result["isError"] is False, result
    finally:
        client.close()


def test_handoff_writes_into_bound_repo_not_workspace(tmp_path):
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    _init_repo(repo_a)
    _init_repo(repo_b)
    aof_home = tmp_path / "aofhome"

    _handoff_via_mcp(repo_a, workspace=tmp_path, aof_home=aof_home)
    _handoff_via_mcp(repo_b, workspace=tmp_path, aof_home=aof_home)

    sessions_a = repo_a / "docs" / "sessions"
    sessions_b = repo_b / "docs" / "sessions"

    assert sessions_a.is_dir(), "repo_a got no docs/sessions -- handoff did not land in the bound repo"
    assert sessions_b.is_dir(), "repo_b got no docs/sessions -- handoff did not land in the bound repo"

    a_files = {p.name for p in sessions_a.iterdir()}
    b_files = {p.name for p in sessions_b.iterdir()}
    assert a_files, "repo_a/docs/sessions is empty"
    assert b_files, "repo_b/docs/sessions is empty"
    # Same-second calls can share a filename (HANDOFF_<stamp>.md) -- that is
    # fine, they live in different directories. is_dir()+non-empty above,
    # plus the leak checks below, are what actually prove separation.
    assert not (tmp_path / "docs" / "sessions").exists(), (
        "handoff leaked into the shared AOF_WORKSPACE instead of the bound repo"
    )


def test_handoff_repeated_in_same_repo_is_idempotent_location(tmp_path):
    """Calling handoff twice in the same repo must keep landing in that repo,
    not drift to the workspace on a second call (e.g. once a lease is held)."""
    repo = tmp_path / "repo_only"
    _init_repo(repo)
    aof_home = tmp_path / "aofhome"
    sessions = repo / "docs" / "sessions"

    _handoff_via_mcp(repo, workspace=tmp_path, aof_home=aof_home)
    assert sessions.is_dir() and list(sessions.iterdir()), "first call did not land in the repo"

    _handoff_via_mcp(repo, workspace=tmp_path, aof_home=aof_home)
    assert sessions.is_dir() and list(sessions.iterdir()), "second call did not land in the repo"
    assert not (tmp_path / "docs" / "sessions").exists(), (
        "second call drifted into the shared AOF_WORKSPACE"
    )
