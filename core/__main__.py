#!/usr/bin/env python3
"""AOF Framework — python -m core entry point."""
import sys

VERSION = "1.0.0"

def main():
    print(f"AOF Framework v{VERSION}")
    print("GENERIC reusable agent operating framework.")
    print()
    print("Modules:")
    print("  core.preflight     — portable preflight gate (python3 -m core.preflight --help)")
    print("  core.check_contract — validate a contract from stdin")
    print("  core.mcp_server   — stdio MCP server for AOF tools")
    print("  core.execution_contract.md  — contract template")
    print("  core.operating_protocol.md  — protocol template")
    sys.exit(0)

if __name__ == "__main__":
    main()
