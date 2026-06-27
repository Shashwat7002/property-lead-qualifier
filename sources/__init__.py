"""Off-market property data sources & enrichers (P1-06).

A production seller-prospecting pipeline composes these to populate owner mailing
address, absentee status, exemptions, equity, vacancy, and contact — the fields
live FMLS cannot supply. The stubs are intentionally inert until a provider is
configured; only `classify_absentee` works without one.
"""

from .base import (
    PropertySource,
    PropertyEnricher,
    classify_absentee,
    normalize_address,
    address_similarity,
)
from .assessor_source import AssessorSource
from .deed_source import DeedEnricher
from .contact_source import ContactEnricher

__all__ = [
    "PropertySource", "PropertyEnricher", "classify_absentee",
    "normalize_address", "address_similarity",
    "AssessorSource", "DeedEnricher", "ContactEnricher",
]
