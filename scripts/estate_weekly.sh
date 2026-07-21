#!/bin/sh
# Weekly estate HTML for CEO glance. Optional cmux open if available.
# Usage: bash scripts/estate_weekly.sh [days]
set -u
DAYS="${1:-7}"
ROOT="$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)"
OUT_DIR="${AOF_ESTATE_OUT:-$HOME/.aof/estate/weekly}"
mkdir -p "$OUT_DIR"
STAMP="$(date +%Y%m%d)"
OUT="$OUT_DIR/ESTATE_${STAMP}.html"

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"
python3 -m core.cli estate-report --days "$DAYS" --html --snapshot --lang vi --out "$OUT"
echo "wrote $OUT"

if command -v cmux >/dev/null 2>&1; then
  # Best-effort: open output directory in cmux (non-fatal).
  cmux open "$OUT_DIR" 2>/dev/null || cmux "$OUT_DIR" 2>/dev/null || true
fi

echo "Next: aof lessons ; aof improve-check --window-hours $((DAYS * 24))"
