"""Task lease: one task, one live writer.

The incident these tests encode (2026-07-20): two agent sessions committed to
the same branch within minutes, three times in one day — nothing blocked the
second writer. And the first C6 spec keyed identity by checkout path, which
would have given every linked worktree its own lease namespace, defeating the
lock exactly where it is needed most.
"""
import json
import os
import subprocess

import pytest

from core import lease

DEAD_PID = 2 ** 22 + 12345  # far above any real pid on test machines


@pytest.fixture()
def audit_env(tmp_path, monkeypatch):
    monkeypatch.setenv("AOF_AUDIT_DIR", str(tmp_path / "aofhome"))
    return tmp_path


def _git_repo(path):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q"], cwd=path, check=True)
    (path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "."], cwd=path, check=True)
    subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", "commit", "-qm", "init"],
        cwd=path, check=True,
    )
    return path


def test_acquire_release_roundtrip(audit_env, tmp_path):
    repo = _git_repo(tmp_path / "repo")
    r = lease.acquire("T-1", str(repo), "sess-a")
    assert r["ok"] and r["status"] == "acquired"
    assert lease.peek("T-1", str(repo))["held"] is True
    rel = lease.release("T-1", str(repo), "sess-a")
    assert rel["ok"] and rel["status"] == "released"
    assert lease.peek("T-1", str(repo))["held"] is False


def test_second_live_session_is_refused(audit_env, tmp_path):
    """The whole point: a live holder makes a second writer FAIL, loudly."""
    repo = _git_repo(tmp_path / "repo")
    assert lease.acquire("T-1", str(repo), "sess-a")["ok"]
    r = lease.acquire("T-1", str(repo), "sess-b")
    assert r["ok"] is False
    assert r["status"] == "conflict"
    assert r["holder"]["session_id"] == "sess-a"
    assert "LIVE" in r["detail"]


def test_same_session_reacquire_renews(audit_env, tmp_path):
    repo = _git_repo(tmp_path / "repo")
    assert lease.acquire("T-1", str(repo), "sess-a")["status"] == "acquired"
    r = lease.acquire("T-1", str(repo), "sess-a")
    assert r["ok"] and r["status"] == "renewed"


def test_stale_lease_dead_pid_is_taken_over(audit_env, tmp_path):
    repo = _git_repo(tmp_path / "repo")
    path = lease.lease_path(str(repo), "T-1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "task": "T-1", "session_id": "sess-dead", "pid": DEAD_PID,
        "acquired_at": 0, "heartbeat_at": 0,
    }), encoding="utf-8")
    r = lease.acquire("T-1", str(repo), "sess-b")
    assert r["ok"] and r["status"] == "takeover"
    assert "stale" in r["lease"]["note"]


def test_release_refuses_foreign_lease(audit_env, tmp_path):
    repo = _git_repo(tmp_path / "repo")
    assert lease.acquire("T-1", str(repo), "sess-a")["ok"]
    r = lease.release("T-1", str(repo), "sess-b")
    assert r["ok"] is False and r["status"] == "not_owner"
    # still held by the rightful owner
    assert lease.peek("T-1", str(repo))["holder"]["session_id"] == "sess-a"


def test_worktrees_share_one_lease_namespace(audit_env, tmp_path):
    """Linked worktrees of one repo MUST collide on the same task.

    Keying by checkout path (the rejected C6 spec) would pass a naive test and
    fail in production: each worktree would get its own lease namespace.
    """
    repo = _git_repo(tmp_path / "repo")
    wt = tmp_path / "wt"
    subprocess.run(
        ["git", "worktree", "add", "-q", str(wt), "-b", "wt-branch"],
        cwd=repo, check=True,
    )
    id_main = lease.repo_identity(str(repo))
    id_wt = lease.repo_identity(str(wt))
    assert id_main == id_wt, "worktree must resolve to the SAME repo identity"

    assert lease.acquire("T-1", str(repo), "sess-a")["ok"]
    r = lease.acquire("T-1", str(wt), "sess-b")
    assert r["ok"] is False and r["status"] == "conflict", (
        "a second session in a linked worktree must be refused — "
        "path-based identity would wrongly allow it"
    )


def test_different_tasks_do_not_collide(audit_env, tmp_path):
    repo = _git_repo(tmp_path / "repo")
    assert lease.acquire("T-1", str(repo), "sess-a")["ok"]
    assert lease.acquire("T-2", str(repo), "sess-b")["ok"]


def test_no_task_means_no_lease(audit_env, tmp_path):
    repo = _git_repo(tmp_path / "repo")
    assert lease.acquire("", str(repo), "sess-a")["status"] == "no_task"
    assert lease.release(None, str(repo), "sess-a")["status"] == "no_task"


def test_corrupt_lease_file_is_replaced_not_crashed(audit_env, tmp_path):
    repo = _git_repo(tmp_path / "repo")
    path = lease.lease_path(str(repo), "T-1")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{not json", encoding="utf-8")
    r = lease.acquire("T-1", str(repo), "sess-a")
    assert r["ok"] and r["status"] == "takeover"


def test_non_git_dir_still_namespaces_consistently(audit_env, tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    assert lease.acquire("T-1", str(plain), "sess-a")["ok"]
    r = lease.acquire("T-1", str(plain), "sess-b")
    assert r["ok"] is False and r["status"] == "conflict"


def test_task_name_is_sanitized_for_filenames(audit_env, tmp_path):
    repo = _git_repo(tmp_path / "repo")
    evil = "../../etc/passwd; rm -rf /"
    r = lease.acquire(evil, str(repo), "sess-a")
    assert r["ok"]
    p = lease.lease_path(str(repo), evil)
    assert p.parent == lease.lease_dir(), "sanitized name must stay inside the lease dir"
    assert os.sep not in p.name and ";" not in p.name
