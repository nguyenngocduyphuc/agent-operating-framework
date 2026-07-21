"""aof log + aof watch — the operator's daily loop must be honest and testable.

Ledger rule: report ONLY what the enforcement layer recorded. A digest that
hides a Blocked or upgrades it to Done is a false report. Watch rule: judge the
worker by its OUTPUT (file mtime/size), never by "session alive" — the 18-minute
hang of 2026-07-20 was invisible to session-based watchdogs.
"""
import json
import os
import time

import pytest

from core import heartbeat
from core.enforcement import audit_file, decision_file
from core.oplog import build_digest, format_digest


@pytest.fixture()
def aof_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AOF_AUDIT_DIR", str(tmp_path / "aofhome"))
    (tmp_path / "aofhome").mkdir()
    return tmp_path / "aofhome"


def _seed(aof_home, now=None):
    now = now or time.time()
    audit = [
        {"event": "session_start", "_session": "s1", "_ts": now - 3600},
        {"event": "lease_conflict", "task": "T-2", "_session": "s2", "_ts": now - 3000},
        {"event": "session_start", "_session": "s2", "_ts": now - 3000},
    ]
    decisions = [
        {"session": "s1", "decision": "check_contract", "ok": True, "task": "T-1", "ts": now - 3500},
        {"session": "s1", "decision": "verify_gate", "passed": False, "task": "T-1", "ts": now - 3400},
        {"session": "s1", "decision": "verify_gate", "passed": True, "task": "T-1", "ts": now - 3300},
        {"session": "s1", "decision": "post_evidence", "resolution": "Done", "task": "T-1", "ts": now - 3200},
        {"session": "s2", "decision": "check_contract", "ok": True, "task": "T-2", "ts": now - 2900},
        {"session": "s2", "decision": "post_evidence", "resolution": "Blocked", "task": "T-2", "ts": now - 2800},
    ]
    with open(audit_file(), "w", encoding="utf-8") as f:
        f.writelines(json.dumps(e) + "\n" for e in audit)
    with open(decision_file(), "w", encoding="utf-8") as f:
        f.writelines(json.dumps(e) + "\n" for e in decisions)


def test_digest_counts_done_blocked_collisions(aof_home):
    _seed(aof_home)
    r = build_digest(since_ts=time.time() - 7200)
    assert r["sessions"] == 2
    assert r["done"] == 1
    assert r["blocked"] == 1
    assert r["collisions"] == 1
    assert r["gate_fail"] == 1
    assert r["tasks"]["T-1"]["verify_pass"] == 1


def test_digest_never_hides_blocked(aof_home):
    """A Blocked closure must appear with the same prominence as Done."""
    _seed(aof_home)
    text = format_digest(build_digest(since_ts=time.time() - 7200), lang="vi")
    assert "BỊ CHẶN" in text
    assert "XONG có bằng chứng" in text
    assert "không tô hồng" in text


def test_digest_window_filters_old_entries(aof_home):
    _seed(aof_home)
    r = build_digest(since_ts=time.time() + 100)  # window in the future
    assert r["has_activity"] is False
    assert "T-1" not in r["tasks"]


def test_digest_task_filter(aof_home):
    _seed(aof_home)
    r = build_digest(since_ts=time.time() - 7200, task="T-2")
    assert "T-1" not in r["tasks"] and "T-2" in r["tasks"]


def test_digest_tolerates_garbage_lines(aof_home):
    _seed(aof_home)
    with open(audit_file(), "a", encoding="utf-8") as f:
        f.write("{broken json\n\nnot even json\n")
    r = build_digest(since_ts=time.time() - 7200)
    assert r["sessions"] == 2, "garbage lines must be skipped, not crash the ledger"


def test_watch_fresh_file(tmp_path):
    p = tmp_path / "out.log"
    p.write_text("working...")
    r = heartbeat.check(str(p), stale_after_s=300)
    assert r["status"] == "fresh"
    assert r["size_bytes"] > 0


def test_watch_stale_file_is_flagged_even_if_process_alive(tmp_path):
    """The 18-minute hang: session alive, output dead. mtime is the truth."""
    p = tmp_path / "out.log"
    p.write_text("stuck")
    old = time.time() - 1200
    os.utime(p, (old, old))
    r = heartbeat.check(str(p), stale_after_s=300)
    assert r["status"] == "stale"
    assert r["age_s"] >= 1100
    text = heartbeat.format_check(r, lang="vi")
    assert "NGHI TREO" in text


def test_watch_missing_file(tmp_path):
    r = heartbeat.check(str(tmp_path / "nope.log"))
    assert r["status"] == "missing"
    assert "CHƯA CÓ GÌ" in heartbeat.format_check(r, lang="vi")


def test_watch_never_raises_on_weird_paths():
    assert heartbeat.check("")["status"] == "missing"
    assert heartbeat.check("/dev/null/impossible/x")["status"] == "missing"
