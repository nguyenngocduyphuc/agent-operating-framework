"""Test isolation: pin the AOF workspace to this repository.

Without this, workspace_root() climbs to the OUTERMOST git repo above the test
cwd. When aof is vendored inside a host project (its normal deployment), that
host's .aof_policy.json leaks into the suite — e.g. a host policy that enables
require_karpathy makes every plain contract brief fail for reasons unrelated
to the code under test. Discovered 2026-07-20 the moment legacy policy keys
started being honoured instead of silently ignored.

Subprocess-based tests inherit os.environ, so setting the env here covers both
in-process calls and spawned servers. Tests that need a different workspace
set AOF_WORKSPACE explicitly and still win.
"""
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]


@pytest.fixture(autouse=True)
def _isolate_aof_workspace(monkeypatch):
    monkeypatch.setenv("AOF_WORKSPACE", str(REPO))
