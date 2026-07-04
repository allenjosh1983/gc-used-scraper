"""Algolia search configuration for retailer sites."""

from dataclasses import dataclass


@dataclass(frozen=True)
class RetailerConfig:
    name: str
    base_url: str
    algolia_app_id: str
    algolia_api_key: str
    algolia_index: str
    used_facet: str = "condition.lvl0:Used"


GUITAR_CENTER = RetailerConfig(
    name="guitarcenter",
    base_url="https://www.guitarcenter.com",
    algolia_app_id="7AQ22QS8RJ",
    algolia_api_key="d04d765e552eb08aff3601eae8f2b729",
    algolia_index="guitarcenter",
)

MUSICIANS_FRIEND = None
DEFAULT_RETAILER = GUITAR_CENTER

HITS_PER_PAGE = 100
ATTRIBUTES = [
    "skuId",
    "displayName",
    "price",
    "listPrice",
    "creationDate",
    "seoUrl",
    "storeName",
    "brand",
    "condition",
    "identifiers",
    "skuCondition",
    "stores",
    "sticker",
    "savings",
]

# Short CLI names -> Guitar Center categories.lvl0 values (Algolia facet).
CATEGORY_PRESETS: dict[str, str] = {
    "guitars": "Guitars",
    "basses": "Basses",
    "amps": "Amps & Effects",
    "drums": "Drums",
    "keys": "Keys & MIDI",
    "recording": "Recording",
    "live-sound": "Live Sound",
    "dj": "DJ",
    "mics": "Mics & Wireless",
    "accessories": "Accessories",
    "lighting": "Lighting",
    "band": "Band & Orchestra",
}

# Algolia facet value for GC "Price Drop" used listings.
PRICE_DROP_FACET = "savings:Price Drop"
