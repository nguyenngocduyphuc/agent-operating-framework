"""Regression tests for portable preflight execution."""

import os
import subprocess
import sys
from pathlib import Path

from core import preflight


REPO = Path(__file__).resolve().parents[1]


def test_nearest_repo_accepts_linked_worktree_git_file(tmp_path):
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: /tmp/main/.git/worktrees/task\n")

    assert preflight.nearest_repo(worktree) == str(worktree)


def test_human_preflight_does_not_crash(tmp_path):
    env = {
        **os.environ,
        "AOF_WORKSPACE": str(tmp_path),
        "PYTHONPATH": str(REPO),
    }
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)

    result = subprocess.run(
        [sys.executable, "-m", "core.preflight", "--bootstrap"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0
    assert "PREFLIGHT" in result.stdout
    assert "Traceback" not in result.stderr
