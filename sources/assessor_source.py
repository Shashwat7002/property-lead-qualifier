"""
County assessor / tax parcel source (P1-06) — stub.

Wire `fetch` to a real Fulton/Forsyth assessor or property-data provider. Output
must follow the contract below. Unknown fields stay None (never False/0) so the
engine routes thin-but-marketable records to REVIEW rather than scoring on
fabricated data.
"""

from .base import classify_absentee


class AssessorSource:
    name = "assessor"

    def __init__(self, provider=None):
        self.provider = provider   # inject a real client in production

    def fetch(self, county: str, filters: dict) -> list[dict]:
        if self.provider is None:
            # No assessor provider configured — return nothing rather than guess.
            return []
        records = self.provider.query(county=county, **(filters or {}))
        return [self.normalize(r, county) for r in records]

    @staticmethod
    def normalize(raw: dict, county: str) -> dict:
        rec = {
            "source_system": "assessor",
            "source_mode": "seller_prospecting",
            "parcel_id": raw.get("parcel_id"),
            "address": raw.get("address", ""),
            "city": raw.get("city", ""),
            "county": county,
            "state": "GA",
            "zip_code": raw.get("zip_code", ""),
            "property_type": raw.get("property_type", "Single Family Residential"),
            "land_use_code": raw.get("land_use_code"),
            "year_built": raw.get("year_built"),
            "bedrooms": raw.get("bedrooms"),
            "assessed_value": raw.get("assessed_value"),
            "owner_name": raw.get("owner_name", ""),
            "owner_mailing_address": raw.get("owner_mailing_address", ""),
            "owner_city": raw.get("owner_city", ""),
            "owner_state": raw.get("owner_state", ""),
            # Booleans only when the source reports them — else None.
            "homestead_exemption": raw.get("homestead_exemption"),
            "senior_exemption": raw.get("senior_exemption"),
            "tax_delinquent": raw.get("tax_delinquent"),
            "seller_outreach_allowed": True,
            "source_confidence": {"assessor": 0.95},
        }
        rec.update(classify_absentee(rec))
        return rec
