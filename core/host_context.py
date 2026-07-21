"""Host / cmux identity for audit rows — so estate can group by workspace.

Stdlib only. Reads optional env vars that cmux (and AOF) set; never requires cmux.
Empty values are omitted so older ledgers stay readable.
"""
from __future__ import annotations

import os
from typing import Any

# Known cmux session identity env (observed on cmux agent launches).
_CMUX_ENV = (
    ("cmux_workspace_id", "CMUX_WORKSPACE_ID"),
    ("cmux_surface_id", "CMUX_SURFACE_ID"),
    ("cmux_panel_id", "CMUX_PANEL_ID"),
    ("cmux_tab_id", "CMUX_TAB_ID"),
    ("cmux_agent_kind", "CMUX_AGENT_LAUNCH_KIND"),
    ("cmux_agent_cwd", "CMUX_AGENT_LAUNCH_CWD"),
)


def capture_host_context(**extra: Any) -> dict[str, Any]:
    """Snapshot host identity for one audit event."""
    ctx: dict[str, Any] = {}
    aof_ws = os.environ.get("AOF_WORKSPACE")
    if aof_ws:
        ctx["aof_workspace"] = aof_ws
    try:
        ctx["cwd"] = os.getcwd()
    except OSError:
        pass
    for key, env_name in _CMUX_ENV:
        val = os.environ.get(env_name)
        if val:
            ctx[key] = val
    for k, v in extra.items():
        if v is not None and v != "":
            ctx[k] = v
    return ctx


def workspace_key(entry: dict[str, Any] | None) -> str:
    """Stable label for estate grouping (prefer cmux workspace, then AOF paths)."""
    if not entry:
        return "(unknown)"
    for k in (
        "cmux_workspace_id",
        "workspace",  # preflight card field
        "aof_workspace",
        "cmux_agent_cwd",
        "cwd",
    ):
        v = entry.get(k)
        if v:
            return str(v)
    return "(unknown)"
