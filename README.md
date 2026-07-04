# GC Used Gear Scraper

Find **newly listed** used gear on [Guitar Center](https://www.guitarcenter.com) via their Algolia search index. Each used SKU has a `creationDate` (Unix milliseconds). Morning inventory drops typically land around **05:00–06:00 UTC**.

## Setup

```powershell
cd C:\Users\5540\projects\gc-used-scraper
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Local dashboard

Browse daily scrape output in a small web UI (sortable table, filters, click-through to GC).

**Start** (binds to all interfaces so others on your Wi‑Fi can connect):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start-dashboard.ps1
```

Or double-click `scripts\start-dashboard.bat`.

Default port: **8765** (override with `$env:GC_DASHBOARD_PORT = 9000` before starting).

| Who | URL |
|-----|-----|
| You (same PC) | http://127.0.0.1:8765/ |
| Partner (same Wi‑Fi) | http://YOUR_LAN_IP:8765/ |

The start script prints your LAN IP(s), e.g. `http://192.168.1.42:8765/`. Your partner opens that URL in a browser — no install needed on their device.

**Requirements:** Run `scripts\run-daily.ps1` at least once so `output/daily/YYYY-MM-DD/` exists. The dashboard reads `new-all.json`, `new-on-sale.json`, `used-price-drops.json`, and `by-category/<date>/*.csv`. The header shows **run history** (completed runs and data days).

**Windows Firewall:** If a partner cannot connect, allow inbound TCP on port 8765 for Private networks when prompted, or add a rule for `python.exe` on your private profile.

## Quick start

```powershell
# New listings in the last 24 hours
python scraper.py --since-hours 24 -o output/new.json

# Guitars only (preset)
python scraper.py --since-hours 24 --preset guitars -o output/guitars.json

# All used price drops on the site (any age)
python scraper.py --since-hours 1 --all-ages --price-drop -o output/drops.json

# New listings with a discount
python scraper.py --since-hours 36 --on-sale -o output/new-deals.json

# At least 15% below list price
python scraper.py --since-hours 36 --min-discount 15 -o output/deals.json

# List category presets
python scraper.py --list-presets
```

## Daily automation (Windows)

**One-shot daily run** (all new SKUs + price drops + on-sale + per-category CSVs):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-daily.ps1
```

**Check run history** (scheduled task + log files):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run-status.ps1
```

Output layout:

```
output/daily/2026-05-18/
  new-all.json          # deduped via data/seen_skus.txt
  used-price-drops.json   # all used GC price drops (~7k items)
  new-on-sale.json        # new listings with a discount
  by-category/2026-05-18/
    guitars.csv
    amps.csv
    ...
output/logs/run-2026-05-18.log
```

**Install scheduled task** (default: every day at 7:00 AM local):

```powershell
powershell -ExecutionPolicy Bypass -File scripts\install-scheduled-task.ps1

# Custom time
powershell -ExecutionPolicy Bypass -File scripts\install-scheduled-task.ps1 -Time "06:30"
```

Remove the task:

```powershell
Unregister-ScheduledTask -TaskName "GC-Used-Gear-Scraper" -Confirm:$false
```

## Category presets

| `--preset`   | GC category      |
|-------------|------------------|
| `guitars`   | Guitars          |
| `basses`    | Basses           |
| `amps`      | Amps & Effects   |
| `drums`     | Drums            |
| `keys`      | Keys & MIDI      |
| `recording` | Recording        |
| `live-sound`| Live Sound       |
| `dj`        | DJ               |
| `mics`      | Mics & Wireless  |
| `accessories` | Accessories    |
| `lighting`  | Lighting         |
| `band`      | Band & Orchestra |

Export **all** presets at once:

```powershell
python run_presets.py --since-hours 36 --output-dir output/presets --format csv
```

## CLI reference

| Flag | Description |
|------|-------------|
| `--since` | `YYYY-MM-DD`, ISO datetime, or Unix timestamp |
| `--since-hours` | Relative window, e.g. `24` or `36` |
| `--until` | Upper bound on `creationDate` |
| `--preset` | Category shortcut (see table) |
| `--category` | Raw GC `categories.lvl0` value |
| `--price-drop` | GC “Price Drop” savings facet |
| `--all-ages` | Skip `creationDate` filter (use with `--price-drop` for full catalog) |
| `--on-sale` | `price < list_price` |
| `--min-discount` | Minimum % off list (e.g. `15`) |
| `--min-price` / `--max-price` | Price range |
| `--known-skus` | Skip SKUs already in this file |
| `--update-known` | Append new SKUs after run |
| `-o` | Output `.json` or `.csv` |

## Output fields

`sku_id`, `gc_item_number`, `title`, `brand`, `price`, `list_price`, `discount_percent`, `savings_amount`, `is_price_drop`, `condition`, `store`, `created_at`, `url`

## Deploy to Hostinger VPS (Ubuntu)

To run the daily scraper and share the dashboard with a partner on a Linux server (cron, systemd, Nginx, HTTPS), see **[DEPLOY.md](DEPLOY.md)**.

## Notes

- The daily script uses a **36-hour** window so the UTC morning drop is always captured.
- Uses GC’s public Algolia search key (same as the website). Unofficial; may break if they change search.
- Musician's Friend not supported yet.
