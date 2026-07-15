#!/usr/bin/env python3
"""Validate the portable AOF execution-contract fields from stdin.

Requires line-start ``Field: non-empty value`` format.  Prose that merely
contains the field name (e.g. "Task Owner Scope DoD") does NOT pass.
"""
import json
import sys

REQUIRED = ("Task", "Owner", "Scope", "DoD", "Do not", "Stop if", "Return")


def validate(brief: str) -> dict:
    lines = brief.split("\n")
    found = []
    for line in lines:
        for field in REQUIRED:
            if line.startswith(field + ":"):
                val = line[len(field) + 1:].strip()
                if val and field not in found:
                    found.append(field)
    missing = [f for f in REQUIRED if f not in found]
    return {"ok": not missing, "found": found, "missing_required": missing}


def main() -> None:
    result = validate(sys.stdin.read())
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["ok"] else 2)


if __name__ == "__main__":
    main()

