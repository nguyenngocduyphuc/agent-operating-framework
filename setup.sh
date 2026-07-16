#!/bin/sh
# setup.sh — AOF zero-dependency workspace setup
#   bash setup.sh [--yes] [target-dir]          — from cloned repo
#   curl -fsSL <raw-url> | bash -s -- [--yes] <target-dir>  — pipe mode
#
# Single command → everything ready. POSIX sh, only needs git + python3.
set -u

REPO_URL="https://github.com/nguyenngocduyphuc/agent-operating-framework.git"

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
# 1. Locate source (clone if running via curl pipe)
# ---------------------------------------------------------------------------
SCRIPT_DIR="$(cd "$(dirname "$0")" 2>/dev/null && pwd)"
TMP_REPO=""
if [ ! -f "$SCRIPT_DIR/core/preflight.py" ]; then
    echo "[setup] cloning AOF repository ..."
    TMP_REPO="$(mktemp -d /tmp/aof-setup-XXXXXX 2>/dev/null || mktemp -d /tmp/aof-setup-XXXXXXXX)"
    git clone -q --depth 1 "$REPO_URL" "$TMP_REPO" || {
        echo "NEEDS ATTENTION: git clone failed. Ensure git is installed and the URL is reachable:"
        echo "  $REPO_URL" >&2
        rm -rf "$TMP_REPO"
        exit 1
    }
    SCRIPT_DIR="$TMP_REPO"
fi

# ---------------------------------------------------------------------------
# 2. Determine TARGET
# ---------------------------------------------------------------------------
if [ -z "$TARGET" ]; then
    TARGET="$(pwd)"
    # Refuse to use the kernel repo as its own target
    if [ -f "$TARGET/core/preflight.py" ]; then
        echo "NEEDS ATTENTION: specify a target directory (running from AOF repo itself)."
        echo "  bash setup.sh /path/to/your-project/" >&2
        [ -n "$TMP_REPO" ] && rm -rf "$TMP_REPO"
        exit 1
    fi
fi

mkdir -p "$TARGET"
TARGET="$(cd "$TARGET" && pwd)"

# Pre-flight checks
command -v python3 >/dev/null 2>&1 || {
    echo "NEEDS ATTENTION: python3 not found. Install Python 3.10+ and ensure it is on PATH." >&2
    [ -n "$TMP_REPO" ] && rm -rf "$TMP_REPO"
    exit 1
}

# ---------------------------------------------------------------------------
# 3. Copy runtime files
# ---------------------------------------------------------------------------
mkdir -p "$TARGET/core"
cp -R "$SCRIPT_DIR/core/." "$TARGET/core/"
cp "$SCRIPT_DIR/.aof_policy.example.json" "$TARGET/"

if [ -f "$TARGET/.aof_policy.json" ]; then
    echo "[setup] kept existing .aof_policy.json"
else
    cp "$SCRIPT_DIR/.aof_policy.example.json" "$TARGET/.aof_policy.json"
fi

touch "$TARGET/.agentframework"

if [ -d "$SCRIPT_DIR/adapters" ]; then
    mkdir -p "$TARGET/adapters"
    cp -R "$SCRIPT_DIR/adapters/." "$TARGET/adapters/"
fi

# ---------------------------------------------------------------------------
# 4. Git init (if target not yet a repo)
# ---------------------------------------------------------------------------
if [ ! -d "$TARGET/.git" ]; then
    (cd "$TARGET" && git init -q)
    USER_NAME="$(git config user.name 2>/dev/null || true)"
    USER_EMAIL="$(git config user.email 2>/dev/null || true)"
    if [ -z "$USER_NAME" ] || [ -z "$USER_EMAIL" ]; then
        (cd "$TARGET" && git -c user.name="AOF Setup" -c user.email="setup@aof.local" commit -q --allow-empty -m "aof init") 2>/dev/null || true
    else
        (cd "$TARGET" && git commit -q --allow-empty -m "aof init") 2>/dev/null || true
    fi
fi

# ---------------------------------------------------------------------------
# 5. Smoke test
# ---------------------------------------------------------------------------
SMOKE_OUTPUT="$(cd "$TARGET" && python3 -m core.preflight --json 2>&1 || true)"
SMOKE_STATUS="$(echo "$SMOKE_OUTPUT" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('status', 'error'))
except Exception:
    print('error')
" 2>/dev/null || echo "error")"

# ---------------------------------------------------------------------------
# 6. MCP registration hint
# ---------------------------------------------------------------------------
if command -v claude >/dev/null 2>&1; then
    echo "[setup] MCP register command:"
    echo "  claude mcp add aof -- python3 -m core.mcp_server"
    if [ "$YES" = "0" ]; then
        printf "[setup] Run now? [Y/n] "
        read -r REPLY
        case "$REPLY" in
            n|N|no) echo "[setup] skipped MCP registration." ;;
            *)
                (cd "$TARGET" && eval "claude mcp add aof -- python3 -m core.mcp_server") 2>&1 || \
                    echo "[setup] MCP registration command failed (run manually)."
                ;;
        esac
    else
        echo "[setup] Non-interactive mode — run manually:"
        echo "  claude mcp add aof -- python3 -m core.mcp_server"
    fi
else
    echo "[setup] MCP: add this block to your agent host's MCP config:"
    echo '  {'
    echo '    "mcpServers": {'
    echo '      "aof": {'
    echo '        "command": "python3",'
    echo '        "args": ["-m", "core.mcp_server"],'
    echo '        "env": {}'
    echo '      }'
    echo '    }'
    echo '  }'
fi

# ---------------------------------------------------------------------------
# 7. Final status
# ---------------------------------------------------------------------------
case "$SMOKE_STATUS" in
    clear|warn)
        echo "AOF READY — preflight $SMOKE_STATUS"
        [ -n "$TMP_REPO" ] && rm -rf "$TMP_REPO"
        exit 0
        ;;
    *)
        echo "NEEDS ATTENTION: preflight reports '$SMOKE_STATUS'. Run 'python3 -m core.preflight' in $TARGET for details." >&2
        [ -n "$TMP_REPO" ] && rm -rf "$TMP_REPO"
        exit 1
        ;;
esac
