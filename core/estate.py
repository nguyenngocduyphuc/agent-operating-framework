"""Estate effectiveness — host-side KPIs across repos/workspaces from AOF ledgers.

Stdlib only. Does not call cmux/Asana (those stay adapters). Dimensions work from
what the enforcement layer already records; preflight rows should include
workspace/repo when available.

Snapshots land in ``audit_dir()/estate/snapshots/`` (append-only files, one JSON
each). ``aof estate-report`` builds a live window without requiring a prior collect.
"""
from __future__ import annotations

import json
import time
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from core.enforcement import audit_dir, audit_file, decision_file, ensure_audit_dir
from core.errors_ledger import fingerprint_counts, latest_by_fingerprint, load_errors
from core.host_context import workspace_key
from core.oplog import _load_jsonl, load_handoff_index


def estate_dir() -> Path:
    return audit_dir() / "estate"


def snapshots_dir() -> Path:
    return estate_dir() / "snapshots"


def _safe_rate(num: float, den: float) -> float | None:
    if den <= 0:
        return None
    return round(num / den, 4)


def _repo_label_from_path(path: str | None) -> str:
    if not path:
        return "(unknown)"
    try:
        p = Path(path).resolve()
        # prefer .../<repo>/docs/sessions/...
        parts = p.parts
        if "docs" in parts:
            i = parts.index("docs")
            if i > 0:
                return parts[i - 1]
        return p.parent.name or str(p)
    except (OSError, ValueError):
        return str(path)[-48:]


def build_estate_report(window_hours: float = 168) -> dict[str, Any]:
    """Aggregate ledgers into estate KPIs for the last ``window_hours``."""
    window_hours = float(window_hours)
    since_ts = time.time() - window_hours * 3600
    audit = _load_jsonl(audit_file(), since_ts)
    decisions = _load_jsonl(decision_file(), since_ts)
    errors = [e for e in load_errors() if float(e.get("ts") or 0) >= since_ts]
    # handoff index is small; filter by ts
    handoffs = [h for h in load_handoff_index() if float(h.get("ts") or 0) >= since_ts]

    sessions = {e.get("_session") for e in audit if e.get("_session")}
    sessions.discard(None)

    # Noise filter: sessions that only start/end (or probe) are test/MCP spam,
    # not operational work. Productive = any enforcement or report event.
    _PRODUCTIVE = frozenset({
        "preflight", "check_contract", "verify_gate", "audit_scope",
        "post_evidence", "session_handoff", "session_recap", "aof_resume",
        "lease", "lease_conflict", "error", "needs_approval",
    })
    events_by_session: dict[str, set[str]] = defaultdict(set)
    for e in audit:
        sid = e.get("_session")
        if sid and e.get("event"):
            events_by_session[str(sid)].add(str(e["event"]))
    productive_sessions = {
        sid for sid, evs in events_by_session.items() if evs & _PRODUCTIVE
    }
    noise_sessions = sessions - productive_sessions

    # Map session -> workspace key (last non-unknown wins; prefer cmux id).
    session_ws: dict[str, str] = {}
    for e in audit:
        sid = e.get("_session")
        if not sid:
            continue
        key = workspace_key(e)
        if key != "(unknown)" or str(sid) not in session_ws:
            session_ws[str(sid)] = key

    per_ws: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "sessions": set(),
            "productive": set(),
            "noise": set(),
            "preflight_clear": 0,
            "preflight_warn": 0,
            "preflight_blocked": 0,
            "handoffs": 0,
            "resumes": 0,
            "lease_collisions": 0,
            "cmux_surface_ids": set(),
            "repos": set(),
        }
    )
    for sid, key in session_ws.items():
        b = per_ws[key]
        b["sessions"].add(sid)
        if sid in productive_sessions:
            b["productive"].add(sid)
        if sid in noise_sessions:
            b["noise"].add(sid)

    event_counts = Counter(e.get("event") for e in audit if e.get("event"))
    preflight_status = Counter()
    workspaces: set[str] = set()
    repos_seen: set[str] = set()
    for e in audit:
        wkey = workspace_key(e)
        if wkey != "(unknown)":
            workspaces.add(wkey)
        wb = per_ws[wkey]
        if e.get("cmux_surface_id"):
            wb["cmux_surface_ids"].add(str(e["cmux_surface_id"]))
        if e.get("event") == "preflight":
            st = e.get("status") or "unknown"
            preflight_status[str(st)] += 1
            if st == "clear":
                wb["preflight_clear"] += 1
            elif st == "warn":
                wb["preflight_warn"] += 1
            elif st == "blocked":
                wb["preflight_blocked"] += 1
            if e.get("workspace"):
                workspaces.add(str(e["workspace"]))
            if e.get("repo"):
                repos_seen.add(str(e["repo"]))
                wb["repos"].add(str(e["repo"]))
        if e.get("event") == "session_handoff":
            wb["handoffs"] += 1
        if e.get("event") == "aof_resume":
            wb["resumes"] += 1
        if e.get("event") == "lease_conflict":
            wb["lease_collisions"] += 1
        if e.get("event") in ("session_handoff", "session_recap") and e.get("path"):
            repos_seen.add(_repo_label_from_path(str(e["path"])))

    collisions = event_counts.get("lease_conflict", 0)
    resumes = event_counts.get("aof_resume", 0)
    handoff_events = event_counts.get("session_handoff", 0)
    # Karpathy enforcement signal: contract failures that mention karpathy in audit
    # are not always tagged; use decision field when present.
    karpathy_blocks = sum(
        1 for d in decisions
        if d.get("decision") == "check_contract"
        and d.get("ok") is False
        and (d.get("karpathy_ok") is False or "karpathy" in str(d.get("hint") or "").lower())
    )

    verify_pass = verify_fail = 0
    contract_ok = contract_fail = 0
    done = blocked = 0
    per_task: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "verify_pass": 0, "verify_fail": 0,
            "contract_ok": 0, "contract_fail": 0,
            "done": 0, "blocked": 0,
        }
    )
    for d in decisions:
        task = d.get("task") or d.get("task_gid") or "(none)"
        kind = d.get("decision")
        b = per_task[str(task)]
        if kind == "verify_gate":
            if d.get("passed"):
                verify_pass += 1
                b["verify_pass"] += 1
            else:
                verify_fail += 1
                b["verify_fail"] += 1
        elif kind == "check_contract":
            if d.get("ok"):
                contract_ok += 1
                b["contract_ok"] += 1
            else:
                contract_fail += 1
                b["contract_fail"] += 1
        elif kind == "post_evidence":
            res = d.get("resolution")
            if res == "Done":
                done += 1
                b["done"] += 1
            elif res == "Blocked":
                blocked += 1
                b["blocked"] += 1

    # also count audit-layer verify/post if decisions sparse
    for e in audit:
        if e.get("event") == "verify_gate" and "passed" in e:
            # avoid double-count if decisions already have them — only use audit
            # when no decision rows for verify
            pass
    if verify_pass + verify_fail == 0:
        for e in audit:
            if e.get("event") == "verify_gate":
                if e.get("passed"):
                    verify_pass += 1
                else:
                    verify_fail += 1
        for e in audit:
            if e.get("event") == "post_evidence":
                if e.get("resolution") == "Done":
                    done += 1
                elif e.get("resolution") == "Blocked":
                    blocked += 1

    fp_counts = fingerprint_counts(errors)
    open_errors = [
        r for r in latest_by_fingerprint(errors).values()
        if str(r.get("status") or "open").lower() != "closed"
    ]
    repeated_fps = {fp: n for fp, n in fp_counts.items() if fp and n >= 2}

    per_repo: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"handoffs": 0, "tasks": set(), "branches": set()}
    )
    for h in handoffs:
        key = h.get("repo_key") or _repo_label_from_path(h.get("handoff_path"))
        bucket = per_repo[str(key)]
        bucket["handoffs"] += 1
        if h.get("task"):
            bucket["tasks"].add(str(h["task"]))
        if h.get("branch"):
            bucket["branches"].add(str(h["branch"]))
        if h.get("repo_identity"):
            bucket["identity"] = h["repo_identity"]
        if h.get("handoff_path"):
            bucket["label"] = _repo_label_from_path(str(h["handoff_path"]))

    per_repo_out = {}
    for k, v in per_repo.items():
        per_repo_out[k] = {
            "handoffs": v["handoffs"],
            "tasks": sorted(v["tasks"]),
            "branches": sorted(v["branches"]),
            "identity": v.get("identity"),
            "label": v.get("label") or k,
        }

    per_workspace_out: dict[str, dict[str, Any]] = {}
    for k, v in per_ws.items():
        n_sess = len(v["sessions"])
        if n_sess == 0 and not any(
            v[x] for x in ("preflight_clear", "preflight_warn", "preflight_blocked",
                           "handoffs", "resumes", "lease_collisions")
        ):
            continue
        per_workspace_out[k] = {
            "sessions": n_sess,
            "productive": len(v["productive"]),
            "noise": len(v["noise"]),
            "noise_rate": _safe_rate(len(v["noise"]), n_sess),
            "preflight_clear": v["preflight_clear"],
            "preflight_warn": v["preflight_warn"],
            "preflight_blocked": v["preflight_blocked"],
            "handoffs": v["handoffs"],
            "resumes": v["resumes"],
            "lease_collisions": v["lease_collisions"],
            "cmux_surface_ids": sorted(v["cmux_surface_ids"])[:20],
            "repos": sorted(v["repos"])[:20],
            "uses_cmux": bool(v["cmux_surface_ids"]) or (
                len(k) >= 32 and k.count("-") >= 4
            ),
        }

    verify_n = verify_pass + verify_fail
    contract_n = contract_ok + contract_fail
    close_n = done + blocked
    preflight_n = sum(preflight_status.values())

    kpis = {
        "sessions": len(sessions),
        "sessions_productive": len(productive_sessions),
        "sessions_noise": len(noise_sessions),
        "noise_session_rate": _safe_rate(len(noise_sessions), len(sessions) or 0),
        "workspaces_seen": len(per_workspace_out) or len(workspaces),
        "cmux_workspaces_seen": sum(1 for w in per_workspace_out.values() if w.get("uses_cmux")),
        "repos_seen": len(repos_seen) or len(per_repo_out),
        "preflight_total": preflight_n,
        "preflight_clear": preflight_status.get("clear", 0),
        "preflight_warn": preflight_status.get("warn", 0),
        "preflight_blocked": preflight_status.get("blocked", 0),
        "preflight_clear_rate": _safe_rate(preflight_status.get("clear", 0), preflight_n),
        "lease_collisions": collisions,
        "handoffs": max(handoff_events, len(handoffs)),
        "resumes": resumes,
        "resume_to_handoff_rate": _safe_rate(resumes, max(handoff_events, len(handoffs), 1))
        if (handoff_events or handoffs)
        else None,
        "verify_pass": verify_pass,
        "verify_fail": verify_fail,
        "verify_fail_rate": _safe_rate(verify_fail, verify_n),
        "contract_ok": contract_ok,
        "contract_fail": contract_fail,
        "contract_fail_rate": _safe_rate(contract_fail, contract_n),
        "karpathy_contract_blocks": karpathy_blocks,
        "untagged_task_activity": (
            per_task.get("(none)", {}).get("verify_pass", 0)
            + per_task.get("(none)", {}).get("verify_fail", 0)
            + per_task.get("(none)", {}).get("contract_ok", 0)
            + per_task.get("(none)", {}).get("contract_fail", 0)
        ),
        "done": done,
        "blocked": blocked,
        "blocked_share": _safe_rate(blocked, close_n),
        "open_errors": len(open_errors),
        "repeated_fingerprints": len(repeated_fps),
        "error_rows_in_window": len(errors),
    }

    # top tasks by verify_fail then activity
    top_tasks = sorted(
        (
            {
                "task": t,
                **vals,
                "verify_fail_rate": _safe_rate(
                    vals["verify_fail"], vals["verify_pass"] + vals["verify_fail"]
                ),
            }
            for t, vals in per_task.items()
        ),
        key=lambda x: (x["verify_fail"], x["verify_pass"] + x["blocked"]),
        reverse=True,
    )[:15]

    return {
        "generated_at": time.time(),
        "window_hours": window_hours,
        "since_ts": since_ts,
        "audit_dir": str(audit_dir()),
        "kpis": kpis,
        "preflight_status": dict(preflight_status),
        "event_counts": dict(event_counts),
        "workspaces": sorted(workspaces),
        "per_workspace": per_workspace_out,
        "per_repo": per_repo_out,
        "top_tasks": top_tasks,
        "repeated_fingerprints": repeated_fps,
        "open_error_titles": [
            {"fingerprint": r.get("fingerprint"), "title": r.get("title")}
            for r in open_errors[:20]
        ],
        "honesty": (
            "Host-local estate from AOF ledgers only. Not multi-machine until "
            "AOF_ESTATE_SOURCES is configured; not a causal n≥30 ROI bench."
        ),
    }


def write_estate_snapshot(report: dict[str, Any] | None = None, window_hours: float = 168) -> str:
    """Persist one JSON snapshot under estate/snapshots/. Returns path."""
    report = report or build_estate_report(window_hours=window_hours)
    ensure_audit_dir()
    out_dir = snapshots_dir()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"ESTATE_{stamp}.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # also refresh "latest" pointer for dashboards
    latest = estate_dir() / "latest.json"
    latest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return str(path)


def format_estate_report(report: dict[str, Any], lang: str | None = None) -> str:
    vi = (lang or "vi") != "en"
    k = report.get("kpis") or {}
    lines: list[str] = []
    if vi:
        lines += [
            "# AOF ESTATE REPORT — hiệu quả vận hành (ledger)",
            f"Cửa sổ: {report.get('window_hours')}h · audit: {report.get('audit_dir')}",
            "",
            "## KPI chính",
            f"- Phiên: {k.get('sessions')} "
            f"(productive={k.get('sessions_productive')} noise={k.get('sessions_noise')} "
            f"noise_rate={k.get('noise_session_rate')})",
            f"- Workspace: {k.get('workspaces_seen')} "
            f"(cmux={k.get('cmux_workspaces_seen')}) · repo: {k.get('repos_seen')}",
            f"- Karpathy contract blocks: {k.get('karpathy_contract_blocks')} · "
            f"activity không gắn task: {k.get('untagged_task_activity')}",
            f"- Preflight clear/warn/blocked: "
            f"{k.get('preflight_clear')}/{k.get('preflight_warn')}/{k.get('preflight_blocked')} "
            f"(clear_rate={k.get('preflight_clear_rate')})",
            f"- Lease collisions (đã chặn): {k.get('lease_collisions')}",
            f"- Handoff / resume: {k.get('handoffs')} / {k.get('resumes')} "
            f"(resume_rate={k.get('resume_to_handoff_rate')})",
            f"- Verify pass/fail: {k.get('verify_pass')}/{k.get('verify_fail')} "
            f"(fail_rate={k.get('verify_fail_rate')})",
            f"- Done / Blocked: {k.get('done')}/{k.get('blocked')} "
            f"(blocked_share={k.get('blocked_share')})",
            f"- Lỗi mở / fingerprint lặp: {k.get('open_errors')} / {k.get('repeated_fingerprints')}",
            "",
            "## Theo repo (handoff index)",
        ]
    else:
        lines += [
            "# AOF ESTATE REPORT — operational effectiveness (ledgers)",
            f"Window: {report.get('window_hours')}h · audit: {report.get('audit_dir')}",
            "",
            "## Core KPIs",
            f"- sessions: {k.get('sessions')} "
            f"(productive={k.get('sessions_productive')} noise={k.get('sessions_noise')} "
            f"noise_rate={k.get('noise_session_rate')})",
            f"- workspaces: {k.get('workspaces_seen')} "
            f"(cmux={k.get('cmux_workspaces_seen')}) · repos: {k.get('repos_seen')}",
            f"- karpathy_contract_blocks: {k.get('karpathy_contract_blocks')} · "
            f"untagged_task_activity: {k.get('untagged_task_activity')}",
            f"- preflight clear/warn/blocked: "
            f"{k.get('preflight_clear')}/{k.get('preflight_warn')}/{k.get('preflight_blocked')} "
            f"(clear_rate={k.get('preflight_clear_rate')})",
            f"- lease collisions (blocked correctly): {k.get('lease_collisions')}",
            f"- handoff / resume: {k.get('handoffs')} / {k.get('resumes')} "
            f"(resume_rate={k.get('resume_to_handoff_rate')})",
            f"- verify pass/fail: {k.get('verify_pass')}/{k.get('verify_fail')} "
            f"(fail_rate={k.get('verify_fail_rate')})",
            f"- done / blocked: {k.get('done')}/{k.get('blocked')} "
            f"(blocked_share={k.get('blocked_share')})",
            f"- open errors / repeated fingerprints: "
            f"{k.get('open_errors')} / {k.get('repeated_fingerprints')}",
            "",
            "## Per repo (handoff index)",
        ]

    repos = report.get("per_repo") or {}
    if not repos:
        lines.append("(none in window)" if not vi else "(không có trong cửa sổ)")
    else:
        for key, info in sorted(repos.items(), key=lambda kv: -kv[1].get("handoffs", 0)):
            label = info.get("label") or key
            lines.append(
                f"- {label}: handoffs={info.get('handoffs')} "
                f"tasks={len(info.get('tasks') or [])} "
                f"branches={','.join(info.get('branches') or []) or '—'}"
            )

    lines.append("")
    lines.append("## Theo workspace (AOF path / cmux id)" if vi else "## Per workspace (AOF path / cmux id)")
    pws = report.get("per_workspace") or {}
    if not pws:
        lines.append("(none)" if not vi else "(không — cần traffic sau khi bật host identity)")
    else:
        ranked = sorted(
            pws.items(),
            key=lambda kv: (-kv[1].get("productive", 0), -kv[1].get("sessions", 0)),
        )[:15]
        for wkey, info in ranked:
            label = wkey if len(wkey) < 64 else wkey[:28] + "…" + wkey[-12:]
            cmux = "cmux" if info.get("uses_cmux") else "path"
            lines.append(
                f"- [{cmux}] {label}: sess={info.get('sessions')} "
                f"prod/noise={info.get('productive')}/{info.get('noise')} "
                f"pf={info.get('preflight_clear')}/{info.get('preflight_warn')}/{info.get('preflight_blocked')} "
                f"handoff/resume={info.get('handoffs')}/{info.get('resumes')} "
                f"lease_col={info.get('lease_collisions')}"
            )

    lines.append("")
    lines.append("## Task nổi bật" if vi else "## Top tasks")
    tops = report.get("top_tasks") or []
    shown = 0
    for t in tops:
        if not any(t.get(x) for x in ("verify_fail", "verify_pass", "done", "blocked", "contract_fail")):
            continue
        lines.append(
            f"- {t.get('task')}: verify {t.get('verify_pass')}/{t.get('verify_fail')} "
            f"done/blocked {t.get('done')}/{t.get('blocked')} "
            f"fail_rate={t.get('verify_fail_rate')}"
        )
        shown += 1
        if shown >= 10:
            break
    if shown == 0:
        lines.append("(không)" if vi else "(none)")

    lines += ["", report.get("honesty") or ""]
    if vi:
        lines += [
            "",
            "Lệnh: `aof estate-report --days 7` · snapshot: `aof estate-report --days 7 --snapshot`",
            "Cải tiến: `aof lessons` · `aof improve-check`",
        ]
    else:
        lines += [
            "",
            "Commands: `aof estate-report --days 7` · snapshot: `aof estate-report --days 7 --snapshot`",
            "Improve loop: `aof lessons` · `aof improve-check`",
        ]
    return "\n".join(lines) + "\n"


def format_estate_html(report: dict[str, Any], lang: str | None = None) -> str:
    """Minimal self-contained HTML (no JS) for weekly CEO glance."""
    text = format_estate_report(report, lang)
    # escape
    esc = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    k = report.get("kpis") or {}
    cards = [
        ("sessions", k.get("sessions")),
        ("verify_fail_rate", k.get("verify_fail_rate")),
        ("lease_collisions", k.get("lease_collisions")),
        ("open_errors", k.get("open_errors")),
        ("handoffs", k.get("handoffs")),
        ("resumes", k.get("resumes")),
    ]
    card_html = "".join(
        f'<div class="card"><div class="k">{n}</div><div class="v">{v}</div></div>'
        for n, v in cards
    )
    return f"""<!DOCTYPE html>
<html lang="{'vi' if (lang or 'vi') != 'en' else 'en'}">
<head>
<meta charset="utf-8"/>
<title>AOF Estate Report</title>
<style>
body{{font-family:ui-monospace,Menlo,Consolas,monospace;margin:24px;background:#0f1419;color:#e7ecf3}}
h1{{font-size:18px}}
.cards{{display:flex;flex-wrap:wrap;gap:12px;margin:16px 0}}
.card{{background:#1a2332;border:1px solid #2a3544;border-radius:8px;padding:12px 16px;min-width:120px}}
.k{{font-size:11px;color:#8b9bb4;text-transform:uppercase}}
.v{{font-size:22px;margin-top:4px}}
pre{{white-space:pre-wrap;background:#1a2332;padding:16px;border-radius:8px;border:1px solid #2a3544}}
.note{{color:#8b9bb4;font-size:12px;margin-top:12px}}
</style>
</head>
<body>
<h1>AOF Estate Report · {report.get('window_hours')}h</h1>
<div class="cards">{card_html}</div>
<pre>{esc}</pre>
<p class="note">{report.get('honesty','')}</p>
</body>
</html>
"""
