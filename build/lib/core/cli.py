#!/usr/bin/env python3
"""AOF CLI entry point.

Usage:
  aof --version
  aof start-mcp-server
"""
import argparse
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

    args = parser.parse_args()

    if args.command == "start-mcp-server":
        from core.mcp_server import main as _mcp
        _mcp()
    else:
        parser.print_help()
        sys.exit(0)


if __name__ == "__main__":
    main()
