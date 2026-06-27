"""
Submarket configuration (P1-10 micro-markets, P2-14 price bands).

Liquidity / band figures are expert-assumed starting points for North Fulton &
Forsyth, to be recalibrated against logged DOM and sale-to-list once outcome data
exists (see db.py). They are NOT measured guarantees.
"""

# ── Micro-markets by ZIP (P1-10) ───────────────────────────────────────────────
# tier: core (strongest demand) → strong → standard → outer (slower liquidity).
MICRO_MARKETS = {
    "30005": {"tier": "core",  "fit_bonus": 12, "liquidity": 88, "label": "Alpharetta / South Forsyth border"},
    "30024": {"tier": "core",  "fit_bonus": 12, "liquidity": 86, "label": "South Forsyth / Johns Creek corridor"},
    "30040": {"tier": "core",  "fit_bonus": 12, "liquidity": 84, "label": "Cumming / South Forsyth"},
    "30041": {"tier": "core",  "fit_bonus": 12, "liquidity": 86, "label": "South Forsyth / Denmark corridor"},
    "30028": {"tier": "outer", "fit_bonus": 6,  "liquidity": 55, "label": "Outer / north Forsyth"},
}

CITY_MARKETS = {
    "milton":        {"tier": "luxury_core", "liquidity": 78},
    "alpharetta":    {"tier": "core",        "liquidity": 88},
    "johns creek":   {"tier": "core",        "liquidity": 84},
    "roswell":       {"tier": "strong",      "liquidity": 80},
    "sandy springs": {"tier": "mixed",       "liquidity": 76},
}


def micro_market_for(zip_code: str, city: str) -> dict:
    """Return {tier, liquidity, label, source} for a property's ZIP/city."""
    z = (zip_code or "")[:5]
    if z in MICRO_MARKETS:
        m = MICRO_MARKETS[z]
        return {"tier": m["tier"], "liquidity": m["liquidity"], "label": m["label"], "source": "zip"}
    c = (city or "").lower().strip()
    if c in CITY_MARKETS:
        m = CITY_MARKETS[c]
        return {"tier": m["tier"], "liquidity": m["liquidity"], "label": c.title(), "source": "city"}
    return {"tier": "unknown", "liquidity": None, "label": "", "source": "unknown"}


# ── Submarket price bands (P2-14) ──────────────────────────────────────────────
# (low, high) sweet-spot / stretch / luxury, in dollars.
PRICE_BANDS = {
    "alpharetta":    {"sweet_spot": (650_000, 1_200_000), "stretch": (1_200_000, 2_200_000), "luxury": (2_200_000, 2_800_000)},
    "milton":        {"sweet_spot": (900_000, 1_800_000), "stretch": (1_800_000, 3_000_000), "luxury": (3_000_000, 4_000_000)},
    "johns creek":   {"sweet_spot": (650_000, 1_200_000), "stretch": (1_200_000, 2_200_000), "luxury": (2_200_000, 2_800_000)},
    "roswell":       {"sweet_spot": (550_000, 1_000_000), "stretch": (1_000_000, 1_600_000), "luxury": (1_600_000, 2_000_000)},
    "sandy springs": {"sweet_spot": (550_000, 1_100_000), "stretch": (1_100_000, 1_800_000), "luxury": (1_800_000, 2_500_000)},
    "south_forsyth": {"sweet_spot": (550_000, 1_100_000), "stretch": (1_100_000, 1_800_000), "luxury": (1_800_000, 2_500_000)},
    "outer_forsyth": {"sweet_spot": (400_000, 850_000),   "stretch": (850_000, 1_300_000),   "luxury": (1_300_000, 1_800_000)},
}

SOUTH_FORSYTH_ZIPS = {"30005", "30024", "30040", "30041"}
OUTER_FORSYTH_ZIPS = {"30028"}


def band_key_for(city: str, county: str, zip_code: str) -> str:
    c = (city or "").lower().strip()
    if c in PRICE_BANDS:
        return c
    if "forsyth" in (county or "").lower():
        return "south_forsyth" if (zip_code or "")[:5] in SOUTH_FORSYTH_ZIPS else "outer_forsyth"
    return "alpharetta"   # reasonable North Fulton default


def price_band_fit(value: float, city: str, county: str, zip_code: str):
    """0–100 marketability of the price within its submarket band (P2-14). None if value unknown."""
    if not value or value <= 0:
        return None
    band = PRICE_BANDS[band_key_for(city, county, zip_code)]
    low, high = band["sweet_spot"]
    if low <= value <= high:
        return 90
    if value < low:
        return max(30, round(90 - (low - value) / low * 60))
    if value <= band["stretch"][1]:
        return 75
    if value <= band["luxury"][1]:
        return 60
    return 40
