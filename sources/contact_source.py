"""
Contact / skip-trace enricher (P1-06) — stub.

Wraps a skip-trace provider (e.g. BatchSkipTracing, PropStream) to add phone,
email, DNC status, and contact confidence. No provider → record unchanged, so
contactability stays NEUTRAL (unknown) rather than falsely "no contact".
"""


class ContactEnricher:
    name = "contact"

    def __init__(self, provider=None):
        self.provider = provider

    def enrich(self, prop: dict) -> dict:
        if self.provider is None:
            return prop
        rec = self.provider.trace(
            owner_name=prop.get("owner_name"),
            mailing_address=prop.get("owner_mailing_address"),
        )
        if not rec:
            return prop

        out = dict(prop)
        for key in ("phone", "email"):
            if rec.get(key):
                out[key] = rec[key]
        if rec.get("do_not_call") is not None:
            out["do_not_call"] = bool(rec["do_not_call"])
        out["verified_mobile"] = bool(rec.get("verified_mobile"))
        out["verified_email"] = bool(rec.get("verified_email"))
        out.setdefault("source_confidence", {})["contact"] = rec.get("confidence", 0.60)
        return out
