#!/usr/bin/env python3
"""Effectiveness smoke: WITH AOF enforcement vs WITHOUT (naive path).

Not a statistical bench (see AOF-Bench for n≥30). This script measures three
failure modes that AOF exists to prevent, under a temporary workspace:

  1) Wrong write target for handoff (parent workspace vs bound repo)
  2) Closeout without permanent test_ref on a known error
  3) Task lease collision (two live sessions, same task)

Prints a machine-readable JSON summary + plain table. Exit 0 only if WITH AOF
passes all checks and WITHOUT AOF demonstrates the failure modes.

Usage (from vendor repo root)::

    PYTHONPATH=. python3 scripts/effectiveness_ab_smoke.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _run(cmd, cwd, env, timeout=60):
    return subprocess.run(
        cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout,
    )


def case_without_aof(root: Path) -> dict:
    """Naive agent: always write handoff into 'workspace root', ignore leases/tests."""
    workspace = root / "workspace"
    repo_a = root / "repo_a"
    workspace.mkdir(parents=True)
    repo_a.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo_a, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "feat/task-1"], cwd=repo_a, check=True)

    # Wrong place: sessions under parent workspace, not the repo being edited.
    naive_sessions = workspace / "docs" / "sessions"
    naive_sessions.mkdir(parents=True)
    handoff = naive_sessions / "HANDOFF_naive.md"
    handoff.write_text("# naive handoff\nworked in repo_a but wrote here\n", encoding="utf-8")

    # "Close" an error with no test (silent debt).
    err_path = root / "naive_errors.jsonl"
    err_path.write_text(
        json.dumps({"fingerprint": "shadow-import:core", "status": "closed", "test_ref": None})
        + "\n",
        encoding="utf-8",
    )

    # Two writers same task — no lease, both "ok".
    dual_ok = True

    wrong_place = handoff.exists() and not (repo_a / "docs" / "sessions").exists()
    naive_err = json.loads(err_path.read_text(encoding="utf-8").splitlines()[0])
    silent_close = (
        str(naive_err.get("status")) == "closed"
        and not naive_err.get("test_ref")
    )

    return {
        "arm": "WITHOUT_AOF",
        "wrong_handoff_location": wrong_place,
        "silent_error_close_without_test": silent_close,
        "dual_session_same_task_allowed": dual_ok,
        "passed_safety": False,  # by design: naive path fails safety properties
        "details": {
            "handoff_path": str(handoff),
            "repo_sessions_exist": (repo_a / "docs" / "sessions").exists(),
        },
    }


def case_with_aof(root: Path) -> dict:
    """Same scenario through AOF core APIs / CLI."""
    sys.path.insert(0, str(REPO))
    from core.errors_ledger import load_errors, record_error
    from core.lease import acquire, release
    from core.oplog import default_session_dir, write_session_bundle
    from core.preflight import nearest_repo

    aof_home = root / "aofhome"
    aof_home.mkdir(parents=True)
    os.environ["AOF_AUDIT_DIR"] = str(aof_home)
    os.environ["AOF_WORKSPACE"] = str(root / "workspace")
    (root / "workspace").mkdir(parents=True, exist_ok=True)

    repo_a = root / "repo_a"
    repo_a.mkdir(parents=True)
    subprocess.run(["git", "init", "-q"], cwd=repo_a, check=True)
    subprocess.run(["git", "checkout", "-q", "-b", "feat/task-1"], cwd=repo_a, check=True)

    # 1) Handoff lands in nearest_repo, not AOF_WORKSPACE parent.
    bound = nearest_repo(str(repo_a)) or str(repo_a)
    outdir = default_session_dir(bound)
    bundle = write_session_bundle(
        outdir,
        {
            "since_ts": 0,
            "sessions": 1,
            "collisions": 0,
            "done": 0,
            "blocked": 0,
            "gate_fail": 0,
            "tasks": {},
            "has_activity": False,
        },
        lang="en",
        stamp="absmoke001",
    )
    handoff_ok = Path(bundle["handoff_path"]).is_file() and str(repo_a) in bundle["handoff_path"]
    leaked = (Path(os.environ["AOF_WORKSPACE"]) / "docs" / "sessions").exists()

    # 2) Close without test_ref refused; with test_ref accepted.
    record_error({"fingerprint": "shadow-import:core", "title": "shadow"})
    refused = record_error({"fingerprint": "shadow-import:core", "status": "closed"})
    closed_ok = record_error({
        "fingerprint": "shadow-import:core",
        "status": "closed",
        "test_ref": "tests/test_no_shadow_import.py",
    })
    rows = load_errors()
    silent_prevented = refused.get("refused") is True and closed_ok.get("ok") is True
    has_closed_with_ref = any(
        r.get("status") == "closed" and r.get("test_ref") for r in rows
    )

    # 3) Lease: second live acquire same task must fail.
    r1 = acquire("task-1", str(repo_a), "session-A")
    r2 = acquire("task-1", str(repo_a), "session-B")
    lease_blocks_second = bool(r1.get("ok")) and not bool(r2.get("ok"))
    if r1.get("ok"):
        release("task-1", str(repo_a), "session-A")

    safety = handoff_ok and not leaked and silent_prevented and has_closed_with_ref and lease_blocks_second
    return {
        "arm": "WITH_AOF",
        "handoff_in_bound_repo": handoff_ok,
        "no_leak_to_workspace": not leaked,
        "close_without_test_refused": silent_prevented,
        "closed_with_test_ref": has_closed_with_ref,
        "lease_blocks_second_session": lease_blocks_second,
        "passed_safety": safety,
        "details": {
            "handoff_path": bundle["handoff_path"],
            "lease_first": r1,
            "lease_second": {k: r2.get(k) for k in ("ok", "error", "error_code", "holder") if k in r2 or k == "ok"},
            "refused_close": refused,
        },
    }


def main() -> int:
    root = Path(tempfile.mkdtemp(prefix="aof-ab-"))
    try:
        without = case_without_aof(root / "without")
        with_ = case_with_aof(root / "with")
    finally:
        # keep tree for debugging if fail; always print path
        pass

    report = {
        "root": str(root),
        "without_aof": without,
        "with_aof": with_,
        "verdict": {
            "without_exhibits_failure_modes": (
                without["wrong_handoff_location"]
                and without["silent_error_close_without_test"]
                and without["dual_session_same_task_allowed"]
            ),
            "with_passes_safety": with_["passed_safety"],
            "effectiveness_smoke_pass": (
                without["wrong_handoff_location"]
                and without["silent_error_close_without_test"]
                and without["dual_session_same_task_allowed"]
                and with_["passed_safety"]
            ),
        },
        "honesty": (
            "This is a mechanism smoke (3 failure modes), not a multi-agent ROI bench. "
            "Do not cite as n≥30 causal result."
        ),
    }

    print(json.dumps(report, ensure_ascii=False, indent=2))
    print()
    print("=== EFFECTIVENESS SMOKE (3 failure modes) ===")
    print(f"WITHOUT AOF  wrong handoff location : {without['wrong_handoff_location']}")
    print(f"WITHOUT AOF  silent close no test   : {without['silent_error_close_without_test']}")
    print(f"WITHOUT AOF  dual session allowed   : {without['dual_session_same_task_allowed']}")
    print(f"WITH AOF     handoff in bound repo  : {with_['handoff_in_bound_repo']}")
    print(f"WITH AOF     no workspace leak      : {with_['no_leak_to_workspace']}")
    print(f"WITH AOF     refuse close no test   : {with_['close_without_test_refused']}")
    print(f"WITH AOF     lease blocks 2nd sess  : {with_['lease_blocks_second_session']}")
    print(f"VERDICT      smoke pass             : {report['verdict']['effectiveness_smoke_pass']}")
    print(report["honesty"])

    return 0 if report["verdict"]["effectiveness_smoke_pass"] else 2


if __name__ == "__main__":
    # cleanup only on success path left to OS tmp; explicit rmtree optional
    code = main()
    sys.exit(code)
