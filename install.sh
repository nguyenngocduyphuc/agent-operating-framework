#!/usr/bin/env bash
# install.sh — one-command setup for agent-operating-framework
# Usage: bash install.sh [--mcp-json /path/to/.mcp.json]
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MCP_SERVER="$REPO_DIR/src/npflight_mcp.py"
CONFIG_DIR="$HOME/.npflight"
CONFIG_FILE="$CONFIG_DIR/config.json"
MCP_JSON="${1:-}"  # optional: path to .mcp.json to update

echo "── agent-operating-framework installer ──"

# 1. Create config dir
mkdir -p "$CONFIG_DIR"
echo "✅ Config dir: $CONFIG_DIR"

# 2. Copy example config if none exists
if [ ! -f "$CONFIG_FILE" ]; then
    cp "$REPO_DIR/examples/config.json" "$CONFIG_FILE"
    echo "✅ Created $CONFIG_FILE (edit to match your workspace)"
else
    echo "  ℹ  Config already exists: $CONFIG_FILE"
fi

# 3. Copy example OPERATING_PROTOCOL.md if user doesn't have one
PROTO_FILE="$CONFIG_DIR/OPERATING_PROTOCOL.md"
if [ ! -f "$PROTO_FILE" ]; then
    cp "$REPO_DIR/examples/OPERATING_PROTOCOL.md" "$PROTO_FILE"
    echo "✅ Created $PROTO_FILE (customize for your workflow)"
fi

# 4. Verify Python can run the server
if python3 -c "import json, os, re, subprocess, sys, uuid, datetime, time, fnmatch, urllib.request" 2>/dev/null; then
    echo "✅ Python stdlib check passed"
else
    echo "❌ Python 3 stdlib check failed — ensure python3 is available"
    exit 1
fi

# 5. Optionally patch .mcp.json
if [ -n "$MCP_JSON" ] && [ -f "$MCP_JSON" ]; then
    if command -v python3 &>/dev/null; then
        python3 - "$MCP_JSON" "$MCP_SERVER" <<'EOF'
import json, sys
path, server = sys.argv[1], sys.argv[2]
with open(path) as f:
    cfg = json.load(f)
cfg.setdefault("mcpServers", {})["operating-framework"] = {
    "command": "python3",
    "args": [server],
    "env": {}
}
with open(path, "w") as f:
    json.dump(cfg, f, indent=2)
    f.write("\n")
print(f"✅ Patched {path} → operating-framework registered")
EOF
    fi
else
    echo ""
    echo "── Manual .mcp.json registration ──"
    echo "Add this to your .mcp.json:"
    echo ""
    echo '  "operating-framework": {'
    echo "    \"command\": \"python3\","
    echo "    \"args\": [\"$MCP_SERVER\"],"
    echo '    "env": {}'
    echo '  }'
    echo ""
    echo "Or run:  bash install.sh --mcp-json /path/to/.mcp.json"
fi

echo ""
echo "── Next steps ──"
echo "1. Edit $CONFIG_FILE — set workspace, operating_protocol_path, gates"
echo "2. Set ASANA_TOKEN env var (if using post_evidence)"
echo "3. Restart Claude Code to pick up the new MCP server"
echo "4. In Claude: call preflight() to verify it works"
echo ""
echo "Done ✅"
