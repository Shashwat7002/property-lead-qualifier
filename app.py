"""
Sprint Lead Generation — Flask Server
"""
import csv
import io
import os
import threading
import webbrowser
from datetime import datetime

from flask import Flask, jsonify, render_template, request, send_file

from settings import settings as cfg
from enrichment import Enricher
from fmls_client import FMLSClient
from lead_engine import LeadEngine
from source_modes import SourceMode, ENGINE_GOAL
import db

app = Flask(__name__)
from ml_lab.routes import ml_blueprint
app.register_blueprint(ml_blueprint)
# NOTE: the scoring engine is instantiated PER REQUEST in /api/scan with the correct
# listing_goal for the chosen SourceMode — there is no shared global engine.


def _make_enricher() -> Enricher:
    return Enricher(
        fred_key         = getattr(cfg, "FRED_API_KEY",      "") or "",
        census_key       = getattr(cfg, "CENSUS_API_KEY",    "") or "",
        gsccca_username  = getattr(cfg, "GSCCCA_USERNAME",   "") or "",
        gsccca_password  = getattr(cfg, "GSCCCA_PASSWORD",   "") or "",
    )


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html")


# ── API: scan ─────────────────────────────────────────────────────────────────

@app.route("/api/scan", methods=["POST"])
def scan():
    data     = request.json or {}
    counties = data.get("counties", ["Forsyth", "North Fulton"])
    if not counties:
        return jsonify({"success": False, "error": "Select at least one county."}), 400

    # P0-01: scan mode drives both the data source population and the engine goal.
    mode = SourceMode.parse(data.get("mode", "seller_prospecting"))
    engine = LeadEngine(listing_goal=ENGINE_GOAL[mode])

    client   = FMLSClient(
        api_key  = cfg.FMLS_API_KEY,
        username = cfg.FMLS_USERNAME,
        password = cfg.FMLS_PASSWORD,
    )
    enricher = _make_enricher()

    try:
        # Prefetch FRED once (single network call, applies to all properties)
        enricher.prefetch_fred()

        all_props     = []
        total_scanned = 0

        for county in counties:
            props = client.get_properties(county, mode=mode.value)
            total_scanned += len(props)
            all_props.extend(props)

        # P0-01: if seller-prospecting found nothing off-market (e.g. only Active/Coming
        # Soon FMLS is configured), warn rather than silently presenting holds as leads.
        warning = None
        if mode == SourceMode.SELLER_PROSPECTING and not cfg.DEMO_MODE and total_scanned == 0:
            warning = ("No off-market seller-prospect source is configured. Active/Coming "
                       "Soon MLS records are available only in Market Intelligence mode.")

        # Enrich in parallel (Census geocoding + OSM + school lookup)
        enricher.enrich_batch(all_props)

        # P0-02: score into separate buckets so COMPLIANCE_HOLD records never sit in the
        # main seller-lead queue or default export.
        lead_rows, review_rows, compliance_rows, market_intel_rows = [], [], [], []
        excluded_count = 0
        for p in all_props:
            scored = engine.score_lead(p)
            tier = scored.get("tier")
            if tier in ("HOT", "WARM", "COOL"):
                lead_rows.append(scored)
            elif tier == "REVIEW":
                review_rows.append(scored)
            elif tier == "COMPLIANCE_HOLD":
                compliance_rows.append(scored)
            elif tier == "PASS":
                excluded_count += 1
            else:
                scored.setdefault("data_quality_notes", []).append(f"Unknown tier {tier}; routed to review")
                review_rows.append(scored)

        # Rank each bucket by operational_priority (qualification score adjusted for
        # contactability), falling back to raw score.
        for bucket in (lead_rows, review_rows, compliance_rows, market_intel_rows):
            bucket.sort(key=lambda x: (x.get("operational_priority") or x.get("score") or 0), reverse=True)

        stats = {
            "total_scanned": total_scanned,
            "hot":        sum(1 for l in lead_rows if l["tier"] == "HOT"),
            "warm":       sum(1 for l in lead_rows if l["tier"] == "WARM"),
            "cool":       sum(1 for l in lead_rows if l["tier"] == "COOL"),
            "review":     len(review_rows),
            "compliance": len(compliance_rows),
            "pass":       excluded_count,
        }

        # P2-11: persist scored leads for future outcome calibration (best-effort).
        try:
            db.record_scores(lead_rows + review_rows, source_mode=mode.value)
        except Exception:
            pass

        return jsonify({
            "success":         True,
            "mode":            mode.value,
            "demo_mode":       cfg.DEMO_MODE,
            "warning":         warning,
            "enrichment":      enricher.status(),
            "stats":           stats,
            "leads":           [_serialize_lead(l) for l in lead_rows],
            "review_leads":    [_serialize_lead(l) for l in review_rows],
            "compliance_holds":[_serialize_lead(l) for l in compliance_rows],
            "market_intel":    [_serialize_lead(l) for l in market_intel_rows],
            "scanned_at":      datetime.now().strftime("%b %d, %Y at %I:%M %p"),
        })

    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ── API: export CSV ───────────────────────────────────────────────────────────

@app.route("/api/export", methods=["POST"])
def export_csv():
    body = request.json or {}
    leads = body.get("leads", [])
    # P0-02: default export must exclude compliance holds. The compliance-hold export
    # is a separate, explicitly-requested bucket (bucket="compliance_holds").
    bucket = body.get("bucket", "leads")
    if bucket != "compliance_holds":
        leads = [l for l in leads if l.get("tier") != "COMPLIANCE_HOLD"]
    if not leads:
        return jsonify({"error": "No leads to export."}), 400

    fieldnames = [
        "Rank", "Score", "OperationalPriority", "BusinessPriorityProxy", "Tier",
        "PriorityBand", "Strategy",
        "MotivationScore", "FitScore", "ConfidenceScore", "ContactabilityScore",
        "RelativeConversion", "OpportunitySize", "ExpectedGCI",
        "SellerOutreachAllowed", "OutreachPolicy", "AllowedChannels", "BlockedChannels",
        "ContactRiskNotes",
        "MicroMarketTier", "MicroMarketLiquidityScore", "PriceBandFitScore",
        "SchoolSource", "SchoolBoundaryConfidence",
        "GSCCCAMatchConfidence", "SourceMode", "SourceSystem",
        "Address", "City", "County", "ZipCode", "State",
        "PropertyType", "YearBuilt", "Bedrooms", "AssessedValue",
        "OwnerName", "OwnerMailingAddress", "OwnerCity", "OwnerState",
        "IsOutOfStateAbsentee", "IsInStateAbsentee",
        "YearsOwned", "TaxDelinquent", "FreeAndClear",
        "EstimatedEquityPct", "TotalPropertiesOwned",
        "SchoolScore", "FredMortgageRate", "FredUnemployment",
        "CensusMedianIncome", "CensusMedianHomeValue",
        "OsmAmenityScore",
        "Flags", "Phone", "Email", "ScanDate",
    ]

    buf    = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()

    scan_date = datetime.now().strftime("%Y-%m-%d")
    for rank, lead in enumerate(leads, 1):
        writer.writerow({
            "Rank":                 rank,
            "Score":                lead.get("score", ""),
            "OperationalPriority":  lead.get("operational_priority", ""),
            "BusinessPriorityProxy": lead.get("business_priority_score", ""),
            "Tier":                 lead.get("tier", ""),
            "PriorityBand":         lead.get("priority_band", ""),
            "Strategy":             lead.get("strategy", ""),
            "MotivationScore":      lead.get("motivation_score", ""),
            "FitScore":             lead.get("fit_score", ""),
            "ConfidenceScore":      lead.get("confidence_score", ""),
            "ContactabilityScore":  lead.get("contactability_score", ""),
            "RelativeConversion":   lead.get("estimated_conversion_pct", ""),
            "OpportunitySize":      lead.get("expected_gci_range", ""),
            "ExpectedGCI":          lead.get("expected_gci", ""),
            "SellerOutreachAllowed": "Yes" if lead.get("seller_outreach_allowed") else "No",
            "OutreachPolicy":       lead.get("outreach_policy", ""),
            "AllowedChannels":      " | ".join(lead.get("allowed_channels", [])),
            "BlockedChannels":      " | ".join(lead.get("blocked_channels", [])),
            "ContactRiskNotes":     " | ".join(lead.get("contact_risk_notes", [])),
            "MicroMarketTier":      lead.get("micro_market_tier", ""),
            "MicroMarketLiquidityScore": lead.get("micro_market_liquidity_score", ""),
            "PriceBandFitScore":    lead.get("price_band_fit_score", ""),
            "SchoolSource":         lead.get("school_score_source", ""),
            "SchoolBoundaryConfidence": lead.get("school_boundary_confidence", ""),
            "GSCCCAMatchConfidence": lead.get("gsccca_match_confidence", ""),
            "SourceMode":           lead.get("source_mode", ""),
            "SourceSystem":         lead.get("source_system", ""),
            "Address":              lead.get("address", ""),
            "City":                 lead.get("city", ""),
            "County":               lead.get("county", ""),
            "ZipCode":              lead.get("zip_code", ""),
            "State":                "GA",
            "PropertyType":         lead.get("property_type", ""),
            "YearBuilt":            lead.get("year_built", ""),
            "Bedrooms":             lead.get("bedrooms", ""),
            "AssessedValue":        lead.get("assessed_value", ""),
            "OwnerName":            lead.get("owner_name", ""),
            "OwnerMailingAddress":  lead.get("owner_mailing_address", ""),
            "OwnerCity":            lead.get("owner_city", ""),
            "OwnerState":           lead.get("owner_state", ""),
            "IsOutOfStateAbsentee": "Yes" if lead.get("is_out_of_state_absentee") else "No",
            "IsInStateAbsentee":    "Yes" if lead.get("is_in_state_absentee") else "No",
            "YearsOwned":           lead.get("years_owned", ""),
            "TaxDelinquent":        "Yes" if lead.get("tax_delinquent") else "No",
            "FreeAndClear":         "Yes" if lead.get("free_and_clear") else "No",
            "EstimatedEquityPct":   lead.get("estimated_equity_pct", ""),
            "TotalPropertiesOwned": lead.get("total_properties_owned", ""),
            "SchoolScore":          lead.get("school_performance_score", ""),
            "FredMortgageRate":     lead.get("fred_mortgage_rate", ""),
            "FredUnemployment":     lead.get("fred_unemployment_rate", ""),
            "CensusMedianIncome":   lead.get("census_median_income", ""),
            "CensusMedianHomeValue":lead.get("census_median_home_value", ""),
            "OsmAmenityScore":      lead.get("osm_amenity_score", ""),
            "Flags":                " | ".join(lead.get("flags", [])),
            "Phone":                lead.get("phone", ""),
            "Email":                lead.get("email", ""),
            "ScanDate":             scan_date,
        })

    buf.seek(0)
    filename = f"sprint_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(
        io.BytesIO(buf.getvalue().encode("utf-8-sig")),
        mimetype="text/csv",
        as_attachment=True,
        download_name=filename,
    )


# ── API: config ───────────────────────────────────────────────────────────────

@app.route("/api/config", methods=["GET", "POST"])
def api_config():
    if request.method == "GET":
        # P0 (audit §7.3): never echo secrets back to the frontend. Return only
        # whether each secret is set, plus non-secret identifiers (username, demo).
        def _is_set(v) -> bool:
            return bool((v or "").strip())

        return jsonify({
            "username":             cfg.FMLS_USERNAME,
            "demo_mode":            cfg.DEMO_MODE,
            "gsccca_username":      getattr(cfg, "GSCCCA_USERNAME", ""),
            # Booleans only — the actual values stay server-side.
            "api_key_set":          _is_set(cfg.FMLS_API_KEY),
            "password_set":         _is_set(getattr(cfg, "FMLS_PASSWORD", "")),
            "fred_api_key_set":     _is_set(getattr(cfg, "FRED_API_KEY", "")),
            "census_api_key_set":   _is_set(getattr(cfg, "CENSUS_API_KEY", "")),
            "gsccca_password_set":  _is_set(getattr(cfg, "GSCCCA_PASSWORD", "")),
        })

    # P0-03: secrets are persisted to the gitignored local_settings.json (JSON, never
    # executable Python). Blank secret fields mean "leave unchanged" — they are simply
    # omitted from the update so the stored value is preserved.
    data = request.json or {}

    def _submitted(key):
        v = (data.get(key) or "").strip()
        return v or None    # None → save_local skips it (keeps existing value)

    updates = {
        "FMLS_USERNAME":   data.get("username", "").strip(),
        "DEMO_MODE":       bool(data.get("demo_mode", True)),
        "GSCCCA_USERNAME": data.get("gsccca_username", "").strip(),
        "FMLS_API_KEY":    _submitted("api_key"),
        "FMLS_PASSWORD":   _submitted("password"),
        "FRED_API_KEY":    _submitted("fred_api_key"),
        "CENSUS_API_KEY":  _submitted("census_api_key"),
        "GSCCCA_PASSWORD": _submitted("gsccca_password"),
    }
    cfg.save_local(updates)

    return jsonify({"success": True, "demo_mode": cfg.DEMO_MODE})


# ── API: enrichment status ────────────────────────────────────────────────────

@app.route("/api/enrichment_status")
def enrichment_status():
    return jsonify(_make_enricher().status())


# ── Outcome tracking / calibration (P2-11) ─────────────────────────────────────

@app.route("/api/outreach_event", methods=["POST"])
def outreach_event():
    d = request.json or {}
    key = (d.get("lead_key") or "").strip()
    event_type = (d.get("event_type") or "").strip()
    if not key or not event_type:
        return jsonify({"success": False, "error": "lead_key and event_type required"}), 400
    rid = db.record_event(key, event_type, d.get("channel", ""),
                          d.get("outcome", ""), d.get("notes", ""))
    return jsonify({"success": True, "event_id": rid})


@app.route("/api/lead_history/<lead_key>")
def lead_history(lead_key):
    return jsonify(db.lead_history(lead_key))


@app.route("/api/calibration_summary")
def calibration_summary():
    return jsonify({"summary": db.calibration_summary()})


# ── Helper ────────────────────────────────────────────────────────────────────

def _serialize_lead(lead: dict) -> dict:
    return {
        "listing_id":               lead.get("listing_id", ""),
        "address":                  lead.get("address", ""),
        "city":                     lead.get("city", ""),
        "county":                   lead.get("county", ""),
        "zip_code":                 lead.get("zip_code", ""),
        "property_type":            lead.get("property_type", ""),
        "year_built":               lead.get("year_built"),
        "bedrooms":                 lead.get("bedrooms", 0),
        "assessed_value":           lead.get("assessed_value", 0),
        "owner_name":               lead.get("owner_name", ""),
        "owner_mailing_address":    lead.get("owner_mailing_address", ""),
        "owner_city":               lead.get("owner_city", ""),
        "owner_state":              lead.get("owner_state", "GA"),
        "is_out_of_state_absentee": lead.get("is_out_of_state_absentee", False),
        "is_in_state_absentee":     lead.get("is_in_state_absentee", False),
        "years_owned":              lead.get("years_owned", 0),
        "tax_delinquent":           lead.get("tax_delinquent", False),
        "free_and_clear":           lead.get("free_and_clear", False),
        "estimated_equity_pct":     lead.get("estimated_equity_pct", 0),
        "total_properties_owned":   lead.get("total_properties_owned", 1),
        "homestead_exemption":      lead.get("homestead_exemption", False),
        "senior_exemption":         lead.get("senior_exemption", False),
        "phone":                    lead.get("phone", ""),
        "email":                    lead.get("email", ""),
        # Scores
        "score":                    lead.get("score", 0),
        "tier":                     lead.get("tier", "COOL"),
        "motivation_score":         lead.get("motivation_score", 0),
        "fit_score":                lead.get("fit_score", 0),
        "confidence_score":         lead.get("confidence_score", 0),
        "contactability_score":     lead.get("contactability_score", 50),
        "operational_priority":     lead.get("operational_priority", lead.get("score", 0)),
        "business_priority_score":  lead.get("business_priority_score"),
        "strategy":                 lead.get("strategy", ""),
        # Signals (public-safe variants preferred by UI/CSV)
        "flags":                    lead.get("public_flags", lead.get("flags", [])),
        "passes":                   lead.get("public_passes", lead.get("passes", [])),
        "warnings":                 lead.get("public_warnings", lead.get("warnings", [])),
        "failures":                 lead.get("failures", []),
        "priority_band":            lead.get("priority_band", ""),
        "estimated_conversion_pct": lead.get("estimated_conversion_pct", ""),
        "expected_gci_range":       lead.get("expected_gci_range", ""),
        "expected_gci":             lead.get("expected_gci"),
        "data_quality_notes":       lead.get("data_quality_notes", []),
        "market_context":           lead.get("market_context", []),
        # Outreach permissions (P0-05)
        "seller_outreach_allowed":  lead.get("seller_outreach_allowed"),
        "outreach_policy":          lead.get("outreach_policy", ""),
        "allowed_channels":         lead.get("allowed_channels", []),
        "blocked_channels":         lead.get("blocked_channels", []),
        "contact_risk_notes":       lead.get("contact_risk_notes", []),
        # Micro-market (P1-10) + source labels
        "micro_market_tier":        lead.get("micro_market_tier", ""),
        "micro_market_liquidity_score": lead.get("micro_market_liquidity_score"),
        "micro_market_label":       lead.get("micro_market_label", ""),
        "price_band_fit_score":     lead.get("price_band_fit_score"),
        "source_mode":              lead.get("source_mode", ""),
        "source_system":            lead.get("source_system", ""),
        # School / GSCCCA provenance (P1-07 / P1-08)
        "school_score_source":      lead.get("school_score_source", ""),
        "school_boundary_confidence": lead.get("school_boundary_confidence"),
        "gsccca_match_confidence":  lead.get("gsccca_match_confidence"),
        # Debug / calibration (raw components)
        "motivation_raw":           lead.get("motivation_raw"),
        "fit_raw":                  lead.get("fit_raw"),
        "confidence_raw":           lead.get("confidence_raw"),
        "hot_evidence_ok":          lead.get("hot_evidence_ok"),
        "urgent_signal_count":      lead.get("urgent_signal_count"),
        "lifecycle_signal_count":   lead.get("lifecycle_signal_count"),
        "financial_signal_count":   lead.get("financial_signal_count"),
        # Enrichment
        "school_performance_score": lead.get("school_performance_score"),
        "fred_mortgage_rate":       lead.get("fred_mortgage_rate"),
        "fred_unemployment_rate":   lead.get("fred_unemployment_rate"),
        "fred_hpi_growth":          lead.get("fred_hpi_growth"),
        "census_median_income":     lead.get("census_median_income"),
        "census_median_home_value": lead.get("census_median_home_value"),
        "census_owner_occupancy_rate": lead.get("census_owner_occupancy_rate"),
        "census_vacancy_rate":      lead.get("census_vacancy_rate"),
        "census_age_65_plus_rate":  lead.get("census_age_65_plus_rate"),
        "osm_amenity_score":        lead.get("osm_amenity_score"),
        "osm_grocery_count":        lead.get("osm_grocery_count"),
        "osm_park_count":           lead.get("osm_park_count"),
        "osm_nearest_grocery":      lead.get("osm_nearest_grocery"),
        "osm_nearest_park":         lead.get("osm_nearest_park"),
        "osm_major_road_nearby":    lead.get("osm_major_road_nearby"),
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    def _open():
        import time
        time.sleep(1.2)
        webbrowser.open("http://localhost:5001")

    threading.Thread(target=_open, daemon=True).start()
    port = int(os.environ.get("PORT", 5001))
    app.run(host="127.0.0.1", port=port, debug=False)
