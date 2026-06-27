"""
Deed / mortgage / equity enricher (P1-06) — stub.

In production this wraps a deed/mortgage data provider to add last-sale date,
years owned, transfer type, mortgage age, free-and-clear, and an equity estimate
with confidence. Without a provider it returns the record unchanged (no guessing).
"""


class DeedEnricher:
    name = "deed"

    def __init__(self, provider=None):
        self.provider = provider

    def enrich(self, prop: dict) -> dict:
        if self.provider is None:
            return prop
        rec = self.provider.lookup(
            address=prop.get("address"), owner_name=prop.get("owner_name"),
            county=prop.get("county"),
        )
        if not rec:
            return prop

        out = dict(prop)
        for key in ("years_owned", "transfer_type", "mortgage_year",
                    "free_and_clear", "last_sale_date"):
            if rec.get(key) is not None:
                out[key] = rec[key]

        out["estimated_equity_pct"] = self._estimate_equity(prop, rec)
        out.setdefault("source_confidence", {})["deed"] = rec.get("confidence", 0.85)
        out.setdefault("source_confidence", {})["equity"] = rec.get("equity_confidence", 0.70)
        out["equity_source"] = "provider" if rec.get("estimated_equity_pct") is not None else "calculated"
        return out

    @staticmethod
    def _estimate_equity(prop: dict, rec: dict):
        if rec.get("estimated_equity_pct") is not None:
            return max(0.0, min(100.0, float(rec["estimated_equity_pct"])))
        value = prop.get("assessed_value")
        balance = rec.get("estimated_mortgage_balance")
        if value and balance is not None and value > 0:
            return max(0.0, min(100.0, (value - balance) / value * 100))
        return prop.get("estimated_equity_pct")   # leave unknown as-is
