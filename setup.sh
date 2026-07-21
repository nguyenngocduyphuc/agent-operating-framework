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
# 1. Prefer installed 'aof'; allow clone-local fallback for pre-publish
# ---------------------------------------------------------------------------
AOF_BIN=""
if command -v aof >/dev/null 2>&1; then
    AOF_BIN="$(command -v aof)"
elif [ -f "$(dirname "$0")/core/cli.py" ]; then
    # running from a git clone before pip install
    AOF_BIN="python3 -m core.cli"
    ROOT_CLONE="$(CDPATH= cd -- "$(dirname "$0")" && pwd)"
    export PYTHONPATH="$ROOT_CLONE${PYTHONPATH:+:$PYTHONPATH}"
    echo "[setup] Using clone-local CLI (pip install . recommended for production)."
else
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

AOF_VERSION="$(eval "$AOF_BIN --version" 2>&1 || true)"
echo "[setup] Found: $AOF_VERSION ($AOF_BIN)"

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
  "require_karpathy": true,
  "require_contract": true,
  "require_evidence": true,
  "require_handoff": true,
  "allow_bootstrap_without_task": true,
  "worker_stale_after_s": 300,
  "expected_repository": "",
  "report_language": "vi",
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
# Prefer absolute path to aof binary to avoid PATH/shadow issues.
if [ -n "${AOF_BIN:-}" ] && [ -x "$AOF_BIN" ]; then
    MCP_CMD="$AOF_BIN"
    MCP_ARGS="start-mcp-server"
else
    MCP_CMD="aof"
    MCP_ARGS="start-mcp-server"
fi
if command -v claude >/dev/null 2>&1; then
    echo "[setup] MCP register command (absolute tool preferred):"
    echo "  claude mcp add aof -- $MCP_CMD $MCP_ARGS"
    if [ "$YES" = "0" ]; then
        printf "[setup] Run now? [Y/n] "
        read -r REPLY
        case "$REPLY" in
            n|N|no) echo "[setup] skipped MCP registration." ;;
            *)
                claude mcp add aof -- $MCP_CMD $MCP_ARGS 2>&1 || \
                    echo "[setup] MCP registration failed (run manually)."
                ;;
        esac
    else
        echo "[setup] Non-interactive mode -- run manually:"
        echo "  claude mcp add aof -- $MCP_CMD $MCP_ARGS"
    fi
else
    echo "[setup] MCP: add this block to your agent host's MCP config:"
    echo '  {'
    echo '    "mcpServers": {'
    echo '      "aof": {'
    echo "        \"command\": \"$MCP_CMD\","
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
echo "  karpathy:  require_karpathy=true (default — agent must state Assumptions + DoD-cmd)"
echo ""
echo "Next:"
echo "  1. aof doctor \"$TARGET\""
echo "  2. Register MCP with the installed 'aof' command (absolute tool path preferred)."
echo "  3. Do NOT use: python -m core.mcp_server from a monorepo root (shadow risk)."
echo "  4. Dogfood: docs/DOGFOOD_7DAY_VI.md"
exit 0
