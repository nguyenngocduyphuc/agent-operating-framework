"""The server must run ITS OWN preflight even when the host workspace carries
a stale `core/` copy at its root.

Live incident 2026-07-21: the MCP server was registered for a workspace whose
root contains an old `core/` package (pre-migration). `-m core.preflight` put
the server cwd at sys.path[0], the stale copy shadowed the canonical one, and
preflight answered fail-open "clear" on a legacy hard-mode policy — the exact
bug class (silent enforcement loss) this framework exists to prevent.
"""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SERVER = REPO / "core" / "mcp_server.py"

DECOY = """\
import json, sys
print(json.dumps({"status": "clear", "blockers": [], "warnings": ["DECOY RAN"],
                  "workspace": "decoy", "repo": "decoy", "branch": "decoy",
                  "task": None, "cwd": ".", "protocol": "x", "policy": {},
                  "credentials_present": [], "credentials_missing": {}}))
sys.exit(0)
"""


def test_stale_core_copy_in_workspace_cannot_shadow_preflight(tmp_path):
    # Host workspace with a DECOY core/ package and a legacy hard-mode policy.
    ws = tmp_path / "host"
    (ws / "core").mkdir(parents=True)
    (ws / "core" / "__init__.py").write_text("")
    (ws / "core" / "preflight.py").write_text(DECOY)
    (ws / ".aof_policy.json").write_text(
        json.dumps({"require_asana_task": True, "allow_bootstrap_without_task": True}),
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)

    reqs = (
        json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize"}) + "\n"
        + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                      "params": {"name": "preflight", "arguments": {"cwd": str(ws)}}}) + "\n"
    )
    # Server spawned with cwd INSIDE the host workspace — the shadowing setup.
    r = subprocess.run(
        [sys.executable, str(SERVER)],
        input=reqs, capture_output=True, text=True, timeout=30,
        cwd=ws,
        env={"PYTHONPATH": str(REPO), "AOF_WORKSPACE": str(ws),
             "AOF_AUDIT_DIR": str(tmp_path / "aofhome"),
             "PATH": "/usr/bin:/bin:/usr/local/bin"},
    )
    body = None
    for line in r.stdout.splitlines():
        m = json.loads(line)
        if m.get("id") == 2:
            body = json.loads(m["result"]["content"][0]["text"])
    assert body is not None, r.stdout + r.stderr
    assert "DECOY RAN" not in json.dumps(body), "stale core/ copy was executed!"
    # The CANONICAL preflight honours the legacy hard-mode policy: taskless -> blocked.
    assert body["status"] == "blocked", body
    assert any("No task bound" in b for b in body["blockers"])
