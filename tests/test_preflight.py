"""Regression tests for portable preflight execution."""

import json
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


def test_normalize_github_owner_repo_ssh_and_https():
    assert (
        preflight.normalize_github_owner_repo(
            "git@github.com:nguyenngocduyphuc/agent-operating-framework.git"
        )
        == "nguyenngocduyphuc/agent-operating-framework"
    )
    assert (
        preflight.normalize_github_owner_repo(
            "https://github.com/nguyenngocduyphuc/agent-operating-framework.git"
        )
        == "nguyenngocduyphuc/agent-operating-framework"
    )
    assert preflight.normalize_github_owner_repo("not-a-github-url") is None


def _write_policy(ws, expected_repository=None):
    policy = {
        "require_task": False,
        "require_contract": True,
        "require_evidence": True,
        "require_handoff": True,
        "allow_bootstrap_without_task": True,
    }
    if expected_repository is not None:
        policy["expected_repository"] = expected_repository
    (ws / ".aof_policy.json").write_text(json.dumps(policy), encoding="utf-8")


def _run_preflight(tmp_path, origin_url=None, set_origin=True):
    env = {
        **os.environ,
        "AOF_WORKSPACE": str(tmp_path),
        "PYTHONPATH": str(REPO),
    }
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    if set_origin and origin_url is not None:
        subprocess.run(
            ["git", "remote", "add", "origin", origin_url],
            cwd=tmp_path,
            check=True,
        )
    return subprocess.run(
        [sys.executable, "-m", "core.preflight", "--bootstrap", "--json"],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
    )


def test_expected_repository_matches_ssh_origin(tmp_path):
    expected = "nguyenngocduyphuc/agent-operating-framework"
    _write_policy(tmp_path, expected)
    result = _run_preflight(
        tmp_path,
        f"git@github.com:{expected}.git",
    )
    assert result.returncode == 0
    card = json.loads(result.stdout)
    assert card["status"] != "blocked"
    assert not any("expected_repository" in b for b in card["blockers"])


def test_expected_repository_matches_https_origin(tmp_path):
    expected = "nguyenngocduyphuc/agent-operating-framework"
    _write_policy(tmp_path, expected)
    result = _run_preflight(
        tmp_path,
        f"https://github.com/{expected}.git",
    )
    assert result.returncode == 0
    card = json.loads(result.stdout)
    assert not any("expected_repository" in b for b in card["blockers"])


def test_expected_repository_mismatch_blocks(tmp_path):
    _write_policy(tmp_path, "nguyenngocduyphuc/agent-operating-framework")
    result = _run_preflight(tmp_path, "git@github.com:other/fork.git")
    assert result.returncode == 2
    card = json.loads(result.stdout)
    assert card["status"] == "blocked"
    assert any("does not match expected_repository" in b for b in card["blockers"])


def test_expected_repository_missing_origin_blocks(tmp_path):
    _write_policy(tmp_path, "nguyenngocduyphuc/agent-operating-framework")
    result = _run_preflight(tmp_path, set_origin=False)
    assert result.returncode == 2
    card = json.loads(result.stdout)
    assert any("origin remote is missing" in b for b in card["blockers"])


def test_expected_repository_unparseable_origin_blocks(tmp_path):
    _write_policy(tmp_path, "nguyenngocduyphuc/agent-operating-framework")
    result = _run_preflight(tmp_path, "ssh://git@gitlab.com/org/repo.git")
    assert result.returncode == 2
    card = json.loads(result.stdout)
    assert any("unparseable" in b for b in card["blockers"])


def test_expected_repository_absent_is_opt_out(tmp_path):
    """No expected_repository key => identity check skipped (compat)."""
    _write_policy(tmp_path, expected_repository=None)
    result = _run_preflight(tmp_path, "git@github.com:any/repo.git")
    assert result.returncode == 0
    card = json.loads(result.stdout)
    assert not any("expected_repository" in b for b in card["blockers"])


def test_expected_repository_empty_string_is_opt_out(tmp_path):
    _write_policy(tmp_path, expected_repository="")
    result = _run_preflight(tmp_path, "git@github.com:any/repo.git")
    assert result.returncode == 0
