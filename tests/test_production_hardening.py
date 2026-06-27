"""
Regression matrix for the production-hardening pass (P2-16).

Covers the execution-ticket mandatory cases: source modes, compliance separation,
contactability/channels, school provenance, GSCCCA confidence, schema (None≠False),
config security, and explainer source-of-truth. Pure pytest (no network).
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from lead_engine import LeadEngine
from schemas import normalize_lead_input
from sources import classify_absentee
from school_service import compute_school_fields
from gsccca_client import _name_match_confidence, _parse_results
from market_config import price_band_fit, micro_market_for

seller_engine = LeadEngine(listing_goal="seller_listing")
buyer_engine = LeadEngine(listing_goal="buyer_or_market")


def base_prop(**overrides):
    p = {
        "county": "Fulton", "city": "Alpharetta", "zip_code": "30005",
        "property_type": "Single Family", "assessed_value": 850_000,
        "year_built": 2015, "bedrooms": 4, "owner_name": "DOE, JOHN",
    }
    p.update(overrides)
    return p


# ── Scoring core ───────────────────────────────────────────────────────────────

def test_high_equity_only_not_hot():
    r = seller_engine.score_lead(base_prop(estimated_equity_pct=65, school_performance_score=95))
    assert r["tier"] != "HOT"


def test_long_tenure_only_not_hot():
    r = seller_engine.score_lead(base_prop(years_owned=15, school_performance_score=95))
    assert r["tier"] != "HOT"


def test_equity_plus_lifecycle_can_be_hot():
    r = seller_engine.score_lead(base_prop(years_owned=14, estimated_equity_pct=70,
                                           homestead_exemption=True, school_performance_score=95))
    assert r["hot_evidence_ok"] is True


def test_estate_plus_vacancy_can_be_hot():
    r = seller_engine.score_lead(base_prop(owner_name="ESTATE OF JANE DOE",
                                           years_owned=18, vacancy=True, estimated_equity_pct=60))
    assert r["hot_evidence_ok"] is True


def test_pre_1985_not_rewarded():
    old = seller_engine.score_lead(base_prop(year_built=1980))
    new = seller_engine.score_lead(base_prop(year_built=2015))
    assert new["fit_raw"] > old["fit_raw"]


def test_2005_2020_highest_build_year_fit():
    a = seller_engine.score_lead(base_prop(year_built=2015))["fit_raw"]
    b = seller_engine.score_lead(base_prop(year_built=2000))["fit_raw"]
    c = seller_engine.score_lead(base_prop(year_built=1990))["fit_raw"]
    assert a >= b >= c


def test_missing_tenure_routes_to_review():
    r = seller_engine.score_lead(base_prop(school_performance_score=93))  # no years_owned
    assert r["tier"] in ("REVIEW", "COOL")


# ── Compliance & source modes ──────────────────────────────────────────────────

def test_active_in_seller_mode_is_compliance_hold():
    r = seller_engine.score_lead(base_prop(listing_status="Active", years_owned=18,
                                           estimated_equity_pct=60))
    assert r["tier"] == "COMPLIANCE_HOLD"


def test_active_in_buyer_mode_not_hold():
    r = buyer_engine.score_lead(base_prop(listing_status="Active", years_owned=18,
                                          estimated_equity_pct=60))
    assert r["tier"] != "COMPLIANCE_HOLD"


def test_compliance_hold_blocks_all_channels():
    r = seller_engine.score_lead(base_prop(listing_status="Active", phone="7705551212",
                                           owner_mailing_address="1 Main"))
    assert r["seller_outreach_allowed"] is False
    assert r["allowed_channels"] == []


# ── Contactability / channels ──────────────────────────────────────────────────

def test_dnc_blocks_phone_allows_mail():
    r = seller_engine.score_lead(base_prop(phone="7705551212", do_not_call=True,
                                           owner_mailing_address="123 Main St"))
    assert "phone" not in r["allowed_channels"]
    assert "phone" in r["blocked_channels"]
    assert "mail" in r["allowed_channels"]


def test_verified_contact_raises_operational_priority():
    no_c = seller_engine.score_lead(base_prop(owner_name="ESTATE OF MARY DOE", years_owned=20,
                                              is_out_of_state_absentee=True, estimated_equity_pct=70))
    with_c = seller_engine.score_lead(base_prop(owner_name="ESTATE OF MARY DOE", years_owned=20,
                                                is_out_of_state_absentee=True, estimated_equity_pct=70,
                                                phone="7705551212", email="o@x.com"))
    assert with_c["operational_priority"] > no_c["operational_priority"]


# ── Micro-market (P1-10) ───────────────────────────────────────────────────────

def test_outer_forsyth_generic_lifecycle_held_to_warm():
    r = seller_engine.score_lead({
        "county": "Forsyth", "city": "Cumming", "zip_code": "30028",
        "property_type": "Single Family", "assessed_value": 600_000, "year_built": 2015,
        "bedrooms": 4, "owner_name": "DOE, JOHN",
        "years_owned": 18, "estimated_equity_pct": 70, "homestead_exemption": True,
    })
    assert r["tier"] != "HOT"


def test_outer_forsyth_estate_absentee_can_be_hot():
    r = seller_engine.score_lead({
        "county": "Forsyth", "city": "Cumming", "zip_code": "30028",
        "property_type": "Single Family", "assessed_value": 600_000, "year_built": 2015,
        "bedrooms": 4, "owner_name": "ESTATE OF JANE DOE",
        "is_out_of_state_absentee": True, "years_owned": 20, "estimated_equity_pct": 80,
    })
    assert r["tier"] == "HOT"


# ── Schema (None ≠ False) ──────────────────────────────────────────────────────

def test_unknown_booleans_stay_none():
    norm = normalize_lead_input({"county": "Fulton"})
    # absent keys are not coerced into the dict as False
    assert norm.get("tax_delinquent") is None
    assert norm.get("homestead_exemption") is None


def test_unknown_value_not_capped_sub_200k():
    r = seller_engine.score_lead(base_prop(assessed_value=0, years_owned=12, estimated_equity_pct=40))
    assert "Value under $200,000 minimum threshold" not in r["failures"]


# ── Absentee classification (P1-06) ────────────────────────────────────────────

def test_absentee_from_mailing_address():
    out = classify_absentee({"address": "1 Main St", "city": "Alpharetta", "state": "GA",
                             "zip_code": "30005", "owner_mailing_address": "9 Ocean Dr",
                             "owner_city": "Miami", "owner_state": "FL"})
    assert out["is_out_of_state_absentee"] is True


def test_absentee_unknown_when_no_mailing():
    out = classify_absentee({"address": "1 Main St", "city": "Alpharetta"})
    assert out["is_out_of_state_absentee"] is None


# ── School provenance (P1-07) ──────────────────────────────────────────────────

def test_zip_school_fallback_low_confidence():
    fields = compute_school_fields({"zip_code": "30041"})
    assert fields["school_score_source"] == "zip_fallback"
    assert fields["school_boundary_confidence"] < 0.75


# ── GSCCCA match confidence (P1-08) ────────────────────────────────────────────

def test_gsccca_exact_match_high_confidence():
    assert _name_match_confidence("SMITH, JOHN", "SMITH, JOHN") >= 0.9


def test_gsccca_ambiguous_returns_unverified():
    html = (
        "<tr><td>SMITH, JOHN</td><td>FULTON</td><td>WARRANTY DEED</td>"
        "<td>05/01/2015</td><td>1234</td></tr>"
        "<tr><td>SMITH, ROBERT</td><td>FULTON</td><td>WARRANTY DEED</td>"
        "<td>06/01/2016</td><td>5678</td></tr>"
    )
    res = _parse_results(html, search_name="SMITH, JOHN")
    assert res.get("gsccca_verified") is False
    assert res.get("gsccca_warning")


# ── Price band (P2-14) ─────────────────────────────────────────────────────────

def test_price_band_sweet_spot_high():
    assert price_band_fit(800_000, "alpharetta", "Fulton", "30005") >= 85


def test_micro_market_outer_forsyth():
    assert micro_market_for("30028", "Cumming")["tier"] == "outer"


# ── Config security (P0-03) ────────────────────────────────────────────────────

def test_config_endpoint_does_not_echo_secrets():
    os.environ["FMLS_API_KEY"] = "super-secret-token"
    import importlib
    import settings as settings_mod
    importlib.reload(settings_mod)
    import app as app_mod
    importlib.reload(app_mod)
    client = app_mod.app.test_client()
    r = client.get("/api/config")
    body = r.get_data(as_text=True)
    assert "super-secret-token" not in body
    assert r.get_json()["api_key_set"] is True
    os.environ.pop("FMLS_API_KEY", None)


# ── Explainer source-of-truth (P0-04) ──────────────────────────────────────────

def test_explainer_has_no_stale_linear_fit():
    text = (Path(__file__).resolve().parent.parent / "generate_explainer_pdf.py").read_text()
    assert "45 + (fit_raw × 2.1)" not in text
    assert "1995–2009 build year" not in text
