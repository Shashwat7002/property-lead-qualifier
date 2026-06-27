"""
Single source of truth for scoring formulas, build-year docs, and PUBLIC-SAFE
labels (P0-04 + P1-09).

The engine, the explainer PDF, and the UI all read from here so they cannot drift
apart. PUBLIC_LABELS keep user-facing copy neutral for fair-housing / steering
safety — internal flags may stay analytic for calibration, but anything shown to a
user or exported should pass through `public_label()`.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SignalDoc:
    key: str
    label: str
    dimension: str
    points: int
    public_description: str


BUILD_YEAR_SIGNALS = [
    SignalDoc("build_2021_plus", "2021+ home", "fit", 4,
              "Modern inventory with strong retail buyer appeal."),
    SignalDoc("build_2005_2020", "2005–2020 home", "fit", 6,
              "Prime retail-buyer lifecycle band for North Fulton / South Forsyth."),
    SignalDoc("build_1995_2004", "1995–2004 home", "fit", 4,
              "Established suburban inventory with broad buyer appeal."),
    SignalDoc("build_1985_1994", "1985–1994 home", "fit", 1,
              "Viable but older layouts/systems may narrow buyer appeal."),
    SignalDoc("build_pre_1985", "Pre-1985 home", "fit", -1,
              "Older systems/layouts can narrow the retail buyer pool."),
]

# Current engine formulas (keep in lockstep with lead_engine.py).
MOTIVATION_FORMULA = "100 / (1 + exp(-0.076 * (motivation_raw - 11.1)))"
FIT_FORMULA = "100 / (1 + exp(-0.11 * (fit_raw - 20)))"
CONFIDENCE_FORMULA = "clamp(72 + confidence_raw * 4, 0, 100)"
BLEND_FORMULA = "0.60 * motivation + 0.25 * fit + 0.15 * confidence"

DIMENSION_WEIGHTS = {"motivation": 0.60, "fit": 0.25, "confidence": 0.15}

TIER_THRESHOLDS = {"HOT": 70, "WARM": 55, "COOL": 40}


# ── Public-safe label mapping (P1-09) ──────────────────────────────────────────
# Internal analytic label → neutral user-facing label. Avoids familial/protected-
# class framing while preserving the underlying record-based signal.
PUBLIC_LABELS = {
    "Empty-nest probability": "Long-tenure large-home transition signal",
    "School-stage lifecycle": "Long-tenure large-home lifecycle signal",
    "Upgrade seller — move-up listing candidate": "Equity-backed move-readiness signal",
    "Homestead downsizer window — long-tenure owner-occupant": "Long-tenure owner-occupant transition window",
    "Homestead move-up window — equity-rich family owner-occupant": "Equity-backed owner-occupant transition window",
    "Equity-backed family lifecycle seller": "Equity-backed owner-occupant transition signal",
    "Equity-backed senior downsizer": "Senior-exemption owner — equity-backed transition signal",
    "Forsyth senior downsizer — long tenure + full school-tax exemption": "Forsyth long-tenure senior-exemption transition signal",
    "Senior exemption lifecycle signal": "Senior-exemption owner — net-sheet review signal",
    "Premium school performance": "High school-zone marketability",
    "Premium school-zone marketability": "High school-zone marketability",
}

# Strategy strings → public-safe equivalents.
PUBLIC_STRATEGIES = {
    "Empty-nest downsizer — listing opportunity": "Long-tenure large-home transition opportunity",
    "School-stage mover — listing opportunity": "Long-tenure owner-occupant transition opportunity",
    "Senior downsizer — listing opportunity": "Senior-exemption owner — net-sheet review opportunity",
    "Premium school zone — fast-sale listing": "High school-zone marketability — strong listing angle",
}


def public_label(label: str) -> str:
    return PUBLIC_LABELS.get(label, label)


def public_strategy(strategy: str) -> str:
    return PUBLIC_STRATEGIES.get(strategy, strategy)
