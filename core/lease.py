"""Task lease — one task, one live writer session. Stdlib only.

Why this exists (incident 2026-07-20): three times in one day, two agent
sessions committed to the same branch while one of them was writing a handoff.
Nothing blocked the second writer. The fix is an exclusive, crash-safe lease
bound to (repository identity, task id).

Repository identity is ``git rev-parse --git-common-dir`` — NOT the checkout
path. Linked worktrees of one repository share the common git dir, so every
worktree of a repo maps to the SAME lease namespace. Keying by checkout path
would give each worktree its own namespace and two sessions could hold "the
same task" in two worktrees without ever colliding (the exact C5/C6 spec bug
caught in review on 2026-07-20).

Lease files live under the audit dir (``~/.aof/leases``), never inside the
repository — a lease must survive branch switches and never dirty the tree.

Liveness is by PID: a lease whose holder process is dead is stale and may be
taken over. A lease whose holder is alive is a hard conflict — the caller is
told who holds it and refused. Same-session re-acquire renews (idempotent).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import time
from pathlib import Path
from typing import Any

from core.enforcement import audit_dir


def lease_dir() -> Path:
    return audit_dir() / "leases"


def repo_identity(cwd: str) -> tuple[str, str]:
    """Return (identity_path, identity_hash) for the repository owning ``cwd``.

    identity_path is the realpath of the git common dir (shared by all linked
    worktrees). Outside any git repo it falls back to realpath(cwd) so the
    lease still namespaces consistently. identity_hash is a short stable key
    safe for filenames.
    """
    identity = None
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            cwd=cwd, capture_output=True, text=True, timeout=10, shell=False,
        )
        if r.returncode == 0 and r.stdout.strip():
            common = r.stdout.strip()
            if not os.path.isabs(common):
                common = os.path.join(cwd, common)
            identity = os.path.realpath(common)
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        identity = None
    if not identity:
        identity = os.path.realpath(cwd)
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:16]
    return identity, digest


def _sanitize(task: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]", "_", task)[:80]


def lease_path(cwd: str, task: str) -> Path:
    _, digest = repo_identity(cwd)
    return lease_dir() / f"{digest}--{_sanitize(task)}.json"


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists, owned by someone else
    except (OverflowError, TypeError, ValueError):
        return False
    return True


def _read(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def _record(task: str, cwd: str, session_id: str, note: str | None = None) -> dict[str, Any]:
    identity, digest = repo_identity(cwd)
    rec = {
        "task": task,
        "repo_identity": identity,
        "repo_key": digest,
        "session_id": session_id,
        "pid": os.getpid(),
        "acquired_at": time.time(),
        "heartbeat_at": time.time(),
    }
    if note:
        rec["note"] = note
    return rec


def _write_atomic(path: Path, rec: dict[str, Any]) -> None:
    tmp = path.with_suffix(f".tmp.{os.getpid()}")
    tmp.write_text(json.dumps(rec, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def acquire(task: str, cwd: str, session_id: str) -> dict[str, Any]:
    """Try to take the lease for (repo, task). Fail closed on live conflict.

    Returns {"ok": bool, "status": acquired|renewed|takeover|conflict|error, ...}.
    """
    if not task or not str(task).strip():
        return {"ok": True, "status": "no_task", "detail": "no task bound; lease not required"}
    task = str(task).strip()
    path = lease_path(cwd, task)
    try:
        lease_dir().mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        # Cannot guarantee exclusivity if the lease store is unwritable.
        return {"ok": False, "status": "error", "error": f"lease dir unavailable: {exc}"}

    rec = _record(task, cwd, session_id)
    # Fast path: atomic exclusive create.
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False))
        return {"ok": True, "status": "acquired", "lease": rec, "path": str(path)}
    except FileExistsError:
        pass
    except OSError as exc:
        return {"ok": False, "status": "error", "error": str(exc)}

    holder = _read(path)
    if holder is None:
        # Unreadable/corrupt lease: replace, but say so.
        rec["note"] = "replaced unreadable lease file"
        try:
            _write_atomic(path, rec)
        except OSError as exc:
            return {"ok": False, "status": "error", "error": str(exc)}
        return {"ok": True, "status": "takeover", "lease": rec, "path": str(path)}

    if holder.get("session_id") == session_id:
        rec["acquired_at"] = holder.get("acquired_at", rec["acquired_at"])
        try:
            _write_atomic(path, rec)
        except OSError as exc:
            return {"ok": False, "status": "error", "error": str(exc)}
        return {"ok": True, "status": "renewed", "lease": rec, "path": str(path)}

    if _pid_alive(holder.get("pid", -1)):
        return {
            "ok": False,
            "status": "conflict",
            "holder": {k: holder.get(k) for k in ("session_id", "pid", "acquired_at", "task")},
            "path": str(path),
            "detail": (
                f"Task '{task}' is held by a LIVE session "
                f"(pid {holder.get('pid')}, session {str(holder.get('session_id'))[:8]}…). "
                "A second writer on the same task is exactly how commits get trampled. "
                "Wait, pick another task, or stop the other session first."
            ),
        }

    # Holder process is dead: stale lease, take over with provenance.
    rec["note"] = (
        f"takeover of stale lease (dead pid {holder.get('pid')}, "
        f"session {str(holder.get('session_id'))[:8]}…)"
    )
    try:
        _write_atomic(path, rec)
    except OSError as exc:
        return {"ok": False, "status": "error", "error": str(exc)}
    # Two sessions can both observe the dead holder and both replace; os.replace
    # is atomic but last-writer-wins. Read back: if another session won the race,
    # yield instead of both believing they own the task.
    final = _read(path)
    if not final or final.get("session_id") != session_id:
        return {
            "ok": False,
            "status": "conflict",
            "holder": {k: (final or {}).get(k) for k in ("session_id", "pid", "acquired_at", "task")},
            "path": str(path),
            "detail": f"Task '{task}' takeover lost a race to another session; yielding.",
        }
    return {"ok": True, "status": "takeover", "lease": rec, "path": str(path)}


def release(task: str, cwd: str, session_id: str) -> dict[str, Any]:
    """Release only a lease this session holds. Never delete someone else's."""
    if not task or not str(task).strip():
        return {"ok": True, "status": "no_task"}
    path = lease_path(cwd, str(task).strip())
    holder = _read(path)
    if holder is None:
        return {"ok": True, "status": "not_held"}
    if holder.get("session_id") != session_id:
        return {"ok": False, "status": "not_owner",
                "detail": "lease is held by another session; refusing to release it"}
    try:
        path.unlink(missing_ok=True)
    except OSError as exc:
        return {"ok": False, "status": "error", "error": str(exc)}
    return {"ok": True, "status": "released"}


def peek(task: str, cwd: str) -> dict[str, Any]:
    """Read-only view of the current lease state for (repo, task)."""
    if not task or not str(task).strip():
        return {"held": False, "status": "no_task"}
    path = lease_path(cwd, str(task).strip())
    holder = _read(path)
    if holder is None:
        return {"held": False, "status": "free"}
    alive = _pid_alive(holder.get("pid", -1))
    return {"held": alive, "status": "held" if alive else "stale", "holder": holder}
