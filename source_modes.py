"""
Source / product modes (P0-01).

A Realtor prospecting for LISTING clients must not treat Active / Coming Soon MLS
records as seller leads — those owners are already (or about to be) represented
(NAR Code of Ethics Art. 16). These modes keep the populations separate.
"""

from enum import Enum


class SourceMode(str, Enum):
    SELLER_PROSPECTING = "seller_prospecting"   # off-market owners → listing leads (default)
    MARKET_INTELLIGENCE = "market_intelligence"  # Active/Coming Soon inventory → comps / intel
    BUYER_OPPORTUNITY = "buyer_opportunity"     # Active/Coming Soon → buyer-side ranking

    @classmethod
    def parse(cls, value, default="seller_prospecting"):
        try:
            return cls(value)
        except (ValueError, TypeError):
            return cls(default)


# Which engine listing_goal each source mode maps to.
ENGINE_GOAL = {
    SourceMode.SELLER_PROSPECTING: "seller_listing",
    SourceMode.MARKET_INTELLIGENCE: "buyer_or_market",
    SourceMode.BUYER_OPPORTUNITY: "buyer_or_market",
}
