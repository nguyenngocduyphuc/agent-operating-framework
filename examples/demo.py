#!/usr/bin/env python3
"""AOF demo — runs preflight and a sample contract check."""

import json
import subprocess
import sys


def main():
    print("=" * 60)
    print("AOF Demo — Agent Operating Framework")
    print("=" * 60)

    # ---- Step 1: Run preflight ----
    print("\n[1/3] Running preflight...")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "core.preflight", "--json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except FileNotFoundError:
        print("  ERROR: 'core.preflight' not found.")
        print("  Copy core/ into your project and run from the project root.")
        sys.exit(1)

    if result.returncode == 0:
        print("  Preflight PASSED.")
    elif result.returncode == 2:
        print("  Preflight FAILED (exit 2). Card:")
        print("  " + result.stdout.replace("\n", "\n  "))
        sys.exit(2)
    else:
        print(f"  Preflight exited with code {result.returncode}.")

    # Print the preflight card
    try:
        card = json.loads(result.stdout)
        print(f"  Workspace: {card.get('workspace', 'unknown')}")
        print(f"  Branch:    {card.get('branch', 'unknown')}")
        print(f"  Status:    {card.get('status', 'unknown')}")
    except (json.JSONDecodeError, KeyError):
        print("  (Preflight output was not valid JSON)")

    # ---- Step 2: Check a sample contract ----
    print("\n[2/3] Validating a sample contract...")
    sample_brief = (
        "Task: Add a health endpoint to the API\n"
        "Owner: codex-worker\n"
        "Scope: src/api/health.py, src/api/__init__.py\n"
        "DoD: GET /health returns 200 with {\"status\":\"ok\"}\n"
        "Do not: touch deploy config, modify database, add deps\n"
        "Stop if: scope includes a file outside src/api/\n"
        "Return: diff + pytest results + evidence link\n"
    )

    try:
        check = subprocess.run(
            [sys.executable, "-m", "core.check_contract"],
            input=sample_brief,
            capture_output=True,
            text=True,
            timeout=15,
        )
        print("  Contract check output:")
        for line in check.stdout.strip().split("\n"):
            print(f"    {line}")
    except FileNotFoundError:
        print("  core.check_contract module not found. Skipping.")

    # ---- Step 3: Summary ----
    print("\n[3/3] Summary")
    print("  Demo completed. AOF is —")
    print("    - core/:     reusable framework modules")
    print("    - adapters/: workspace-specific config (not committed)")
    print("    - examples/: templates and this demo")
    print("=" * 60)


if __name__ == "__main__":
    main()
