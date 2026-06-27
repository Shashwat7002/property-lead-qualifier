"""
Typed input normalization (P2-15).

The engine historically accepted arbitrary dicts, which let "unknown" silently
become False/0 — the root of earlier bugs (the −18 tenure penalty, the sub-$200k
cap on missing values). `normalize_lead_input` enforces the critical rule:

    UNKNOWN ≠ FALSE and UNKNOWN ≠ 0.

Booleans stay None until a source explicitly says True/False. Numerics stay None
unless present and valid. The engine already treats None defensively; this layer
makes the contract explicit and testable. Dataclasses (no pydantic dependency).
"""

from dataclasses import dataclass, fields
from typing import Optional


def _as_bool(v):
    if v is None or v == "":
        return None
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    if s in {"true", "1", "yes", "y"}:
        return True
    if s in {"false", "0", "no", "n"}:
        return False
    return None


def _as_int(v, lo=None, hi=None):
    if v is None or v == "":
        return None
    try:
        n = int(float(v))
    except (TypeError, ValueError):
        return None
    if lo is not None:
        n = max(lo, n)
    if hi is not None:
        n = min(hi, n)
    return n


def _as_float(v, lo=None, hi=None):
    if v is None or v == "":
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if lo is not None:
        f = max(lo, f)
    if hi is not None:
        f = min(hi, f)
    return f


@dataclass
class LeadInput:
    # Identity / location
    address: str = ""
    city: str = ""
    county: str = ""
    state: str = "GA"
    zip_code: str = ""
    property_type: str = ""
    listing_status: str = ""
    # Property
    year_built: Optional[int] = None
    assessed_value: Optional[float] = None
    bedrooms: Optional[int] = None
    # Owner / intent (UNKNOWN stays None — never coerced to False)
    owner_name: str = ""
    owner_mailing_address: str = ""
    owner_city: str = ""
    owner_state: str = ""
    is_out_of_state_absentee: Optional[bool] = None
    is_in_state_absentee: Optional[bool] = None
    years_owned: Optional[int] = None
    tax_delinquent: Optional[bool] = None
    foreclosure: Optional[bool] = None
    free_and_clear: Optional[bool] = None
    estimated_equity_pct: Optional[float] = None
    homestead_exemption: Optional[bool] = None
    senior_exemption: Optional[bool] = None
    vacancy: Optional[bool] = None
    mortgage_year: Optional[int] = None
    total_properties_owned: Optional[int] = None
    transfer_type: str = ""
    # Contact
    phone: str = ""
    email: str = ""
    do_not_call: Optional[bool] = None
    # Source labels
    source_system: str = ""
    source_mode: str = ""


def normalize_lead_input(raw: dict) -> dict:
    """Return a normalized dict, preserving every extra (enrichment) key as-is.

    Unknown booleans/numerics become None, not False/0. Keys not in the schema
    (school scores, FRED/Census enrichment, etc.) pass through untouched.
    """
    out = dict(raw)  # keep enrichment / extra keys

    out["year_built"] = _as_int(raw.get("year_built"), 1900, 2100)
    out["assessed_value"] = _as_float(raw.get("assessed_value"), 0)
    out["bedrooms"] = _as_int(raw.get("bedrooms"), 0, 30)
    out["years_owned"] = _as_int(raw.get("years_owned"), 0, 200)
    out["mortgage_year"] = _as_int(raw.get("mortgage_year"), 1900, 2100)
    out["total_properties_owned"] = _as_int(raw.get("total_properties_owned"), 0)
    out["estimated_equity_pct"] = _as_float(raw.get("estimated_equity_pct"), 0, 100)

    for b in ("is_out_of_state_absentee", "is_in_state_absentee", "tax_delinquent",
              "foreclosure", "free_and_clear", "homestead_exemption",
              "senior_exemption", "vacancy", "do_not_call"):
        if b in raw:
            out[b] = _as_bool(raw.get(b))

    return out
