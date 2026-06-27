"""
Sprint Lead Qualification Engine v2
-------------------------------------
Multi-dimensional weighted scoring for North Fulton / Forsyth County listing leads.
Target: individual homebuyers (families, move-up, downsizers) — NOT investors/flippers.

Score formula
  motivationScore  = 100 / (1 + e^(-0.076·(motivationRaw − 11.1)))   ← logistic
  fitScore         = clamp(45 + fitRaw × 2.1,  0, 100)
  confidenceScore  = clamp(72 + confidenceRaw × 4, 0, 100)
  blended          = motivationScore×0.6 + fitScore×0.25 + confidenceScore×0.15

Tiers  HOT ≥70  |  WARM ≥55  |  COOL ≥40  |  PASS <40   (+ REVIEW, see below)
Tier gates (audit §13.3): HOT requires motivationScore ≥ 62; WARM requires ≥ 45 —
fit/confidence alone cannot manufacture a top tier from a low-intent owner.
REVIEW: marketable property (fit ≥ 60) whose seller intent is UNKNOWN (no GSCCCA
tenure) and would otherwise fall to COOL/PASS — routed for data enrichment, not discard.

── KEY CHANGES FROM EXTERNAL AUDIT (2026-06-26) ───────────────────────────────
  • Motivation uses a LOGISTIC transform, not linear — fixes the "fast saturation"
    defect where every motivated lead pinned at 100 and the top tier was unrankable.
  • Tenure-null bug fixed: live FMLS unknown tenure is None (lowers confidence),
    never 0 (which falsely fired the −18 short-tenure penalty).
  • Homestead penalty softened −12→−4; owner-occupant lifecycle made net-positive.
  • Macro signals (HPI, unemployment) route to market_context, NOT confidence.
  • FRED HPI fixed: county-specific series + true YoY (was Fulton-only, 12-yr gap).
  • Georgia tax intelligence + South Forsyth micro-market + Coming Soon priority added.

── SCORING ASSUMPTIONS (analysis-assumptions-log) ─────────────────────────────
All weights below are expert-assumed, not empirically derived from conversion data.
The audit is explicit: these become trustworthy only after outcome calibration.
estimated_conversion_pct is therefore RELATIVE priority, not a promised rate.
ROADMAP (audit §8): migrate to a probability stack — P(intent)·marketability·
confidence·contactability·E[GCI] — and fit logistic/hazard coefficients from logged
listing outcomes (mailed→contacted→appointment→signed). Recalibrate at ≥100 outcomes.

  Dimension weights   motivation 60 / fit 25 / confidence 15
  Logistic params     k=0.076, x0=11.1  (raw 4→37, 12→52, 18→63, 30→81, 50→95)
  Key signal weights  probate +18, tax distress +18, free-and-clear +15,
                      OOS absentee +14, empty-nest +8, vacancy +8,
                      long tenure (15+ yr) +10, Mom-and-Pop +8, senior +6,
                      upgrade seller +6, in-state absentee +6
  Hard caps (verified disqualifiers only — never on missing data):
                      outside geography → 39, commercial → 39, value <$200K → 39,
                      institutional → 39, no motivation → 38,
                      OOS with GSCCCA-confirmed <10 yr tenure → 54

── DATA SOURCES ────────────────────────────────────────────────────────────────
  FMLS        Active/off-market listings (property_type, bedrooms, year_built, ListPrice)
  GSCCCA      Georgia deed index: years_owned, transfer_type, homestead_exemption
              County IDs: Fulton=60, Forsyth=58 — free account at apps.gsccca.org
  FRED        3 macro series: mortgage rate (30-yr fixed), unemployment (Atlanta MSA),
              HPI growth (GA county level)
  Census ACS  Tract-level: median income, median home value, owner-occupancy rate,
              vacancy rate, age-65+ share
  OSM/Overpass  Amenity access: grocery, parks, major roads
  GOSA        School CCRPI by ZIP (≥92 = $150K–$200K buyer premium in North Fulton)
"""

import math
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

# Institutional-scale entity signals — triggers hard cap even if corporate (by name or volume)
# Small LLCs / family entities without these terms are treated as portfolio-exit opportunities
INSTITUTIONAL_TERMS = [
    " reit", " bank", " financial", " mortgage", " builder",
    " developer", " development", " construction", " hoa ",
]

# Submarket-specific value ceilings so Milton ($1.13M median) isn't penalised
SUBMARKET_CEILINGS = {
    "milton":       3_000_000,
    "alpharetta":   2_200_000,
    "johns creek":  2_200_000,
    "sandy springs":1_800_000,
    "roswell":      1_600_000,
}

# South Forsyth (high-demand, newer, school-sensitive family submarket near
# Halcyon / GA-400) behaves very differently from rural outer Forsyth. The audit
# (§6.1, Appendix C) flags that scoring all Forsyth identically hides the best leads.
SOUTH_FORSYTH_ZIPS = {"30005", "30024", "30040", "30041"}
# Outer/rural Forsyth (north of Cumming) — slower DOM, weaker buyer demand than the
# South Forsyth / GA-400 corridor. Realtor.com mid-2026: 30028 ~71 DOM vs 30040/41 ~40.
OUTER_FORSYTH_ZIPS = {"30028"}

POSITIVE_MOTIVATION_FLAGS = {
    "Out-of-state absentee", "In-state absentee",
    "Probate, trust, or estate signal", "Verified tax or foreclosure distress",
    "Property-level vacancy indicator", "Empty-nest probability",
    "School-stage lifecycle", "Senior exemption lifecycle signal",
    "No homestead on likely SFR", "Free and clear", "High-equity owner",
    "Owner-occupied with long tenure", "Mom-and-Pop landlord",
    "Ownership transfer anomaly", "Upgrade seller — move-up listing candidate",
    "Homestead downsizer window — long-tenure owner-occupant",
    "Homestead move-up window — equity-rich family owner-occupant",
}

# ── HOT evidence gate (independent seller-intent corroboration) ─────────────────
# A lead reaches HOT only if it has INDEPENDENT motivation evidence, not just a high
# score from equity (capacity, not intent) plus marketability. Three buckets:
#   URGENT    — time-pressured / distress / absentee (a single one is strong)
#   LIFECYCLE — owner is in a transition window (downsize, move-up, school stage)
#   FINANCIAL — owner CAN sell easily (equity, free-and-clear). Capacity, not intent.
# Equity×lifecycle interaction flags are classified LIFECYCLE because they represent
# equity confirmation PAIRED with a life-stage signal — the reviewer's accepted
# corroborator for a normal owner-occupant seller.
URGENT_SIGNALS = {
    "Probate, trust, or estate signal",
    "Verified tax or foreclosure distress",
    "Property-level vacancy indicator",
    "Out-of-state absentee",
    "In-state absentee",
    "Ownership transfer anomaly",
}
LIFECYCLE_SIGNALS = {
    "Empty-nest probability",
    "School-stage lifecycle",
    "Senior exemption lifecycle signal",
    "Upgrade seller — move-up listing candidate",
    "Homestead downsizer window — long-tenure owner-occupant",
    "Homestead move-up window — equity-rich family owner-occupant",
    "Forsyth senior downsizer — long tenure + full school-tax exemption",
    "Equity-backed family lifecycle seller",
    "Equity-backed senior downsizer",
    "Equity-rich absentee exit candidate",
}
FINANCIAL_SIGNALS = {
    "Free and clear",
    "High-equity owner",
    "Meaningful equity estimate",
}


def _hot_evidence_ok(flags) -> bool:
    """True if the lead has enough independent seller-intent evidence to be HOT.
    High equity alone (financial only) or long tenure alone (lifecycle only) is NOT
    enough — the reviewer's core correction."""
    f = set(flags)
    urgent    = len(f & URGENT_SIGNALS)
    lifecycle = len(f & LIFECYCLE_SIGNALS)
    financial = len(f & FINANCIAL_SIGNALS)
    return (
        urgent >= 2                                  # e.g. probate + vacancy
        or (urgent >= 1 and (lifecycle + financial) >= 1)  # distress + equity, absentee + downsizer
        or (lifecycle >= 1 and financial >= 1)       # empty-nest + equity (equity-confirmed lifecycle)
    )


class LeadEngine:

    def __init__(self, listing_goal: str = "seller_listing"):
        # "seller_listing" → prospecting owners to sign a LISTING agreement. NAR Code
        #   of Ethics Article 16 / SOP 16-4: do not solicit owners already exclusively
        #   listed with another broker. Active & Coming Soon FMLS records are therefore
        #   routed to COMPLIANCE_HOLD (use for comps / market intel only, not outreach).
        # "buyer_or_market" → buyer-side or market-intelligence use, where Active /
        #   Coming Soon inventory is legitimate to score.
        self.listing_goal = listing_goal

    def score_lead(self, prop: dict) -> dict:
        result = dict(prop)

        # ── Parse inputs ─────────────────────────────────────────────────────
        county        = (prop.get("county") or "").lower()
        city          = (prop.get("city") or "").lower().strip()
        zip_code      = (str(prop.get("zip_code") or "").strip())[:5]
        listing_status = (prop.get("listing_status") or "").lower().strip()
        prop_type     = (prop.get("property_type") or "").lower()
        owner_name    = (prop.get("owner_name") or "").upper()
        years_owned_raw  = prop.get("years_owned")
        years_owned      = int(years_owned_raw or 0)
        gsccca_connected = years_owned_raw is not None  # None = GSCCCA not queried or key absent

        # Flask demo stores full market values in 'assessed_value' (from FMLS ListPrice)
        market_value  = float(prop.get("assessed_value") or 0)

        bedrooms      = max(0, min(int(prop.get("bedrooms") or 0), 10))   # clamp 0-10
        _yb_raw       = int(prop.get("year_built") or 0)
        year_built    = _yb_raw if 1900 <= _yb_raw <= CURRENT_YEAR else 0  # reject impossible values

        is_oos        = bool(prop.get("is_out_of_state_absentee"))
        is_instate    = bool(prop.get("is_in_state_absentee"))
        tax_delinquent = bool(prop.get("tax_delinquent"))
        foreclosure   = bool(prop.get("foreclosure"))
        free_and_clear = bool(prop.get("free_and_clear"))
        equity_pct    = max(0.0, min(float(prop.get("estimated_equity_pct") or 0), 100.0))
        equity_ratio  = (equity_pct / 100) if equity_pct else None
        total_props   = int(prop.get("total_properties_owned") or 1)

        homestead        = bool(prop.get("homestead_exemption"))
        senior_exemption = bool(prop.get("senior_exemption"))
        vacancy          = bool(prop.get("vacancy"))
        mortgage_year    = prop.get("mortgage_year")
        school_score     = prop.get("school_performance_score")
        transfer_type    = (prop.get("transfer_type") or "").lower()

        # Contactability inputs (usually absent until skip-traced — treat unknown as
        # NEUTRAL, never as uncontactable).
        phone            = (prop.get("phone") or "").strip()
        email            = (prop.get("email") or "").strip()
        do_not_call      = bool(prop.get("do_not_call"))
        mailing_verified = bool(prop.get("owner_mailing_address"))

        # ── Scorer state ─────────────────────────────────────────────────────
        motivation_raw = 0
        fit_raw        = 0
        confidence_raw = 0
        exec_fit_used  = 0
        score_cap      = 100
        hard_excluded  = False   # True only for verified business-rule disqualifiers
        flags              = []
        passes             = []
        warnings           = []
        failures           = []
        data_quality_notes = []
        market_context     = []

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
            # Forsyth is not monolithic: the South Forsyth / GA-400 corridor is a
            # high-demand newer-family submarket; outer/rural north Forsyth is slower.
            if zip_code in SOUTH_FORSYTH_ZIPS:
                apply(12, "South Forsyth core — high-demand target submarket", "fit", "pass")
            elif zip_code in OUTER_FORSYTH_ZIPS:
                apply(6, "Outer Forsyth — target county, slower submarket", "fit", "pass")
                market_context.append("Outer/rural Forsyth ZIP — longer DOM; require stronger price, school, or lifecycle support")
            elif zip_code:
                apply(9, "Forsyth County target area", "fit", "pass")
            else:
                apply(9, "Forsyth County target area (ZIP unknown)", "fit", "pass")
            apply(2, "Forsyth County — precise geography", "confidence", "pass")
        elif (is_fulton or not county) and in_target_city:
            apply(12, "North Fulton target city", "fit", "pass")
            apply(2, "City in North Fulton coverage area", "confidence", "pass")
        else:
            apply(-18, "Outside North Fulton or Forsyth County", "fit", "failure")
            score_cap = min(score_cap, 39)
            hard_excluded = True

        # ── Property type ────────────────────────────────────────────────────
        if re.search(r"commercial|industrial|office|retail|hotel|storage|hospital|church|school", prop_type):
            apply(-20, "Nonresidential asset type", "fit", "failure")
            score_cap = min(score_cap, 39)
            hard_excluded = True
        elif re.search(r"single|sfr|detached|residential", prop_type):
            apply(8, "Strong residential property fit", "fit", "pass")
        elif re.search(r"townhouse|townhome|condo|attached", prop_type):
            apply(6, "Attached residential fit", "fit", "pass")
        elif re.search(r"duplex|triplex|multi.?family", prop_type):
            apply(3, "Small residential rental property", "fit", "pass")
        elif prop_type:
            apply(-4, "Unclear property type", "fit", "warning")

        # ── Ownership tenure ─────────────────────────────────────────────────
        # A TRUSTEE'S DEED / gift moving a long-held home into a revocable trust is NOT
        # an arm's-length recent purchase — it must not trigger the recent-sale penalty.
        is_life_event_transfer = bool(re.search(
            r"quit.?claim|estate|inherited|inheritance|divorce|sheriff|relocation|"
            r"non.?arm|family transfer|trust transfer|gift|deed of gift",
            transfer_type,
        ))
        if gsccca_connected:
            if years_owned < 3:
                if is_life_event_transfer:
                    # Inherited / divorce / relocation transfers aren't speculative flips — soften penalty
                    apply(-4, "Short tenure — life-event transfer (override)", "motivation", "warning")
                    warnings.append("Recent transfer under 3 yr — likely estate/divorce/relocation, verify before outreach")
                else:
                    apply(-18, "Recent sale under 3 years", "motivation", "failure")
            elif years_owned >= 15:
                apply(10, f"Owned {years_owned}+ years", "motivation", "flag")
            elif years_owned >= 8:
                apply(6, f"Owned {years_owned}+ years", "motivation", "pass")
            elif years_owned >= 5:
                apply(3, f"Owned {years_owned}+ years", "motivation", "pass")

        # ── Market value ─────────────────────────────────────────────────────
        # Audit T25: a MISSING value (0/None) is unknown, not "sub-$200k". Only a
        # positive value below threshold is a true business-rule exclusion; an
        # unknown value lowers confidence and requires AVM/assessment enrichment.
        ceiling = SUBMARKET_CEILINGS.get(city, 1_800_000 if is_forsyth else 1_500_000)
        if market_value <= 0:
            apply(-3, "Property value unknown — enrich with AVM/assessment", "confidence", "warning")
            data_quality_notes.append("Market value missing — value-band fit and GCI not scored")
        elif market_value < 200_000:
            apply(-8, "Value under $200,000 minimum threshold", "fit", "failure")
            score_cap = min(score_cap, 39)
            hard_excluded = True
        elif market_value <= ceiling:
            apply(4, "Within submarket value band", "fit", "pass")
        elif years_owned >= 10 and equity_ratio and equity_ratio >= 0.4:
            apply(3, "Above ceiling but high-equity long-tenure — high-GCI listing candidate", "motivation", "pass")
        else:
            apply(0, "Above submarket ceiling — verify listing motivation", "fit", "warning")

        # ── Probate / estate ─────────────────────────────────────────────────
        # Living trusts are common in affluent North Fulton suburbs — trust alone ≠ probate urgency.
        # Only hard-signal terms (ESTATE/HEIRS/EXECUTOR/ADMINISTRATOR/PROBATE) or a corroborated
        # TRUST (senior + OOS + long tenure + vacancy ≥2) warrant full +18 urgency.
        is_true_probate = bool(
            re.search(r'\b(ESTATE|HEIRS|HEIR|EXECUTOR|ADMINISTRATOR|PROBATE)\b', owner_name)
            or "estate" in transfer_type
            or "probate" in transfer_type
        )
        is_trust_only = bool(re.search(r'\b(TRUST|TRUSTEE)\b', owner_name)) and not is_true_probate

        if is_true_probate:
            apply(18, "Probate, trust, or estate signal", "motivation", "flag")
        elif is_trust_only:
            trust_corroborators = sum([
                senior_exemption,
                is_oos,
                years_owned >= 15,
                vacancy,
            ])
            if trust_corroborators >= 2:
                # Enough corroboration — treat as succession/estate-planning urgency
                apply(18, "Probate, trust, or estate signal", "motivation", "flag")
            else:
                # Living trust, insufficient corroboration — soft signal only
                apply(6, "Living trust — possible succession planning", "motivation", "pass")
                warnings.append("Trust name only — corroborate with senior exemption / OOS / long tenure")

        # ── Corporate / entity owner ──────────────────────────────────────────
        # Institutional entities (REITs, banks, builders, ≥10-unit operators) → hard cap.
        # Family LLCs / small landlord entities (≤10 props, no institutional terms) →
        # portfolio-exit opportunity — treat like Mom-and-Pop with entity wrapper.
        is_corporate = _is_corporate(owner_name)
        if is_corporate:
            if _is_institutional(owner_name, total_props):
                apply(-15, "Institutional entity owner — excluded per ownership filter", "fit", "failure")
                score_cap = min(score_cap, 39)
                hard_excluded = True
            else:
                # Small family / landlord LLC — eligible for portfolio-exit listing conversion
                apply(5, "Small-entity owner — portfolio-exit listing candidate", "motivation", "pass")
                if 2 <= total_props <= 5:
                    apply(5, "Mom-and-Pop landlord", "motivation", "flag")
                elif total_props > 5:
                    apply(2, "Small multi-property entity", "motivation", "pass")
        else:
            # Natural-person ownership is ELIGIBILITY, not seller intent — no motivation
            # points (reviewer fix). Landlord scale IS an intent signal, so it stays.
            passes.append("Natural person individual owner")
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
            # Long owner-occupied tenure is a mild intent signal (closer to a life
            # transition); kept modest, and cannot reach HOT without the evidence gate.
            apply(4, "Owner-occupied with long tenure", "motivation", "pass")
        else:
            # Same-address occupancy is context, not intent — no motivation points.
            passes.append("Owner-occupied (same-address owner)")

        # ── Homestead exemption ───────────────────────────────────────────────
        # Audit §6.6 (the most important Realtor-specific fix): most retail listings
        # are owner-occupied before sale. A -12 penalty buries normal owner-occupant
        # lifecycle sellers. Homestead alone is a mild negative (-4); it becomes net
        # POSITIVE when paired with a lifecycle/equity transition window.
        if homestead:
            has_other = any(f in flags for f in [
                "Probate, trust, or estate signal", "Verified tax or foreclosure distress",
                "Property-level vacancy indicator", "Out-of-state absentee", "In-state absentee",
                "Senior exemption lifecycle signal",
            ])
            apply(-3 if has_other else -4, "Verified owner-occupied homestead", "motivation", "warning")
            apply(3, "Homestead status verified", "confidence", "pass")

            # Owner-occupant lifecycle positives (audit §6.6 recommended replacement).
            # These name the normal-seller patterns the old model was blind to.
            if gsccca_connected and years_owned >= 20 and (senior_exemption or bedrooms >= 4):
                apply(8, "Homestead downsizer window — long-tenure owner-occupant", "motivation", "flag")
            elif gsccca_connected and years_owned >= 10 and bedrooms >= 4 and equity_ratio and equity_ratio >= 0.40:
                apply(6, "Homestead move-up window — equity-rich family owner-occupant", "motivation", "flag")

            # Rate-lock is archetype-dependent (audit §8.5): it only bites owners who
            # must finance a NEXT purchase. Downsizers, free-and-clear, senior, and
            # relocating (absentee) sellers are largely immune — skip the penalty.
            rate_lock_immune = free_and_clear or senior_exemption or is_oos or is_instate
            if mortgage_year and 2018 <= int(mortgage_year) <= 2022 and not rate_lock_immune:
                apply(-5, "Rate-lock cohort: 2018–22 sub-4% mortgage — move-up friction", "motivation", "warning")

        # ── Senior exemption ──────────────────────────────────────────────────
        if senior_exemption:
            apply(6, "Senior exemption lifecycle signal", "motivation", "flag")
            apply(2, "Senior exemption verified", "confidence", "pass")

        # ── Georgia tax intelligence (carrying-cost marketability) ─────────────
        # From the quantitative design report: Forsyth County has materially lower
        # carrying costs than Fulton, and its Code L1 senior exemption ELIMINATES
        # school M&O + bond tax with no income limit (worth ~$10K/yr on a $1.5M home).
        # Lower TCO = stronger retail buyer demand (fit). A Forsyth senior who has
        # maximized that benefit and held long is a clean downsizer story (motivation).
        if is_forsyth:
            apply(1, "Forsyth lower tax burden — favorable carrying cost for buyers", "fit", "pass", True)
            if senior_exemption:
                market_context.append("Forsyth Code L1 senior exemption — school tax eliminated (no income limit); strong downsizer net-sheet story")
                if gsccca_connected and years_owned >= 15:
                    apply(3, "Forsyth senior downsizer — long tenure + full school-tax exemption", "motivation", "pass")
        elif is_fulton and senior_exemption:
            market_context.append("Fulton senior school-tax exemption is income-limited — higher carrying cost than Forsyth; useful net-sheet talking point")

        # South Forsyth micro-market context (geography block already scored the ZIP tier).
        if is_forsyth and zip_code in SOUTH_FORSYTH_ZIPS:
            market_context.append("South Forsyth / GA-400 corridor — newer, school-sensitive family demand")

        # ── FMLS listing status (Coming Soon = day-one priority) ───────────────
        # Coming Soon listings don't accrue DOM yet (FMLS Rule). Only relevant for
        # BUYER-side / market use — in seller-listing mode these owners are already
        # represented (see COMPLIANCE_HOLD), so we do not score them as outreach targets.
        if self.listing_goal != "seller_listing" and "coming soon" in listing_status:
            apply(2, "Coming Soon listing — engage before active window opens", "fit", "flag", True)
            market_context.append("Coming Soon status — DOM not yet accruing; prioritize day-one outreach")

        # ── Vacancy ───────────────────────────────────────────────────────────
        if vacancy:
            apply(8, "Property-level vacancy indicator", "motivation", "flag")

        # ── Equity / free-and-clear ───────────────────────────────────────────
        # Equity is CAPACITY to sell, not INTENT to sell (reviewer's key correction).
        # In high-appreciation North Fulton / Forsyth, most owners are equity-rich
        # simply because the market rose. So standalone equity weights are reduced,
        # and the real motivation comes from equity PAIRED with a transition signal.
        high_equity = free_and_clear or (equity_ratio is not None and equity_ratio >= 0.6)
        if free_and_clear:
            apply(10, "Free and clear", "motivation", "flag")
        elif equity_ratio is not None:
            if equity_ratio >= 0.6:
                apply(8, "High-equity owner", "motivation", "flag")
            elif equity_ratio >= 0.4:
                apply(6, "Meaningful equity estimate", "motivation", "pass")
            elif equity_ratio >= 0.2:
                apply(3, "Moderate equity estimate", "motivation", "pass")
            else:
                apply(-2, "Low estimated equity", "motivation", "failure")

        # Equity × transition interactions — this is where equity becomes real intent.
        # These are LIFECYCLE-class flags for the HOT evidence gate (equity-confirmed).
        if high_equity and gsccca_connected and years_owned >= 10 and bedrooms >= 4:
            apply(5, "Equity-backed family lifecycle seller", "motivation", "flag")
        if high_equity and senior_exemption:
            apply(6, "Equity-backed senior downsizer", "motivation", "flag")
        if high_equity and (is_oos or is_instate):
            apply(6, "Equity-rich absentee exit candidate", "motivation", "flag")

        # ── Ownership transfer anomaly ────────────────────────────────────────
        if re.search(r"quit.?claim|family transfer|non.?arm|trust transfer|divorce|sheriff|relocation", transfer_type):
            apply(8, "Ownership transfer anomaly", "motivation", "flag")

        # ── Tax / foreclosure distress ────────────────────────────────────────
        if tax_delinquent or foreclosure:
            apply(18, "Verified tax or foreclosure distress", "motivation", "flag")

        # ── Year built — listing marketability, not seller motivation ────────────
        # Motivation (tenure, equity, absentee, estate, rate-lock) already answers
        # "will they sell?" Build year answers "how easy will it be to sell once listed?"
        # 2005–2020 sweet spot: 5–20 yr tenure, large appreciation, family transitions,
        # modern finishes that buyers expect in North Fulton / South Forsyth.
        if year_built:
            if year_built >= 2021:
                apply(4, "2021+ home — modern inventory, strong buyer demand", "fit", "pass", True)
            elif year_built >= 2005:
                apply(6, "2005–2020 home — prime lifecycle: equity, demand, and transitions aligned", "fit", "pass", True)
            elif year_built >= 1995:
                apply(4, "1995–2004 home — solid suburban stock, entering renovation consideration", "fit", "pass", True)
            elif year_built >= 1985:
                apply(1, "1985–1994 home — older layouts may affect buyer appeal", "fit", "pass", True)
            else:
                apply(-1, "Pre-1985 home — dated systems and layouts reduce buyer demand", "fit", "warning", True)

        # ── Bedroom count → individual buyer appeal ──────────────────────────
        # North Fulton / South Forsyth target buyer is an individual family,
        # not an investor. Bedroom count is the primary listing marketability
        # filter (listing-arsenal: target buyer = young families, move-up buyers).
        if bedrooms >= 5:
            apply(2, "5+ bedroom home — premium family buyer demand", "fit", "pass", True)
        elif bedrooms >= 4:
            apply(2, "4-bedroom home — ideal for North Fulton family buyers", "fit", "pass", True)
        elif bedrooms >= 3:
            apply(1, "3-bedroom home — broad individual buyer appeal", "fit", "pass", True)
        elif 0 < bedrooms <= 2:
            apply(-2, "2 or fewer bedrooms — limited individual buyer pool in this market", "fit", "warning", True)

        # ── Lifecycle signals (empty-nest, school-stage, upgrade seller) ─────
        # Sources: nurture-coach seller profiles — Downsizer, School-Stage,
        # and Upgrade Seller archetypes. Each maps to a distinct listing conversation.
        # Guard: lifecycle signals require confirmed tenure data from GSCCCA.
        if gsccca_connected:
            if bedrooms >= 3 and years_owned >= 20:
                apply(8, "Empty-nest probability", "motivation", "flag")
            elif bedrooms >= 3 and years_owned >= 15:
                apply(6, "Empty-nest probability", "motivation", "flag")
            elif bedrooms >= 4 and years_owned >= 10:
                apply(4, "School-stage lifecycle", "motivation", "flag")
            elif bedrooms == 3 and 7 <= years_owned <= 14 and homestead:
                # Upgrade Seller (nurture-coach): 3-bed starter home with equity buildup.
                # Owner is living in the home, likely outgrowing it — wants to upsize.
                # Most common move-up seller in the North Fulton market.
                apply(6, "Upgrade seller — move-up listing candidate", "motivation", "flag")
            elif years_owned >= 20:
                apply(4, "Long-tenure lifecycle signal", "motivation", "pass")

        # ── Investor-magnet warning (individual buyer focus) ──────────────────
        # Properties that combine severe distress + vacancy + pre-1985 build are
        # more likely to attract cash investors / flippers than individual buyers.
        # Flag so the listing agent can assess the realistic buyer pool.
        if tax_delinquent and vacancy and year_built and year_built < 1985:
            apply(-3, "Distressed vacant pre-1985 home — likely attracts investors over individual buyers", "fit", "warning")

        # ── Original-owner cohort (cohort-analysis: build-year × tenure) ────────
        # If current_year − years_owned ≈ year_built, owner likely purchased new.
        # Original owners of 2000–2018 homes with 10+ yr tenure are the highest-density
        # North Fulton listing conversion cohort: maximum equity, emotional history,
        # and predictable life-stage transitions (empty-nest, upgrade, downsize).
        if gsccca_connected and year_built and years_owned >= 10:
            est_purchase_year = CURRENT_YEAR - years_owned
            if abs(est_purchase_year - year_built) <= 2:
                apply(3, "Likely original owner — bought new, peak equity and lifecycle alignment", "motivation", "pass")

        # ── FRED macro signals (market context, NOT data confidence) ───────────
        # Audit §5.2/§6.16: macro variables describe the market, not the reliability
        # of this lead's data. They route to motivation (seller-timing pressure) or
        # to a non-scoring market-context note — never to the confidence dimension.
        fred_mortgage = prop.get("fred_mortgage_rate")
        fred_unemp    = prop.get("fred_unemployment_rate")
        fred_hpi      = prop.get("fred_hpi_growth")

        if fred_mortgage is not None:
            if float(fred_mortgage) >= 6.25:
                if is_oos or is_instate:
                    apply(2, "Higher-rate environment may pressure non-owner holdings", "motivation", "pass")
                # Owner-occupant rate-lock is handled archetype-aware in the homestead
                # block (mortgage_year + must-buy-next), not as a blanket macro penalty.

        if fred_unemp is not None:
            u = float(fred_unemp)
            if u >= 5.0:
                apply(2, "Local job-market stress — may accelerate seller decisions", "motivation", "pass")
            else:
                market_context.append(f"Atlanta unemployment {u:.1f}% — healthy demand backdrop")

        if fred_hpi is not None:
            # Thresholds recalibrated for the corrected county-specific annual YoY
            # (audit §6.12): real 2025 growth is ~2.4% Forsyth / ~1.2% Fulton, so the
            # old 10%/20% gates never fired. Use realistic post-surge bands.
            hpi = float(fred_hpi)
            if hpi >= 0.05:
                market_context.append(f"County HPI +{hpi*100:.1f}% YoY — strong equity build")
                if is_oos or is_instate:
                    apply(2, "Appreciating market — equity-rich absentee may time exit", "motivation", "pass")
            elif hpi >= 0.02:
                market_context.append(f"County HPI +{hpi*100:.1f}% YoY — steady appreciation")
            elif hpi < 0:
                market_context.append(f"County HPI {hpi*100:.1f}% YoY — softening; price discipline matters")

        # ── Census tract signals ──────────────────────────────────────────────
        census_income  = prop.get("census_median_income")
        census_home    = prop.get("census_median_home_value")
        census_oo_rate = prop.get("census_owner_occupancy_rate")
        census_vac     = prop.get("census_vacancy_rate")
        census_age65   = prop.get("census_age_65_plus_rate")

        if census_income is not None:
            ci = float(census_income)
            if ci >= 180_000:
                apply(2, "Very high-income census tract", "fit", "pass", True)
            elif ci >= 120_000:
                apply(1, "High-income census tract", "fit", "pass", True)

        if census_home is not None:
            ch = float(census_home)
            if ch >= 650_000:
                apply(2, "Premium tract median home values", "fit", "pass", True)
            elif ch >= 450_000:
                apply(1, "Strong tract median home values", "fit", "pass", True)

        if census_oo_rate is not None:
            oo = float(census_oo_rate)
            if oo >= 0.75:
                apply(1, "High owner-occupancy neighborhood", "fit", "pass", True)
            elif oo < 0.50:
                apply(2, "Rental-heavy neighborhood — landlord turnover likely", "motivation", "pass")

        if census_age65 is not None:
            a = float(census_age65)
            if a >= 0.18:
                apply(4, "Older-neighborhood lifecycle signal", "motivation", "flag")
            elif a >= 0.12:
                apply(2, "Mature-neighborhood lifecycle signal", "motivation", "pass")

        if census_vac is not None and float(census_vac) >= 0.06:
            apply(2, "Higher local vacancy rate — selling pressure in area", "motivation", "pass")

        # ── OSM / amenity signals ─────────────────────────────────────────────
        osm_score   = prop.get("osm_amenity_score")
        osm_grocery = prop.get("osm_grocery_count")
        osm_park    = prop.get("osm_park_count")
        osm_near_g  = prop.get("osm_nearest_grocery")
        osm_near_p  = prop.get("osm_nearest_park")
        osm_road    = prop.get("osm_major_road_nearby", False)

        if osm_score is not None:
            os_ = float(osm_score)
            if os_ >= 8:
                apply(2, "Strong walkability and amenity access", "fit", "pass", True)
            elif os_ >= 5:
                apply(1, "Useful nearby amenities", "fit", "pass", True)

        if osm_near_g is not None and float(osm_near_g) <= 1.0:
            apply(1, "Grocery access within one mile", "fit", "pass", True)
        elif osm_grocery is not None and int(osm_grocery) >= 1:
            apply(1, "Grocery access nearby", "fit", "pass", True)

        if osm_near_p is not None and float(osm_near_p) <= 0.75:
            apply(1, "Park access within 0.75 miles", "fit", "pass", True)
        elif osm_park is not None and int(osm_park) >= 2:
            apply(1, "Multiple parks within one mile", "fit", "pass", True)

        if osm_road:
            apply(-3, "Possible major-road noise exposure", "fit", "failure")

        # ── School performance (GOSA ≥92 = $150K–$200K buyer premium in N. Fulton)
        if school_score is not None:
            ss = float(school_score)
            if ss >= 92:
                # School quality drives demand / liquidity (fit), NOT seller motivation
                apply(3, "Premium school performance", "fit", "flag", True)
            elif ss >= 85:
                apply(2, "Strong school performance", "fit", "pass", True)
            elif ss >= 75:
                apply(1, "Solid school performance", "fit", "pass", True)
            elif ss < 65:
                apply(-4, "Weaker school performance", "fit", "failure")

        # ── Data completeness → confidence calibration ─────────────────────────
        # Confidence answers "how much should we trust this lead's score?"
        # Penalize when key enrichment sources are absent; reward confirmed data.
        if gsccca_connected and years_owned > 0:
            apply(3, "Tenure confirmed via GSCCCA", "confidence", "pass")
        elif not gsccca_connected:
            apply(-5, "GSCCCA unavailable — tenure and lifecycle signals unknown", "confidence", "failure")
            data_quality_notes.append("GSCCCA not connected — years_owned unknown; lifecycle signals (empty-nest, upgrade seller) not scored")

        if equity_ratio is not None or free_and_clear:
            apply(2, "Equity position confirmed", "confidence", "pass")
        else:
            apply(-3, "Equity estimate unavailable", "confidence", "failure")
            data_quality_notes.append("Equity data unavailable — financial motivation score relies on free-and-clear status only")

        if bedrooms > 0:
            apply(1, "Bedroom count confirmed", "confidence", "pass")
        else:
            data_quality_notes.append("Bedroom count missing — listing fit score may be understated")

        if year_built > 0:
            apply(1, "Year built confirmed", "confidence", "pass")
        else:
            data_quality_notes.append("Year built unknown — marketability signal not scored")

        if is_oos:
            data_quality_notes.append("Out-of-state owner — phone/email enrichment needed before outreach")

        # ── Guards ────────────────────────────────────────────────────────────
        # "Owned X+ years" flag text is dynamic — check by prefix so it counts as positive.
        has_positive = (
            any(f in POSITIVE_MOTIVATION_FLAGS for f in flags)
            or any(f.startswith("Owned ") and f.endswith("+ years") for f in flags)
        )
        if not has_positive and motivation_raw <= 5:
            score_cap = min(score_cap, 38)
            warnings.append("No seller motivation signals detected — capped below tier-C")

        # OOS alone (without 10+ yr tenure or overriding distress) → cap at B-tier.
        # Only apply when GSCCCA is connected and tenure is confirmed short; if tenure
        # is unknown (GSCCCA offline) we cannot penalize for unverified data.
        has_oos_flag   = "Out-of-state absentee" in flags
        has_long_tenure = gsccca_connected and years_owned >= 10
        has_overriding = any(f in flags for f in [
            "Probate, trust, or estate signal", "Verified tax or foreclosure distress",
            "Property-level vacancy indicator", "Ownership transfer anomaly",
        ])
        if has_oos_flag and not has_overriding:
            if gsccca_connected and not has_long_tenure:
                score_cap = min(score_cap, 54)
                warnings.append("OOS absentee — tenure confirmed short (< 10 yr via GSCCCA), capped at B-tier")
            elif not gsccca_connected:
                warnings.append("OOS absentee — GSCCCA offline, 10-yr tenure unverified")

        # ── Blend scores ──────────────────────────────────────────────────────
        # Motivation uses a LOGISTIC transform (audit §5.2/§8.2 — fixes the Figure 1
        # "fast saturation" defect). The old linear 30+raw×2.4 pinned every motivated
        # lead at 100, so a probate-only lead and an estate+absentee+vacant+free-clear
        # lead scored identically and the top tier could not be ranked. The logistic
        # gives diminishing returns: one strong signal lands ~55-65, stacked signals
        # spread up toward ~95 without everyone hitting the ceiling.
        #   raw  -18 → 10   |  4 → 37  |  12 → 52  |  18 → 63  |  30 → 81  |  50 → 95
        motivation_score = round(100 / (1 + math.exp(-0.076 * (motivation_raw - 11.1))))
        motivation_score = max(0, min(100, motivation_score))
        # Fit is also LOGISTIC now (reviewer fix). The old linear 45 + fit_raw×2.1
        # saturated at 100 for any ordinary target-market SFR (geography + SFR + build
        # year alone ≈ raw 26), so "good" and "excellent" listings were indistinguishable.
        # Logistic spreads them: raw 12→29, 20→50, 26→66, 32→79, 40→90.
        fit_score        = round(100 / (1 + math.exp(-0.11 * (fit_raw - 20))))
        fit_score        = max(0, min(100, fit_score))
        confidence_score = max(0, min(100, round(72 + confidence_raw * 4)))
        blended = motivation_score * 0.6 + fit_score * 0.25 + confidence_score * 0.15
        score   = max(0, min(100, min(round(blended), score_cap)))

        # ── Contactability (operational, not qualification) ───────────────────
        # Unknown contact data is NEUTRAL (50), never "uncontactable" — most leads
        # aren't skip-traced yet. Verified contact lifts operational priority; DNC
        # sinks it. This adjusts ranking WITHOUT corrupting the qualification score.
        contactability_score = 50
        if phone:            contactability_score += 25
        if email:            contactability_score += 15
        if mailing_verified: contactability_score += 10
        if do_not_call:      contactability_score -= 45
        contactability_score = max(0, min(100, contactability_score))
        contact_factor = 0.80 + 0.004 * contactability_score   # 0→0.80, 50→1.0, 100→1.20
        operational_priority = round(score * contact_factor, 1)

        # ── Tier assignment ───────────────────────────────────────────────────
        tier = _tier(score)

        # HOT evidence gate (reviewer's central fix): HOT requires both a high
        # motivation score AND independent corroborating intent signals. Equity alone
        # or long tenure alone cannot manufacture HOT.
        if tier == "HOT" and motivation_score < 62:
            tier = "WARM"
            warnings.append("Held at WARM — strong score but motivation score below HOT floor")
        elif tier == "HOT" and not _hot_evidence_ok(flags):
            tier = "WARM"
            warnings.append("Held at WARM — high score but insufficient independent seller-intent evidence (e.g. equity alone)")
        if tier == "WARM" and motivation_score < 45:
            tier = "COOL"

        # REVIEW tier (audit §13.3): marketable property whose seller intent is unknown
        # only because data is missing — enrich rather than discard.
        tenure_unknown = not gsccca_connected
        if (tier in ("PASS", "COOL")
                and not hard_excluded
                and fit_score >= 55
                and tenure_unknown):
            tier = "REVIEW"
            data_quality_notes.append("Strong property fit but seller intent unknown — enrich tenure/equity before discarding")

        # Do-not-call is a hard operational ceiling regardless of qualification.
        if do_not_call and tier in ("HOT", "WARM"):
            tier = "COOL"
            warnings.append("Owner on Do-Not-Call list — demoted; written/mail outreach only")

        # COMPLIANCE_HOLD (NAR Article 16 / SOP 16-4): in seller-listing mode, an owner
        # already represented (Active / Coming Soon on FMLS) must not be solicited for a
        # listing. Overrides all other tiers — use for comps / market intel only.
        is_listed_elsewhere = listing_status in ("active", "coming soon")
        if self.listing_goal == "seller_listing" and is_listed_elsewhere:
            tier = "COMPLIANCE_HOLD"
            warnings.append("Already listed/Coming-Soon with a broker — NAR Article 16: do not solicit for listing")
            market_context.append("Source record is an active MLS listing; appropriate for buyer-side or comp use only, not seller prospecting")

        strategy = _strategy(flags, failures, tier)

        return {
            **result,
            "score":            score,
            "tier":             tier,
            "motivation_score": motivation_score,
            "fit_score":        fit_score,
            "confidence_score": confidence_score,
            "contactability_score":     contactability_score,
            "operational_priority":     operational_priority,
            "strategy":         strategy,
            "flags":            list(dict.fromkeys(flags)),
            "passes":           list(dict.fromkeys(passes)),
            "warnings":         list(dict.fromkeys(warnings)),
            "failures":                list(dict.fromkeys(failures)),
            "priority_band":            _priority_band(tier),
            "estimated_conversion_pct": _conversion_pct(tier),
            "expected_gci_range":       _gci_range(tier),
            "data_quality_notes":       data_quality_notes,
            "market_context":           market_context,
            # ── Debug / calibration export (raw components) ───────────────────
            "motivation_raw":           motivation_raw,
            "fit_raw":                  fit_raw,
            "confidence_raw":           confidence_raw,
            "score_cap_applied":        score_cap,
            "hot_evidence_ok":          _hot_evidence_ok(flags),
            "urgent_signal_count":      len(set(flags) & URGENT_SIGNALS),
            "lifecycle_signal_count":   len(set(flags) & LIFECYCLE_SIGNALS),
            "financial_signal_count":   len(set(flags) & FINANCIAL_SIGNALS),
        }


# ── Helpers ────────────────────────────────────────────────────────────────────

def _is_corporate(name_upper: str) -> bool:
    padded = " " + name_upper.lower() + " "
    return any(t in padded for t in CORPORATE_TERMS)


def _is_institutional(name_upper: str, total_props: int) -> bool:
    """Return True if the corporate entity shows institutional-scale signals.
    Large volume (>10 props) or institutional name terms → hard cap applies.
    Small LLCs / family holding entities without these terms → portfolio-exit path.
    """
    if total_props > 10:
        return True
    padded = " " + name_upper.lower() + " "
    return any(t in padded for t in INSTITUTIONAL_TERMS)


def _tier(score: int) -> str:
    if score >= 70:  return "HOT"
    if score >= 55:  return "WARM"
    if score >= 40:  return "COOL"
    return "PASS"


def _strategy(flags: list, failures: list, tier: str) -> str:
    if tier == "COMPLIANCE_HOLD":
        return "Already listed with a broker — do NOT solicit (NAR Art. 16); comps / buyer-side only"
    if tier == "REVIEW":
        return "Marketable home, intent unknown — verify tenure/equity, then re-score"
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
    if "Upgrade seller — move-up listing candidate" in flags: return "Upgrade seller — upsize listing opportunity"
    if "School-stage lifecycle" in flags:                   return "School-stage mover — listing opportunity"
    if "Free and clear" in flags or "High-equity owner" in flags:
        return "Equity-rich seller — strong listing position"
    if "Premium school performance" in flags:
        return "Premium school zone — fast-sale listing"
    if "Senior exemption lifecycle signal" in flags:        return "Senior downsizer — listing opportunity"

    if tier == "HOT":  return "Priority outreach — call within 24 hours"
    if tier == "WARM": return "Warm outreach — schedule call this week"
    return "Nurture — monitor for motivation signals"


def _priority_band(tier: str) -> str:
    """Relative work-priority label (audit §4.2: use relative priority, not implied
    conversion %, until real outreach outcomes are logged)."""
    return {
        "HOT":    "P1 — work first",
        "WARM":   "P2 — work this week",
        "COOL":   "P3 — nurture queue",
        "REVIEW": "P2-hold — enrich data first",
        "COMPLIANCE_HOLD": "Hold — do not solicit (Art. 16)",
        "PASS":   "P4 — excluded",
    }.get(tier, "unknown")


def _conversion_pct(tier: str) -> str:
    """RELATIVE listing-conversion likelihood by tier.

    Audit §4.2 / §7 (P2): the prior absolute ranges (HOT 15–25%) are unrealistic for
    cold outbound and unvalidated. These are ordinal expectations to be replaced with
    measured precision@K once outreach outcomes are logged — NOT promised rates.
    """
    return {
        "HOT":    "Highest relative likelihood",
        "WARM":   "Moderate relative likelihood",
        "COOL":   "Lower — nurture",
        "REVIEW": "Unknown until enriched",
        "COMPLIANCE_HOLD": "Not applicable — do not solicit",
        "PASS":   "Excluded",
    }.get(tier, "unknown")


def _gci_range(tier: str) -> str:
    """Illustrative GCI per converted listing (~$875K avg list × 2.5% side).
    Shown as opportunity size, not a forecast — conversion probability is unvalidated."""
    return {
        "HOT":    "~$21,900 GCI per signed listing (illustrative)",
        "WARM":   "~$21,900 GCI per signed listing (illustrative)",
        "COOL":   "~$21,900 GCI per signed listing (illustrative)",
        "REVIEW": "Size after data enrichment",
        "COMPLIANCE_HOLD": "Not a listing-prospect record",
        "PASS":   "Below outreach threshold",
    }.get(tier, "")
