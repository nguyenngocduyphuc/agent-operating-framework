"""aof recap (HTML) + aof handoff (md) — per-session docs that update themselves.

Honesty rules carry over from the ledger: a Blocked closure renders as loudly
as a Done, and the recap must be a single self-contained file (no JS, no
external assets) so it still opens years later from a folder.
"""
import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.enforcement import audit_file, decision_file
from core.oplog import build_digest, format_handoff, render_html

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture()
def aof_home(tmp_path, monkeypatch):
    monkeypatch.setenv("AOF_AUDIT_DIR", str(tmp_path / "aofhome"))
    (tmp_path / "aofhome").mkdir()
    return tmp_path


def _seed(now=None):
    now = now or time.time()
    audit = [
        {"event": "session_start", "_session": "s1", "_ts": now - 3600},
        {"event": "lease_conflict", "task": "T-2", "_session": "s2", "_ts": now - 3000},
    ]
    decisions = [
        {"session": "s1", "decision": "check_contract", "ok": True, "task": "T-1", "ts": now - 3500},
        {"session": "s1", "decision": "verify_gate", "passed": True, "task": "T-1", "ts": now - 3300},
        {"session": "s1", "decision": "post_evidence", "resolution": "Done", "task": "T-1", "ts": now - 3200},
        {"session": "s2", "decision": "check_contract", "ok": True, "task": "T-2", "ts": now - 2900},
        {"session": "s2", "decision": "post_evidence", "resolution": "Blocked", "task": "T-2", "ts": now - 2800},
        {"session": "s2", "decision": "check_contract", "ok": True, "task": "T-3", "ts": now - 2000},
    ]
    with open(audit_file(), "w", encoding="utf-8") as f:
        f.writelines(json.dumps(e) + "\n" for e in audit)
    with open(decision_file(), "w", encoding="utf-8") as f:
        f.writelines(json.dumps(e) + "\n" for e in decisions)


def test_recap_html_is_self_contained_and_honest(aof_home):
    _seed()
    html = render_html(build_digest(since_ts=time.time() - 7200), lang="vi")
    assert html.startswith("<!DOCTYPE html>")
    for forbidden in ("<script", "http://", "https://"):
        assert forbidden not in html, f"recap must be self-contained (found {forbidden})"
    assert "Xong có bằng chứng" in html
    assert "⛔" in html, "a Blocked closure must be visible, not hidden"
    assert "không tô hồng" in html.lower() or "Không tô hồng" in html


def test_recap_html_escapes_task_names(aof_home):
    _seed()
    with open(decision_file(), "a", encoding="utf-8") as f:
        f.write(json.dumps({"session": "s3", "decision": "check_contract", "ok": True,
                            "task": "<img src=x onerror=alert(1)>", "ts": time.time() - 100}) + "\n")
    html = render_html(build_digest(since_ts=time.time() - 7200))
    assert "<img" not in html, "task names must be HTML-escaped"
    assert "&lt;img" in html


def test_handoff_separates_done_blocked_open(aof_home):
    _seed()
    md = format_handoff(build_digest(since_ts=time.time() - 7200), lang="vi")
    done_at = md.index("Đã xong")
    blocked_at = md.index("bị chặn")
    open_at = md.index("Đang mở")
    assert md.index("T-1") > done_at and md.index("T-1") < blocked_at
    assert done_at < md.index("T-2")
    assert md.index("T-3") > open_at, "T-3 has no evidence -> must be listed as open"
    assert "aof doctor" in md, "handoff must tell the next session what to run first"


def test_cli_recap_and_handoff_write_into_docs_sessions(aof_home, tmp_path):
    _seed()
    ws = tmp_path / "ws"
    ws.mkdir()
    env = {"AOF_AUDIT_DIR": str(aof_home / "aofhome"), "PATH": "/usr/bin:/bin",
           "PYTHONPATH": str(REPO)}
    for cmd, suffix in (("recap", ".html"), ("handoff", ".md")):
        r = subprocess.run(
            [sys.executable, "-m", "core.cli", cmd, "--since-hours", "2"],
            capture_output=True, text=True, cwd=ws, env=env, timeout=60,
        )
        assert r.returncode == 0, r.stderr
        out = Path(r.stdout.strip())
        assert out.exists() and out.suffix == suffix
        assert out.parent == ws / "docs" / "sessions", "docs must update under the workspace"


def test_init_policy_enables_karpathy_by_default(tmp_path):
    from core.doctor import run_init
    run_init(str(tmp_path))
    policy = json.loads((tmp_path / ".aof_policy.json").read_text(encoding="utf-8"))
    assert policy["require_karpathy"] is True, (
        "thinking-before-doing must be ON by default — the agent pays, not the operator"
    )
