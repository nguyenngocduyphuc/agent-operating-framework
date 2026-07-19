"""Audit trail, decision records, and stall detection.

Stdlib only.

Scope note: the hard preconditions (preflight -> contract -> verify_gate ->
audit_scope -> post_evidence) live in the mcp_server handler chain and are
ALWAYS ON, enforced at the JSON-RPC error layer. This module is strictly
additive -- it records what happened and warns about retry loops. Nothing here
can relax a precondition.

BREAKING CHANGE (0.2.0b2): the default audit directory moved to ``~/.aof``. Point
``AOF_AUDIT_DIR`` at the previous location to keep writing there. Existing logs are
NOT migrated automatically. See CHANGELOG.md for the exact prior path.
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

# Entry statuses counted as a failed attempt by stall detection.
FAILURE_STATUSES = frozenset({"fail", "failed", "blocked", "timeout", "policy_block", "error"})

# Repeated identical failures before the caller is told to stop looping.
STALL_THRESHOLD = 5

# ponytail: fixed tail window rather than an index. The audit log is append-only
# and a session's recent failures are always near the end, so a bounded tail read
# keeps cost flat on a file that grows across every session.
STALL_SCAN_LINES = 300


def audit_dir() -> Path:
    """Resolve the audit directory: ``AOF_AUDIT_DIR`` env, else ``~/.aof``."""
    env = os.environ.get("AOF_AUDIT_DIR")
    if env:
        return Path(env).expanduser()
    return Path.home() / ".aof"


def audit_file() -> Path:
    return audit_dir() / "audit.jsonl"


def decision_file() -> Path:
    return audit_dir() / "decisions.jsonl"


def ensure_audit_dir() -> None:
    audit_dir().mkdir(parents=True, exist_ok=True)


def _append_jsonl(path: Path, record: dict[str, Any], label: str) -> None:
    """Append one JSON line. Never raises -- losing the trail must not kill the server."""
    try:
        ensure_audit_dir()
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        # stdout is the JSON-RPC channel -- diagnostics go to stderr only.
        sys.stderr.write(f"[aof] {label} write failed: {exc}\n")


def write_decision(record: dict[str, Any]) -> None:
    """Append a decision record (contract outcomes, gate verdicts) to decisions.jsonl."""
    entry = dict(record)
    entry.setdefault("ts", time.time())
    _append_jsonl(decision_file(), entry, "decision")


def _entry_failed(entry: dict[str, Any]) -> bool:
    """Decide whether one audit entry represents a failed attempt."""
    for key in ("passed", "ok"):
        if key in entry:
            return entry[key] is False
    raw = entry.get("status") or entry.get("result") or ""
    token = str(raw).split(":", 1)[0].split(" ", 1)[0].strip().lower()
    return token in FAILURE_STATUSES


def _entry_operation(entry: dict[str, Any]) -> Any:
    """Operation name, tolerating both the 'event' and 'tool' entry shapes."""
    return entry.get("event") or entry.get("tool")


def stall_check(session_id: str, operation: str, threshold: int = STALL_THRESHOLD) -> dict[str, Any]:
    """Report a retry loop: one operation failing repeatedly within one session.

    Returns ``{}`` when there is nothing to report, so callers can merge blindly.
    """
    try:
        lines = audit_file().read_text(encoding="utf-8").splitlines()[-STALL_SCAN_LINES:]
    except OSError:
        return {}

    count = 0
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(entry, dict):
            continue
        if entry.get("_session") != session_id and entry.get("session_id") != session_id:
            continue
        if _entry_operation(entry) != operation:
            continue
        if _entry_failed(entry):
            count += 1

    if count < threshold:
        return {}
    # ponytail: warn, never block. Blocking a repeated failure would also block the
    # retry that fixes it, and would recreate the very stall it detects.
    return {
        "stall_warning": True,
        "stall_count": count,
        "stall_hint": (
            f"'{operation}' has failed {count} times in this session. Stop retrying: "
            "change approach or return a blocker to the orchestrator (execution contract stop-if)."
        ),
    }


def with_stall_warning(result: dict[str, Any], session_id: str, operation: str) -> dict[str, Any]:
    """Merge any stall warning into a tool result."""
    result.update(stall_check(session_id, operation))
    return result
