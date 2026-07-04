# Deploy GC Used Scraper on Hostinger VPS (Ubuntu)

Step-by-step guide to run the daily scraper and share the dashboard with a partner on a Hostinger VPS (Ubuntu 22.04 or 24.04). Commands are copy-paste ready; run them **on your VPS** after you SSH in, unless noted as running on your Windows PC.

---

## What you will have when done

| Component | Purpose |
|-----------|---------|
| `scripts/run-daily.sh` | Daily scrape (cron) |
| `gc-scraper.service` | Dashboard always on (localhost only) |
| Nginx | HTTPS or HTTP on 80/443, optional password for partner |
| UFW firewall | SSH + web only; port 8765 **not** public |

---

## Prerequisites

- Hostinger VPS with **Ubuntu 22.04 or 24.04**
- Root or sudo access
- SSH from your PC (Hostinger panel shows IP, username, password or SSH key)
- Optional: a domain pointed at the VPS A record (for `https://yourdomain.com`)
- On Windows: PowerShell or [PuTTY](https://www.putty.org/) for SSH; [FileZilla](https://filezilla-project.org/) optional for SFTP

Replace placeholders in commands:

| Placeholder | Example |
|-------------|---------|
| `YOUR_VPS_IP` | `123.45.67.89` |
| `YOUR_LINUX_USER` | `root` or `ubuntu` |
| `YOUR_DOMAIN` | `gear.example.com` |
| Project path on VPS | `/home/YOUR_LINUX_USER/gc-used-scraper` |

---

## Step 1 — Connect to the VPS

On your **Windows PC**:

```powershell
ssh YOUR_LINUX_USER@YOUR_VPS_IP
```

First login may ask to accept the host key. Use the password from Hostinger or your SSH key.

Update packages:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip git nginx ufw apache2-utils
```

---

## Step 2 — Upload the project

Pick **one** method.

### Option A — Git (easiest if you use GitHub)

On the VPS:

```bash
cd ~
git clone https://github.com/YOUR_USER/gc-used-scraper.git
cd gc-used-scraper
```

Push your repo from Windows first if it is not on GitHub yet.

### Option B — `scp` from Windows (PowerShell)

On your **Windows PC** (not on the VPS):

```powershell
scp -r C:\Users\5540\projects\gc-used-scraper YOUR_LINUX_USER@YOUR_VPS_IP:~/gc-used-scraper
```

This copies the whole folder. Large `output/` folders are optional to upload; the scraper will recreate them.

### Option C — `rsync` (if you have rsync on Windows, e.g. WSL)

```bash
rsync -avz --exclude '.venv' --exclude 'output' --exclude '__pycache__' \
  /mnt/c/Users/5540/projects/gc-used-scraper/ \
  YOUR_LINUX_USER@YOUR_VPS_IP:~/gc-used-scraper/
```

### Option D — SFTP (FileZilla)

1. Host: `sftp://YOUR_VPS_IP`, user/password from Hostinger, port `22`
2. Upload the project folder to `/home/YOUR_LINUX_USER/gc-used-scraper`
3. Skip `.venv` and optionally `output/` (recreated on server)

---

## Step 3 — Python environment

On the VPS:

```bash
cd ~/gc-used-scraper

python3 --version
# Should be 3.11+; Ubuntu 24.04 ships 3.12. On 22.04, 3.10 works; for 3.11+:
# sudo apt install -y python3.11 python3.11-venv

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

Create data directory for SKU deduplication (gitignored locally):

```bash
mkdir -p data output/logs
touch data/seen_skus.txt
```

Test a manual daily run:

```bash
chmod +x scripts/run-daily.sh
./scripts/run-daily.sh
```

Check log and output:

```bash
ls -la output/daily/
tail -20 output/logs/run-$(date +%Y-%m-%d).log
```

---

## Step 4 — Schedule daily scrape (cron)

Morning inventory on Guitar Center is around **05:00–06:00 UTC**. A **36-hour** window in `run-daily.sh` covers that regardless of timezone.

Edit crontab:

```bash
crontab -e
```

Add one line (7:00 AM **server local time** — adjust hour if needed):

```cron
0 7 * * * /home/YOUR_LINUX_USER/gc-used-scraper/scripts/run-daily.sh >> /home/YOUR_LINUX_USER/gc-used-scraper/output/logs/cron.log 2>&1
```

Use the full path to your install. List cron jobs:

```bash
crontab -l
```

---

## Step 5 — Dashboard as a systemd service

The dashboard listens on **127.0.0.1:8765** only (not the public internet). Nginx will expose it safely.

```bash
cd ~/gc-used-scraper
chmod +x scripts/install-systemd.sh
./scripts/install-systemd.sh
```

This copies `deploy/gc-scraper.service` with your real Linux user and project path (no manual `YOUR_LINUX_USER` edits).

Manual install (if you prefer):

```bash
nano deploy/gc-scraper.service
# Replace YOUR_LINUX_USER and /home/YOUR_LINUX_USER/gc-used-scraper

sudo cp deploy/gc-scraper.service /etc/systemd/system/gc-scraper.service
sudo systemctl daemon-reload
sudo systemctl enable gc-scraper
sudo systemctl start gc-scraper
sudo systemctl status gc-scraper
```

Test locally on the VPS:

```bash
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8765/
# Expect 200 after at least one daily run created output/daily/
```

Logs:

```bash
journalctl -u gc-scraper -f
```

---

## Step 6 — Nginx reverse proxy (partner access)

Do **not** open port 8765 in the firewall. Partners reach the dashboard through Nginx on **8080** (recommended on Hostinger when LiteSpeed already uses port 80) or **80/443**.

### Hostinger note (LiteSpeed on port 80)

Many Hostinger VPS images run **LiteSpeed on port 80**. If `nginx` fails with `bind() to 0.0.0.0:80 failed`, use the **8080** config instead of port 80:

```bash
sudo cp deploy/nginx-gc-dashboard-8080.conf.example /etc/nginx/sites-available/gc-dashboard
```

If another nginx site still listens on 80, disable it so nginx can start:

```bash
ls /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/jallendevworks   # example — only if it conflicts
```

Partner URL: **`http://YOUR_VPS_IP:8080/`**

### HTTP basic auth (recommended)

```bash
sudo htpasswd -c /etc/nginx/.htpasswd-gc-dashboard partner_name
# Enter a password when prompted
```

### Configure Nginx

```bash
cd ~/gc-used-scraper
# Port 8080 (Hostinger / LiteSpeed):
sudo cp deploy/nginx-gc-dashboard-8080.conf.example /etc/nginx/sites-available/gc-dashboard
# Or standard port 80:
# sudo cp deploy/nginx-gc-dashboard.conf.example /etc/nginx/sites-available/gc-dashboard
sudo nano /etc/nginx/sites-available/gc-dashboard
```

- **With a domain:** use the first `server` block; set `server_name YOUR_DOMAIN;`
- **IP only:** comment out the domain block and uncomment **Option B** at the bottom of the file (`server_name _;`)

Enable the site:

```bash
sudo rm -f /etc/nginx/sites-enabled/default
sudo ln -s /etc/nginx/sites-available/gc-dashboard /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### HTTPS with Let's Encrypt (domain required)

Point your domain's **A record** to `YOUR_VPS_IP` in Hostinger DNS, wait a few minutes, then:

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d YOUR_DOMAIN
```

Certbot adds SSL and renewal. Re-open the Nginx site file and ensure `auth_basic` is still inside the `location /` block certbot uses (certbot may create a new `server` block for 443).

### How your partner opens the dashboard

| Setup | Partner URL | Login |
|-------|-------------|--------|
| Domain + HTTPS | `https://YOUR_DOMAIN/` | HTTP basic auth user/password |
| Domain, HTTP only | `http://YOUR_DOMAIN/` | Same |
| No domain | `http://YOUR_VPS_IP:8080/` (LiteSpeed hosts) or `http://YOUR_VPS_IP/` | Same |

They do not need Python or any install—only a browser.

### Disable public access (keep scraper on VPS)

To stop partners from reaching the dashboard without uninstalling:

```bash
chmod +x scripts/toggle-public-access.sh
./scripts/toggle-public-access.sh off
```

Re-enable later:

```bash
./scripts/toggle-public-access.sh on
```

Cron and `output/daily/` keep running; only the public nginx URL is turned off.

### Check how often the scraper ran (VPS)

```bash
ls output/logs/run-*.log | wc -l
ls output/daily/
tail -5 output/logs/run-$(date +%Y-%m-%d).log
```

The dashboard also shows run history at `/api/stats` and in the **Run history** panel.

---

## Step 7 — Firewall (UFW)

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

Allowed: **22** (SSH), **80**, **443**. Port **8765** stays closed to the internet; only Nginx on localhost talks to the dashboard.

---

## Security notes

- **Do not commit secrets** — `.env` files, private API keys, or partner passwords belong only on the server. This project uses Guitar Center's **public** Algolia search key (same as the website); it is search-only, not a secret credential.
- **Use basic auth** (or VPN) before exposing the dashboard on a public IP.
- **Keep the system updated:** `sudo apt update && sudo apt upgrade` periodically.
- **SSH:** prefer SSH keys over passwords; disable root password login in Hostinger/hardening guides when comfortable.
- **Backups:** `data/seen_skus.txt` and `output/daily/` are valuable; copy them off the VPS occasionally.

---

## Updating the app

**Git:**

```bash
cd ~/gc-used-scraper
git pull
source .venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart gc-scraper
```

**SCP/rsync:** upload changed files, then restart the service as above.

---

## Troubleshooting

| Problem | What to check |
|---------|----------------|
| Cron did not run | `grep CRON /var/log/syslog`; paths in `crontab -l`; `chmod +x scripts/run-daily.sh` |
| Empty dashboard | Run `./scripts/run-daily.sh` once; `ls output/daily/` |
| 502 Bad Gateway | `sudo systemctl status gc-scraper`; dashboard on `127.0.0.1:8765` |
| Partner cannot connect | UFW allows 8080 or 80/443; Nginx running; correct IP/domain |
| Nginx won't start (port 80 in use) | LiteSpeed on 80 — use `nginx-gc-dashboard-8080.conf.example`; remove conflicting `sites-enabled` entries |
| Auth loop | Correct username/password; file `/etc/nginx/.htpasswd-gc-dashboard` |
| Scraper errors | `tail -50 output/logs/run-*.log`; `source .venv/bin/activate` and run `python scraper.py --since-hours 24 -o /tmp/test.json` |
| `bad interpreter` or `/bin/bash^M` after upload from Windows | Shell scripts need Unix (LF) line endings. On the VPS: `sed -i 's/\r$//' scripts/run-daily.sh` then `chmod +x scripts/run-daily.sh`. Re-upload from Git, or convert locally before `scp`/SFTP. |

---

## Quick reference

```bash
# Manual scrape
~/gc-used-scraper/scripts/run-daily.sh

# Dashboard service
sudo systemctl restart gc-scraper
journalctl -u gc-scraper -n 50

# Nginx
sudo nginx -t && sudo systemctl reload nginx
```

---

## File map (deployment)

| File | Role |
|------|------|
| `DEPLOY.md` | This guide |
| `scripts/run-daily.sh` | Linux daily scrape for cron |
| `deploy/gc-scraper.service` | systemd unit for dashboard |
| `deploy/nginx-gc-dashboard-8080.conf.example` | Nginx on port 8080 (Hostinger / LiteSpeed) |
| `scripts/toggle-public-access.sh` | Enable/disable partner URL |
| `scripts/install-systemd.sh` | Install dashboard systemd unit |
| `scripts/run-status.ps1` | Windows run history summary |
