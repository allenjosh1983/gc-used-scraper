#!/usr/bin/env python3
"""Local HTTP dashboard for GC used scraper daily output."""

from __future__ import annotations

import argparse
import csv
import json
import re
import socket
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
DAILY_DIR = ROOT / "output" / "daily"
LOG_DIR = ROOT / "output" / "logs"
DASHBOARD_DIR = Path(__file__).resolve().parent

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

JSON_SOURCES = {
    "new-all": "new-all.json",
    "new-on-sale": "new-on-sale.json",
    "used-price-drops": "used-price-drops.json",
}


def local_ips() -> list[str]:
    ips: list[str] = []
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            ips.append(s.getsockname()[0])
    except OSError:
        pass
    try:
        ips.extend(
            info[4][0]
            for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)
        )
    except OSError:
        pass
    seen: set[str] = set()
    out: list[str] = []
    for ip in ips:
        if ip and ip not in seen and not ip.startswith("127."):
            seen.add(ip)
            out.append(ip)
    return out


def parse_run_log(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    completed = "=== Done." in text
    started_at: str | None = None
    for line in text.splitlines():
        if "=== GC used scraper daily run ===" in line:
            started_at = line[:19] if len(line) >= 19 else None
            break
    return {
        "date": path.stem.removeprefix("run-"),
        "completed": completed,
        "started_at": started_at,
        "updated_at": iso_mtime(path),
        "log_path": str(path.relative_to(ROOT)),
    }


def run_stats() -> dict:
    dates = list_dates()
    runs: list[dict] = []
    if LOG_DIR.is_dir():
        for path in sorted(LOG_DIR.glob("run-*.log"), reverse=True):
            if DATE_RE.match(path.stem.removeprefix("run-")):
                runs.append(parse_run_log(path))
    completed = sum(1 for run in runs if run["completed"])
    latest = runs[0] if runs else None
    return {
        "total_run_days": len(runs),
        "completed_runs": completed,
        "incomplete_runs": len(runs) - completed,
        "data_days": len(dates),
        "latest_run": latest,
        "runs": runs[:30],
    }


def list_dates() -> list[str]:
    if not DAILY_DIR.is_dir():
        return []
    dates = [
        p.name
        for p in DAILY_DIR.iterdir()
        if p.is_dir() and DATE_RE.match(p.name)
    ]
    return sorted(dates, reverse=True)


def date_dir(date: str) -> Path:
    if not DATE_RE.match(date):
        raise ValueError("invalid date")
    path = (DAILY_DIR / date).resolve()
    if not path.is_dir() or DAILY_DIR.resolve() not in path.parents:
        raise FileNotFoundError(date)
    return path


def iso_mtime(path: Path) -> str | None:
    if not path.is_file():
        return None
    ts = path.stat().st_mtime
    return datetime.fromtimestamp(ts, tz=timezone.utc).isoformat()


def parse_bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in ("1", "true", "yes", "y")


def normalize_row(row: dict) -> dict:
    out: dict = {}
    for key, val in row.items():
        if val is None or val == "":
            out[key] = None
            continue
        if key in ("price", "list_price", "discount_percent", "savings_amount"):
            try:
                out[key] = float(val)
            except (TypeError, ValueError):
                out[key] = val
        elif key == "is_price_drop":
            out[key] = parse_bool(val)
        else:
            out[key] = val
    if out.get("category") is None and row.get("_category"):
        out["category"] = row["_category"]
    return out


def load_json_file(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ValueError("expected JSON array")
    return [normalize_row(item) for item in data]


def load_csv_file(path: Path, category: str) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            row["_category"] = category
            rows.append(normalize_row(row))
    return rows


def list_categories(day: Path) -> list[str]:
    base = day / "by-category"
    if not base.is_dir():
        return []
    names: set[str] = set()
    for sub in base.iterdir():
        if sub.is_dir():
            for csv_path in sub.glob("*.csv"):
                names.add(csv_path.stem)
        elif sub.suffix.lower() == ".csv":
            names.add(sub.stem)
    return sorted(names)


def load_category(day: Path, category: str) -> list[dict]:
    if not re.match(r"^[a-z0-9-]+$", category):
        raise ValueError("invalid category")
    base = day / "by-category"
    candidates = [
        base / f"{category}.csv",
        base / day.name / f"{category}.csv",
    ]
    for sub in base.iterdir() if base.is_dir() else []:
        if sub.is_dir():
            candidates.append(sub / f"{category}.csv")
    for path in candidates:
        if path.is_file():
            return load_csv_file(path, category)
    raise FileNotFoundError(category)


_SOURCE_LABELS = {
    "new-all": "New listings (all)",
    "new-on-sale": "New on sale",
    "used-price-drops": "Used price drops",
}


def sources_for_date(day: Path) -> dict:
    json_available = [
        {"id": key, "label": _SOURCE_LABELS[key], "path": name}
        for key, name in JSON_SOURCES.items()
        if (day / name).is_file()
    ]
    categories = list_categories(day)
    return {"json": json_available, "categories": categories}


def load_source(day: Path, source: str) -> tuple[list[dict], Path | None]:
    if source in JSON_SOURCES:
        path = day / JSON_SOURCES[source]
        if not path.is_file():
            raise FileNotFoundError(source)
        return load_json_file(path), path
    if source.startswith("category:"):
        cat = source.split(":", 1)[1]
        rows = load_category(day, cat)
        return rows, None
    raise ValueError("unknown source")


class DashboardHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DASHBOARD_DIR), **kwargs)

    def log_message(self, fmt: str, *args) -> None:
        print(f"[dashboard] {self.address_string()} - {fmt % args}")

    def end_headers(self) -> None:
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path.startswith("/api/"):
            self._handle_api(parsed)
            return
        if parsed.path in ("", "/"):
            self.path = "/index.html"
        return super().do_GET()

    def _send_json(self, status: int, payload: dict) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _handle_api(self, parsed) -> None:
        qs = parse_qs(parsed.query)
        try:
            if parsed.path == "/api/dates":
                return self._send_json(200, {"dates": list_dates()})

            if parsed.path == "/api/stats":
                return self._send_json(200, run_stats())

            date = (qs.get("date") or [None])[0]
            if not date:
                return self._send_json(400, {"error": "date required"})

            day = date_dir(date)

            if parsed.path == "/api/sources":
                return self._send_json(200, {"date": date, **sources_for_date(day)})

            if parsed.path == "/api/meta":
                meta = {"date": date, "files": {}}
                for key, name in JSON_SOURCES.items():
                    p = day / name
                    if p.is_file():
                        meta["files"][key] = {
                            "path": str(p.relative_to(ROOT)),
                            "updated_at": iso_mtime(p),
                            "count": len(load_json_file(p)),
                        }
                cats = list_categories(day)
                meta["categories"] = cats
                return self._send_json(200, meta)

            if parsed.path == "/api/listings":
                source = (qs.get("source") or ["new-all"])[0]
                rows, path = load_source(day, source)
                updated = iso_mtime(path) if path else None
                return self._send_json(
                    200,
                    {
                        "date": date,
                        "source": source,
                        "count": len(rows),
                        "updated_at": updated,
                        "items": rows,
                    },
                )

            return self._send_json(404, {"error": "not found"})
        except FileNotFoundError:
            return self._send_json(404, {"error": "not found"})
        except ValueError as exc:
            return self._send_json(400, {"error": str(exc)})

    def list_directory(self, path: str) -> None:
        self.send_error(403, "Directory listing forbidden")


def main() -> int:
    parser = argparse.ArgumentParser(description="GC used gear scraper dashboard")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    args = parser.parse_args()

    if not DAILY_DIR.is_dir():
        print(f"Note: {DAILY_DIR} does not exist yet. Run scripts/run-daily.ps1 first.")

    server = ThreadingHTTPServer((args.host, args.port), DashboardHandler)
    host_label = "127.0.0.1" if args.host in ("0.0.0.0", "::") else args.host
    print("GC Used Gear Dashboard")
    print(f"  Local:   http://{host_label}:{args.port}/")
    for ip in local_ips():
        print(f"  LAN:     http://{ip}:{args.port}/")
    print("Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
