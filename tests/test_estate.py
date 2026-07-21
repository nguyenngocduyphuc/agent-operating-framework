"""Estate effectiveness report from AOF ledgers."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.enforcement import audit_file, decision_file
from core.errors_ledger import record_error
from core.estate import build_estate_report, format_estate_report, write_estate_snapshot
from core.oplog import append_handoff_index

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture()
def aof_home(tmp_path, monkeypatch):
    home = tmp_path / "aofhome"
    home.mkdir()
    monkeypatch.setenv("AOF_AUDIT_DIR", str(home))
    return home


def _seed(aof_home, now=None):
    now = now or time.time()
    audit = [
        {"event": "session_start", "_session": "s1", "_ts": now - 100},
        {
            "event": "preflight", "status": "clear", "workspace": "/ws/A",
            "repo": "repoA", "branch": "feat/x", "task": "T-1", "_session": "s1", "_ts": now - 90,
        },
        {
            "event": "preflight", "status": "blocked", "workspace": "/ws/B",
            "repo": "repoB", "_session": "s2", "_ts": now - 80,
        },
        {"event": "lease_conflict", "task": "T-1", "_session": "s3", "_ts": now - 70},
        {
            "event": "session_handoff",
            "path": "/ws/A/repoA/docs/sessions/HANDOFF.md",
            "_session": "s1", "_ts": now - 60,
        },
        {"event": "aof_resume", "task": "T-1", "_session": "s4", "_ts": now - 50},
        {"event": "session_start", "_session": "s2", "_ts": now - 40},
    ]
    decisions = [
        {"session": "s1", "decision": "verify_gate", "passed": True, "task": "T-1", "ts": now - 85},
        {"session": "s1", "decision": "verify_gate", "passed": False, "task": "T-1", "ts": now - 84},
        {"session": "s1", "decision": "verify_gate", "passed": False, "task": "T-1", "ts": now - 83},
        {"session": "s1", "decision": "post_evidence", "resolution": "Done", "task": "T-1", "ts": now - 55},
        {"session": "s2", "decision": "post_evidence", "resolution": "Blocked", "task": "T-2", "ts": now - 45},
    ]
    audit_file().write_text("\n".join(json.dumps(e) for e in audit) + "\n", encoding="utf-8")
    decision_file().write_text("\n".join(json.dumps(e) for e in decisions) + "\n", encoding="utf-8")
    record_error({"fingerprint": "shadow-import:core", "title": "shadow"})
    record_error({"fingerprint": "shadow-import:core", "title": "shadow2"})
    append_handoff_index(
        "/ws/A/repoA/.git", "key-a", "feat/x", "T-1",
        {
            "handoff_path": "/ws/A/repoA/docs/sessions/HANDOFF.md",
            "recap_path": "/ws/A/repoA/docs/sessions/RECAP.html",
            "stamp": "1",
        },
        {"done": 1},
    )


def test_build_estate_kpis(aof_home):
    _seed(aof_home)
    r = build_estate_report(window_hours=24)
    k = r["kpis"]
    assert k["sessions"] >= 2
    assert k["lease_collisions"] == 1
    assert k["resumes"] == 1
    assert k["verify_fail"] == 2
    assert k["verify_pass"] == 1
    assert k["verify_fail_rate"] is not None
    assert k["done"] == 1 and k["blocked"] == 1
    assert k["open_errors"] >= 1
    assert k["repeated_fingerprints"] >= 1
    assert k["preflight_clear"] == 1
    assert k["preflight_blocked"] == 1
    assert "/ws/A" in r["workspaces"] or "repoA" in str(r)
    assert r["per_repo"]
    text = format_estate_report(r, "en")
    assert "ESTATE REPORT" in text
    assert "verify" in text.lower() or "fail_rate" in text


def test_snapshot_and_cli(aof_home, tmp_path):
    _seed(aof_home)
    path = write_estate_snapshot(window_hours=24)
    assert Path(path).is_file()
    latest = Path(aof_home) / "estate" / "latest.json"
    assert latest.is_file()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert "kpis" in data

    env = {
        **dict(**{k: v for k, v in __import__("os").environ.items()}),
        "AOF_AUDIT_DIR": str(aof_home),
        "PYTHONPATH": str(REPO),
        "PATH": "/usr/bin:/bin",
    }
    out = tmp_path / "estate.md"
    r = subprocess.run(
        [
            sys.executable, "-m", "core.cli", "estate-report",
            "--days", "1", "--lang", "en", "--snapshot", "--out", str(out),
        ],
        capture_output=True, text=True, env=env, timeout=30,
    )
    assert r.returncode == 0, r.stderr
    assert out.is_file()
    body = out.read_text(encoding="utf-8")
    assert "ESTATE" in body
