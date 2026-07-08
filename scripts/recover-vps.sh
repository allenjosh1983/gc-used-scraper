#!/usr/bin/env bash
# One-shot recovery: dashboard backend + nginx on port 8080.
# Run on the VPS (Hostinger browser terminal):
#   cd ~/gc-used-scraper && chmod +x scripts/recover-vps.sh && ./scripts/recover-vps.sh

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "=== GC scraper recovery ==="
echo "Project: $ROOT"
echo ""

# 1) Python env
if [[ ! -x "$ROOT/.venv/bin/python" ]]; then
  echo "Creating venv..."
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip
  .venv/bin/pip install -r requirements.txt
fi

mkdir -p data output/logs output/daily
touch data/seen_skus.txt

# 2) Scrape if no data yet
if [[ -z "$(ls -A output/daily 2>/dev/null || true)" ]]; then
  echo "No daily output yet — running scrape (may take a minute)..."
  chmod +x scripts/run-daily.sh
  sed -i 's/\r$//' scripts/run-daily.sh 2>/dev/null || true
  ./scripts/run-daily.sh
fi

# 3) systemd dashboard
chmod +x scripts/install-systemd.sh
sed -i 's/\r$//' scripts/install-systemd.sh 2>/dev/null || true
./scripts/install-systemd.sh

# 4) nginx on 8080
if [[ ! -f /etc/nginx/.htpasswd-gc-dashboard ]]; then
  echo ""
  echo "Creating dashboard login (username: partner)"
  sudo htpasswd -bc /etc/nginx/.htpasswd-gc-dashboard partner changeme123
  echo ">>> Change password later: sudo htpasswd /etc/nginx/.htpasswd-gc-dashboard partner"
fi

sudo cp deploy/nginx-gc-dashboard-8080.conf.example /etc/nginx/sites-available/gc-dashboard
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -sf /etc/nginx/sites-available/gc-dashboard /etc/nginx/sites-enabled/gc-dashboard

# Drop other enabled sites that bind port 80 and break nginx start
for site in /etc/nginx/sites-enabled/*; do
  [[ "$(basename "$site")" == "gc-dashboard" ]] && continue
  if sudo grep -q 'listen 80' "$site" 2>/dev/null; then
    echo "Disabling conflicting site: $(basename "$site")"
    sudo rm -f "$site"
  fi
done

sudo nginx -t
sudo systemctl enable nginx gc-scraper
sudo systemctl restart gc-scraper
sudo systemctl restart nginx

echo ""
echo "=== Status ==="
sudo systemctl is-active gc-scraper nginx
sudo ss -tlnp | grep -E ':8080|:8765' || true

CODE8080="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8080/ || echo 000)"
CODE8765="$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8765/ || echo 000)"
echo "Local test 8080 (nginx): $CODE8080  (want 401 or 200)"
echo "Local test 8765 (app):     $CODE8765  (want 200)"
echo ""
IP="$(curl -s ifconfig.me 2>/dev/null || hostname -I | awk '{print $1}')"
echo "Open in browser: http://${IP}:8080/"
echo "Login user: partner  (password: changeme123 if just created)"
echo "See username: sudo cat /etc/nginx/.htpasswd-gc-dashboard | cut -d: -f1"
