#!/bin/sh
# Post AOF estate effectiveness to a GitHub tracking issue.
# Runs on the MACHINE that has ~/.aof ledgers (not inside empty CI).
#
# Usage:
#   bash scripts/post_effectiveness_to_github.sh [days] [--save-json]
# Requires: gh auth, network; aof or PYTHONPATH=repo python -m core.cli
set -u

DAYS=7
SAVE_JSON=0
for a in "$@"; do
  case "$a" in
    --save-json) SAVE_JSON=1 ;;
    '' ) ;;
    *[!0-9.]* ) ;;
    *) DAYS="$a" ;;
  esac
done

ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

if command -v aof >/dev/null 2>&1; then
  CLI="aof"
else
  CLI="python3 -m core.cli"
fi

if ! command -v gh >/dev/null 2>&1; then
  echo "gh CLI required (https://cli.github.com/). Abort."
  exit 1
fi

REPO="${AOF_GH_REPO:-nguyenngocduyphuc/agent-operating-framework}"
LABEL="effectiveness"
TITLE="AOF Effectiveness Tracker"

# Ensure label (ignore errors)
gh label create "$LABEL" --repo "$REPO" --color "0E8A16" --description "Operational effectiveness metrics" 2>/dev/null || true

# Find or create tracking issue (compatible with older gh without create --json)
NUM="$(gh issue list --repo "$REPO" --label "$LABEL" --state open --limit 30 \
  --json number,title 2>/dev/null \
  --jq ".[] | select(.title|test(\"Effectiveness Tracker\"; \"i\")) | .number" | head -1)"

if [ -z "${NUM:-}" ]; then
  # fallback: search title without label filter
  NUM="$(gh issue list --repo "$REPO" --state open --limit 50 --search "Effectiveness Tracker in:title" \
    --json number,title 2>/dev/null --jq '.[0].number' | head -1)"
fi

if [ -z "${NUM:-}" ]; then
  BODY_FILE="$(mktemp)"
  cat >"$BODY_FILE" <<'EOF'
# AOF Effectiveness Tracker

This issue is the **GitHub cockpit** for operational effectiveness (not CI build status).

## How metrics get here
- Host machine runs `bash scripts/post_effectiveness_to_github.sh [days]`
- Or MCP no-code: `status_report` / `estate_report` + file `~/.aof/estate/HIEU_QUA_HOM_NAY.md`
- Optional JSON snapshots: `docs/metrics/YYYY-MM-DD.json` (with `--save-json`)

## Targets (dogfood)
| KPI | Target |
|---|---|
| handoffs / work-day | ≥ 1 |
| resumes / week | ≥ 3 |
| blocked when stuck | > 0 if real blocks |
| noise_session_rate | trend down |
| verify_fail_rate | watched, not zero-forced |

See `docs/MASTER_PLAN.md` and `docs/metrics/README.md`.
EOF
  CREATED_URL="$(gh issue create --repo "$REPO" --title "$TITLE" --label "$LABEL" --body-file "$BODY_FILE")"
  rm -f "$BODY_FILE"
  NUM="$(printf '%s' "$CREATED_URL" | grep -oE '[0-9]+$')"
  echo "Created tracking issue #$NUM ($CREATED_URL)"
else
  echo "Using tracking issue #$NUM"
fi

if [ -z "${NUM:-}" ]; then
  echo "Could not create or find tracking issue."
  exit 3
fi

# Generate reports
PULSE_JSON="$(mktemp)"
PULSE_TXT="$(mktemp)"
eval "$CLI estate-report --days \"$DAYS\" --json" >"$PULSE_JSON" 2>/dev/null || {
  echo "estate-report failed. Is AOF installed / PYTHONPATH set?"
  exit 2
}
eval "$CLI estate-report --days \"$DAYS\" --lang vi" >"$PULSE_TXT" 2>/dev/null || true

STAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
HOST="$(hostname 2>/dev/null || echo unknown)"

COMMENT_FILE="$(mktemp)"
{
  echo "## Pulse — last ${DAYS} day(s)"
  echo ""
  echo "- **UTC:** $STAMP"
  echo "- **Host:** \`$HOST\` (ledger: local \`~/.aof\`)"
  echo "- **Source:** \`scripts/post_effectiveness_to_github.sh\`"
  echo ""
  echo '```'
  # Prefer short KPI extract from JSON
  python3 - "$PULSE_JSON" <<'PY'
import json,sys
from pathlib import Path
p=Path(sys.argv[1])
try:
    r=json.loads(p.read_text())
except Exception as e:
    print("json read error", e)
    sys.exit(0)
k=r.get("kpis") or {}
keys=["sessions","sessions_productive","sessions_noise","noise_session_rate",
      "preflight_clear","preflight_blocked","verify_pass","verify_fail","verify_fail_rate",
      "done","blocked","handoffs","resumes","open_errors","workspaces_seen","cmux_workspaces_seen"]
for key in keys:
    if key in k:
        print(f"{key}: {k[key]}")
pws=r.get("per_workspace") or {}
if pws:
    print("--- per_workspace (top 5) ---")
    items=sorted(pws.items(), key=lambda kv: (-(kv[1].get("productive") or 0), -(kv[1].get("sessions") or 0)))[:5]
    for name, info in items:
        short=name if len(name)<48 else name[:20]+"…"+name[-12:]
        print(f"{short}: sess={info.get('sessions')} prod={info.get('productive')} "
              f"h/r={info.get('handoffs')}/{info.get('resumes')} "
              f"pf={info.get('preflight_clear')}/{info.get('preflight_blocked')}")
PY
  echo '```'
  echo ""
  echo "<details><summary>Full estate text (vi)</summary>"
  echo ""
  echo '```'
  head -c 12000 "$PULSE_TXT" 2>/dev/null || true
  echo '```'
  echo "</details>"
} >"$COMMENT_FILE"

gh issue comment "$NUM" --repo "$REPO" --body-file "$COMMENT_FILE"
echo "Commented on https://github.com/$REPO/issues/$NUM"

if [ "$SAVE_JSON" = "1" ]; then
  mkdir -p "$ROOT/docs/metrics"
  OUT="$ROOT/docs/metrics/$(date +%Y-%m-%d).json"
  cp "$PULSE_JSON" "$OUT"
  echo "Wrote $OUT (commit manually if you want history in git)"
fi

rm -f "$PULSE_JSON" "$PULSE_TXT" "$COMMENT_FILE"
