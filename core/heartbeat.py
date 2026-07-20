"""aof watch — is that worker actually working? Judge the OUTPUT, not the session.

Incident encoded here (2026-07-20): a worker hung for 18 minutes while tmux
still reported the session alive. Every watchdog that asks "is the process
alive?" is blind to this failure mode. The only honest signal is the worker's
output file: if it has not grown or been touched recently, the worker is stuck
no matter what the session table says.

Stdlib only. One primitive: check(path, stale_after_s) -> fresh | stale | missing.
"""
from __future__ import annotations

import os
import time
from typing import Any

_T = {
    "vi": {
        "fresh": "✅ ĐANG LÀM THẬT — file lớn lên / vừa được ghi",
        "stale": "⛔ NGHI TREO — file không nhúc nhích",
        "missing": "⛔ CHƯA CÓ GÌ — file chưa tồn tại",
        "age": "lần ghi cuối cách đây",
        "size": "kích thước",
        "hint_stale": "Worker có thể đã treo dù phiên vẫn 'sống'. Kiểm tra hoặc khởi động lại worker.",
        "hint_missing": "Worker chưa ghi output. Nếu đã giao việc lâu rồi, coi như treo.",
        "seconds": "giây",
    },
    "en": {
        "fresh": "✅ ACTUALLY WORKING — file growing / recently written",
        "stale": "⛔ LIKELY HUNG — file has not moved",
        "missing": "⛔ NOTHING YET — file does not exist",
        "age": "last write",
        "size": "size",
        "hint_stale": "The worker may be hung even though the session looks alive. Inspect or restart it.",
        "hint_missing": "The worker has produced no output. If the job started long ago, treat it as hung.",
        "seconds": "s ago",
    },
}

DEFAULT_STALE_AFTER_S = 300


def check(path: str, stale_after_s: int = DEFAULT_STALE_AFTER_S) -> dict[str, Any]:
    """Classify a worker output file. Never raises."""
    try:
        st = os.stat(path)
    except OSError:
        return {"status": "missing", "path": path, "stale_after_s": stale_after_s}
    age = max(0.0, time.time() - st.st_mtime)
    status = "fresh" if age <= stale_after_s else "stale"
    return {
        "status": status,
        "path": path,
        "age_s": round(age, 1),
        "size_bytes": st.st_size,
        "stale_after_s": stale_after_s,
    }


def format_check(result: dict[str, Any], lang: str | None = None) -> str:
    t = _T[lang if lang in ("vi", "en") else "vi"]
    status = result["status"]
    lines = [t[status], f"  {result['path']}"]
    if status != "missing":
        lines.append(
            f"  {t['age']}: {result['age_s']} {t['seconds']} · "
            f"{t['size']}: {result['size_bytes']} bytes"
        )
    if status == "stale":
        lines.append(f"  {t['hint_stale']}")
    elif status == "missing":
        lines.append(f"  {t['hint_missing']}")
    return "\n".join(lines)
