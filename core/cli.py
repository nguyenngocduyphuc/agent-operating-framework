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
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
