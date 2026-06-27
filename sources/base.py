"""
Off-market data source / enrichment contracts (P1-06).

These Protocols define the seams a production install fills with real providers
(county assessor, deed/mortgage, contact). Concrete adapters here are stubs that
return nothing until configured — the system never fabricates owner data.

The one fully-implemented helper is `classify_absentee`, which derives absentee
status from situs vs. mailing address (no external provider required).
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class PropertySource(Protocol):
    name: str
    def fetch(self, county: str, filters: dict) -> list[dict]: ...


@runtime_checkable
class PropertyEnricher(Protocol):
    name: str
    def enrich(self, prop: dict) -> dict: ...


# ── Address normalization + absentee classification (no provider needed) ───────

_SUFFIX = {
    "street": "st", "st": "st", "avenue": "ave", "ave": "ave", "road": "rd",
    "rd": "rd", "drive": "dr", "dr": "dr", "lane": "ln", "ln": "ln",
    "court": "ct", "ct": "ct", "boulevard": "blvd", "blvd": "blvd",
    "place": "pl", "pl": "pl", "way": "way", "circle": "cir", "cir": "cir",
    "terrace": "ter", "trail": "trl", "parkway": "pkwy",
}


def normalize_address(street: str, city: str = "", state: str = "", zip_code: str = "") -> str:
    s = " ".join(str(street or "").lower().split())
    parts = []
    for tok in s.replace(",", " ").split():
        parts.append(_SUFFIX.get(tok, tok))
    base = " ".join(parts)
    tail = " ".join(t for t in (str(city or "").lower().strip(),
                                str(state or "").lower().strip(),
                                str(zip_code or "")[:5]) if t)
    return (base + " " + tail).strip()


def address_similarity(a: str, b: str) -> float:
    """Token-overlap similarity in [0,1]. 0 if either side is empty."""
    ta, tb = set(a.split()), set(b.split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def classify_absentee(prop: dict) -> dict:
    """Derive absentee status by comparing situs and owner-mailing addresses (P1-06).
    Returns None for absentee flags when the mailing address is unknown (not False)."""
    mailing_raw = (prop.get("owner_mailing_address") or "").strip()
    if not mailing_raw:
        return {"is_in_state_absentee": None, "is_out_of_state_absentee": None,
                "owner_occupancy_confidence": None}

    situs = normalize_address(prop.get("address", ""), prop.get("city", ""),
                              prop.get("state", ""), prop.get("zip_code", ""))
    mailing = normalize_address(mailing_raw, prop.get("owner_city", ""),
                                prop.get("owner_state", ""), prop.get("owner_zip", ""))
    # 0.80 tolerates a missing ZIP on one side; production should use a proper
    # address-normalization library for higher precision.
    same = address_similarity(situs, mailing) >= 0.80
    owner_state = (prop.get("owner_state") or "").upper().strip()
    in_state = (not same) and owner_state == "GA"
    out_state = (not same) and bool(owner_state) and owner_state != "GA"
    return {
        "is_in_state_absentee": in_state,
        "is_out_of_state_absentee": out_state,
        "owner_occupancy_confidence": 0.95 if same else 0.80,
    }
