# Sprint Lead Generation — Configuration
# ----------------------------------------
# Fill in credentials below.  Leave DEMO_MODE = True to explore with sample data first.
#
# API key registration:
#   FMLS       — Contact First MLS directly for RESO API credentials
#   FRED       — https://fred.stlouisfed.org/docs/api/api_key.html  (free, instant)
#   Census     — https://api.census.gov/data/key_signup.html         (free, instant)
#   OSM        — No key required (Overpass API is public)
#   School     — No key required (static GOSA lookup bundled in enrichment.py)

# ── First MLS (FMLS) ──────────────────────────────────────────────────────────
FMLS_API_KEY  = ""
FMLS_USERNAME = ""
FMLS_PASSWORD = ""
DEMO_MODE     = True   # Set False once FMLS credentials are entered

# ── Enrichment APIs ───────────────────────────────────────────────────────────
FRED_API_KEY   = ""    # FRED macro signals: mortgage rate, unemployment, HPI
CENSUS_API_KEY = ""    # Census ACS: tract income, home values, age 65+, vacancy
# OSM / Overpass and school zone lookup require no keys
