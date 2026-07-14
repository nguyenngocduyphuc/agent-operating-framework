#!/usr/bin/env python3
"""AOF full-flow demo — plan -> decompose -> dispatch -> verify -> evidence.

Runs end-to-end with zero setup beyond stdlib. No real Asana token required:
when TRACKER_TOKEN is unset it runs in DRY mode and prints what WOULD be posted.

Run from the repo root:
    python3 examples/full_flow_demo.py
"""
import os
import subprocess
import sys
from pathlib import Path

# Make `core` and `adapters` importable when run as a bare script from the repo root.
REPO = Path(__file__).resolve().parent.parent
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from core.check_contract import validate  # noqa: E402


def _load_adapter():
    try:
        from adapters import asana_adapter
        return asana_adapter
    except Exception:
        import importlib.util
        p = REPO / "adapters" / "asana_adapter.py"
        spec = importlib.util.spec_from_file_location("asana_adapter", p)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod


SAMPLE_BRIEF = (
    "Task: Add a /health endpoint to the API\n"
    "Owner: codex-worker\n"
    "Scope: src/api/health.py, src/api/__init__.py\n"
    "DoD: GET /health returns 200 with {\"status\":\"ok\"} and a test proves it\n"
    "Do not: touch deploy config, modify the database, add dependencies\n"
    "Stop if: the fix needs any file outside src/api/\n"
    "Return: diff + pytest results + evidence link\n"
    "References: docs/architecture.md#health-checks (internal), none-external (trivial)\n"
)

SAMPLE_TASK_GID = "0000000000000000"  # placeholder — no real workspace GID


def hr(title):
    print("\n" + "=" * 64)
    print(title)
    print("=" * 64)


def main():
    hr("AOF FULL-FLOW DEMO — plan -> decompose -> dispatch -> verify -> evidence")

    # ---- Step 1: Plan / load the brief ----
    hr("[1/5] PLAN — load a task brief (7 contract fields + References)")
    print(SAMPLE_BRIEF)

    # ---- Step 2: check_contract (task decomposition gate) ----
    hr("[2/5] DECOMPOSE — validate the execution contract")
    result = validate(SAMPLE_BRIEF)
    print(f"  contract ok:       {result['ok']}")
    print(f"  found fields:      {result['found']}")
    print(f"  missing required:  {result['missing_required']}")
    if not result["ok"]:
        print("  -> contract incomplete; a real run would STOP here and return a blocker.")
        return 2

    # ---- Step 3: dispatch to worker (stub — workspace-specific in real use) ----
    hr("[3/5] DISPATCH — hand the scoped task to a worker (stubbed)")
    print(f"  would dispatch to worker: {result['found'][0] if result['found'] else 'worker'}")
    print("  (real dispatch is workspace-specific: scripts/dispatch.py / cmux — out of scope here)")
    print("  worker returns: diff + test output; orchestrator then verifies below.")

    # ---- Step 4: verify_gate (trivially verifiable: py_compile on this file) ----
    hr("[4/5] VERIFY — run a real gate (py_compile on this demo)")
    gate = subprocess.run(
        [sys.executable, "-m", "py_compile", str(Path(__file__).resolve())],
        capture_output=True, text=True,
    )
    verify_ok = gate.returncode == 0
    print(f"  gate: py_compile -> exit {gate.returncode} ({'PASS' if verify_ok else 'FAIL'})")
    if not verify_ok:
        print(f"  stderr: {gate.stderr.strip()}")
        return 1

    # ---- Step 5: post_evidence (real if TRACKER_TOKEN set, else DRY) ----
    hr("[5/5] EVIDENCE — post closeout (DRY unless a real tracker is configured)")
    adapter = _load_adapter()
    token = adapter.load_token()
    tracker_type = os.environ.get("TRACKER_TYPE", "").lower()
    exit_code = 0 if verify_ok else 1
    evidence = (
        f"AOF demo evidence — resolution={'Done' if exit_code == 0 else 'Blocked'} "
        f"| gate=py_compile exit={gate.returncode} | task={SAMPLE_TASK_GID}"
    )
    if token and tracker_type == "asana":
        print("  TRACKER_TOKEN present + TRACKER_TYPE=asana -> posting for real...")
        out = adapter.post_comment(SAMPLE_TASK_GID, evidence, token)
        print(f"  post_comment result: {out}")
    else:
        print("  DRY mode (no TRACKER_TOKEN / TRACKER_TYPE!=asana). Would POST this comment:")
        print(f"    task_gid: {SAMPLE_TASK_GID}")
        print(f"    comment:  {evidence}")
        print("  Set TRACKER_TYPE=asana + TRACKER_TOKEN=<pat> to post for real.")

    hr("DONE — you just saw plan -> decompose -> dispatch -> verify -> evidence")
    return 0


if __name__ == "__main__":
    sys.exit(main())
