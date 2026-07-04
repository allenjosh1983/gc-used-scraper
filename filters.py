"""Post-fetch and query filter helpers."""

from __future__ import annotations

from typing import Any


def discount_percent(price: float | None, list_price: float | None) -> float | None:
    if price is None or list_price is None or list_price <= 0:
        return None
    if price >= list_price:
        return 0.0
    return round((list_price - price) / list_price * 100, 1)


def has_price_drop_sticker(hit: dict[str, Any]) -> bool:
    stickers = hit.get("sticker") or []
    return any(s.get("name") == "Price Drop" for s in stickers if isinstance(s, dict))


def passes_price_filters(
    row: dict[str, Any],
    *,
    price_drop_only: bool = False,
    on_sale_only: bool = False,
    min_discount: float | None = None,
    min_price: float | None = None,
    max_price: float | None = None,
) -> bool:
    price = row.get("price")
    if min_price is not None and (price is None or price < min_price):
        return False
    if max_price is not None and (price is None or price > max_price):
        return False

    pct = row.get("discount_percent")
    if on_sale_only and (pct is None or pct <= 0):
        return False
    if min_discount is not None and (pct is None or pct < min_discount):
        return False
    if price_drop_only and not row.get("is_price_drop"):
        return False
    return True


def enrich_row(row: dict[str, Any], raw_hit: dict[str, Any] | None = None) -> dict[str, Any]:
    """Add discount / price-drop fields for output and filtering."""
    pct = discount_percent(row.get("price"), row.get("list_price"))
    is_drop = False
    if raw_hit:
        is_drop = has_price_drop_sticker(raw_hit) or "Price Drop" in (raw_hit.get("savings") or [])
    row = dict(row)
    row["discount_percent"] = pct
    row["savings_amount"] = (
        round(row["list_price"] - row["price"], 2)
        if pct and pct > 0 and row.get("list_price") and row.get("price") is not None
        else 0.0
    )
    row["is_price_drop"] = is_drop
    return row
