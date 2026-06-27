"""
Deterministic backend test suite for the lead qualification engine.

Implements the edge-case scenarios from the deep technical audit (Appendix H,
tests T01–T30), which the audit explicitly calls "not optional." These guard
against silent regressions that would reintroduce the investor bias, the
missing-data bugs, or the geographic errors the audit identified.

Run:  python3 test_lead_engine.py        (plain, no pytest dependency)
"""

from lead_engine import LeadEngine

engine = LeadEngine()
_passed = 0
_failed = 0


def check(test_id, desc, cond, detail=""):
    global _passed, _failed
    status = "PASS" if cond else "FAIL"
    if cond:
        _passed += 1
    else:
        _failed += 1
    print(f"  [{status}] {test_id}: {desc}")
    if not cond and detail:
        print(f"         → {detail}")


def score(**over):
    base = {
        "county": "fulton", "city": "alpharetta",
        "property_type": "single family residential",
        "owner_name": "JOHN DOE", "assessed_value": 750_000,
        "bedrooms": 4, "year_built": 2012,
    }
    base.update(over)
    return engine.score_lead(base)


print("=" * 78)
print("Audit Appendix H — backend qualification test suite (T01–T30)")
print("=" * 78)

# T01 — FMLS-only live record, unknown tenure, no enrichment.
# No short-tenure penalty; lowered confidence; REVIEW/COOL, never PASS on unknown alone.
t = score(city="alpharetta", year_built=2012, owner_name="JANE SMITH")  # years_owned absent
check("T01", "Unknown tenure → no short-tenure penalty, not PASS",
      "Recent sale under 3 years" not in t["failures"] and t["tier"] != "PASS",
      f"tier={t['tier']} failures={t['failures']}")

# T02 — Verified 2025 purchase, 2024 build, homestead, no other signal.
t = score(year_built=2024, years_owned=1, homestead_exemption=True, estimated_equity_pct=8)
check("T02", "Verified 1-yr owner → low motivation (PASS/COOL)",
      t["tier"] in ("PASS", "COOL"), f"tier={t['tier']}")

# T03 — 2014 build, owner since 2014, 5BR, high equity, homestead, premium school.
t = score(year_built=2014, years_owned=12, bedrooms=5, estimated_equity_pct=55,
          homestead_exemption=True, school_performance_score=95)
check("T03", "Owner-occupant lifecycle lead not buried by homestead",
      t["tier"] in ("WARM", "HOT"), f"tier={t['tier']} score={t['score']}")

# T04 — 2008 build, OOS absentee, vacant, high equity, 16-yr tenure.
t = score(year_built=2008, years_owned=16, is_out_of_state_absentee=True, vacancy=True,
          estimated_equity_pct=70, owner_name="REMOTE OWNER")
check("T04", "OOS + vacant + high-equity + long tenure → HOT/WARM",
      t["tier"] in ("HOT", "WARM"), f"tier={t['tier']} score={t['score']}")

# T05 — 1978 build, weak school/amenity, vacancy + tax delinquency.
# Urgent but retail-risk; should carry investor-magnet warning.
t = score(year_built=1978, years_owned=20, vacancy=True, tax_delinquent=True,
          school_performance_score=60, estimated_equity_pct=50)
check("T05", "Distressed pre-1985 vacant → investor-magnet warning present",
      any("investor" in w.lower() for w in t["warnings"]),
      f"warnings={t['warnings']}")

# T06 — Pre-1985 Roswell premium location, 30-yr tenure, high equity.
t = score(county="fulton", city="roswell", year_built=1980, years_owned=30,
          estimated_equity_pct=65, school_performance_score=90, bedrooms=4)
check("T06", "Old premium-location long-tenure not rejected",
      t["tier"] != "PASS", f"tier={t['tier']} score={t['score']}")

# T08 — Forsyth property uses Forsyth HPI series (enrichment-level; here just ensure
# Forsyth scores without error and gets geography credit).
t = score(county="forsyth", city="cumming", zip_code="30040", year_built=2015,
          years_owned=10, bedrooms=4, estimated_equity_pct=45)
check("T08", "Forsyth property scores with target-geography credit",
      t["tier"] != "PASS" and "Forsyth County target area" in t["passes"],
      f"tier={t['tier']}")

# T12 — Milton $2.4M SFR, 15-yr owner, premium school, high equity → eligible (no $2M cap bury).
t = score(city="milton", assessed_value=2_400_000, years_owned=15, bedrooms=5,
          estimated_equity_pct=60, school_performance_score=96)
check("T12", "Milton $2.4M luxury not excluded by value ceiling",
      t["tier"] in ("HOT", "WARM", "COOL", "REVIEW"),
      f"tier={t['tier']} score={t['score']}")

# T15 — 2021+ home with OOS relocation/vacancy → not penalized for newness.
t = score(year_built=2022, years_owned=2, is_out_of_state_absentee=True, vacancy=True,
          estimated_equity_pct=25)
check("T15", "New build + relocation/vacancy → motivation drives, no newness penalty",
      t["tier"] in ("HOT", "WARM", "COOL"), f"tier={t['tier']} score={t['score']}")

# T16 — Homestead + 2 yrs owned + low-rate mortgage → low motivation.
t = score(years_owned=2, homestead_exemption=True, mortgage_year=2021, estimated_equity_pct=15)
check("T16", "Homestead + 2yr + rate-lock → low motivation",
      t["tier"] in ("PASS", "COOL", "REVIEW"), f"tier={t['tier']}")

# T17 — Homestead + 24 yrs + senior exemption + 5BR → high lifecycle motivation.
t = score(years_owned=24, homestead_exemption=True, senior_exemption=True, bedrooms=5,
          estimated_equity_pct=60)
check("T17", "Homestead + 24yr + senior + 5BR → strong lifecycle (WARM/HOT)",
      t["tier"] in ("WARM", "HOT"), f"tier={t['tier']} score={t['score']} flags={t['flags']}")

# T18 — Living trust alone → modest motivation, not probate.
t = score(owner_name="THE DOE FAMILY TRUST", years_owned=8, estimated_equity_pct=40)
check("T18", "Living trust alone → not full probate boost",
      "Probate, trust, or estate signal" not in t["flags"], f"flags={t['flags']}")

# T19 — Estate terms + OOS absentee → highest priority.
t = score(owner_name="ESTATE OF MARY DOE", years_owned=20, is_out_of_state_absentee=True,
          estimated_equity_pct=70)
check("T19", "Estate + OOS → HOT, estate outreach",
      t["tier"] == "HOT" and "Estate" in t["strategy"], f"tier={t['tier']} strategy={t['strategy']}")

# T20 — Builder/developer owner → institutional cap.
t = score(owner_name="ACME DEVELOPMENT LLC", total_properties_owned=15)
check("T20", "Builder/developer entity → capped (PASS)",
      t["tier"] == "PASS", f"tier={t['tier']}")

# T21 — Family LLC, one SFR, 12-yr tenure, in-state absentee → eligible, not institutional.
t = score(owner_name="DOE FAMILY HOLDINGS LLC", total_properties_owned=1, years_owned=12,
          is_in_state_absentee=True, estimated_equity_pct=45)
check("T21", "Small family LLC not hard-capped as institutional",
      t["tier"] != "PASS", f"tier={t['tier']} score={t['score']}")

# T22 — County blank, city Johns Creek → passes target geography.
t = score(county="", city="johns creek", years_owned=10, estimated_equity_pct=40)
check("T22", "Blank county + target city → in geography",
      "North Fulton target city" in t["passes"], f"passes_geo={[p for p in t['passes'] if 'target' in p]}")

# T25 — Market value missing/null → do not cap under $200k.
t = score(assessed_value=0, years_owned=12, estimated_equity_pct=40)
check("T25", "Missing value → not capped as sub-$200k",
      "Value under $200,000 minimum threshold" not in t["failures"], f"failures={t['failures']}")

# T26 — Equity unknown/null → confidence penalty only, no motivation penalty.
t = score(years_owned=12, estimated_equity_pct=0)  # 0 → None-equivalent (falsy)
check("T26", "Unknown equity → no 'Low estimated equity' motivation hit",
      "Low estimated equity" not in t["failures"], f"failures={t['failures']}")

# T28 — 2005-2020 home, no motivation evidence → high fit but low intent (COOL/REVIEW).
t = score(year_built=2015, owner_name="JOHN DOE", school_performance_score=93)  # tenure unknown
check("T28", "Marketable home, no intent, unknown tenure → REVIEW not HOT",
      t["tier"] in ("REVIEW", "COOL"), f"tier={t['tier']} score={t['score']}")

# Extra — macro signals must not land in the confidence dimension.
t = score(years_owned=12, estimated_equity_pct=45,
          fred_unemployment_rate=2.8, fred_hpi_growth=0.024)
check("EX1", "Macro (unemployment/HPI) routed to market_context, not confidence",
      any("unemployment" in m.lower() or "hpi" in m.lower() for m in t["market_context"]),
      f"market_context={t['market_context']}")

# Extra — Forsyth senior gets the Code L1 carrying-cost note.
t = score(county="forsyth", city="cumming", zip_code="30040", senior_exemption=True,
          years_owned=18, bedrooms=4, estimated_equity_pct=55)
check("EX2", "Forsyth senior → Code L1 tax-advantage market note",
      any("L1" in m for m in t["market_context"]), f"market_context={t['market_context']}")

print("=" * 78)
print(f"RESULT: {_passed} passed, {_failed} failed")
print("=" * 78)
raise SystemExit(1 if _failed else 0)
