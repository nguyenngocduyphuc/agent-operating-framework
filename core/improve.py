"""Self-improve loop (core-only): propose at most ONE policy change from evidence.

Never writes ``.aof_policy.json``. Never touches Asana/cmux. Humans approve via
``session_log needs_approval`` / PR. See docs/ARCHITECTURE.md and REWIRE_MAP.
"""
from __future__ import annotations

import time
from typing import Any

from core.errors_ledger import latest_by_fingerprint, load_errors
from core.oplog import build_digest

# Minimum verify samples before we invent a rate-based proposal.
_MIN_VERIFY_SAMPLES = 5
# Fail rate at or above this (with enough samples) triggers a tighten proposal.
_HIGH_FAIL_RATE = 0.4


def propose_policy_change(window_hours: float = 168) -> dict[str, Any]:
    """Read op_log window + error ledger; return exactly 0 or 1 proposal.

    Shape::
        {
          "proposal": None | {"key": str, "from": Any, "to": Any, "reason": str},
          "reason": str,          # human summary / CHƯA ĐỦ DATA / KHÔNG BẤT THƯỜNG
          "evidence": {...},
        }
    """
    since = time.time() - float(window_hours) * 3600
    digest = build_digest(since_ts=since)
    errors = load_errors()
    open_fps = [
        fp for fp, row in latest_by_fingerprint(errors).items()
        if str(row.get("status") or "open").lower() != "closed"
    ]

    verify_pass = sum(b.get("verify_pass", 0) for b in digest["tasks"].values())
    verify_fail = sum(b.get("verify_fail", 0) for b in digest["tasks"].values())
    verify_n = verify_pass + verify_fail
    fail_rate = (verify_fail / verify_n) if verify_n else 0.0
    evidence = {
        "window_hours": window_hours,
        "verify_pass": verify_pass,
        "verify_fail": verify_fail,
        "verify_n": verify_n,
        "fail_rate": round(fail_rate, 3),
        "gate_fail": digest.get("gate_fail", 0),
        "collisions": digest.get("collisions", 0),
        "open_errors": len(open_fps),
        "error_fingerprints_open": open_fps[:10],
        "sessions": digest.get("sessions", 0),
    }

    if verify_n < _MIN_VERIFY_SAMPLES and len(open_fps) < 2:
        return {
            "proposal": None,
            "reason": "CHƯA ĐỦ DATA",
            "evidence": evidence,
        }

    # Priority 1: open error fingerprints → keep require_evidence hard.
    if len(open_fps) >= 2:
        return {
            "proposal": {
                "key": "require_evidence",
                "from": None,
                "to": True,
                "reason": (
                    f"{len(open_fps)} open error fingerprints in ledger; "
                    "keep require_evidence=true so closeout cannot skip proof."
                ),
            },
            "reason": "open_errors",
            "evidence": evidence,
        }

    # Priority 2: high verify fail rate with enough samples → default multi-trial.
    if verify_n >= _MIN_VERIFY_SAMPLES and fail_rate >= _HIGH_FAIL_RATE:
        return {
            "proposal": {
                "key": "verify_default_trials",
                "from": 1,
                "to": 3,
                "reason": (
                    f"verify fail_rate={fail_rate:.0%} over n={verify_n} in "
                    f"{window_hours:.0f}h (threshold {_HIGH_FAIL_RATE:.0%}); "
                    "default verify_gate trials 1→3 for flaky gates."
                ),
            },
            "reason": "high_verify_fail_rate",
            "evidence": evidence,
        }

    # Priority 3: lease collisions → surface require_task so work is named.
    if evidence["collisions"] >= 2:
        return {
            "proposal": {
                "key": "require_task",
                "from": None,
                "to": True,
                "reason": (
                    f"{evidence['collisions']} lease collisions in window; "
                    "require_task=true reduces anonymous trampling."
                ),
            },
            "reason": "lease_collisions",
            "evidence": evidence,
        }

    return {
        "proposal": None,
        "reason": "KHÔNG BẤT THƯỜNG",
        "evidence": evidence,
    }


def format_proposal(result: dict[str, Any], lang: str | None = None) -> str:
    vi = (lang or "vi") != "en"
    prop = result.get("proposal")
    lines = ["# AOF IMPROVE-CHECK", ""]
    if prop is None:
        label = result.get("reason") or ""
        if vi:
            lines.append(f"Đề xuất: (không) — {label}")
            lines.append("Không ghi .aof_policy.json. Không merge tự động.")
        else:
            lines.append(f"Proposal: (none) — {label}")
            lines.append("Does not write .aof_policy.json. No auto-merge.")
    else:
        if vi:
            lines.append("Đề xuất ĐÚNG 1 thay đổi (chờ người duyệt):")
        else:
            lines.append("Exactly ONE proposed change (await human approval):")
        lines.append(f"- key: {prop.get('key')}")
        lines.append(f"- to: {prop.get('to')!r}")
        lines.append(f"- reason: {prop.get('reason')}")
        if vi:
            lines.append("")
            lines.append("Bước tiếp: session_log needs_approval hoặc mở PR; KHÔNG tự ghi policy.")
        else:
            lines.append("")
            lines.append("Next: session_log needs_approval or open a PR; do NOT write policy.")
    ev = result.get("evidence") or {}
    lines += [
        "",
        "## Evidence",
        f"- verify_n={ev.get('verify_n')} fail_rate={ev.get('fail_rate')} "
        f"open_errors={ev.get('open_errors')} collisions={ev.get('collisions')}",
    ]
    return "\n".join(lines) + "\n"
