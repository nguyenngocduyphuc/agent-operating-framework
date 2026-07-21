#!/usr/bin/env python3
"""CI smoke: live tools/list count must match TOOLS catalog."""
from __future__ import annotations

import json
import subprocess
import sys


def main() -> int:
    from core.mcp_server import TOOLS

    reqs = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "ci", "version": "0"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    payload = "\n".join(json.dumps(r) for r in reqs) + "\n"
    proc = subprocess.run(
        [sys.executable, "-m", "core.mcp_server"],
        input=payload,
        text=True,
        capture_output=True,
        timeout=30,
    )
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr or proc.stdout or "mcp_server failed\n")
        return 2
    names = None
    for line in proc.stdout.splitlines():
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if obj.get("id") == 2:
            names = [t["name"] for t in obj["result"]["tools"]]
    if names is None:
        sys.stderr.write(proc.stdout or "no tools/list reply\n")
        return 2
    if len(names) != len(TOOLS):
        sys.stderr.write(f"expected {len(TOOLS)} tools, got {len(names)}: {names}\n")
        return 2
    print("tools", len(names), names)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
