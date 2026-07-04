#!/usr/bin/env python3
"""Run the scraper for every category preset and write separate output files."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from config import CATEGORY_PRESETS
from scraper import (
    SearchFilters,
    collect_listings,
    parse_since,
    since_hours_ago_ms,
    write_csv,
    write_json,
)
from config import DEFAULT_RETAILER


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export new used gear per category preset.")
    since_group = parser.add_mutually_exclusive_group(required=True)
    since_group.add_argument("--since")
    since_group.add_argument("--since-hours", type=float, metavar="HOURS")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("output/presets"),
        help="Directory for per-preset files (default: output/presets).",
    )
    parser.add_argument("--format", choices=("json", "csv"), default="json")
    parser.add_argument("--price-drop", action="store_true")
    parser.add_argument("--on-sale", action="store_true")
    parser.add_argument("--min-discount", type=float, default=None)
    parser.add_argument("--delay", type=float, default=0.15)
    args = parser.parse_args(argv)

    if args.since_hours is not None:
        since_ms = since_hours_ago_ms(args.since_hours)
    else:
        since_ms = parse_since(args.since)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = args.output_dir / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    total = 0
    for preset, category in sorted(CATEGORY_PRESETS.items()):
        filters = SearchFilters(
            category=category,
            price_drop_facet=args.price_drop,
            price_drop_only=args.price_drop,
            on_sale_only=args.on_sale,
            min_discount=args.min_discount,
        )
        rows, _ = collect_listings(
            DEFAULT_RETAILER,
            since_ms,
            filters=filters,
            delay_sec=args.delay,
        )
        ext = args.format
        path = out_dir / f"{preset}.{ext}"
        if ext == "csv":
            write_csv(path, rows)
        else:
            write_json(path, rows)
        print(f"{preset:14} {len(rows):5} -> {path}")
        total += len(rows)

    print(f"Done. {total} listings across {len(CATEGORY_PRESETS)} presets in {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
