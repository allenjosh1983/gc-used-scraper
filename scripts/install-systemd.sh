#!/usr/bin/env bash
# Install gc-scraper systemd unit with the current user and project path.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
USER_NAME="$(id -un)"
GROUP_NAME="$(id -gn)"
UNIT_SRC="$ROOT/deploy/gc-scraper.service"
UNIT_DST="/etc/systemd/system/gc-scraper.service"

if [[ ! -f "$UNIT_SRC" ]]; then
  echo "Missing $UNIT_SRC"
  exit 1
fi

TMP="$(mktemp)"
sed \
  -e "s|YOUR_LINUX_USER|${USER_NAME}|g" \
  -e "s|/home/YOUR_LINUX_USER/gc-used-scraper|${ROOT}|g" \
  "$UNIT_SRC" > "$TMP"

echo "Installing systemd unit for user ${USER_NAME} at ${ROOT}"
sudo cp "$TMP" "$UNIT_DST"
rm -f "$TMP"

sudo systemctl daemon-reload
sudo systemctl enable gc-scraper
sudo systemctl restart gc-scraper
sudo systemctl status gc-scraper --no-pager
