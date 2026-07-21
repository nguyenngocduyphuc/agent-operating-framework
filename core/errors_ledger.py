"""Error ledger — append-only lessons so real failures do not silently repeat.

Stdlib only. One writer (record_error), one schema, lives under audit_dir()
(``~/.aof/errors.jsonl`` or ``$AOF_AUDIT_DIR/errors.jsonl``).
"""
from __future__ import annotations

import json
import time
from collections import Counter
from pathlib import Path
from typing import Any

from core.enforcement import audit_dir, ensure_audit_dir


def errors_path() -> Path:
    return audit_dir() / "errors.jsonl"


def load_errors() -> list[dict[str, Any]]:
    path = errors_path()
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _append(row: dict[str, Any]) -> str:
    ensure_audit_dir()
    path = errors_path()
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return str(path)


def record_error(
    data: dict[str, Any] | None,
    session: str | None = None,
) -> dict[str, Any]:
    """Append an error-ledger row. Closing without test_ref is refused.

    Returns ``{ok, path?, refused?, reason?, row?}``.
    """
    data = dict(data or {})
    status = str(data.get("status") or "open").strip().lower()
    if status not in ("open", "closed"):
        status = "open"
    fingerprint = data.get("fingerprint")
    test_ref = (data.get("test_ref") or "").strip() if data.get("test_ref") else ""

    if status == "closed" and not test_ref:
        return {
            "ok": False,
            "refused": True,
            "reason": (
                "Cannot close error without test_ref — each real failure must leave "
                "a permanent regression test path (e.g. tests/test_foo.py::test_bar)."
            ),
            "status": "open",
        }

    row = {
        "ts": time.time(),
        "fingerprint": fingerprint,
        "title": data.get("title"),
        "session": session,
        "fix_commit": data.get("fix_commit"),
        "test_ref": test_ref or None,
        "status": status,
    }
    path = _append(row)
    return {"ok": True, "path": path, "row": row, "refused": False}


def latest_by_fingerprint(rows: list[dict[str, Any]] | None = None) -> dict[str, dict[str, Any]]:
    """Last row per fingerprint (append order = chronological)."""
    out: dict[str, dict[str, Any]] = {}
    for row in rows if rows is not None else load_errors():
        fp = str(row.get("fingerprint") or "")
        if not fp:
            continue
        out[fp] = row
    return out


def fingerprint_counts(rows: list[dict[str, Any]] | None = None) -> Counter:
    rows = rows if rows is not None else load_errors()
    return Counter(str(r.get("fingerprint") or "") for r in rows if r.get("fingerprint"))


def preflight_error_warnings(rows: list[dict[str, Any]] | None = None) -> list[str]:
    """WARN strings for preflight — never blockers.

    - any latest status != closed
    - any fingerprint appearing >= 2 times in the ledger
    """
    rows = rows if rows is not None else load_errors()
    if not rows:
        return []
    warns: list[str] = []
    counts = fingerprint_counts(rows)
    for fp, n in counts.items():
        if fp and n >= 2:
            warns.append(
                f"Error ledger: fingerprint {fp!r} seen {n} times — do not repeat; "
                "read `aof lessons` and close only with a test_ref."
            )
    for fp, row in latest_by_fingerprint(rows).items():
        if str(row.get("status") or "open").lower() != "closed":
            title = row.get("title") or fp
            warns.append(
                f"Open error in ledger: {title!r} (fingerprint {fp!r}). "
                "Fix with a permanent test, then session_log event=error status=closed + test_ref."
            )
    # de-dupe while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for w in warns:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique


def format_lessons(lang: str | None = None) -> str:
    """Two groups: open errors, and rows still missing test_ref."""
    vi = (lang or "vi") != "en"
    rows = load_errors()
    latest = latest_by_fingerprint(rows)
    open_rows = [
        r for r in latest.values()
        if str(r.get("status") or "open").lower() != "closed"
    ]
    missing_ref = [
        r for r in latest.values()
        if not (r.get("test_ref") or "").strip()
    ]

    if vi:
        lines = [
            "# BÀI HỌC / ERROR LEDGER",
            "",
            f"## Lỗi đang mở ({len(open_rows)})",
        ]
        if not open_rows:
            lines.append("(không có)")
        else:
            for r in open_rows:
                lines.append(
                    f"- [{r.get('fingerprint')}] {r.get('title') or '?'} "
                    f"status={r.get('status')} test_ref={r.get('test_ref') or '—'}"
                )
        lines += ["", f"## Thiếu test_ref ({len(missing_ref)})"]
        if not missing_ref:
            lines.append("(không có)")
        else:
            for r in missing_ref:
                lines.append(
                    f"- [{r.get('fingerprint')}] {r.get('title') or '?'} "
                    f"status={r.get('status')}"
                )
        lines += [
            "",
            "Đóng lỗi: session_log event=error data={fingerprint, status:closed, test_ref:\"tests/...\"}",
        ]
        return "\n".join(lines) + "\n"

    lines = [
        "# LESSONS / ERROR LEDGER",
        "",
        f"## Open errors ({len(open_rows)})",
    ]
    if not open_rows:
        lines.append("(none)")
    else:
        for r in open_rows:
            lines.append(
                f"- [{r.get('fingerprint')}] {r.get('title') or '?'} "
                f"status={r.get('status')} test_ref={r.get('test_ref') or '—'}"
            )
    lines += ["", f"## Missing test_ref ({len(missing_ref)})"]
    if not missing_ref:
        lines.append("(none)")
    else:
        for r in missing_ref:
            lines.append(
                f"- [{r.get('fingerprint')}] {r.get('title') or '?'} "
                f"status={r.get('status')}"
            )
    lines += [
        "",
        "Close: session_log event=error data={fingerprint, status:closed, test_ref:\"tests/...\"}",
    ]
    return "\n".join(lines) + "\n"
