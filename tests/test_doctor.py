"""aof doctor / aof init — the zero-knowledge onboarding path must be provable.

A doctor that guesses (import-checks instead of probing) is the false-success
dispatcher all over again. These tests force every probe to be real: the MCP
check spawns an actual server; the failure cases actually fail.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from core.doctor import format_doctor, format_init, run_doctor, run_init

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture()
def ws(tmp_path, monkeypatch):
    monkeypatch.setenv("AOF_WORKSPACE", str(tmp_path))
    monkeypatch.setenv("AOF_AUDIT_DIR", str(tmp_path / "aofhome"))
    monkeypatch.setenv("PYTHONPATH", str(REPO))
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def test_init_creates_policy_and_marker_idempotently(ws):
    r1 = run_init(str(ws))
    assert r1["policy_created"] is True
    assert (ws / ".aof_policy.json").exists()
    assert (ws / ".agentframework").exists()
    r2 = run_init(str(ws))
    assert r2["policy_created"] is False, "second init must keep the existing policy"
    policy = json.loads((ws / ".aof_policy.json").read_text(encoding="utf-8"))
    assert policy["require_contract"] is True


def test_doctor_ready_on_initialized_workspace(ws):
    run_init(str(ws))
    report = run_doctor(str(ws))
    assert report["failed"] == [], f"unexpected failures: {report['failed']}"
    assert report["ok"] is True
    assert report["checks"]["mcp"]["ok"] is True, "MCP probe must be a REAL handshake"


def test_doctor_fails_on_corrupt_policy(ws):
    (ws / ".aof_policy.json").write_text("{broken", encoding="utf-8")
    report = run_doctor(str(ws))
    assert report["ok"] is False
    assert "policy" in report["failed"]


def test_doctor_reports_legacy_policy_migration(ws):
    (ws / ".aof_policy.json").write_text(
        json.dumps({"require_asana_task": True, "allow_bootstrap_without_task": True}),
        encoding="utf-8",
    )
    report = run_doctor(str(ws))
    assert report["checks"]["policy"]["migrated"] == ["require_asana_task -> require_task"]
    text = format_doctor(report)
    assert "require_asana_task" in text, "migration must be visible to the operator"


def test_doctor_text_is_plain_language_with_next_step(ws):
    run_init(str(ws))
    vi = format_doctor(run_doctor(str(ws), lang="vi"))
    assert "Bước tiếp theo" in vi
    en = format_doctor(run_doctor(str(ws), lang="en"))
    assert "Next step" in en
    assert not vi.lstrip().startswith("{"), "default output is for humans, not JSON"


def test_init_output_mentions_registration(ws):
    out = format_init(run_init(str(ws), lang="en"))
    assert "claude mcp add aof" in out


def test_cli_doctor_exit_codes(ws):
    run_init(str(ws))
    env = {**os.environ}
    ok = subprocess.run(
        [sys.executable, "-m", "core.cli", "doctor", str(ws)],
        capture_output=True, text=True, env=env, cwd=REPO, timeout=60,
    )
    assert ok.returncode == 0, ok.stdout + ok.stderr
    (ws / ".aof_policy.json").write_text("{broken", encoding="utf-8")
    bad = subprocess.run(
        [sys.executable, "-m", "core.cli", "doctor", str(ws)],
        capture_output=True, text=True, env=env, cwd=REPO, timeout=60,
    )
    assert bad.returncode == 2, "doctor must exit 2 when a check fails"


def test_cli_doctor_json_mode(ws):
    run_init(str(ws))
    r = subprocess.run(
        [sys.executable, "-m", "core.cli", "doctor", str(ws), "--json"],
        capture_output=True, text=True, env={**os.environ}, cwd=REPO, timeout=60,
    )
    report = json.loads(r.stdout)
    assert report["ok"] is True and "checks" in report
