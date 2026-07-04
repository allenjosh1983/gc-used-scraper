#!/usr/bin/env bash
# Enable or disable public dashboard access via nginx (port 8080 by default).
# Run on the VPS: ./scripts/toggle-public-access.sh off|on|status

set -euo pipefail

ACTION="${1:-status}"
SITE_NAME="gc-dashboard"
SITES_AVAILABLE="/etc/nginx/sites-available/${SITE_NAME}"
SITES_ENABLED="/etc/nginx/sites-enabled/${SITE_NAME}"
PORT="${GC_DASHBOARD_PUBLIC_PORT:-8080}"

status() {
  if [[ -L "$SITES_ENABLED" || -f "$SITES_ENABLED" ]]; then
    echo "Public access: ENABLED (nginx site linked)"
    echo "Partner URL: http://YOUR_VPS_IP:${PORT}/"
  else
    echo "Public access: DISABLED (nginx site not enabled)"
  fi
  if command -v systemctl >/dev/null 2>&1; then
    systemctl is-active nginx 2>/dev/null && echo "nginx: running" || echo "nginx: not running"
  fi
}

disable() {
  if [[ -L "$SITES_ENABLED" || -f "$SITES_ENABLED" ]]; then
    sudo rm -f "$SITES_ENABLED"
    echo "Removed $SITES_ENABLED"
  else
    echo "Already disabled."
  fi
  sudo nginx -t
  sudo systemctl reload nginx
  echo "Public dashboard access disabled. Scraper files and cron are unchanged."
}

enable() {
  if [[ ! -f "$SITES_AVAILABLE" ]]; then
    echo "Missing $SITES_AVAILABLE"
    echo "Copy deploy/nginx-gc-dashboard-8080.conf.example there first."
    exit 1
  fi
  sudo ln -sf "$SITES_AVAILABLE" "$SITES_ENABLED"
  sudo nginx -t
  sudo systemctl reload nginx
  echo "Public dashboard access enabled on port ${PORT}."
  echo "Partner URL: http://YOUR_VPS_IP:${PORT}/"
}

case "$ACTION" in
  on|enable) enable ;;
  off|disable) disable ;;
  status) status ;;
  *)
    echo "Usage: $0 {on|off|status}"
    exit 1
    ;;
esac
