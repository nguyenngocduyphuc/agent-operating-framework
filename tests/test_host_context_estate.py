"""Host/cmux identity on audit + estate per-workspace grouping."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

from core.enforcement import audit_file
from core.estate import build_estate_report, format_estate_report
from core.host_context import capture_host_context, workspace_key

REPO = Path(__file__).resolve().parents[1]


def test_capture_host_context_reads_cmux_env(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AOF_WORKSPACE", "/ws/main")
    monkeypatch.setenv("CMUX_WORKSPACE_ID", "WS-AAAA-BBBB")
    monkeypatch.setenv("CMUX_SURFACE_ID", "SURF-1")
    monkeypatch.setenv("CMUX_AGENT_LAUNCH_KIND", "grok")
    monkeypatch.delenv("CMUX_PANEL_ID", raising=False)
    ctx = capture_host_context()
    assert ctx["aof_workspace"] == "/ws/main"
    assert ctx["cmux_workspace_id"] == "WS-AAAA-BBBB"
    assert ctx["cmux_surface_id"] == "SURF-1"
    assert ctx["cmux_agent_kind"] == "grok"
    assert "cmux_panel_id" not in ctx
    assert workspace_key(ctx) == "WS-AAAA-BBBB"


def test_workspace_key_fallback_order():
    assert workspace_key({"cwd": "/a", "aof_workspace": "/b"}) == "/b"
    assert workspace_key({"cwd": "/a"}) == "/a"
    assert workspace_key({}) == "(unknown)"


def test_session_start_audit_includes_cmux_identity(tmp_path, monkeypatch):
    aof_home = tmp_path / "aofhome"
    aof_home.mkdir()
    monkeypatch.setenv("AOF_AUDIT_DIR", str(aof_home))
    monkeypatch.setenv("CMUX_WORKSPACE_ID", "WS-TEST-ID")
    monkeypatch.setenv("CMUX_SURFACE_ID", "SURF-TEST")
    monkeypatch.setenv("AOF_WORKSPACE", str(tmp_path))
    # spawn mcp server briefly so main() writes session_start
    server = REPO / "core" / "mcp_server.py"
    env = {**os.environ, "PYTHONPATH": str(REPO), "AOF_AUDIT_DIR": str(aof_home),
           "CMUX_WORKSPACE_ID": "WS-TEST-ID", "CMUX_SURFACE_ID": "SURF-TEST",
           "AOF_WORKSPACE": str(tmp_path)}
    proc = subprocess.Popen(
        [sys.executable, str(server)],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, env=env,
    )
    try:
        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0", "id": 1, "method": "initialize",
            "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                       "clientInfo": {"name": "t", "version": "0"}},
        }) + "\n")
        proc.stdin.flush()
        proc.stdout.readline()
    finally:
        proc.stdin.close()
        proc.wait(timeout=5)

    lines = audit_file().read_text(encoding="utf-8").splitlines()
    starts = [json.loads(L) for L in lines if '"session_start"' in L]
    assert starts, "session_start must be audited"
    row = starts[0]
    assert row.get("cmux_workspace_id") == "WS-TEST-ID"
    assert row.get("cmux_surface_id") == "SURF-TEST"


def test_estate_groups_by_workspace(tmp_path, monkeypatch):
    aof_home = tmp_path / "aofhome"
    aof_home.mkdir()
    monkeypatch.setenv("AOF_AUDIT_DIR", str(aof_home))
    now = time.time()
    audit = [
        {
            "event": "session_start", "_session": "sA", "_ts": now - 100,
            "cmux_workspace_id": "WS-A", "cmux_surface_id": "S1",
            "aof_workspace": "/ws/A",
        },
        {
            "event": "preflight", "status": "clear", "_session": "sA", "_ts": now - 90,
            "cmux_workspace_id": "WS-A", "workspace": "/ws/A", "repo": "repoA",
        },
        {
            "event": "session_handoff", "_session": "sA", "_ts": now - 80,
            "cmux_workspace_id": "WS-A", "path": "/ws/A/repo/docs/sessions/H.md",
        },
        {
            "event": "session_start", "_session": "sB", "_ts": now - 70,
            "cmux_workspace_id": "WS-B", "cmux_surface_id": "S2",
        },
        {
            "event": "session_end", "_session": "sB", "_ts": now - 60,
            "cmux_workspace_id": "WS-B",
        },
    ]
    audit_file().write_text("\n".join(json.dumps(e) for e in audit) + "\n", encoding="utf-8")
    r = build_estate_report(window_hours=1)
    assert "WS-A" in r["per_workspace"]
    assert "WS-B" in r["per_workspace"]
    assert r["per_workspace"]["WS-A"]["productive"] >= 1
    assert r["per_workspace"]["WS-A"]["handoffs"] >= 1
    assert r["per_workspace"]["WS-A"]["preflight_clear"] >= 1
    assert r["per_workspace"]["WS-B"]["noise"] >= 1
    assert r["kpis"]["cmux_workspaces_seen"] >= 1
    text = format_estate_report(r, "en")
    assert "Per workspace" in text
    assert "WS-A" in text
