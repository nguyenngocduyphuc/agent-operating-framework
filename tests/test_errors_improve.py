"""F3: error ledger, preflight warnings, lessons, improve-check (propose only)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.enforcement import decision_file
from core.errors_ledger import (
    format_lessons,
    load_errors,
    preflight_error_warnings,
    record_error,
)
from core.improve import propose_policy_change

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture()
def aof_home(tmp_path, monkeypatch):
    home = tmp_path / "aofhome"
    home.mkdir()
    monkeypatch.setenv("AOF_AUDIT_DIR", str(home))
    return home


def test_record_error_appends_schema(aof_home):
    r1 = record_error({"fingerprint": "shadow-import:core", "title": "shadow"}, session="s1")
    r2 = record_error({"fingerprint": "shadow-import:core", "title": "again"}, session="s2")
    assert r1["ok"] and r2["ok"]
    rows = load_errors()
    assert len(rows) == 2
    for key in ("ts", "fingerprint", "title", "session", "fix_commit", "test_ref", "status"):
        assert key in rows[0]
    assert rows[0]["fingerprint"] == rows[1]["fingerprint"] == "shadow-import:core"
    assert rows[0]["status"] == "open"


def test_close_without_test_ref_refused(aof_home):
    record_error({"fingerprint": "fail-open:policy", "title": "x"})
    refused = record_error({
        "fingerprint": "fail-open:policy",
        "status": "closed",
        "title": "x",
    })
    assert refused["ok"] is False
    assert refused["refused"] is True
    assert refused["status"] == "open"
    # no closed row written
    assert all(r.get("status") != "closed" for r in load_errors())


def test_close_with_test_ref_ok(aof_home):
    record_error({"fingerprint": "x:y", "title": "t"})
    ok = record_error({
        "fingerprint": "x:y",
        "status": "closed",
        "test_ref": "tests/test_errors_improve.py::test_close_with_test_ref_ok",
        "title": "t",
    })
    assert ok["ok"] is True
    assert any(r.get("status") == "closed" for r in load_errors())


def test_preflight_warns_on_repeat_and_open(aof_home, tmp_path):
    record_error({"fingerprint": "shadow-import:core", "title": "one"})
    record_error({"fingerprint": "shadow-import:core", "title": "two"})
    warns = preflight_error_warnings()
    assert any("seen 2 times" in w for w in warns)
    assert any("Open error" in w for w in warns)

    # live preflight JSON must include warnings, not blockers for ledger alone
    env = {
        **os.environ,
        "AOF_WORKSPACE": str(tmp_path),
        "AOF_AUDIT_DIR": str(aof_home),
        "PYTHONPATH": str(REPO),
    }
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "feat/x"], cwd=tmp_path, check=True)
    r = subprocess.run(
        [sys.executable, "-m", "core.preflight", "--json", "--bootstrap"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
    )
    assert r.returncode == 0, r.stderr
    card = json.loads(r.stdout)
    assert card["status"] in ("warn", "clear", "blocked")
    # feature branch + bootstrap → not blocked by main; ledger → warn
    assert any("fingerprint" in w or "Open error" in w or "Error ledger" in w
               for w in card.get("warnings", []))
    assert not any("Error ledger" in b for b in card.get("blockers", []))


def test_preflight_no_false_positive_without_errors(aof_home, tmp_path):
    assert preflight_error_warnings() == []
    env = {
        **os.environ,
        "AOF_WORKSPACE": str(tmp_path),
        "AOF_AUDIT_DIR": str(aof_home),
        "PYTHONPATH": str(REPO),
    }
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "feat/y"], cwd=tmp_path, check=True)
    r = subprocess.run(
        [sys.executable, "-m", "core.preflight", "--json", "--bootstrap"],
        cwd=tmp_path, env=env, capture_output=True, text=True, timeout=30,
    )
    card = json.loads(r.stdout)
    assert not any("Error ledger" in w or "Open error" in w for w in card.get("warnings", []))


def test_format_lessons_two_groups(aof_home):
    record_error({"fingerprint": "a", "title": "open A"})
    record_error({
        "fingerprint": "b", "title": "closed B", "status": "closed",
        "test_ref": "tests/test_b.py",
    })
    text = format_lessons("en")
    assert "Open errors" in text
    assert "Missing test_ref" in text
    assert "open A" in text
    assert "[a]" in text


def test_cli_lessons(aof_home):
    record_error({"fingerprint": "z", "title": "Z"})
    env = {**os.environ, "AOF_AUDIT_DIR": str(aof_home), "PYTHONPATH": str(REPO), "PATH": "/usr/bin:/bin"}
    r = subprocess.run(
        [sys.executable, "-m", "core.cli", "lessons", "--lang", "en"],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert "Open errors" in r.stdout
    assert "Z" in r.stdout


def _seed_verifies(fails: int, passes: int, task: str = "T-1"):
    now = time.time()
    lines = []
    for i in range(fails):
        lines.append(json.dumps({
            "session": "s", "decision": "verify_gate", "passed": False,
            "task": task, "ts": now - i,
        }))
    for i in range(passes):
        lines.append(json.dumps({
            "session": "s", "decision": "verify_gate", "passed": True,
            "task": task, "ts": now - fails - i,
        }))
    decision_file().write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_propose_high_fail_rate(aof_home):
    _seed_verifies(fails=4, passes=1)  # n=5, fail_rate=0.8
    r = propose_policy_change(window_hours=168)
    assert r["proposal"] is not None
    assert r["proposal"]["key"] == "verify_default_trials"
    assert r["proposal"]["to"] == 3
    assert "fail_rate" in r["proposal"]["reason"] or "fail_rate" in str(r["evidence"])


def test_propose_thin_data(aof_home):
    _seed_verifies(fails=1, passes=1)  # n=2
    r = propose_policy_change(window_hours=168)
    assert r["proposal"] is None
    assert r["reason"] == "CHƯA ĐỦ DATA"


def test_propose_no_anomaly(aof_home):
    _seed_verifies(fails=0, passes=6)
    r = propose_policy_change(window_hours=168)
    assert r["proposal"] is None
    assert r["reason"] == "KHÔNG BẤT THƯỜNG"


def test_propose_open_errors(aof_home):
    record_error({"fingerprint": "e1", "title": "1"})
    record_error({"fingerprint": "e2", "title": "2"})
    r = propose_policy_change(window_hours=168)
    assert r["proposal"] is not None
    assert r["proposal"]["key"] == "require_evidence"


def test_improve_check_cli_never_writes_policy(aof_home, tmp_path):
    _seed_verifies(fails=4, passes=1)
    policy = tmp_path / ".aof_policy.json"
    policy.write_text('{"require_task": false}\n', encoding="utf-8")
    before = policy.read_text(encoding="utf-8")
    env = {
        **os.environ,
        "AOF_AUDIT_DIR": str(aof_home),
        "AOF_WORKSPACE": str(tmp_path),
        "PYTHONPATH": str(REPO),
        "PATH": "/usr/bin:/bin",
    }
    r = subprocess.run(
        [sys.executable, "-m", "core.cli", "improve-check", "--window-hours", "168", "--lang", "en"],
        capture_output=True, text=True, cwd=tmp_path, env=env, timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert "IMPROVE-CHECK" in r.stdout
    assert policy.read_text(encoding="utf-8") == before
    # proposal path should mention no auto write
    assert "not write" in r.stdout.lower() or "KHÔNG" in r.stdout or "do NOT" in r.stdout


def test_session_log_error_via_mcp(aof_home, tmp_path):
    import queue
    import threading

    server = REPO / "core" / "mcp_server.py"

    class _C:
        def __init__(self):
            self.proc = subprocess.Popen(
                [sys.executable, str(server)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, bufsize=1,
                env={**os.environ, "PYTHONPATH": str(REPO),
                     "AOF_AUDIT_DIR": str(aof_home), "AOF_WORKSPACE": str(tmp_path)},
            )
            self.q: queue.Queue = queue.Queue()
            threading.Thread(target=self._r, daemon=True).start()

        def _r(self):
            for line in self.proc.stdout:
                self.q.put(line)
            self.q.put(None)

        def req(self, method, params=None, req_id=1):
            msg = {"jsonrpc": "2.0", "method": method, "id": req_id}
            if params is not None:
                msg["params"] = params
            self.proc.stdin.write(json.dumps(msg) + "\n")
            self.proc.stdin.flush()
            line = self.q.get(timeout=5)
            return json.loads(line)

        def close(self):
            try:
                self.proc.stdin.close()
            except Exception:
                pass
            self.proc.kill()

    c = _C()
    try:
        c.req("initialize", req_id=1)
        c.req("tools/call", {
            "name": "session_log",
            "arguments": {
                "event": "error",
                "data": {"fingerprint": "mcp:err", "title": "from mcp"},
            },
        }, req_id=2)
        rows = load_errors()
        assert any(r.get("fingerprint") == "mcp:err" for r in rows)
        # refuse close without test_ref
        c.req("tools/call", {
            "name": "session_log",
            "arguments": {
                "event": "error",
                "data": {"fingerprint": "mcp:err", "status": "closed"},
            },
        }, req_id=3)
        assert all(
            not (r.get("fingerprint") == "mcp:err" and r.get("status") == "closed")
            for r in load_errors()
        )
    finally:
        c.close()
