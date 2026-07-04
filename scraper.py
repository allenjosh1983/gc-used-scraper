#!/usr/bin/env python3
"""
Scrape newly listed used gear from Guitar Center via their Algolia search index.

GC assigns each used SKU a creationDate (Unix ms). Morning inventory drops show up
as a batch of new creationDate values around ~05:00–06:00 UTC.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlencode

import requests

from config import (
    ATTRIBUTES,
    CATEGORY_PRESETS,
    DEFAULT_RETAILER,
    HITS_PER_PAGE,
    GUITAR_CENTER,
    PRICE_DROP_FACET,
    RetailerConfig,
)
from filters import enrich_row, passes_price_filters

ALGOLIA_URL = "https://{app_id}-dsn.algolia.net/1/indexes/*/queries"


@dataclass
class SearchFilters:
    category: str | None = None
    price_drop_facet: bool = False
    min_price: float | None = None
    max_price: float | None = None
    price_drop_only: bool = False
    on_sale_only: bool = False
    min_discount: float | None = None
    skip_creation_filter: bool = False


def parse_since(value: str) -> int:
    """Parse --since as ISO date, datetime, or Unix timestamp (sec or ms)."""
    value = value.strip()
    if value.isdigit():
        n = int(value)
        return n if n > 10_000_000_000 else n * 1000

    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%dT%H:%M",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y-%m-%d %H:%M:%S",
    ):
        try:
            dt = datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            return int(dt.timestamp() * 1000)
        except ValueError:
            continue

    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"Could not parse date: {value!r}. Use YYYY-MM-DD or ISO datetime."
        ) from exc


def since_hours_ago_ms(hours: float) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
    return int(cutoff.timestamp() * 1000)


def now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def now_sec() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def resolve_category(preset: str | None, category: str | None) -> str | None:
    if preset and category:
        raise argparse.ArgumentTypeError("Use only one of --preset or --category.")
    if preset:
        key = preset.lower().strip()
        if key not in CATEGORY_PRESETS:
            choices = ", ".join(sorted(CATEGORY_PRESETS))
            raise argparse.ArgumentTypeError(
                f"Unknown preset {preset!r}. Choose from: {choices}"
            )
        return CATEGORY_PRESETS[key]
    return category


def build_params(
    *,
    creation_after_ms: int,
    creation_before_ms: int | None = None,
    filters: SearchFilters | None = None,
    page: int = 0,
) -> str:
    filters = filters or SearchFilters()
    facet_filters: list[str] = [GUITAR_CENTER.used_facet]
    if filters.category:
        facet_filters.append(f"categories.lvl0:{filters.category}")
    if filters.price_drop_facet:
        facet_filters.append(PRICE_DROP_FACET)

    numeric_filters = [f"startDate<={now_sec()}"]
    if not filters.skip_creation_filter:
        numeric_filters.extend(
            [
                f"creationDate>={creation_after_ms}",
                f"creationDate<={creation_before_ms or now_ms()}",
            ]
        )
    if filters.min_price is not None:
        numeric_filters.append(f"price>={filters.min_price}")
    if filters.max_price is not None:
        numeric_filters.append(f"price<={filters.max_price}")

    params: dict[str, str | int] = {
        "facetFilters": json.dumps(facet_filters),
        "numericFilters": json.dumps(numeric_filters),
        "hitsPerPage": HITS_PER_PAGE,
        "page": page,
        "attributesToRetrieve": json.dumps(ATTRIBUTES),
    }
    return urlencode(params)


def search_page(
    retailer: RetailerConfig,
    creation_after_ms: int,
    *,
    creation_before_ms: int | None = None,
    filters: SearchFilters | None = None,
    page: int = 0,
    session: requests.Session | None = None,
) -> dict[str, Any]:
    session = session or requests.Session()
    params = build_params(
        creation_after_ms=creation_after_ms,
        creation_before_ms=creation_before_ms,
        filters=filters,
        page=page,
    )
    body = {"requests": [{"indexName": retailer.algolia_index, "params": params}]}
    url = (
        ALGOLIA_URL.format(app_id=retailer.algolia_app_id.lower())
        + "?"
        + urlencode(
            {
                "x-algolia-application-id": retailer.algolia_app_id,
                "x-algolia-api-key": retailer.algolia_api_key,
            }
        )
    )
    resp = session.post(url, json=body, timeout=60)
    resp.raise_for_status()
    return resp.json()["results"][0]


def iter_listings(
    retailer: RetailerConfig,
    creation_after_ms: int,
    *,
    creation_before_ms: int | None = None,
    filters: SearchFilters | None = None,
    delay_sec: float = 0.15,
) -> Iterator[dict[str, Any]]:
    session = requests.Session()
    page = 0
    while True:
        result = search_page(
            retailer,
            creation_after_ms,
            creation_before_ms=creation_before_ms,
            filters=filters,
            page=page,
            session=session,
        )
        for hit in result.get("hits") or []:
            row = enrich_row(normalize_hit(hit, retailer), hit)
            if passes_price_filters(
                row,
                price_drop_only=(filters.price_drop_only if filters else False),
                on_sale_only=(filters.on_sale_only if filters else False),
                min_discount=(filters.min_discount if filters else None),
                min_price=(filters.min_price if filters else None),
                max_price=(filters.max_price if filters else None),
            ):
                yield row
        nb_pages = result.get("nbPages", 0)
        if page + 1 >= nb_pages:
            break
        page += 1
        if delay_sec > 0:
            time.sleep(delay_sec)


def normalize_hit(hit: dict[str, Any], retailer: RetailerConfig) -> dict[str, Any]:
    creation_ms = hit.get("creationDate") or 0
    created_at = (
        datetime.fromtimestamp(creation_ms / 1000, tz=timezone.utc).isoformat()
        if creation_ms
        else None
    )
    seo = hit.get("seoUrl") or ""
    url = f"{retailer.base_url}{seo}" if seo.startswith("/") else seo
    condition = hit.get("condition") or {}
    identifiers = hit.get("identifiers") or {}
    return {
        "sku_id": hit.get("skuId"),
        "gc_item_number": identifiers.get("gcItemNumber"),
        "title": hit.get("displayName"),
        "brand": hit.get("brand"),
        "price": hit.get("price"),
        "list_price": hit.get("listPrice"),
        "condition": condition.get("lvl1") or condition.get("lvl0"),
        "sku_condition": hit.get("skuCondition"),
        "store": hit.get("storeName"),
        "stores": hit.get("stores"),
        "creation_date_ms": creation_ms,
        "created_at": created_at,
        "url": url,
    }


def load_known_skus(path: Path) -> set[str]:
    if not path.exists():
        return set()
    return {line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def append_known_skus(path: Path, sku_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        for sku in sku_ids:
            f.write(sku + "\n")


def write_json(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2), encoding="utf-8")


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def count_listings(
    retailer: RetailerConfig,
    creation_after_ms: int,
    *,
    creation_before_ms: int | None = None,
    filters: SearchFilters | None = None,
) -> int:
    """Approximate count; post-filters may reduce rows when fetching."""
    result = search_page(
        retailer,
        creation_after_ms,
        creation_before_ms=creation_before_ms,
        filters=filters,
        page=0,
    )
    return int(result.get("nbHits", 0))


def collect_listings(
    retailer: RetailerConfig,
    creation_after_ms: int,
    *,
    creation_before_ms: int | None = None,
    filters: SearchFilters | None = None,
    known_skus: set[str] | None = None,
    delay_sec: float = 0.15,
) -> tuple[list[dict[str, Any]], list[str]]:
    rows: list[dict[str, Any]] = []
    new_skus: list[str] = []
    for row in iter_listings(
        retailer,
        creation_after_ms,
        creation_before_ms=creation_before_ms,
        filters=filters,
        delay_sec=delay_sec,
    ):
        sku = row.get("sku_id")
        if known_skus and sku in known_skus:
            continue
        rows.append(row)
        if sku:
            new_skus.append(sku)
    return rows, new_skus


def list_presets() -> None:
    print("Available --preset values:")
    for key, label in sorted(CATEGORY_PRESETS.items()):
        print(f"  {key:14} -> {label}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="List Guitar Center used gear created after a given date.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Presets: " + ", ".join(sorted(CATEGORY_PRESETS.keys())),
    )
    since_group = parser.add_mutually_exclusive_group(required=False)
    since_group.add_argument(
        "--since",
        help="Only SKUs created on/after this time (YYYY-MM-DD, ISO datetime, or Unix ts).",
    )
    since_group.add_argument(
        "--since-hours",
        type=float,
        metavar="HOURS",
        help="Only SKUs created within the last N hours (e.g. 24 for daily run).",
    )
    parser.add_argument(
        "--until",
        default=None,
        help="Optional upper bound on creationDate (same formats as --since).",
    )
    parser.add_argument(
        "--preset",
        default=None,
        help="Category shortcut (guitars, amps, drums, ...). Use --list-presets to see all.",
    )
    parser.add_argument(
        "--category",
        default=None,
        help='Raw GC category.lvl0 value, e.g. "Guitars".',
    )
    parser.add_argument(
        "--list-presets",
        action="store_true",
        help="Print category presets and exit.",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        default=None,
        help="Write results to this file (.json or .csv). Default: print JSON to stdout.",
    )
    parser.add_argument(
        "--known-skus",
        type=Path,
        default=None,
        help="Path to a file of previously seen sku_ids; only emit SKUs not in this file.",
    )
    parser.add_argument(
        "--update-known",
        action="store_true",
        help="Append newly emitted sku_ids to --known-skus after a successful run.",
    )
    parser.add_argument(
        "--count-only",
        action="store_true",
        help="Print Algolia hit count (before post-filters).",
    )
    parser.add_argument(
        "--delay",
        type=float,
        default=0.15,
        help="Seconds between paginated Algolia requests (default: 0.15).",
    )
    price = parser.add_argument_group("price filters")
    price.add_argument(
        "--price-drop",
        action="store_true",
        help="Only items tagged as Price Drop (Algolia savings facet + sticker).",
    )
    price.add_argument(
        "--on-sale",
        action="store_true",
        help="Only items where price is below list_price.",
    )
    price.add_argument(
        "--min-discount",
        type=float,
        metavar="PCT",
        help="Minimum percent below list price (e.g. 10 for 10%% off).",
    )
    price.add_argument(
        "--min-price",
        type=float,
        help="Minimum listing price.",
    )
    price.add_argument(
        "--max-price",
        type=float,
        help="Maximum listing price.",
    )
    parser.add_argument(
        "--all-ages",
        action="store_true",
        help="Ignore creationDate (e.g. all current used price drops, not just new SKUs).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.list_presets:
        list_presets()
        return 0

    if args.since is None and args.since_hours is None:
        parser.error("one of --since or --since-hours is required")

    if args.since_hours is not None:
        since_ms = since_hours_ago_ms(args.since_hours)
    else:
        since_ms = parse_since(args.since)
    until_ms = parse_since(args.until) if args.until else None

    category = resolve_category(args.preset, args.category)
    search_filters = SearchFilters(
        category=category,
        price_drop_facet=args.price_drop,
        min_price=args.min_price,
        max_price=args.max_price,
        price_drop_only=args.price_drop and not args.all_ages,
        on_sale_only=args.on_sale,
        min_discount=args.min_discount,
        skip_creation_filter=args.all_ages,
    )

    retailer = DEFAULT_RETAILER

    if args.count_only:
        print(
            count_listings(
                retailer,
                since_ms,
                creation_before_ms=until_ms,
                filters=search_filters,
            )
        )
        return 0

    known = load_known_skus(args.known_skus) if args.known_skus else set()
    rows, new_skus = collect_listings(
        retailer,
        since_ms,
        creation_before_ms=until_ms,
        filters=search_filters,
        known_skus=known if known else None,
        delay_sec=args.delay,
    )

    if args.output:
        if args.output.suffix.lower() == ".csv":
            write_csv(args.output, rows)
        else:
            write_json(args.output, rows)
        print(f"Wrote {len(rows)} listings to {args.output}", file=sys.stderr)
    else:
        json.dump(rows, sys.stdout, indent=2)
        print(file=sys.stdout)

    if args.update_known and args.known_skus and new_skus:
        append_known_skus(args.known_skus, new_skus)
        print(f"Appended {len(new_skus)} sku_ids to {args.known_skus}", file=sys.stderr)

    print(f"Total: {len(rows)} listings", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
