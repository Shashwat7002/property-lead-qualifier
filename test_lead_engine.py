"""
Deterministic backend test suite for the lead qualification engine.

Implements the edge-case scenarios from the deep technical audit (Appendix H,
tests T01–T30) plus the R-series regression tests for the final-review fixes
(HOT evidence gate, equity-as-capacity, Fit logistic, compliance hold, etc.).

Run two ways:
    python3 test_lead_engine.py     # standalone, prints a PASS/FAIL table
    pytest test_lead_engine.py      # CI — collects test_audit_suite()

The module no longer raises SystemExit at import time, so pytest collection is clean.
"""

from lead_engine import LeadEngine

engine = LeadEngine()                       # default: seller_listing mode
buyer_engine = LeadEngine(listing_goal="buyer_or_market")


def score(**over):
    base = {
        "county": "fulton", "city": "alpharetta",
        "property_type": "single family residential",
        "owner_name": "JOHN DOE", "assessed_value": 750_000,
        "bedrooms": 4, "year_built": 2012,
    }
    base.update(over)
    return engine.score_lead(base)


def run_suite(verbose=True):
    """Run all checks. Returns the number of failures (0 = all green)."""
    passed = failed = 0

    def check(test_id, desc, cond, detail=""):
        nonlocal passed, failed
        if cond:
            passed += 1
        else:
            failed += 1
        if verbose:
            print(f"  [{'PASS' if cond else 'FAIL'}] {test_id}: {desc}")
            if not cond and detail:
                print(f"         → {detail}")

    if verbose:
        print("=" * 78)
        print("Backend qualification test suite — audit (T) + final-review fixes (R)")
        print("=" * 78)

    # ── Audit Appendix H (T-series) ──────────────────────────────────────────
    t = score(city="alpharetta", year_built=2012, owner_name="JANE SMITH")
    check("T01", "Unknown tenure → no short-tenure penalty, not PASS",
          "Recent sale under 3 years" not in t["failures"] and t["tier"] != "PASS",
          f"tier={t['tier']} failures={t['failures']}")

    t = score(year_built=2024, years_owned=1, homestead_exemption=True, estimated_equity_pct=8)
    check("T02", "Verified 1-yr owner → low motivation (PASS/COOL)",
          t["tier"] in ("PASS", "COOL"), f"tier={t['tier']}")

    t = score(year_built=2014, years_owned=12, bedrooms=5, estimated_equity_pct=55,
              homestead_exemption=True, school_performance_score=95)
    check("T03", "Owner-occupant lifecycle lead not buried by homestead",
          t["tier"] in ("WARM", "HOT"), f"tier={t['tier']} score={t['score']}")

    t = score(year_built=2008, years_owned=16, is_out_of_state_absentee=True, vacancy=True,
              estimated_equity_pct=70, owner_name="REMOTE OWNER")
    check("T04", "OOS + vacant + high-equity + long tenure → HOT/WARM",
          t["tier"] in ("HOT", "WARM"), f"tier={t['tier']} score={t['score']}")

    t = score(year_built=1978, years_owned=20, vacancy=True, tax_delinquent=True,
              school_performance_score=60, estimated_equity_pct=50)
    check("T05", "Distressed pre-1985 vacant → investor-magnet warning present",
          any("investor" in w.lower() for w in t["warnings"]), f"warnings={t['warnings']}")

    t = score(county="fulton", city="roswell", year_built=1980, years_owned=30,
              estimated_equity_pct=65, school_performance_score=90, bedrooms=4)
    check("T06", "Old premium-location long-tenure not rejected",
          t["tier"] != "PASS", f"tier={t['tier']} score={t['score']}")

    t = score(county="forsyth", city="cumming", zip_code="30040", year_built=2015,
              years_owned=10, bedrooms=4, estimated_equity_pct=45)
    check("T08", "Forsyth property scores with target-geography credit",
          t["tier"] != "PASS" and any("Forsyth" in p for p in t["passes"]),
          f"tier={t['tier']} passes={[p for p in t['passes'] if 'Forsyth' in p]}")

    south = score(county="forsyth", city="cumming", zip_code="30040", year_built=2015,
                  years_owned=10, bedrooms=4, estimated_equity_pct=45)
    outer = score(county="forsyth", city="cumming", zip_code="30028", year_built=2015,
                  years_owned=10, bedrooms=4, estimated_equity_pct=45)
    check("T08b", "Outer Forsyth fit_raw < South Forsyth fit_raw",
          outer["fit_raw"] < south["fit_raw"],
          f"outer={outer['fit_raw']} south={south['fit_raw']}")

    t = score(city="milton", assessed_value=2_400_000, years_owned=15, bedrooms=5,
              estimated_equity_pct=60, school_performance_score=96)
    check("T12", "Milton $2.4M luxury not excluded by value ceiling",
          t["tier"] in ("HOT", "WARM", "COOL", "REVIEW"), f"tier={t['tier']} score={t['score']}")

    t = score(year_built=2022, years_owned=2, is_out_of_state_absentee=True, vacancy=True,
              estimated_equity_pct=25)
    check("T15", "New build + relocation/vacancy → motivation drives, no newness penalty",
          t["tier"] in ("HOT", "WARM", "COOL"), f"tier={t['tier']} score={t['score']}")

    t = score(years_owned=2, homestead_exemption=True, mortgage_year=2021, estimated_equity_pct=15)
    check("T16", "Homestead + 2yr + rate-lock → low motivation",
          t["tier"] in ("PASS", "COOL", "REVIEW"), f"tier={t['tier']}")

    t = score(years_owned=24, homestead_exemption=True, senior_exemption=True, bedrooms=5,
              estimated_equity_pct=60)
    check("T17", "Homestead + 24yr + senior + 5BR → strong lifecycle (WARM/HOT)",
          t["tier"] in ("WARM", "HOT"), f"tier={t['tier']} score={t['score']}")

    t = score(owner_name="THE DOE FAMILY TRUST", years_owned=8, estimated_equity_pct=40)
    check("T18", "Living trust alone → not full probate boost",
          "Probate, trust, or estate signal" not in t["flags"], f"flags={t['flags']}")

    t = score(owner_name="ESTATE OF MARY DOE", years_owned=20, is_out_of_state_absentee=True,
              estimated_equity_pct=70)
    check("T19", "Estate + OOS → HOT, estate outreach",
          t["tier"] == "HOT" and "Estate" in t["strategy"],
          f"tier={t['tier']} strategy={t['strategy']}")

    t = score(owner_name="ACME DEVELOPMENT LLC", total_properties_owned=15)
    check("T20", "Builder/developer entity → capped (PASS)",
          t["tier"] == "PASS", f"tier={t['tier']}")

    t = score(owner_name="DOE FAMILY HOLDINGS LLC", total_properties_owned=1, years_owned=12,
              is_in_state_absentee=True, estimated_equity_pct=45)
    check("T21", "Small family LLC not hard-capped as institutional",
          t["tier"] != "PASS", f"tier={t['tier']} score={t['score']}")

    t = score(county="", city="johns creek", years_owned=10, estimated_equity_pct=40)
    check("T22", "Blank county + target city → in geography",
          "North Fulton target city" in t["passes"],
          f"passes={[p for p in t['passes'] if 'target' in p]}")

    t = score(assessed_value=0, years_owned=12, estimated_equity_pct=40)
    check("T25", "Missing value → not capped as sub-$200k",
          "Value under $200,000 minimum threshold" not in t["failures"], f"failures={t['failures']}")

    t = score(years_owned=12, estimated_equity_pct=0)
    check("T26", "Unknown equity → no 'Low estimated equity' motivation hit",
          "Low estimated equity" not in t["failures"], f"failures={t['failures']}")

    t = score(year_built=2015, owner_name="JOHN DOE", school_performance_score=93)
    check("T28", "Marketable home, no intent, unknown tenure → REVIEW not HOT",
          t["tier"] in ("REVIEW", "COOL"), f"tier={t['tier']} score={t['score']}")

    t = score(years_owned=12, estimated_equity_pct=45,
              fred_unemployment_rate=2.8, fred_hpi_growth=0.024)
    check("EX1", "Macro routed to market_context, not confidence",
          any("unemployment" in m.lower() or "hpi" in m.lower() for m in t["market_context"]),
          f"market_context={t['market_context']}")

    t = score(county="forsyth", city="cumming", zip_code="30040", senior_exemption=True,
              years_owned=18, bedrooms=4, estimated_equity_pct=55)
    check("EX2", "Forsyth senior → Code L1 tax-advantage market note",
          any("L1" in m for m in t["market_context"]), f"market_context={t['market_context']}")

    # ── Final-review fixes (R-series) ────────────────────────────────────────

    # R01 — High equity ALONE must not produce HOT (equity = capacity, not intent).
    t = score(year_built=2015, bedrooms=4, estimated_equity_pct=65,
              school_performance_score=95, owner_name="JOHN DOE")  # tenure unknown, no other signal
    check("R01", "High equity alone → NOT HOT (held at WARM or lower)",
          t["tier"] != "HOT", f"tier={t['tier']} score={t['score']} hot_evidence_ok={t['hot_evidence_ok']}")

    # R02 — Long tenure + 4BR ALONE (no equity/senior/absentee) must not be HOT.
    t = score(year_built=2015, years_owned=15, bedrooms=4, homestead_exemption=False,
              school_performance_score=95, estimated_equity_pct=0)  # equity unknown
    check("R02", "Long tenure + 4BR alone → NOT HOT",
          t["tier"] != "HOT", f"tier={t['tier']} score={t['score']} flags={t['flags']}")

    # R03 — Equity-CONFIRMED lifecycle (high equity + long tenure + 4BR) CAN be HOT.
    t = score(year_built=2012, years_owned=14, bedrooms=4, estimated_equity_pct=70,
              homestead_exemption=True, school_performance_score=95)
    check("R03", "High equity + long tenure + 4BR (equity-confirmed lifecycle) → may reach HOT",
          t["hot_evidence_ok"] is True, f"tier={t['tier']} flags={t['flags']}")

    # R04 — Estate + vacancy (two urgent signals) clears the evidence gate.
    t = score(owner_name="ESTATE OF JANE DOE", years_owned=18, vacancy=True, estimated_equity_pct=60)
    check("R04", "Estate + vacancy (2 urgent) → evidence gate passes",
          t["hot_evidence_ok"] is True, f"tier={t['tier']} urgent={t['urgent_signal_count']}")

    # R05 — Natural-person ownership adds NO motivation (eligibility only).
    plain = score(year_built=2015, owner_name="JOHN DOE", estimated_equity_pct=0)  # no signals
    check("R05", "Natural person owner adds no motivation_raw inflation",
          "Natural person individual owner" in plain["passes"]
          and "Natural person owner" not in plain["flags"],
          f"passes-has-natural={'Natural person individual owner' in plain['passes']}")

    # R06 — Fit no longer saturates: an excellent listing scores higher Fit than an
    #       adequate one (logistic spreads them instead of both pinning at 100).
    adequate = score(year_built=1990, bedrooms=3, city="roswell")
    excellent = score(year_built=2015, bedrooms=5, city="milton", school_performance_score=97)
    check("R06", "Fit logistic distinguishes excellent vs adequate (both < 100, ordered)",
          excellent["fit_score"] > adequate["fit_score"] and excellent["fit_score"] < 100,
          f"adequate={adequate['fit_score']} excellent={excellent['fit_score']}")

    # R07 — Trust transfer + short tenure does NOT fire the recent-sale penalty.
    t = score(years_owned=2, transfer_type="trust transfer", owner_name="DOE FAMILY TRUST")
    check("R07", "Recent trust transfer → no '-18 recent sale' penalty",
          "Recent sale under 3 years" not in t["failures"], f"failures={t['failures']}")

    # R08 — Compliance hold: Active listing in seller mode → COMPLIANCE_HOLD.
    active = engine.score_lead({
        "county": "fulton", "city": "alpharetta", "property_type": "single family residential",
        "owner_name": "JOHN DOE", "assessed_value": 800_000, "bedrooms": 4, "year_built": 2015,
        "listing_status": "Active", "years_owned": 18, "estimated_equity_pct": 60,
    })
    check("R08", "Active listing in seller_listing mode → COMPLIANCE_HOLD",
          active["tier"] == "COMPLIANCE_HOLD", f"tier={active['tier']}")

    # R08b — Same record in buyer/market mode is scored normally (not held).
    active_buyer = buyer_engine.score_lead({
        "county": "fulton", "city": "alpharetta", "property_type": "single family residential",
        "owner_name": "JOHN DOE", "assessed_value": 800_000, "bedrooms": 4, "year_built": 2015,
        "listing_status": "Active", "years_owned": 18, "estimated_equity_pct": 60,
    })
    check("R08b", "Active listing in buyer_or_market mode → NOT compliance-held",
          active_buyer["tier"] != "COMPLIANCE_HOLD", f"tier={active_buyer['tier']}")

    # R09 — Do-not-call demotes an otherwise-strong lead and lowers contactability.
    dnc = score(owner_name="ESTATE OF MARY DOE", years_owned=20, is_out_of_state_absentee=True,
                estimated_equity_pct=70, do_not_call=True)
    check("R09", "Do-Not-Call → demoted out of HOT/WARM, contactability low",
          dnc["tier"] not in ("HOT", "WARM") and dnc["contactability_score"] < 50,
          f"tier={dnc['tier']} contactability={dnc['contactability_score']}")

    # R10 — Verified contact lifts operational_priority above an identical no-contact lead.
    no_contact = score(owner_name="ESTATE OF MARY DOE", years_owned=20,
                       is_out_of_state_absentee=True, estimated_equity_pct=70)
    with_contact = score(owner_name="ESTATE OF MARY DOE", years_owned=20,
                        is_out_of_state_absentee=True, estimated_equity_pct=70,
                        phone="770-555-1212", email="owner@example.com")
    check("R10", "Verified contact raises operational_priority over identical no-contact lead",
          with_contact["operational_priority"] > no_contact["operational_priority"],
          f"no_contact={no_contact['operational_priority']} with={with_contact['operational_priority']}")

    # R11 — Debug export fields are present.
    t = score(years_owned=12, estimated_equity_pct=45)
    check("R11", "Debug/calibration fields exported",
          all(k in t for k in ("motivation_raw", "fit_raw", "confidence_raw",
                               "urgent_signal_count", "lifecycle_signal_count",
                               "financial_signal_count", "hot_evidence_ok")),
          f"keys={[k for k in ('motivation_raw','fit_raw','hot_evidence_ok') if k in t]}")

    if verbose:
        print("=" * 78)
        print(f"RESULT: {passed} passed, {failed} failed")
        print("=" * 78)
    return failed


def test_audit_suite():
    """pytest entry point — fails if any check fails."""
    assert run_suite(verbose=False) == 0


if __name__ == "__main__":
    raise SystemExit(1 if run_suite() else 0)
