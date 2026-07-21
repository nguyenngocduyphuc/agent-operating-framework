"""Legacy (v1) policy schema must keep its teeth under the v2 loader.

Incident encoded here (2026-07-20 audit): a hard-mode workspace declared
``require_asana_task: true`` (v1 name). The v2 loader only read ``require_task``,
defaulted it to false, and preflight answered "clear" with no task bound. A
policy rename must NEVER silently disable enforcement — fail-open by renaming
is the worst failure mode a gate can have.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

from core.preflight import load_policy

REPO = Path(__file__).resolve().parents[1]


def _write(ws, policy: dict):
    (ws / ".aof_policy.json").write_text(json.dumps(policy), encoding="utf-8")


def test_legacy_require_asana_task_maps_to_require_task(tmp_path):
    _write(tmp_path, {"require_asana_task": True})
    p = load_policy(str(tmp_path))
    assert p["require_task"] is True
    assert p["policy_migrated_keys"] == ["require_asana_task -> require_task"]


def test_legacy_require_ponytail_maps_to_require_karpathy(tmp_path):
    _write(tmp_path, {"require_ponytail": True})
    p = load_policy(str(tmp_path))
    assert p["require_karpathy"] is True


def test_explicit_modern_key_wins_over_legacy(tmp_path):
    """When both names are present, the modern key is authoritative."""
    _write(tmp_path, {"require_asana_task": True, "require_task": False})
    p = load_policy(str(tmp_path))
    assert p["require_task"] is False
    assert "policy_migrated_keys" not in p


def test_legacy_hard_mode_actually_blocks_taskless_preflight(tmp_path):
    """End to end: v1 policy, no task, no bootstrap -> exit 2, blocked."""
    _write(tmp_path, {"require_asana_task": True, "allow_bootstrap_without_task": True})
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    env = {**os.environ, "AOF_WORKSPACE": str(tmp_path), "PYTHONPATH": str(REPO)}
    r = subprocess.run(
        [sys.executable, "-m", "core.preflight", "--json"],
        cwd=tmp_path, env=env, capture_output=True, text=True,
    )
    assert r.returncode == 2, "legacy hard mode must BLOCK, not fail open"
    card = json.loads(r.stdout)
    assert card["status"] == "blocked"
    assert any("No task bound" in b for b in card["blockers"])
    assert any("Legacy policy key" in w for w in card["warnings"]), (
        "the migration must be visible, not silent"
    )


def test_modern_policy_unaffected(tmp_path):
    _write(tmp_path, {"require_task": False})
    p = load_policy(str(tmp_path))
    assert p["require_task"] is False
    assert "policy_migrated_keys" not in p


def test_worker_stale_after_s_default_and_override(tmp_path):
    """F4-1: policy key for worker hang threshold; default 300 when unset."""
    p0 = load_policy(str(tmp_path))  # no file → defaults
    assert p0.get("worker_stale_after_s") == 300
    _write(tmp_path, {"worker_stale_after_s": 120})
    p1 = load_policy(str(tmp_path))
    assert p1["worker_stale_after_s"] == 120
