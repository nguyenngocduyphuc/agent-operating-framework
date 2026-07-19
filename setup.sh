#!/bin/sh
# setup.sh -- AOF workspace config setup (config-only; code is installed separately).
#
# INSTALL FIRST:
#   uv tool install agent-operating-framework   # from PyPI (once published)
#   uv tool install .                           # from this clone
#   pip install .                               # fallback
#
# THEN run:
#   bash setup.sh [--yes] [target-dir]
#
# What this script does (Serena pattern: code lives in the tool, not the project):
#   1. Checks that the 'aof' command is installed.
#   2. Creates .aof_policy.json in the target (configuration, not code).
#   3. Creates the .agentframework workspace marker.
#   4. Prints MCP registration using the installed 'aof' command.
#
# POSIX sh, no dependencies beyond python3 and the installed 'aof' tool.
set -u

# --- Parse args ---
YES=0
TARGET=""
for arg in "$@"; do
    case "$arg" in
        --yes) YES=1 ;;
        *) TARGET="$arg" ;;
    esac
done

# ---------------------------------------------------------------------------
# 1. Require the 'aof' command -- fail fast and clearly
# ---------------------------------------------------------------------------
if ! command -v aof >/dev/null 2>&1; then
    echo "NEEDS ATTENTION: 'aof' command not found."
    echo ""
    echo "Install it first:"
    echo "  uv tool install .                            # from this clone"
    echo "  uv tool install agent-operating-framework   # from PyPI"
    echo "  pip install .                                # pip fallback"
    echo ""
    echo "Then re-run this script."
    exit 1
fi

AOF_VERSION="$(aof --version 2>&1 || true)"
echo "[setup] Found: $AOF_VERSION"

# ---------------------------------------------------------------------------
# 2. Determine TARGET
# ---------------------------------------------------------------------------
if [ -z "$TARGET" ]; then
    TARGET="$(pwd)"
fi

mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

# ---------------------------------------------------------------------------
# 3. Create .aof_policy.json from embedded template (config only -- no code copy)
# ---------------------------------------------------------------------------
if [ -f "$TARGET/.aof_policy.json" ]; then
    echo "[setup] kept existing .aof_policy.json"
else
    # ponytail: embed the template inline so no clone is required
    cat > "$TARGET/.aof_policy.json" << 'JSON'
{
  "workspace_name": "my-project",
  "require_task": false,
  "require_contract": true,
  "require_evidence": true,
  "require_handoff": true,
  "allow_bootstrap_without_task": true,
  "expected_repository": "",
  "credential_groups": {
    "TaskTracker": ["TRACKER_TOKEN"],
    "GitHub": ["GITHUB_TOKEN"]
  }
}
JSON
    echo "[setup] created .aof_policy.json (edit workspace_name and flags)"
fi

touch "$TARGET/.agentframework"
echo "[setup] .agentframework marker ready"

# ---------------------------------------------------------------------------
# 4. MCP registration -- point to the installed 'aof' command, not a local file
# ---------------------------------------------------------------------------
if command -v claude >/dev/null 2>&1; then
    echo "[setup] MCP register command:"
    echo "  claude mcp add aof -- aof start-mcp-server"
    if [ "$YES" = "0" ]; then
        printf "[setup] Run now? [Y/n] "
        read -r REPLY
        case "$REPLY" in
            n|N|no) echo "[setup] skipped MCP registration." ;;
            *)
                claude mcp add aof -- aof start-mcp-server 2>&1 || \
                    echo "[setup] MCP registration failed (run manually)."
                ;;
        esac
    else
        echo "[setup] Non-interactive mode -- run manually:"
        echo "  claude mcp add aof -- aof start-mcp-server"
    fi
else
    echo "[setup] MCP: add this block to your agent host's MCP config:"
    echo '  {'
    echo '    "mcpServers": {'
    echo '      "aof": {'
    echo '        "command": "aof",'
    echo '        "args": ["start-mcp-server"],'
    echo '        "env": {}'
    echo '      }'
    echo '    }'
    echo '  }'
fi

# ---------------------------------------------------------------------------
# 5. Done
# ---------------------------------------------------------------------------
echo ""
echo "AOF READY"
echo "  workspace: $TARGET"
echo "  tool:      $AOF_VERSION"
echo "  policy:    $TARGET/.aof_policy.json"
echo ""
echo "Next: edit .aof_policy.json, then register the MCP server with your agent host."
exit 0
