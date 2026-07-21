"""F1-2 / F1-3: central handoff index + aof resume brief."""
from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

import pytest

from core.oplog import (
    append_handoff_index,
    format_resume_brief,
    load_handoff_index,
    select_handoff_row,
)

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture()
def aof_home(tmp_path, monkeypatch):
    home = tmp_path / "aofhome"
    home.mkdir()
    monkeypatch.setenv("AOF_AUDIT_DIR", str(home))
    return tmp_path


def test_append_handoff_index_is_append_only(aof_home, tmp_path):
    bundle_a = {
        "handoff_path": str(tmp_path / "a" / "HANDOFF.md"),
        "recap_path": str(tmp_path / "a" / "RECAP.html"),
        "stamp": "s1",
    }
    bundle_b = {
        "handoff_path": str(tmp_path / "b" / "HANDOFF.md"),
        "recap_path": str(tmp_path / "b" / "RECAP.html"),
        "stamp": "s2",
    }
    p1 = append_handoff_index("/repo/a/.git", "key-a", "feat/a", "T-A", bundle_a, {"done": 1})
    p2 = append_handoff_index("/repo/b/.git", "key-b", "feat/b", "T-B", bundle_b, {"done": 0})
    assert p1 == p2
    rows = load_handoff_index()
    assert len(rows) == 2
    assert rows[0]["repo_key"] == "key-a" and rows[0]["task"] == "T-A"
    assert rows[1]["repo_key"] == "key-b" and rows[1]["handoff_path"].endswith("HANDOFF.md")
    # schema keys required by ExecPlan
    for key in ("ts", "repo_identity", "repo_key", "branch", "task", "handoff_path", "recap_path"):
        assert key in rows[0]


def test_select_and_resume_filters_by_repo(aof_home, tmp_path):
    repo_a = tmp_path / "repo_a"
    repo_b = tmp_path / "repo_b"
    for r in (repo_a, repo_b):
        (r / "docs" / "sessions").mkdir(parents=True)
    # write real handoff bodies so resume can load them
    ha = repo_a / "docs" / "sessions" / "HANDOFF_A.md"
    hb = repo_b / "docs" / "sessions" / "HANDOFF_B.md"
    ha.write_text("# handoff A\nnext: fix A\n", encoding="utf-8")
    hb.write_text("# handoff B\nnext: fix B\n", encoding="utf-8")
    append_handoff_index(
        str(repo_a / ".git"), "key-a", "feat/a", "T-A",
        {"handoff_path": str(ha), "recap_path": str(ha).replace(".md", ".html"), "stamp": "1"},
    )
    time.sleep(0.01)
    append_handoff_index(
        str(repo_b / ".git"), "key-b", "feat/b", "T-B",
        {"handoff_path": str(hb), "recap_path": str(hb).replace(".md", ".html"), "stamp": "2"},
    )
    row_b = select_handoff_row(load_handoff_index(), repo=str(repo_b))
    assert row_b is not None
    assert row_b["task"] == "T-B"
    brief = format_resume_brief(repo=str(repo_b), lang="en")
    assert "RESUME BRIEF" in brief
    assert "fix B" in brief
    assert "fix A" not in brief
    brief_task = format_resume_brief(task="T-A", lang="vi")
    assert "fix A" in brief_task


def test_cli_resume_and_handoff_index(aof_home, tmp_path, monkeypatch):
    """CLI handoff appends index; resume prints brief for that repo."""
    from core.enforcement import audit_file, decision_file

    now = time.time()
    with open(audit_file(), "w", encoding="utf-8") as f:
        f.write(json.dumps({"event": "session_start", "_session": "s", "_ts": now - 10}) + "\n")
    with open(decision_file(), "w", encoding="utf-8") as f:
        f.write(json.dumps({
            "session": "s", "decision": "post_evidence", "resolution": "Done",
            "task": "T-1", "ts": now - 5,
        }) + "\n")

    repo = tmp_path / "work"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "feat/cli"], cwd=repo, check=True)
    env = {
        "AOF_AUDIT_DIR": str(aof_home / "aofhome"),
        "PATH": "/usr/bin:/bin",
        "PYTHONPATH": str(REPO),
    }
    r = subprocess.run(
        [sys.executable, "-m", "core.cli", "handoff", "--since-hours", "2"],
        capture_output=True, text=True, cwd=repo, env=env, timeout=60,
    )
    assert r.returncode == 0, r.stderr
    handoff_path = Path(r.stdout.strip())
    assert handoff_path.is_file()
    assert "docs/sessions" in str(handoff_path)
    # index under AOF_AUDIT_DIR
    idx = Path(env["AOF_AUDIT_DIR"]) / "handoffs" / "index.jsonl"
    assert idx.is_file()
    rows = [
        json.loads(line)
        for line in idx.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(rows) == 1

    r2 = subprocess.run(
        [sys.executable, "-m", "core.cli", "resume", "--repo", str(repo), "--lang", "en"],
        capture_output=True, text=True, cwd=repo, env=env, timeout=60,
    )
    assert r2.returncode == 0, r2.stderr
    assert "RESUME BRIEF" in r2.stdout
    assert handoff_path.name in r2.stdout or handoff_path.read_text(encoding="utf-8")[:20] in r2.stdout
