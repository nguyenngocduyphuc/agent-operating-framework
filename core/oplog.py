"""aof log — the operator's daily ledger, in plain language. Stdlib only.

The audit trail (audit.jsonl + decisions.jsonl) already records everything, but
JSON lines are value locked in a file no operator reads. This module turns them
into the answer to the four daily questions: what ran, what finished WITH
proof, what is stuck, and did any sessions collide.

Honesty rule inherited from the whole framework: this digest only reports what
the enforcement layer itself recorded. It never re-interprets, never upgrades a
"Blocked" into a "Done", and shows collisions and failures with the same
prominence as successes — a ledger that hides failures is a false report.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from core.enforcement import audit_file, decision_file

_T = {
    "vi": {
        "title": "NHẬT KÝ VẬN HÀNH AOF",
        "since": "Từ",
        "sessions": "Phiên làm việc",
        "no_activity": "Không có hoạt động nào trong khoảng thời gian này.",
        "done": "Xong — có bằng chứng",
        "blocked": "Đóng dạng bị chặn",
        "collisions": "Va chạm khoá nhiệm vụ (đã chặn đúng)",
        "gate_fail": "Lần kiểm chứng thất bại",
        "task_none": "(chưa gắn nhiệm vụ)",
        "verify": "kiểm chứng",
        "pass_": "đạt",
        "fail": "trượt",
        "contract_ok": "hợp đồng rõ ràng",
        "contract_fail": "hợp đồng bị trả lại",
        "evidence_done": "✔ XONG có bằng chứng",
        "evidence_blocked": "⛔ Đóng dạng BỊ CHẶN",
        "note_honest": "Số liệu lấy nguyên từ sổ cưỡng chế — không tô hồng.",
    },
    "en": {
        "title": "AOF OPERATIONS LEDGER",
        "since": "Since",
        "sessions": "Sessions",
        "no_activity": "No activity in this window.",
        "done": "Done — with proof",
        "blocked": "Closed as blocked",
        "collisions": "Task-lock collisions (correctly refused)",
        "gate_fail": "Failed verification runs",
        "task_none": "(no task bound)",
        "verify": "verify",
        "pass_": "passed",
        "fail": "failed",
        "contract_ok": "contract accepted",
        "contract_fail": "contract rejected",
        "evidence_done": "✔ DONE with proof",
        "evidence_blocked": "⛔ Closed as BLOCKED",
        "note_honest": "Numbers come straight from the enforcement ledger — no polish.",
    },
}


def _load_jsonl(path, since_ts: float) -> list[dict[str, Any]]:
    entries = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return entries
    for line in lines:
        try:
            e = json.loads(line)
        except (json.JSONDecodeError, TypeError):
            continue
        if not isinstance(e, dict):
            continue
        ts = e.get("ts") or e.get("_ts") or 0
        if ts >= since_ts:
            entries.append(e)
    return entries


def today_start_ts() -> float:
    now = datetime.now()
    return datetime(now.year, now.month, now.day).timestamp()


def build_digest(since_ts: float | None = None, task: str | None = None) -> dict[str, Any]:
    since_ts = today_start_ts() if since_ts is None else since_ts
    audit = _load_jsonl(audit_file(), since_ts)
    decisions = _load_jsonl(decision_file(), since_ts)

    sessions = {e["_session"] for e in audit if e.get("_session")}
    collisions = [e for e in audit if e.get("event") == "lease_conflict"]

    per_task: dict[str, dict[str, Any]] = {}

    def bucket(name: str | None) -> dict[str, Any]:
        key = name or ""
        if key not in per_task:
            per_task[key] = {
                "contract_ok": 0, "contract_fail": 0,
                "verify_pass": 0, "verify_fail": 0,
                "resolutions": [],  # (ts, "Done"|"Blocked")
            }
        return per_task[key]

    for d in decisions:
        t = d.get("task")
        if task and t != task:
            continue
        kind = d.get("decision")
        if kind == "check_contract":
            b = bucket(t)
            b["contract_ok" if d.get("ok") else "contract_fail"] += 1
        elif kind == "verify_gate":
            b = bucket(t)
            b["verify_pass" if d.get("passed") else "verify_fail"] += 1
        elif kind == "post_evidence":
            b = bucket(t)
            b["resolutions"].append((d.get("ts", 0), d.get("resolution")))

    done = sum(1 for b in per_task.values() for _, r in b["resolutions"] if r == "Done")
    blocked = sum(1 for b in per_task.values() for _, r in b["resolutions"] if r == "Blocked")
    gate_fail = sum(b["verify_fail"] for b in per_task.values())

    return {
        "since_ts": since_ts,
        "sessions": len(sessions),
        "collisions": len(collisions),
        "done": done,
        "blocked": blocked,
        "gate_fail": gate_fail,
        "tasks": per_task,
        "has_activity": bool(audit or decisions),
    }


def _fmt_ts(ts: float) -> str:
    try:
        return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return "?"


def format_digest(report: dict[str, Any], lang: str | None = None) -> str:
    t = _T[lang if lang in ("vi", "en") else "vi"]
    lines = [t["title"], f"{t['since']}: {_fmt_ts(report['since_ts'])}", ""]
    if not report["has_activity"]:
        lines.append(t["no_activity"])
        return "\n".join(lines)
    lines.append(
        f"{t['sessions']}: {report['sessions']} · "
        f"{t['done']}: {report['done']} · "
        f"{t['blocked']}: {report['blocked']} · "
        f"{t['collisions']}: {report['collisions']} · "
        f"{t['gate_fail']}: {report['gate_fail']}"
    )
    for name, b in sorted(report["tasks"].items()):
        label = name or t["task_none"]
        lines.append("")
        lines.append(f"[{label}]")
        if b["contract_ok"] or b["contract_fail"]:
            parts = []
            if b["contract_ok"]:
                parts.append(f"{b['contract_ok']}× {t['contract_ok']}")
            if b["contract_fail"]:
                parts.append(f"{b['contract_fail']}× {t['contract_fail']}")
            lines.append("  " + " · ".join(parts))
        if b["verify_pass"] or b["verify_fail"]:
            lines.append(
                f"  {t['verify']}: {b['verify_pass']}× {t['pass_']}, "
                f"{b['verify_fail']}× {t['fail']}"
            )
        for ts, res in b["resolutions"]:
            mark = t["evidence_done"] if res == "Done" else t["evidence_blocked"]
            lines.append(f"  {mark} — {_fmt_ts(ts)}")
    lines.append("")
    lines.append(t["note_honest"])
    return "\n".join(lines)
