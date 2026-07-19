#!/usr/bin/env python3
"""Validate the portable AOF execution-contract fields from stdin.

Requires line-start ``Field: non-empty value`` format.  Prose that merely
contains the field name (e.g. "Task Owner Scope DoD") does NOT pass.

When the workspace policy sets ``require_karpathy``, three extra structural
checks run.  They are deliberately NOT keyword counts over the prose: each one
binds to machinery that executes later, so a contract that passes has to keep
paying for the claim it made.

  1. Think before coding   -> an ``Assumptions:``/``Tradeoffs:`` line must exist
     and carry substance.  (Weakest check -- see ``KARPATHY_LIMITS``.)
  2. Goal-driven execution -> a ``DoD-cmd:`` must exist and not be a no-op.  The
     server binds it to the ``dod`` gate and RUNS it, so a fake command fails at
     verify time instead of passing silently.
  3. Simplicity / surgical -> ``Scope:`` must be bounded.  A wildcard-only glob
     means "I may touch anything", which ``audit_scope`` would then wave through.
"""
import json
import sys

REQUIRED = ("Task", "Owner", "Scope", "DoD", "Do not", "Stop if", "Return")

# --- Karpathy mode ---------------------------------------------------------
ASSUMPTION_FIELDS = ("Assumptions", "Tradeoffs")
MIN_ASSUMPTION_CHARS = 20
# ponytail: a literal denylist, not a command analyser. It rejects the laziest
# no-ops only; `python -c pass` still gets through (see KARPATHY_LIMITS).
TRIVIAL_DOD_CMDS = frozenset({"true", ":", "false", "exit", "exit 0", "echo ok"})
# A glob built solely from these characters matches the entire tree.
_WILDCARD_CHARS = frozenset("*./")

KARPATHY_LIMITS = (
    "These checks test the STRUCTURE of the contract, not the truth of what it "
    "says. 'Assumptions: none that matter for this change' passes. The value is "
    "that the claim exists, is named, and lands in the audit trail where a "
    "reviewer can hold you to it -- detection, not prevention."
)


def _field_value(lines, field):
    """First line-start ``field:`` value, or None. Same rule as REQUIRED."""
    for line in lines:
        if line.startswith(field + ":"):
            return line[len(field) + 1:].strip()
    return None


def _is_unbounded_glob(entry):
    """True when a scope entry matches the whole tree (``*``, ``**/*``, ``.``)."""
    stripped = entry.strip()
    while stripped.startswith("./"):
        stripped = stripped[2:]
    return not stripped or set(stripped) <= _WILDCARD_CHARS


def _karpathy_findings(brief):
    """Return a list of {principle, problem, fix} for every failed check."""
    lines = brief.split("\n")
    findings = []

    stated = [v for v in (_field_value(lines, f) for f in ASSUMPTION_FIELDS) if v]
    if not stated:
        findings.append({
            "principle": "1. Think before coding",
            "problem": "No `Assumptions:` or `Tradeoffs:` line in the brief.",
            "fix": "Add a line starting `Assumptions: ` naming what you took as "
                   "given and what breaks if it is wrong. If you weighed options, "
                   "use `Tradeoffs: ` and say what you gave up.",
        })
    elif max(len(v) for v in stated) < MIN_ASSUMPTION_CHARS:
        findings.append({
            "principle": "1. Think before coding",
            "problem": f"`Assumptions:`/`Tradeoffs:` is present but under "
                       f"{MIN_ASSUMPTION_CHARS} characters -- a placeholder, not a stated assumption.",
            "fix": "Write what you are assuming and the consequence of it being wrong.",
        })

    dod_cmd = _field_value(lines, "DoD-cmd")
    if not dod_cmd:
        findings.append({
            "principle": "4. Goal-driven execution",
            "problem": "No `DoD-cmd:` line -- the DoD is prose, so nothing can prove it.",
            "fix": "Add `DoD-cmd: <command>` that fails when the work is not done "
                   "(e.g. `DoD-cmd: python -m pytest tests/test_health.py`). The "
                   "server runs it via verify_gate with gate_type='dod'.",
        })
    elif dod_cmd.strip().lower() in TRIVIAL_DOD_CMDS:
        findings.append({
            "principle": "4. Goal-driven execution",
            "problem": f"`DoD-cmd: {dod_cmd}` is a no-op -- it passes whether or not the work is done.",
            "fix": "Point DoD-cmd at a real test or check that fails before the "
                   "change and passes after.",
        })

    scope = _field_value(lines, "Scope")
    entries = [s.strip() for s in (scope or "").split(",") if s.strip()]
    unbounded = [e for e in entries if _is_unbounded_glob(e)]
    if entries and unbounded:
        findings.append({
            "principle": "2/3. Simplicity first + surgical changes",
            "problem": f"Scope entries {unbounded} match the whole tree, so "
                       "audit_scope can never catch drift.",
            "fix": "List the files or directories you actually intend to touch "
                   "(e.g. `Scope: core/mcp_server.py, tests/test_mcp_server.py`).",
        })

    return findings


def _karpathy_hint(findings):
    """Render a teachable block message: what is missing and how to fix it."""
    out = [
        "BLOCKED by policy require_karpathy: the brief shows no auditable thinking "
        "before code. Fix each item below in the brief, then call check_contract again.",
        "",
    ]
    for f in findings:
        out.append(f["principle"])
        out.append(f"  problem: {f['problem']}")
        out.append(f"  fix:     {f['fix']}")
        out.append("")
    out.append(f"Limits of this check: {KARPATHY_LIMITS}")
    return "\n".join(out)


def validate(brief: str, require_karpathy: bool = False) -> dict:
    lines = brief.split("\n")
    found = []
    dod_cmd = None
    for line in lines:
        for field in REQUIRED:
            if line.startswith(field + ":"):
                val = line[len(field) + 1:].strip()
                if val and field not in found:
                    found.append(field)
        # OPTIONAL line-start field — never part of REQUIRED (backward compatible)
        if dod_cmd is None and line.startswith("DoD-cmd:"):
            cmd_val = line[len("DoD-cmd:"):].strip()
            if cmd_val:
                dod_cmd = cmd_val
    missing = [f for f in REQUIRED if f not in found]
    result = {"ok": not missing, "found": found, "missing_required": missing,
              "dod_cmd": dod_cmd, "karpathy_required": bool(require_karpathy)}

    if require_karpathy:
        findings = _karpathy_findings(brief)
        result["karpathy_ok"] = not findings
        result["karpathy_findings"] = findings
        result["karpathy_limits"] = KARPATHY_LIMITS
        if findings:
            result["ok"] = False
            result["hint"] = _karpathy_hint(findings)

    return result


def main() -> None:
    result = validate(sys.stdin.read())
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["ok"] else 2)


if __name__ == "__main__":
    main()
