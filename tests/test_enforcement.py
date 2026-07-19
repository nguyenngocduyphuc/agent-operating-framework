"""Tests for the additive enforcement helpers: audit location, decisions, stall detection."""
import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import enforcement  # noqa: E402


@pytest.fixture
def audit_home(tmp_path, monkeypatch):
    """Redirect the audit directory into a temp dir for every test."""
    monkeypatch.setenv("AOF_AUDIT_DIR", str(tmp_path))
    return tmp_path


def _write_entries(path, entries):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for e in entries:
            fh.write(json.dumps(e) + "\n")


# --- audit location -------------------------------------------------------

def test_audit_dir_defaults_to_dot_aof(monkeypatch):
    monkeypatch.delenv("AOF_AUDIT_DIR", raising=False)
    assert enforcement.audit_dir() == Path.home() / ".aof"


def test_audit_dir_honours_env_override(audit_home):
    assert enforcement.audit_dir() == audit_home
    assert enforcement.audit_file() == audit_home / "audit.jsonl"
    assert enforcement.decision_file() == audit_home / "decisions.jsonl"


def test_default_audit_dir_carries_no_internal_tool_name(monkeypatch):
    """The public default must not resurrect the internal tool name."""
    monkeypatch.delenv("AOF_AUDIT_DIR", raising=False)
    assert "npflight" not in str(enforcement.audit_dir())


# --- decision records -----------------------------------------------------

def test_write_decision_appends_and_timestamps(audit_home):
    enforcement.write_decision({"decision": "check_contract", "ok": True})
    enforcement.write_decision({"decision": "post_evidence", "resolution": "Done"})
    lines = enforcement.decision_file().read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2
    first = json.loads(lines[0])
    assert first["decision"] == "check_contract"
    assert isinstance(first["ts"], float)


def test_write_decision_survives_unwritable_dir(audit_home, monkeypatch, capsys):
    """Losing the trail must never kill the server."""
    monkeypatch.setenv("AOF_AUDIT_DIR", str(audit_home / "nested"))
    audit_home.joinpath("nested").mkdir()
    os.chmod(audit_home / "nested", 0o500)
    try:
        enforcement.write_decision({"decision": "x"})  # must not raise
        assert "write failed" in capsys.readouterr().err
    finally:
        os.chmod(audit_home / "nested", 0o700)


# --- stall detection ------------------------------------------------------

def test_stall_check_silent_below_threshold(audit_home):
    _write_entries(enforcement.audit_file(),
                   [{"_session": "s1", "event": "verify_gate", "passed": False}] * 4)
    assert enforcement.stall_check("s1", "verify_gate") == {}


def test_stall_check_fires_at_threshold(audit_home):
    _write_entries(enforcement.audit_file(),
                   [{"_session": "s1", "event": "verify_gate", "passed": False}] * 5)
    r = enforcement.stall_check("s1", "verify_gate")
    assert r["stall_warning"] is True
    assert r["stall_count"] == 5
    assert "Stop retrying" in r["stall_hint"]


def test_stall_check_ignores_other_sessions_and_operations(audit_home):
    _write_entries(enforcement.audit_file(), [
        *[{"_session": "other", "event": "verify_gate", "passed": False}] * 5,
        *[{"_session": "s1", "event": "audit_scope", "passed": False}] * 5,
    ])
    assert enforcement.stall_check("s1", "verify_gate") == {}


def test_stall_check_ignores_successes(audit_home):
    _write_entries(enforcement.audit_file(),
                   [{"_session": "s1", "event": "verify_gate", "passed": True}] * 8)
    assert enforcement.stall_check("s1", "verify_gate") == {}


def test_stall_check_tolerates_corrupt_lines(audit_home):
    path = enforcement.audit_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        fh.write("not json\n")
        fh.write("[1,2,3]\n")  # valid json, wrong shape
        for _ in range(5):
            fh.write(json.dumps({"_session": "s1", "event": "verify_gate", "ok": False}) + "\n")
    assert enforcement.stall_check("s1", "verify_gate")["stall_count"] == 5


def test_stall_check_missing_file_is_silent(audit_home):
    assert enforcement.stall_check("s1", "verify_gate") == {}


def test_with_stall_warning_merges_into_result(audit_home):
    _write_entries(enforcement.audit_file(),
                   [{"_session": "s1", "event": "verify_gate", "passed": False}] * 5)
    out = enforcement.with_stall_warning({"passed": False}, "s1", "verify_gate")
    assert out["passed"] is False
    assert out["stall_warning"] is True
