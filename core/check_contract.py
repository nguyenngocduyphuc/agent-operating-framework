#!/usr/bin/env python3
"""Validate the portable AOF execution-contract fields from stdin."""
import json
import sys

REQUIRED = ("Task", "Owner", "Scope", "DoD", "Do not", "Stop if", "Return")


def validate(brief: str) -> dict:
    found = [field for field in REQUIRED if field.lower() in brief.lower()]
    missing = [field for field in REQUIRED if field not in found]
    return {"ok": not missing, "found": found, "missing_required": missing}


def main() -> None:
    result = validate(sys.stdin.read())
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["ok"] else 2)


if __name__ == "__main__":
    main()
