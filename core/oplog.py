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
import os
import time
from datetime import datetime
from typing import Any

from core.enforcement import audit_dir, audit_file, decision_file

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


_HTML_T = {
    "vi": {
        "title": "Recap phiên AOF",
        "since": "Từ",
        "made": "Tạo lúc",
        "cards": [("sessions", "Phiên"), ("done", "Xong có bằng chứng"),
                  ("blocked", "Đóng dạng bị chặn"), ("collisions", "Va chạm khoá (đã chặn)"),
                  ("gate_fail", "Kiểm chứng trượt")],
        "per_task": "Theo nhiệm vụ",
        "contract": "hợp đồng",
        "verify": "kiểm chứng",
        "ok": "đạt",
        "fail": "trượt",
        "task_none": "(chưa gắn nhiệm vụ)",
        "no_activity": "Không có hoạt động trong khoảng này.",
        "honest": "Số liệu in nguyên từ sổ cưỡng chế — kể cả thất bại. Không tô hồng.",
    },
    "en": {
        "title": "AOF Session Recap",
        "since": "Since",
        "made": "Generated",
        "cards": [("sessions", "Sessions"), ("done", "Done with proof"),
                  ("blocked", "Closed as blocked"), ("collisions", "Lock collisions (refused)"),
                  ("gate_fail", "Failed verifications")],
        "per_task": "Per task",
        "contract": "contract",
        "verify": "verify",
        "ok": "pass",
        "fail": "fail",
        "task_none": "(no task bound)",
        "no_activity": "No activity in this window.",
        "honest": "Numbers come straight from the enforcement ledger — failures included. No polish.",
    },
}


def render_html(report: dict[str, Any], lang: str | None = None) -> str:
    """Self-contained recap HTML. One file, inline CSS, opens anywhere.

    ponytail: no JS, no framework, no external assets — a recap must still
    open in ten years from a USB stick.
    """
    t = _HTML_T[lang if lang in ("vi", "en") else "vi"]

    def esc(s: object) -> str:
        return (str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    cards = "".join(
        f'<div class="card"><div class="num">{report[key]}</div>'
        f'<div class="lbl">{esc(label)}</div></div>'
        for key, label in t["cards"]
    )
    rows = []
    for name, b in sorted(report["tasks"].items()):
        label = esc(name) if name else t["task_none"]
        res = " ".join(
            ("✔" if r == "Done" else "⛔") + f" {_fmt_ts(ts)}" for ts, r in b["resolutions"]
        ) or "—"
        rows.append(
            f"<tr><td>{label}</td>"
            f"<td>{b['contract_ok']}✔ / {b['contract_fail']}✘</td>"
            f"<td>{b['verify_pass']} {t['ok']} / {b['verify_fail']} {t['fail']}</td>"
            f"<td>{res}</td></tr>"
        )
    body_tasks = (
        f"<h2>{t['per_task']}</h2><table><tr><th></th><th>{t['contract']}</th>"
        f"<th>{t['verify']}</th><th>Evidence</th></tr>{''.join(rows)}</table>"
        if rows else f"<p>{t['no_activity']}</p>"
    )
    return f"""<!DOCTYPE html>
<html lang="{lang or 'vi'}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{t['title']}</title>
<style>
 body{{font-family:-apple-system,'Segoe UI',sans-serif;max-width:760px;margin:2rem auto;
      padding:0 1rem;color:#1a1a2e;background:#fafafa}}
 h1{{font-size:1.4rem}} h2{{font-size:1.1rem;margin-top:1.6rem}}
 .meta{{color:#666;font-size:.9rem}}
 .cards{{display:flex;gap:.6rem;flex-wrap:wrap;margin:1rem 0}}
 .card{{background:#fff;border:1px solid #e2e2ea;border-radius:10px;padding:.8rem 1rem;
       min-width:104px;text-align:center}}
 .num{{font-size:1.6rem;font-weight:700}} .lbl{{font-size:.78rem;color:#555}}
 table{{border-collapse:collapse;width:100%;background:#fff}}
 th,td{{border:1px solid #e2e2ea;padding:.45rem .6rem;font-size:.9rem;text-align:left}}
 th{{background:#f1f1f6}}
 .honest{{margin-top:1.4rem;font-size:.82rem;color:#777;border-top:1px solid #e2e2ea;
         padding-top:.6rem}}
</style></head><body>
<h1>{t['title']}</h1>
<p class="meta">{t['since']}: {_fmt_ts(report['since_ts'])} · {t['made']}: {_fmt_ts(time.time())}</p>
<div class="cards">{cards}</div>
{body_tasks}
<p class="honest">{t['honest']}</p>
</body></html>
"""


_HANDOFF_T = {
    "vi": {
        "title": "# BÀN GIAO PHIÊN (HANDOFF)",
        "recap_link": "Recap (HTML)",
        "window": "Cửa sổ",
        "done": "## Đã xong — có bằng chứng",
        "blocked": "## Đóng dạng bị chặn (phiên sau xử tiếp)",
        "open_": "## Đang mở (có hợp đồng/kiểm chứng nhưng chưa chốt evidence)",
        "collisions": "Va chạm khoá nhiệm vụ trong cửa sổ",
        "none": "(không có)",
        "next": "## Phiên sau đọc trước",
        "next_items": [
            "Chạy `aof doctor` xác nhận môi trường trước khi làm.",
            "Đọc mục 'Đang mở' — mỗi dòng là một nhiệm vụ chưa chốt, preflight đúng task đó để nhận khoá.",
            "Không tin recap này thay bằng chứng: mọi số đối chiếu được bằng `aof log`.",
        ],
    },
    "en": {
        "title": "# SESSION HANDOFF",
        "recap_link": "Recap (HTML)",
        "window": "Window",
        "done": "## Done — with proof",
        "blocked": "## Closed as blocked (next session continues)",
        "open_": "## Open (contract/verify activity but no evidence yet)",
        "collisions": "Task-lock collisions in window",
        "none": "(none)",
        "next": "## Next session, read first",
        "next_items": [
            "Run `aof doctor` before working.",
            "Each 'Open' line is an unclosed task — preflight that task to take its lease.",
            "Do not trust this recap over evidence: every number is checkable via `aof log`.",
        ],
    },
}


def format_handoff(report: dict[str, Any], lang: str | None = None) -> str:
    """Markdown handoff a NEXT session (human or agent) can act on directly."""
    t = _HANDOFF_T[lang if lang in ("vi", "en") else "vi"]
    done_lines, blocked_lines, open_lines = [], [], []
    for name, b in sorted(report["tasks"].items()):
        label = name or t["none"]
        resolved = {r for _, r in b["resolutions"]}
        line = (f"- {label} — {t_contract(b)} · verify {b['verify_pass']}✔/{b['verify_fail']}✘")
        if "Done" in resolved:
            done_lines.append(line)
        elif "Blocked" in resolved:
            blocked_lines.append(line)
        else:
            open_lines.append(line)
    out = [
        t["title"],
        "",
        f"{t['window']}: {_fmt_ts(report['since_ts'])} → {_fmt_ts(time.time())}"
        f" · {t['collisions']}: {report['collisions']}",
        "",
        t["done"], *(done_lines or [t["none"]]),
        "",
        t["blocked"], *(blocked_lines or [t["none"]]),
        "",
        t["open_"], *(open_lines or [t["none"]]),
        "",
        t["next"],
        *(f"{i+1}. {x}" for i, x in enumerate(t["next_items"])),
        "",
    ]
    return "\n".join(out)


def t_contract(b: dict[str, Any]) -> str:
    return f"contract {b['contract_ok']}✔/{b['contract_fail']}✘"


def default_session_dir(base: str) -> str:
    """docs/sessions/ under the workspace — the per-session docs home."""
    return os.path.join(base, "docs", "sessions")


def write_session_bundle(
    outdir: str, report: dict[str, Any], lang: str | None = None, stamp: str | None = None,
) -> dict[str, str]:
    """Write a handoff .md + recap .html sharing one stamp, cross-linked.

    F2 (AOF v0.4): one call = the whole handoff. Before this, a session had to
    remember to run both `session_recap` and `session_handoff` separately, and
    nothing tied the two files together. Now the handoff always carries a
    working link to its own recap, and both share a timestamp so an index
    (F1) can key on one stamp for the pair.
    """
    t = _HANDOFF_T[lang if lang in ("vi", "en") else "vi"]
    stamp = stamp or datetime.now().strftime("%Y%m%d_%H%M%S")
    recap_name = f"RECAP_{stamp}.html"
    handoff_name = f"HANDOFF_{stamp}.md"
    os.makedirs(outdir, exist_ok=True)

    recap_content = render_html(report, lang)
    body = format_handoff(report, lang)
    title, _, rest = body.partition("\n")
    handoff_content = f"{title}\n\n{t['recap_link']}: ./{recap_name}\n{rest}"

    recap_path = os.path.join(outdir, recap_name)
    handoff_path = os.path.join(outdir, handoff_name)
    with open(recap_path, "w", encoding="utf-8") as fh:
        fh.write(recap_content)
    with open(handoff_path, "w", encoding="utf-8") as fh:
        fh.write(handoff_content)
    return {"handoff_path": handoff_path, "recap_path": recap_path, "stamp": stamp}


def handoff_index_path() -> str:
    """Central append-only handoff index (one writer, one schema).

    Lives under ``audit_dir()/handoffs/index.jsonl`` so ``AOF_AUDIT_DIR`` keeps
    tests and multi-machine hosts isolated (defaults to ``~/.aof/...``).
    """
    return str(audit_dir() / "handoffs" / "index.jsonl")


def append_handoff_index(
    repo_identity_path: str,
    repo_key: str,
    branch: str,
    task: str | None,
    bundle: dict[str, str],
    summary: dict[str, Any] | None = None,
) -> str:
    """Append one index row after a handoff bundle is written. Sole writer."""
    idx_path = audit_dir() / "handoffs" / "index.jsonl"
    idx_path.parent.mkdir(parents=True, exist_ok=True)
    row = {
        "ts": time.time(),
        "repo_identity": repo_identity_path,
        "repo_key": repo_key,
        "branch": branch or "",
        "task": task,
        "handoff_path": bundle["handoff_path"],
        "recap_path": bundle["recap_path"],
        "stamp": bundle.get("stamp"),
        "summary": summary or {},
    }
    with open(idx_path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return str(idx_path)


def load_handoff_index() -> list[dict[str, Any]]:
    """Read the full handoff index (best-effort; corrupt lines skipped)."""
    path = audit_dir() / "handoffs" / "index.jsonl"
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
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def select_handoff_row(
    rows: list[dict[str, Any]],
    task: str | None = None,
    repo: str | None = None,
) -> dict[str, Any] | None:
    """Pick the newest matching index row (by ts). ``repo`` matches path or key."""
    if not rows:
        return None
    candidates = rows
    if task:
        candidates = [r for r in candidates if (r.get("task") or "") == task]
    if repo:
        repo_norm = os.path.realpath(os.path.expanduser(repo))
        filtered = []
        for r in candidates:
            ident = str(r.get("repo_identity") or "")
            key = str(r.get("repo_key") or "")
            handoff = str(r.get("handoff_path") or "")
            if (
                key == repo
                or ident in (repo, repo_norm)
                or handoff.startswith(repo_norm + os.sep)
                or handoff.startswith(repo.rstrip("/") + "/")
            ):
                filtered.append(r)
                continue
            # Allow matching the working-tree root stored indirectly via handoff path.
            try:
                if repo_norm and repo_norm in os.path.realpath(handoff):
                    filtered.append(r)
            except OSError:
                pass
        candidates = filtered
    if not candidates:
        return None
    return max(candidates, key=lambda r: float(r.get("ts") or 0))


def format_resume_brief(
    task: str | None = None,
    repo: str | None = None,
    lang: str | None = None,
) -> str:
    """Build a plain-text RESUME BRIEF from the handoff index + file contents."""
    vi = (lang or "vi") != "en"
    rows = load_handoff_index()
    row = select_handoff_row(rows, task=task, repo=repo)
    if row is None:
        if vi:
            return (
                "# RESUME BRIEF\n\n"
                "Chưa có handoff trong index. Chạy `aof handoff` hoặc tool "
                "`session_handoff` trong phiên trước, rồi gọi lại `aof resume`.\n"
            )
        return (
            "# RESUME BRIEF\n\n"
            "No handoff in the index yet. Run `aof handoff` / `session_handoff` "
            "in a prior session, then call `aof resume` again.\n"
        )

    handoff_path = row.get("handoff_path") or ""
    body = ""
    if handoff_path and os.path.isfile(handoff_path):
        try:
            with open(handoff_path, encoding="utf-8") as fh:
                body = fh.read().strip()
        except OSError as exc:
            body = f"(could not read handoff: {exc})"
    else:
        body = f"(handoff file missing: {handoff_path})"

    rules = (
        "## Luật bắt buộc khi tiếp tục\n"
        "1. History Gate — đọc docs/HISTORY_GOVERNANCE.md trước đổi semantics.\n"
        "2. preflight lại trên đúng repo/branch; không tin trạng thái phiên cũ.\n"
        "3. verify_gate do orchestrator chạy — worker không tự chấm DoD.\n"
        "4. Self-improve chỉ đề xuất; không tự merge policy / không đụng tracker.\n"
        if vi
        else
        "## Required rules before continuing\n"
        "1. History Gate — read docs/HISTORY_GOVERNANCE.md before semantic changes.\n"
        "2. Re-run preflight on the correct repo/branch; do not trust old session state.\n"
        "3. Orchestrator owns verify_gate — workers never self-grade DoD.\n"
        "4. Self-improve proposes only; never auto-merge policy or touch trackers.\n"
    )
    next_cmds = (
        "## Lệnh làm tiếp\n"
        f"- Recap: {row.get('recap_path') or '(none)'}\n"
        f"- Handoff: {handoff_path}\n"
        "- `aof doctor` rồi preflight → contract → verify → evidence\n"
        if vi
        else
        "## Commands to continue\n"
        f"- Recap: {row.get('recap_path') or '(none)'}\n"
        f"- Handoff: {handoff_path}\n"
        "- `aof doctor` then preflight → contract → verify → evidence\n"
    )
    header = (
        f"# RESUME BRIEF\n\n"
        f"- task: {row.get('task') or '(none)'}\n"
        f"- branch: {row.get('branch') or '(unknown)'}\n"
        f"- repo_key: {row.get('repo_key') or ''}\n"
        f"- repo_identity: {row.get('repo_identity') or ''}\n"
        f"- ts: {row.get('ts')}\n\n"
    )
    return f"{header}{rules}\n{next_cmds}\n---\n\n{body}\n"


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
