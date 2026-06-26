"""
Sprint Lead Qualification Engine v2
-------------------------------------
Multi-dimensional weighted scoring — ported from property-lead-qualifier (TypeScript).

Score formula
  motivationScore  = clamp(30 + motivationRaw × 2.4,  0, 100)
  fitScore         = clamp(45 + fitRaw × 2.1,          0, 100)
  confidenceScore  = clamp(72 + confidenceRaw × 4,     0, 100)
  blended          = motivationScore×0.6 + fitScore×0.25 + confidenceScore×0.15

Tiers  A ≥70 → HOT  |  B ≥55 → WARM  |  C ≥40 → COOL  |  discard → PASS
"""

import re

CURRENT_YEAR = 2026
EXEC_FIT_LIMIT = 16  # Cap on "execution fit" bonus signals (school zone, amenities, etc.)

NORTH_FULTON_CITIES = {"alpharetta", "johns creek", "milton", "roswell", "sandy springs"}

CORPORATE_TERMS = [
    " llc", " l.l.c", " inc", " incorporated", " corp", " corporation",
    " lp", " l.p", " llp", " ltd", " company", " co.",
    " holdings", " properties", " investments", " partners",
    " capital", " asset", " fund",
]

# Submarket-specific value ceilings so Milton ($1.13M median) isn't penalised
SUBMARKET_CEILINGS = {
    "milton":       3_000_000,
    "alpharetta":   2_200_000,
    "johns creek":  2_200_000,
    "sandy springs":1_800_000,
    "roswell":      1_600_000,
}

POSITIVE_MOTIVATION_FLAGS = {
    "Out-of-state absentee", "In-state absentee",
    "Probate, trust, or estate signal", "Verified tax or foreclosure distress",
    "Property-level vacancy indicator", "Empty-nest probability",
    "School-stage lifecycle", "Senior exemption lifecycle signal",
    "No homestead on likely SFR", "Free and clear", "High-equity owner",
    "Owner-occupied with long tenure", "Mom-and-Pop landlord",
    "Ownership transfer anomaly",
    "Premium school performance — North Fulton resale driver",
}


class LeadEngine:

    def score_lead(self, prop: dict) -> dict:
        result = dict(prop)

        # ── Parse inputs ─────────────────────────────────────────────────────
        county        = (prop.get("county") or "").lower()
        city          = (prop.get("city") or "").lower().strip()
        prop_type     = (prop.get("property_type") or "").lower()
        owner_name    = (prop.get("owner_name") or "").upper()
        years_owned   = int(prop.get("years_owned") or 0)

        # Flask demo stores full market values in 'assessed_value' (from FMLS ListPrice)
        market_value  = float(prop.get("assessed_value") or 0)

        bedrooms      = int(prop.get("bedrooms") or 0)
        year_built    = int(prop.get("year_built") or 0)

        is_oos        = bool(prop.get("is_out_of_state_absentee"))
        is_instate    = bool(prop.get("is_in_state_absentee"))
        tax_delinquent = bool(prop.get("tax_delinquent"))
        foreclosure   = bool(prop.get("foreclosure"))
        free_and_clear = bool(prop.get("free_and_clear"))
        equity_pct    = float(prop.get("estimated_equity_pct") or 0)
        equity_ratio  = (equity_pct / 100) if equity_pct else None
        total_props   = int(prop.get("total_properties_owned") or 1)

        homestead        = bool(prop.get("homestead_exemption"))
        senior_exemption = bool(prop.get("senior_exemption"))
        vacancy          = bool(prop.get("vacancy"))
        mortgage_year    = prop.get("mortgage_year")
        school_score     = prop.get("school_performance_score")
        transfer_type    = (prop.get("transfer_type") or "").lower()

        # ── Scorer state ─────────────────────────────────────────────────────
        motivation_raw = 0
        fit_raw        = 0
        confidence_raw = 0
        exec_fit_used  = 0
        score_cap      = 100
        flags          = []
        passes         = []
        warnings       = []
        failures       = []

        def apply(points, message, category, reason_type, cap_exec=False):
            nonlocal motivation_raw, fit_raw, confidence_raw, exec_fit_used
            effective = points
            if cap_exec and points > 0:
                remaining = max(0, EXEC_FIT_LIMIT - exec_fit_used)
                effective = min(points, remaining)
                exec_fit_used += effective
            if category == "motivation":
                motivation_raw += effective
            elif category == "fit":
                fit_raw += effective
            else:
                confidence_raw += effective
            if reason_type == "flag":
                flags.append(message)
                passes.append(message)
            elif reason_type == "warning":
                warnings.append(message)
            elif reason_type == "failure":
                failures.append(message)
            else:
                passes.append(message)

        # ── Geography ────────────────────────────────────────────────────────
        is_forsyth      = "forsyth" in county
        is_fulton       = "fulton" in county or "north fulton" in county
        in_target_city  = city in NORTH_FULTON_CITIES

        if is_forsyth:
            apply(12, "Forsyth County target area", "fit", "pass")
            apply(2, "Forsyth County — precise geography", "confidence", "pass")
        elif (is_fulton or not county) and in_target_city:
            apply(12, "North Fulton target city", "fit", "pass")
            apply(2, "City in North Fulton coverage area", "confidence", "pass")
        else:
            apply(-18, "Outside North Fulton or Forsyth County", "fit", "failure")
            score_cap = min(score_cap, 39)

        # ── Property type ────────────────────────────────────────────────────
        if re.search(r"commercial|industrial|office|retail|hotel|storage|hospital|church|school", prop_type):
            apply(-20, "Nonresidential asset type", "fit", "failure")
            score_cap = min(score_cap, 39)
        elif re.search(r"single|sfr|detached|residential", prop_type):
            apply(8, "Strong residential property fit", "fit", "pass")
        elif re.search(r"townhouse|townhome|condo|attached", prop_type):
            apply(6, "Attached residential fit", "fit", "pass")
        elif re.search(r"duplex|triplex|multi.?family", prop_type):
            apply(3, "Small residential rental property", "fit", "pass")
        elif prop_type:
            apply(-4, "Unclear property type", "fit", "warning")

        # ── Ownership tenure ─────────────────────────────────────────────────
        if years_owned < 3:
            apply(-18, "Recent sale under 3 years", "motivation", "failure")
        elif years_owned >= 15:
            apply(10, f"Owned {years_owned}+ years", "motivation", "flag")
        elif years_owned >= 8:
            apply(6, f"Owned {years_owned}+ years", "motivation", "pass")
        elif years_owned >= 5:
            apply(3, f"Owned {years_owned}+ years", "motivation", "pass")

        # ── Market value ─────────────────────────────────────────────────────
        ceiling = SUBMARKET_CEILINGS.get(city, 1_800_000 if is_forsyth else 1_500_000)
        if market_value < 200_000:
            apply(-8, "Value under $200,000 minimum threshold", "fit", "failure")
            score_cap = min(score_cap, 39)
        elif market_value <= ceiling:
            apply(4, "Within submarket value band", "fit", "pass")
        elif years_owned >= 10 and equity_ratio and equity_ratio >= 0.4:
            apply(3, "Above ceiling but high-equity long-tenure — high-GCI listing candidate", "motivation", "pass")
        else:
            apply(0, "Above submarket ceiling — verify listing motivation", "fit", "warning")

        # ── Probate / estate ─────────────────────────────────────────────────
        if re.search(r'\b(ESTATE|HEIRS|HEIR|TRUSTEE|TRUST|EXECUTOR|ADMINISTRATOR|PROBATE)\b', owner_name) \
                or "estate" in transfer_type:
            apply(18, "Probate, trust, or estate signal", "motivation", "flag")

        # ── Corporate owner ───────────────────────────────────────────────────
        is_corporate = _is_corporate(owner_name)
        if is_corporate:
            apply(-15, "Corporate entity owner — excluded per ownership filter", "fit", "failure")
            score_cap = min(score_cap, 39)
        else:
            apply(3, "Natural person owner", "motivation", "pass")
            if 2 <= total_props <= 5:
                apply(8, "Mom-and-Pop landlord", "motivation", "flag")
            elif total_props > 5:
                apply(3, "Multi-property individual owner", "motivation", "pass")

        # ── Absentee / occupancy ─────────────────────────────────────────────
        if is_oos:
            apply(14, "Out-of-state absentee", "motivation", "flag")
        elif is_instate:
            apply(6, "In-state absentee", "motivation", "flag")
        elif years_owned >= 15:
            apply(4, "Owner-occupied with long tenure", "motivation", "pass")
        else:
            apply(1, "Owner-occupied or same-address owner", "motivation", "pass")

        # ── Homestead exemption ───────────────────────────────────────────────
        if homestead:
            has_other = any(f in flags for f in [
                "Probate, trust, or estate signal", "Verified tax or foreclosure distress",
                "Property-level vacancy indicator", "Out-of-state absentee", "In-state absentee",
                "Senior exemption lifecycle signal",
            ])
            apply(-6 if has_other else -12, "Verified owner-occupied homestead", "motivation", "failure")
            apply(3, "Homestead status verified", "confidence", "pass")
            if mortgage_year and 2020 <= int(mortgage_year) <= 2022:
                apply(-6, "Rate-lock cohort: 2020–22 mortgage on homestead", "motivation", "failure")

        # ── Senior exemption ──────────────────────────────────────────────────
        if senior_exemption:
            apply(6, "Senior exemption lifecycle signal", "motivation", "flag")
            apply(2, "Senior exemption verified", "confidence", "pass")

        # ── Vacancy ───────────────────────────────────────────────────────────
        if vacancy:
            apply(8, "Property-level vacancy indicator", "motivation", "flag")

        # ── Equity / free-and-clear ───────────────────────────────────────────
        if free_and_clear:
            apply(15, "Free and clear", "motivation", "flag")
        elif equity_ratio is not None:
            if equity_ratio >= 0.6:
                apply(15, "High-equity owner", "motivation", "flag")
            elif equity_ratio >= 0.4:
                apply(10, "Meaningful equity estimate", "motivation", "pass")
            elif equity_ratio >= 0.2:
                apply(4, "Moderate equity estimate", "motivation", "pass")
            else:
                apply(-2, "Low estimated equity", "motivation", "failure")

        # ── Ownership transfer anomaly ────────────────────────────────────────
        if re.search(r"quit.?claim|family transfer|non.?arm|trust transfer|divorce|sheriff|relocation", transfer_type):
            apply(8, "Ownership transfer anomaly", "motivation", "flag")

        # ── Tax / foreclosure distress ────────────────────────────────────────
        if tax_delinquent or foreclosure:
            apply(18, "Verified tax or foreclosure distress", "motivation", "flag")

        # ── Year built ────────────────────────────────────────────────────────
        if year_built:
            if year_built < 1985:
                apply(4, "Pre-1985 home with renovation upside", "fit", "pass", True)
            elif year_built < 1995:
                apply(3, "Pre-1995 home", "fit", "pass", True)
            elif year_built < 2010:
                apply(0, "1995–2009 home — neutral age signal", "fit", "pass")
            else:
                apply(-2, "Newer home (2010+) — lower renovation upside", "fit", "warning")

        # ── Lifecycle signals (empty-nest, school-stage) ─────────────────────
        if bedrooms >= 3 and years_owned >= 20:
            apply(8, "Empty-nest probability", "motivation", "flag")
        elif bedrooms >= 3 and years_owned >= 15:
            apply(6, "Empty-nest probability", "motivation", "flag")
        elif bedrooms >= 4 and years_owned >= 10:
            apply(4, "School-stage lifecycle", "motivation", "flag")
        elif years_owned >= 20:
            apply(4, "Long-tenure lifecycle signal", "motivation", "pass")

        # ── School performance (GOSA ≥92 = $150K–$200K buyer premium in N. Fulton)
        if school_score is not None:
            ss = float(school_score)
            if ss >= 92:
                apply(3, "Premium school performance", "fit", "flag", True)
                apply(4, "Premium school performance — North Fulton resale driver", "motivation", "flag")
            elif ss >= 85:
                apply(2, "Strong school performance", "fit", "pass", True)
            elif ss >= 75:
                apply(1, "Solid school performance", "fit", "pass", True)
            elif ss < 65:
                apply(-4, "Weaker school performance", "fit", "failure")

        # ── Guards ────────────────────────────────────────────────────────────
        has_positive = any(f in POSITIVE_MOTIVATION_FLAGS for f in flags)
        if not has_positive and motivation_raw <= 5:
            score_cap = min(score_cap, 38)
            warnings.append("No seller motivation signals detected — capped below tier-C")

        # OOS alone (without 10+ yr tenure or overriding distress) → cap at B-tier
        has_oos_flag = "Out-of-state absentee" in flags
        has_long_tenure = years_owned >= 10
        has_overriding = any(f in flags for f in [
            "Probate, trust, or estate signal", "Verified tax or foreclosure distress",
            "Property-level vacancy indicator", "Ownership transfer anomaly",
        ])
        if has_oos_flag and not has_long_tenure and not has_overriding:
            score_cap = min(score_cap, 54)
            warnings.append("OOS absentee without confirmed 10+ yr tenure — capped at B-tier")

        # ── Blend scores ──────────────────────────────────────────────────────
        motivation_score = max(0, min(100, round(30 + motivation_raw * 2.4)))
        fit_score        = max(0, min(100, round(45 + fit_raw * 2.1)))
        confidence_score = max(0, min(100, round(72 + confidence_raw * 4)))
        blended = motivation_score * 0.6 + fit_score * 0.25 + confidence_score * 0.15
        score   = max(0, min(100, min(round(blended), score_cap)))

        tier     = _tier(score)
        strategy = _strategy(flags, failures, tier)

        return {
            **result,
            "score":            score,
            "tier":             tier,
            "motivation_score": motivation_score,
            "fit_score":        fit_score,
            "confidence_score": confidence_score,
            "strategy":         strategy,
            "flags":            list(dict.fromkeys(flags)),
            "passes":           list(dict.fromkeys(passes)),
            "warnings":         list(dict.fromkeys(warnings)),
            "failures":         list(dict.fromkeys(failures)),
        }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_corporate(name_upper: str) -> bool:
    padded = " " + name_upper.lower() + " "
    return any(t in padded for t in CORPORATE_TERMS)


def _tier(score: int) -> str:
    if score >= 70:  return "HOT"
    if score >= 55:  return "WARM"
    if score >= 40:  return "COOL"
    return "PASS"


def _strategy(flags: list, failures: list, tier: str) -> str:
    if tier == "PASS":
        if "Outside North Fulton or Forsyth County" in failures:
            return "Outside target area"
        return "Poor fit — discard"

    has_oos     = "Out-of-state absentee" in flags
    has_probate = "Probate, trust, or estate signal" in flags
    has_distress = "Verified tax or foreclosure distress" in flags

    # Compound — highest-urgency combos checked first
    if has_probate and has_distress:   return "Estate in distress — highest urgency listing"
    if has_probate and has_oos:        return "Estate + absentee — call today"
    if has_distress and has_oos:       return "Distressed absentee — urgent outreach"

    # Single-signal
    if has_probate:                                         return "Estate transition — listing opportunity"
    if has_distress:                                        return "Motivated seller — timeline pressure"
    if "Mom-and-Pop landlord" in flags:                     return "Portfolio exit — listing conversion"
    if has_oos or "In-state absentee" in flags:             return "Absentee owner — listing outreach"
    if "Empty-nest probability" in flags:                   return "Empty-nest downsizer — listing opportunity"
    if "School-stage lifecycle" in flags:                   return "School-stage mover — listing opportunity"
    if "Free and clear" in flags or "High-equity owner" in flags:
        return "Equity-rich seller — strong listing position"
    if "Premium school performance — North Fulton resale driver" in flags:
        return "Premium school zone — fast-sale listing"
    if "Senior exemption lifecycle signal" in flags:        return "Senior downsizer — listing opportunity"

    if tier == "HOT":  return "Priority outreach"
    if tier == "WARM": return "Secondary outreach"
    return "Nurture / manual review"
