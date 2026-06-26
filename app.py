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
from fmls_client import FMLSClient
from lead_engine import LeadEngine

app = Flask(__name__)
engine = LeadEngine()


# ── Pages ─────────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return render_template('index.html')


# ── API: scan ─────────────────────────────────────────────────────────────────

@app.route('/api/scan', methods=['POST'])
def scan():
    data     = request.json or {}
    counties = data.get('counties', ['Forsyth', 'North Fulton'])
    if not counties:
        return jsonify({'success': False, 'error': 'Select at least one county.'}), 400

    client = FMLSClient(
        api_key=cfg.FMLS_API_KEY,
        username=cfg.FMLS_USERNAME,
        password=cfg.FMLS_PASSWORD,
    )

    try:
        raw_leads = []
        total_scanned = 0

        for county in counties:
            props = client.get_properties(county)
            total_scanned += len(props)
            for p in props:
                scored = engine.score_lead(p)
                if scored['tier'] != 'PASS':
                    raw_leads.append(scored)

        raw_leads.sort(key=lambda x: x['score'], reverse=True)

        leads = [_serialize_lead(l) for l in raw_leads]

        stats = {
            'total_scanned': total_scanned,
            'hot':  sum(1 for l in leads if l['tier'] == 'HOT'),
            'warm': sum(1 for l in leads if l['tier'] == 'WARM'),
            'cool': sum(1 for l in leads if l['tier'] == 'COOL'),
        }

        return jsonify({
            'success':    True,
            'demo_mode':  cfg.DEMO_MODE,
            'stats':      stats,
            'leads':      leads,
            'scanned_at': datetime.now().strftime('%b %d, %Y at %I:%M %p'),
        })

    except Exception as exc:
        return jsonify({'success': False, 'error': str(exc)}), 500


# ── API: export CSV ───────────────────────────────────────────────────────────

@app.route('/api/export', methods=['POST'])
def export_csv():
    leads = (request.json or {}).get('leads', [])
    if not leads:
        return jsonify({'error': 'No leads to export.'}), 400

    fieldnames = [
        'Rank', 'Score', 'Tier', 'Strategy',
        'MotivationScore', 'FitScore', 'ConfidenceScore',
        'Address', 'City', 'County', 'ZipCode', 'State',
        'PropertyType', 'YearBuilt', 'Bedrooms', 'AssessedValue',
        'OwnerName', 'OwnerMailingAddress', 'OwnerCity', 'OwnerState',
        'IsOutOfStateAbsentee', 'IsInStateAbsentee',
        'YearsOwned', 'TaxDelinquent', 'FreeAndClear',
        'EstimatedEquityPct', 'TotalPropertiesOwned',
        'Flags', 'Phone', 'Email', 'ScanDate',
    ]

    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames, extrasaction='ignore')
    writer.writeheader()

    scan_date = datetime.now().strftime('%Y-%m-%d')
    for rank, lead in enumerate(leads, 1):
        writer.writerow({
            'Rank':                  rank,
            'Score':                 lead.get('score', ''),
            'Tier':                  lead.get('tier', ''),
            'Strategy':              lead.get('strategy', ''),
            'MotivationScore':       lead.get('motivation_score', ''),
            'FitScore':              lead.get('fit_score', ''),
            'ConfidenceScore':       lead.get('confidence_score', ''),
            'Address':               lead.get('address', ''),
            'City':                  lead.get('city', ''),
            'County':                lead.get('county', ''),
            'ZipCode':               lead.get('zip_code', ''),
            'State':                 'GA',
            'PropertyType':          lead.get('property_type', ''),
            'YearBuilt':             lead.get('year_built', ''),
            'Bedrooms':              lead.get('bedrooms', ''),
            'AssessedValue':         lead.get('assessed_value', ''),
            'OwnerName':             lead.get('owner_name', ''),
            'OwnerMailingAddress':   lead.get('owner_mailing_address', ''),
            'OwnerCity':             lead.get('owner_city', ''),
            'OwnerState':            lead.get('owner_state', ''),
            'IsOutOfStateAbsentee':  'Yes' if lead.get('is_out_of_state_absentee') else 'No',
            'IsInStateAbsentee':     'Yes' if lead.get('is_in_state_absentee') else 'No',
            'YearsOwned':            lead.get('years_owned', ''),
            'TaxDelinquent':         'Yes' if lead.get('tax_delinquent') else 'No',
            'FreeAndClear':          'Yes' if lead.get('free_and_clear') else 'No',
            'EstimatedEquityPct':    lead.get('estimated_equity_pct', ''),
            'TotalPropertiesOwned':  lead.get('total_properties_owned', ''),
            'Flags':                 ' | '.join(lead.get('flags', [])),
            'Phone':                 lead.get('phone', ''),
            'Email':                 lead.get('email', ''),
            'ScanDate':              scan_date,
        })

    buf.seek(0)
    filename = f"sprint_leads_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return send_file(
        io.BytesIO(buf.getvalue().encode('utf-8-sig')),  # BOM for Excel
        mimetype='text/csv',
        as_attachment=True,
        download_name=filename,
    )


# ── API: config ───────────────────────────────────────────────────────────────

@app.route('/api/config', methods=['GET', 'POST'])
def api_config():
    if request.method == 'GET':
        return jsonify({
            'api_key':   cfg.FMLS_API_KEY,
            'username':  cfg.FMLS_USERNAME,
            'demo_mode': cfg.DEMO_MODE,
        })

    data = request.json or {}
    config_path = os.path.join(os.path.dirname(__file__), 'config.py')
    api_key   = data.get('api_key', '').strip()
    username  = data.get('username', '').strip()
    password  = data.get('password', '').strip()
    demo_mode = bool(data.get('demo_mode', True))

    with open(config_path, 'w') as f:
        f.write('# Sprint Lead Generation — Configuration\n')
        f.write(f'FMLS_API_KEY  = "{api_key}"\n')
        f.write(f'FMLS_USERNAME = "{username}"\n')
        f.write(f'FMLS_PASSWORD = "{password}"\n')
        f.write(f'DEMO_MODE = {demo_mode}\n')

    import importlib
    importlib.reload(cfg)

    return jsonify({'success': True, 'demo_mode': cfg.DEMO_MODE})


# ── Helper ────────────────────────────────────────────────────────────────────

def _serialize_lead(lead: dict) -> dict:
    return {
        'listing_id':              lead.get('listing_id', ''),
        'address':                 lead.get('address', ''),
        'city':                    lead.get('city', ''),
        'county':                  lead.get('county', ''),
        'zip_code':                lead.get('zip_code', ''),
        'property_type':           lead.get('property_type', ''),
        'year_built':              lead.get('year_built'),
        'bedrooms':                lead.get('bedrooms', 0),
        'assessed_value':          lead.get('assessed_value', 0),
        'owner_name':              lead.get('owner_name', ''),
        'owner_mailing_address':   lead.get('owner_mailing_address', ''),
        'owner_city':              lead.get('owner_city', ''),
        'owner_state':             lead.get('owner_state', 'GA'),
        'is_out_of_state_absentee': lead.get('is_out_of_state_absentee', False),
        'is_in_state_absentee':    lead.get('is_in_state_absentee', False),
        'years_owned':             lead.get('years_owned', 0),
        'tax_delinquent':          lead.get('tax_delinquent', False),
        'free_and_clear':          lead.get('free_and_clear', False),
        'estimated_equity_pct':    lead.get('estimated_equity_pct', 0),
        'total_properties_owned':  lead.get('total_properties_owned', 1),
        'homestead_exemption':     lead.get('homestead_exemption', False),
        'senior_exemption':        lead.get('senior_exemption', False),
        'phone':                   lead.get('phone', ''),
        'email':                   lead.get('email', ''),
        'score':                   lead.get('score', 0),
        'tier':                    lead.get('tier', 'COOL'),
        'motivation_score':        lead.get('motivation_score', 0),
        'fit_score':               lead.get('fit_score', 0),
        'confidence_score':        lead.get('confidence_score', 0),
        'strategy':                lead.get('strategy', ''),
        'flags':                   lead.get('flags', []),
        'passes':                  lead.get('passes', []),
        'warnings':                lead.get('warnings', []),
        'failures':                lead.get('failures', []),
    }


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    def _open():
        import time
        time.sleep(1.2)
        webbrowser.open('http://localhost:5001')

    threading.Thread(target=_open, daemon=True).start()
    port = int(os.environ.get('PORT', 5001))
    app.run(host='127.0.0.1', port=port, debug=False)
