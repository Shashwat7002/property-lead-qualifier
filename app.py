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

import config as cfg
from enrichment import Enricher
from fmls_client import FMLSClient
from lead_engine import LeadEngine

app    = Flask(__name__)
engine = LeadEngine()


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
            props = client.get_properties(county)
            total_scanned += len(props)
            all_props.extend(props)

        # Enrich in parallel (Census geocoding + OSM + school lookup)
        enricher.enrich_batch(all_props)

        # Score
        raw_leads = []
        for p in all_props:
            scored = engine.score_lead(p)
            if scored["tier"] != "PASS":
                raw_leads.append(scored)

        # Rank by operational_priority (qualification score adjusted for contactability),
        # falling back to raw score. Contactability is neutral when contact data is
        # absent, so demo ordering is unchanged.
        raw_leads.sort(key=lambda x: (x.get("operational_priority") or x["score"]), reverse=True)
        leads = [_serialize_lead(l) for l in raw_leads]

        stats = {
            "total_scanned": total_scanned,
            "hot":        sum(1 for l in leads if l["tier"] == "HOT"),
            "warm":       sum(1 for l in leads if l["tier"] == "WARM"),
            "cool":       sum(1 for l in leads if l["tier"] == "COOL"),
            "review":     sum(1 for l in leads if l["tier"] == "REVIEW"),
            "compliance": sum(1 for l in leads if l["tier"] == "COMPLIANCE_HOLD"),
        }

        return jsonify({
            "success":      True,
            "demo_mode":    cfg.DEMO_MODE,
            "enrichment":   enricher.status(),
            "stats":        stats,
            "leads":        leads,
            "scanned_at":   datetime.now().strftime("%b %d, %Y at %I:%M %p"),
        })

    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# ── API: export CSV ───────────────────────────────────────────────────────────

@app.route("/api/export", methods=["POST"])
def export_csv():
    leads = (request.json or {}).get("leads", [])
    if not leads:
        return jsonify({"error": "No leads to export."}), 400

    fieldnames = [
        "Rank", "Score", "OperationalPriority", "Tier", "PriorityBand", "Strategy",
        "MotivationScore", "FitScore", "ConfidenceScore", "ContactabilityScore",
        "RelativeConversion", "OpportunitySize",
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
            "Tier":                 lead.get("tier", ""),
            "PriorityBand":         lead.get("priority_band", ""),
            "Strategy":             lead.get("strategy", ""),
            "MotivationScore":      lead.get("motivation_score", ""),
            "FitScore":             lead.get("fit_score", ""),
            "ConfidenceScore":      lead.get("confidence_score", ""),
            "ContactabilityScore":  lead.get("contactability_score", ""),
            "RelativeConversion":   lead.get("estimated_conversion_pct", ""),
            "OpportunitySize":      lead.get("expected_gci_range", ""),
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

    data      = request.json or {}
    cfg_path  = os.path.join(os.path.dirname(__file__), "config.py")

    # Blank secret fields mean "leave unchanged" (the GET no longer pre-fills them),
    # so fall back to the currently stored value instead of wiping it.
    def _keep(submitted, current):
        s = (submitted or "").strip()
        return s if s else (current or "")

    username         = data.get("username",          "").strip()
    demo_mode        = bool(data.get("demo_mode",    True))
    gsccca_username  = data.get("gsccca_username",  "").strip()

    api_key          = _keep(data.get("api_key"),         cfg.FMLS_API_KEY)
    password         = _keep(data.get("password"),        getattr(cfg, "FMLS_PASSWORD", ""))
    fred_api_key     = _keep(data.get("fred_api_key"),    getattr(cfg, "FRED_API_KEY", ""))
    census_api_key   = _keep(data.get("census_api_key"),  getattr(cfg, "CENSUS_API_KEY", ""))
    gsccca_password  = _keep(data.get("gsccca_password"), getattr(cfg, "GSCCCA_PASSWORD", ""))

    with open(cfg_path, "w") as f:
        f.write("# Sprint Lead Generation — Configuration\n")
        f.write("# (auto-generated — edit via API Settings panel)\n\n")
        f.write(f'FMLS_API_KEY  = "{api_key}"\n')
        f.write(f'FMLS_USERNAME = "{username}"\n')
        f.write(f'FMLS_PASSWORD = "{password}"\n')
        f.write(f'DEMO_MODE     = {demo_mode}\n\n')
        f.write(f'FRED_API_KEY   = "{fred_api_key}"\n')
        f.write(f'CENSUS_API_KEY = "{census_api_key}"\n\n')
        f.write(f'GSCCCA_USERNAME = "{gsccca_username}"\n')
        f.write(f'GSCCCA_PASSWORD = "{gsccca_password}"\n')

    import importlib
    importlib.reload(cfg)

    return jsonify({"success": True, "demo_mode": cfg.DEMO_MODE})


# ── API: enrichment status ────────────────────────────────────────────────────

@app.route("/api/enrichment_status")
def enrichment_status():
    return jsonify(_make_enricher().status())


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
        "strategy":                 lead.get("strategy", ""),
        # Signals
        "flags":                    lead.get("flags", []),
        "passes":                   lead.get("passes", []),
        "warnings":                 lead.get("warnings", []),
        "failures":                 lead.get("failures", []),
        "priority_band":            lead.get("priority_band", ""),
        "estimated_conversion_pct": lead.get("estimated_conversion_pct", ""),
        "expected_gci_range":       lead.get("expected_gci_range", ""),
        "data_quality_notes":       lead.get("data_quality_notes", []),
        "market_context":           lead.get("market_context", []),
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
