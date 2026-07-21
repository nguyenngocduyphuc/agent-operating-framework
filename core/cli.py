#!/usr/bin/env python3
"""AOF CLI entry point.

Usage:
  aof --version
  aof start-mcp-server
  aof init [path] [--lang vi|en]
  aof doctor [path] [--lang vi|en] [--json]
"""
import argparse
import json
import sys

# ponytail: keep version in one place -- pyproject.toml is canonical, cli imports from __init__
from core import __version__


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="aof",
        description="Agent Operating Framework -- portable gate for AI-agent workspaces.",
    )
    parser.add_argument("--version", action="version", version=f"aof {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.add_parser("start-mcp-server", help="Start the stdio MCP server (JSON-RPC 2.0).")

    p_init = sub.add_parser("init", help="Prepare a workspace: default policy + marker (idempotent).")
    p_init.add_argument("path", nargs="?", default=None)
    p_init.add_argument("--lang", choices=["vi", "en"], default=None)

    p_doc = sub.add_parser("doctor", help="Health-check the installation with real probes (exit 0/2).")
    p_doc.add_argument("path", nargs="?", default=None)
    p_doc.add_argument("--lang", choices=["vi", "en"], default=None)
    p_doc.add_argument("--json", action="store_true", dest="as_json")

    p_log = sub.add_parser("log", help="Plain-language operations ledger from the audit trail.")
    p_log.add_argument("--since-hours", type=float, default=None,
                       help="look back N hours (default: since local midnight)")
    p_log.add_argument("--task", default=None)
    p_log.add_argument("--lang", choices=["vi", "en"], default=None)
    p_log.add_argument("--json", action="store_true", dest="as_json")

    p_recap = sub.add_parser("recap", help="Write a self-contained HTML session recap into docs/sessions/.")
    p_recap.add_argument("--since-hours", type=float, default=None)
    p_recap.add_argument("--out", default=None, help="output file (default docs/sessions/RECAP_<ts>.html)")
    p_recap.add_argument("--lang", choices=["vi", "en"], default=None)

    p_handoff = sub.add_parser("handoff", help="Write a markdown session handoff into docs/sessions/.")
    p_handoff.add_argument("--since-hours", type=float, default=None)
    p_handoff.add_argument("--out", default=None, help="output file (default docs/sessions/HANDOFF_<ts>.md)")
    p_handoff.add_argument("--lang", choices=["vi", "en"], default=None)

    p_watch = sub.add_parser("watch", help="Judge a worker by its OUTPUT file mtime/size, not its session.")
    p_watch.add_argument("file")
    p_watch.add_argument("--stale-after", type=int, default=None,
                         help="seconds without a write before 'hung' (default 300)")
    p_watch.add_argument("--lang", choices=["vi", "en"], default=None)
    p_watch.add_argument("--json", action="store_true", dest="as_json")

    p_resume = sub.add_parser(
        "resume",
        help="Print RESUME BRIEF from the host handoff index (newest matching task/repo).",
    )
    p_resume.add_argument("--task", default=None)
    p_resume.add_argument("--repo", default=None, help="working-tree path or repo_key")
    p_resume.add_argument("--lang", choices=["vi", "en"], default=None)

    p_lessons = sub.add_parser(
        "lessons",
        help="List open error-ledger items and entries still missing test_ref.",
    )
    p_lessons.add_argument("--lang", choices=["vi", "en"], default=None)

    p_improve = sub.add_parser(
        "improve-check",
        help="Propose at most ONE policy change from op_log+errors (never writes policy).",
    )
    p_improve.add_argument("--window-hours", type=float, default=168)
    p_improve.add_argument("--lang", choices=["vi", "en"], default=None)
    p_improve.add_argument("--json", action="store_true", dest="as_json")

    args = parser.parse_args()

    if args.command == "start-mcp-server":
        from core.mcp_server import main as _mcp
        _mcp()
    elif args.command == "init":
        from core.doctor import format_init, run_init
        print(format_init(run_init(args.path, args.lang)))
        sys.exit(0)
    elif args.command == "doctor":
        from core.doctor import format_doctor, run_doctor
        report = run_doctor(args.path, args.lang)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.as_json
              else format_doctor(report))
        sys.exit(0 if report["ok"] else 2)
    elif args.command == "log":
        import time as _time

        from core.oplog import build_digest, format_digest
        since = (_time.time() - args.since_hours * 3600) if args.since_hours else None
        report = build_digest(since_ts=since, task=args.task)
        print(json.dumps(report, ensure_ascii=False, indent=2) if args.as_json
              else format_digest(report, args.lang))
        sys.exit(0)
    elif args.command in ("recap", "handoff"):
        import os
        import subprocess
        import time as _time
        from datetime import datetime

        from core.lease import repo_identity
        from core.oplog import (
            append_handoff_index,
            build_digest,
            default_session_dir,
            render_html,
            write_session_bundle,
        )
        from core.preflight import nearest_repo

        since = (_time.time() - args.since_hours * 3600) if args.since_hours else None
        report = build_digest(since_ts=since)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        cwd = os.getcwd()
        repo_root = nearest_repo(cwd) or cwd
        if args.command == "recap":
            content = render_html(report, args.lang)
            out = args.out or os.path.join(
                default_session_dir(repo_root), f"RECAP_{stamp}.html")
            os.makedirs(os.path.dirname(out) or ".", exist_ok=True)
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(content)
            print(out)
        else:
            # F2: handoff always carries its own recap, same stamp, cross-linked.
            # F1-1: write next to nearest git root, not a random subdir cwd.
            if args.out:
                outdir = os.path.dirname(args.out) or "."
            else:
                outdir = default_session_dir(repo_root)
            bundle = write_session_bundle(outdir, report, args.lang, stamp)
            if args.out:
                os.replace(bundle["handoff_path"], args.out)
                bundle["handoff_path"] = args.out
            try:
                ident_path, ident_key = repo_identity(repo_root)
            except Exception:
                ident_path, ident_key = repo_root, ""
            try:
                br = subprocess.run(
                    ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                    cwd=repo_root, capture_output=True, text=True, timeout=10,
                )
                branch = br.stdout.strip() if br.returncode == 0 else ""
            except (OSError, subprocess.TimeoutExpired):
                branch = ""
            summary = {
                "sessions": report["sessions"], "done": report["done"],
                "blocked": report["blocked"], "collisions": report["collisions"],
            }
            append_handoff_index(ident_path, ident_key, branch, None, bundle, summary)
            print(bundle["handoff_path"])
            print(bundle["recap_path"], file=sys.stderr)
        sys.exit(0)
    elif args.command == "resume":
        from core.oplog import format_resume_brief
        print(format_resume_brief(task=args.task, repo=args.repo, lang=args.lang))
        sys.exit(0)
    elif args.command == "lessons":
        from core.errors_ledger import format_lessons
        print(format_lessons(args.lang))
        sys.exit(0)
    elif args.command == "improve-check":
        from core.enforcement import write_decision
        from core.improve import format_proposal, propose_policy_change
        result = propose_policy_change(window_hours=args.window_hours)
        # Record needs_approval when there is a real proposal — never auto-merge.
        if result.get("proposal"):
            write_decision({
                "decision": "needs_approval",
                "kind": "policy_change_proposal",
                "proposal": result["proposal"],
                "evidence": result.get("evidence"),
                "ok": True,
            })
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.as_json
              else format_proposal(result, args.lang))
        sys.exit(0)
    elif args.command == "watch":
        import os as _os

        from core.heartbeat import DEFAULT_STALE_AFTER_S, check, format_check
        from core.preflight import load_policy, workspace_root
        if args.stale_after is not None:
            stale = args.stale_after
        else:
            try:
                stale = int(
                    load_policy(workspace_root(_os.getcwd())).get("worker_stale_after_s")
                    or DEFAULT_STALE_AFTER_S
                )
            except (TypeError, ValueError):
                stale = DEFAULT_STALE_AFTER_S
        result = check(args.file, stale)
        print(json.dumps(result, ensure_ascii=False, indent=2) if args.as_json
              else format_check(result, args.lang))
        sys.exit(0 if result["status"] == "fresh" else 2)
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
