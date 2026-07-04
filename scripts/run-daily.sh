#!/usr/bin/env bash
# Daily scrape: new used SKUs (36h window), dedupe, price drops, on-sale, category CSVs.
# Run manually or from cron — see DEPLOY.md

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON="python3"
fi

STAMP="$(date +%Y-%m-%d)"
OUT_DIR="$ROOT/output/daily/$STAMP"
LOG_DIR="$ROOT/output/logs"
mkdir -p "$OUT_DIR" "$LOG_DIR"

LOG_FILE="$LOG_DIR/run-$STAMP.log"

log() {
  local line
  line="$(date '+%Y-%m-%d %H:%M:%S') $*"
  echo "$line" | tee -a "$LOG_FILE"
}

log "=== GC used scraper daily run ==="

SINCE_HOURS=36

KNOWN_SKUS="$ROOT/data/seen_skus.txt"
ALL_JSON="$OUT_DIR/new-all.json"
log "Fetching all new used (last ${SINCE_HOURS}h)..."
"$PYTHON" "$ROOT/scraper.py" \
  --since-hours "$SINCE_HOURS" \
  --known-skus "$KNOWN_SKUS" \
  --update-known \
  -o "$ALL_JSON"
log "Wrote $ALL_JSON"

DEALS_JSON="$OUT_DIR/used-price-drops.json"
log "Fetching all used price drops..."
"$PYTHON" "$ROOT/scraper.py" \
  --since-hours 1 \
  --all-ages \
  --price-drop \
  -o "$DEALS_JSON"
log "Wrote $DEALS_JSON"

NEW_DEALS_JSON="$OUT_DIR/new-on-sale.json"
log "Fetching discounted new listings..."
"$PYTHON" "$ROOT/scraper.py" \
  --since-hours "$SINCE_HOURS" \
  --on-sale \
  -o "$NEW_DEALS_JSON"
log "Wrote $NEW_DEALS_JSON"

PRESET_DIR="$OUT_DIR/by-category"
log "Running category presets..."
"$PYTHON" "$ROOT/run_presets.py" \
  --since-hours "$SINCE_HOURS" \
  --output-dir "$PRESET_DIR" \
  --format csv

log "=== Done. Output: $OUT_DIR ==="
