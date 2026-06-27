"""
Sprint Lead Generation — Property Enrichment
---------------------------------------------
Fetches external signals and writes them onto property dicts before scoring.

APIs used:
  FRED      — 30-yr mortgage rate, Atlanta unemployment, county HPI
  Census    — ACS tract-level income, home values, age 65+, vacancy, owner-occupancy
  Overpass  — OSM amenity access (groceries, parks, major-road proximity)
  GOSA      — School performance score by ZIP (static lookup, updated annually)

All API calls are cached (FRED once per scan; Census by tract; OSM by 1km grid).
Enrichment is fully optional — missing keys or failures leave the field unpopulated
and the scoring engine degrades gracefully.
"""

import hashlib
import math
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Optional

import requests

from gsccca_client import GsccaClient

# ---------------------------------------------------------------------------
# Static GOSA school performance index by ZIP
# Source: Georgia Governor's Office of Student Achievement — CCRPI scores
# Updated: school year 2022-23  (update annually from gosa.georgia.gov)
# ---------------------------------------------------------------------------
GOSA_BY_ZIP = {
    # North Fulton
    "30004": 94.2,   # Milton — Milton HS zone
    "30005": 96.1,   # Alpharetta — Cambridge / Northview HS zone
    "30009": 90.8,   # Alpharetta — Alpharetta HS zone
    "30022": 91.7,   # Alpharetta/Johns Creek — Johns Creek / Northview HS zone
    "30097": 89.4,   # Johns Creek
    "30075": 84.3,   # Roswell — Roswell HS zone
    "30076": 81.9,   # Roswell — Centennial HS zone
    "30327": 82.1,   # Sandy Springs — Riverwood HS zone
    "30328": 79.8,   # Sandy Springs — North Springs HS zone
    "30350": 85.6,   # Sandy Springs / Dunwoody border
    # Forsyth County
    "30040": 90.1,   # Cumming — South Forsyth HS zone
    "30041": 92.8,   # Cumming — Denmark HS zone (highest in Forsyth)
    "30028": 85.4,   # Cumming — West Forsyth HS zone
    "30042": 87.9,   # Cumming — Forsyth Central HS zone
    "30024": 88.6,   # Cumming / Johns Creek border — South Forsyth area
}

# Approximate city center coordinates for OSM fallback when geocoding fails
CITY_COORDS = {
    "alpharetta":    (34.0754, -84.2941),
    "milton":        (34.1357, -84.3060),
    "johns creek":   (34.0289, -84.1986),
    "roswell":       (34.0232, -84.3616),
    "sandy springs": (33.9304, -84.3733),
    "cumming":       (34.2073, -84.1401),
    "coal mountain": (34.2500, -84.1500),
    "sawnee":        (34.2200, -84.1600),
    "vickery creek": (34.1700, -84.1800),
}

# County-specific FHFA all-transactions HPI series (annual).
HPI_SERIES = {
    "fulton":  "ATNHPIUS13121A",
    "forsyth": "ATNHPIUS13117A",
}

FRED_BASE     = "https://api.stlouisfed.org/fred/series/observations"
CENSUS_GEO    = "https://geocoding.geo.census.gov/geocoder/geographies/address"
CENSUS_ACS    = "https://api.census.gov/data/2023/acs/acs5"
OVERPASS_URL  = "https://overpass-api.de/api/interpreter"
TIMEOUT_SHORT = 8
TIMEOUT_LONG  = 16


class Enricher:

    def __init__(self, fred_key: str = "", census_key: str = "",
                 gsccca_username: str = "", gsccca_password: str = ""):
        self.fred_key    = fred_key.strip()
        self.census_key  = census_key.strip()
        self._fred_ctx   = {"hpi_growth_by_county": {}}  # populated once per scan
        self._geo_cache  = {}        # address hash → (lat, lng, tract_geoid)
        self._tract_cache = {}       # tract_geoid → census dict
        self._osm_cache  = {}        # (rounded_lat, rounded_lng) → osm dict
        self.gsccca: Optional[GsccaClient] = (
            GsccaClient(gsccca_username, gsccca_password)
            if gsccca_username and gsccca_password else None
        )

    # ── Public ───────────────────────────────────────────────────────────────

    def prefetch_fred(self):
        """Fetch FRED macro signals once. Call before enrich_batch()."""
        if not self.fred_key:
            return

        def _fetch(series_id, limit=2):
            try:
                r = requests.get(FRED_BASE, params={
                    "series_id":   series_id,
                    "api_key":     self.fred_key,
                    "file_type":   "json",
                    "sort_order":  "desc",
                    "limit":       limit,
                }, timeout=TIMEOUT_SHORT)
                return r.json().get("observations", [])
            except Exception:
                return []

        # 30-yr fixed mortgage rate (weekly)
        for obs in _fetch("MORTGAGE30US"):
            if obs["value"] != ".":
                self._fred_ctx["mortgage_rate"] = float(obs["value"])
                break

        # Atlanta-Sandy Springs-Roswell metro unemployment (monthly)
        # Series: ATLA013URN — confirmed correct per FRED (ATLATSA647N is a different series)
        for obs in _fetch("ATLA013URN"):
            if obs["value"] != ".":
                self._fred_ctx["unemployment"] = float(obs["value"])
                break

        # County HPI — FHFA all-transactions index, ANNUAL series.
        # P0 (audit §6.12/§7.2): previous code used Fulton series for both counties
        # and compared vals[0] to vals[12] — a 12-YEAR gap, not one year. Correct YoY
        # compares the latest annual observation to the immediately prior one.
        # Series: Forsyth=ATNHPIUS13117A, Fulton=ATNHPIUS13121A.
        for county_key, series_id in HPI_SERIES.items():
            recent = _fetch(series_id, limit=3)
            vals = [o for o in recent if o["value"] != "."]
            if len(vals) >= 2:
                curr = float(vals[0]["value"])
                prev = float(vals[1]["value"])
                if prev:
                    self._fred_ctx["hpi_growth_by_county"][county_key] = (curr - prev) / prev

    def enrich_batch(self, props: list) -> list:
        """
        Enrich all properties in-place. Returns same list.
        School GOSA lookup is instant. FRED fields are already prefetched.
        Census + OSM run in parallel threads.
        GSCCCA deed history runs sequentially with throttle (0.5 s/req).
        """
        for p in props:
            self._apply_school(p)
            self._apply_fred(p)

        # Geo enrichment: geocode → Census → OSM (IO-bound, parallelised)
        with ThreadPoolExecutor(max_workers=12) as ex:
            futs = {ex.submit(self._enrich_geo, p): p for p in props}
            for fut in as_completed(futs):
                try:
                    fut.result()
                except Exception:
                    pass

        # GSCCCA deed history — throttled sequential (login once, then per-property)
        if self.gsccca and self.gsccca.configured:
            self._enrich_gsccca_batch(props)

        return props

    def status(self) -> dict:
        """Return which enrichment sources are configured."""
        return {
            "fred":    bool(self.fred_key),
            "census":  bool(self.census_key),
            "osm":     True,        # always available (no key)
            "school":  True,        # static lookup, always available
            "gsccca":  bool(self.gsccca and self.gsccca.configured),
        }

    # ── GSCCCA deed history ───────────────────────────────────────────────────

    def _enrich_gsccca_batch(self, props: list):
        """
        Login once, then look up each property sequentially with 0.5 s throttle.
        Skips properties that already have years_owned > 0 (demo data or FMLS provided).
        Writes years_owned, transfer_type, gsccca_verified back onto the dict.
        """
        if not self.gsccca:
            return
        if not self.gsccca.login():
            return   # bad credentials or network error — degrade silently

        for prop in props:
            # Skip when the upstream already populated years_owned (e.g. demo data).
            # Use (... or 0) so a None (unknown tenure) does not raise on comparison.
            if (prop.get("years_owned") or 0) > 0:
                continue

            owner_name = (prop.get("owner_name") or "").strip()
            county     = (prop.get("county") or "").strip()
            if not owner_name or not county:
                continue

            result = self.gsccca.lookup_deed(owner_name, county)
            if result:
                prop.update(result)
                if result.get("years_owned") is not None:
                    prop["tenure_verified"] = True
                    prop["tenure_source"]   = "gsccca"

            time.sleep(0.5)   # ~2 req/sec to stay polite with GSCCCA servers

    # ── School ───────────────────────────────────────────────────────────────

    def _apply_school(self, prop: dict):
        if prop.get("school_performance_score") is not None:
            return  # already populated (e.g., demo data)
        zip_ = (prop.get("zip_code") or "")[:5]
        score = GOSA_BY_ZIP.get(zip_)
        if score is not None:
            prop["school_performance_score"] = score

    # ── FRED ─────────────────────────────────────────────────────────────────

    def _apply_fred(self, prop: dict):
        if self._fred_ctx.get("mortgage_rate") is not None:
            prop["fred_mortgage_rate"]    = self._fred_ctx["mortgage_rate"]
        if self._fred_ctx.get("unemployment") is not None:
            prop["fred_unemployment_rate"] = self._fred_ctx["unemployment"]
        # County-specific HPI growth (Forsyth vs Fulton appreciate differently).
        by_county = self._fred_ctx.get("hpi_growth_by_county", {})
        county    = (prop.get("county") or "").lower()
        county_key = "forsyth" if "forsyth" in county else "fulton" if "fulton" in county else None
        if county_key and by_county.get(county_key) is not None:
            prop["fred_hpi_growth"] = by_county[county_key]

    # ── Geo enrichment ────────────────────────────────────────────────────────

    def _enrich_geo(self, prop: dict):
        """Geocode address, then Census + OSM. Modifies prop in-place."""
        lat, lng, tract = self._geocode(prop)

        # Fallback to city-level coords for OSM if geocoding failed
        if lat is None:
            city = (prop.get("city") or "").lower().strip()
            coords = CITY_COORDS.get(city)
            if coords:
                lat, lng = coords

        if self.census_key and tract:
            self._apply_census(prop, tract)

        if lat is not None:
            self._apply_osm(prop, lat, lng)

    def _geocode(self, prop: dict):
        """
        Census Geocoder → (lat, lng, tract_geoid) or (None, None, None).
        Cached by MD5 of address+city+zip.
        """
        address = prop.get("address", "")
        city    = prop.get("city", "")
        state   = prop.get("state", "GA")
        zip_    = prop.get("zip_code", "")

        key = hashlib.md5(f"{address}|{city}|{zip_}".lower().encode()).hexdigest()
        if key in self._geo_cache:
            return self._geo_cache[key]

        result = (None, None, None)
        try:
            r = requests.get(CENSUS_GEO, params={
                "street":    address,
                "city":      city,
                "state":     state,
                "zip":       zip_,
                "benchmark": "Public_AR_Current",
                "vintage":   "Current_Current",
                "layers":    "Census Tracts",
                "format":    "json",
            }, timeout=TIMEOUT_LONG)
            matches = r.json().get("result", {}).get("addressMatches", [])
            if matches:
                m      = matches[0]
                coords = m["coordinates"]
                tracts = m.get("geographies", {}).get("Census Tracts", [])
                geoid  = tracts[0]["GEOID"] if tracts else None
                result = (float(coords["y"]), float(coords["x"]), geoid)
        except Exception:
            pass

        self._geo_cache[key] = result
        return result

    # ── Census ────────────────────────────────────────────────────────────────

    def _apply_census(self, prop: dict, tract_geoid: str):
        if not tract_geoid or not self.census_key:
            return

        if tract_geoid in self._tract_cache:
            prop.update(self._tract_cache[tract_geoid])
            return

        state_fips  = tract_geoid[:2]
        county_fips = tract_geoid[2:5]
        tract_fips  = tract_geoid[5:]

        variables = ",".join([
            "B19013_001E",   # median household income
            "B25077_001E",   # median home value (owner-occupied)
            "B25003_001E",   # occupied housing units
            "B25003_002E",   # owner-occupied units
            "B25002_001E",   # total housing units
            "B25002_003E",   # vacant housing units
            "B01001_001E",   # total population
            # Male 65+: B01001_020E → 025E
            "B01001_020E","B01001_021E","B01001_022E",
            "B01001_023E","B01001_024E","B01001_025E",
            # Female 65+: B01001_044E → 049E
            "B01001_044E","B01001_045E","B01001_046E",
            "B01001_047E","B01001_048E","B01001_049E",
        ])

        enriched = {}
        try:
            r = requests.get(CENSUS_ACS, params={
                "get": variables,
                "for": f"tract:{tract_fips}",
                "in":  f"state:{state_fips} county:{county_fips}",
                "key": self.census_key,
            }, timeout=TIMEOUT_LONG)
            data = r.json()
            if len(data) < 2:
                return
            row = dict(zip(data[0], data[1]))

            def v(k):
                val = row.get(k)
                if val and str(val) not in ("-666666666", "-999999999", "null"):
                    try:
                        return float(val)
                    except Exception:
                        pass
                return None

            median_income  = v("B19013_001E")
            median_home    = v("B25077_001E")
            total_occ      = v("B25003_001E")
            owner_occ      = v("B25003_002E")
            total_units    = v("B25002_001E")
            vacant_units   = v("B25002_003E")
            total_pop      = v("B01001_001E")

            male_65   = sum(x for k in [f"B01001_0{i:02d}E" for i in range(20, 26)] if (x := v(k)) is not None)
            female_65 = sum(x for k in [f"B01001_0{i:02d}E" for i in range(44, 50)] if (x := v(k)) is not None)
            age65 = male_65 + female_65

            if median_income:  enriched["census_median_income"]         = median_income
            if median_home:    enriched["census_median_home_value"]      = median_home
            if total_occ and owner_occ:
                enriched["census_owner_occupancy_rate"] = owner_occ / total_occ
            if total_units and vacant_units:
                enriched["census_vacancy_rate"] = vacant_units / total_units
            if total_pop and age65:
                enriched["census_age_65_plus_rate"] = age65 / total_pop

        except Exception:
            pass

        self._tract_cache[tract_geoid] = enriched
        prop.update(enriched)

    # ── OSM / Overpass ────────────────────────────────────────────────────────

    def _apply_osm(self, prop: dict, lat: float, lng: float):
        """Single Overpass query: groceries + parks + major roads in one call."""
        grid_key = (round(lat, 2), round(lng, 2))
        if grid_key in self._osm_cache:
            prop.update(self._osm_cache[grid_key])
            return

        radius = 1609  # 1 mile in metres
        query = f"""
[out:json][timeout:15];
(
  node["shop"~"supermarket|grocery"](around:{radius},{lat},{lng});
  node["amenity"~"supermarket|marketplace"](around:{radius},{lat},{lng});
  way["leisure"="park"](around:{radius},{lat},{lng});
  node["leisure"="park"](around:{radius},{lat},{lng});
  way["highway"~"motorway|trunk|primary"](around:150,{lat},{lng});
);
out center;
"""
        try:
            r = requests.post(OVERPASS_URL, data={"data": query}, timeout=TIMEOUT_LONG)
            elements = r.json().get("elements", [])
        except Exception:
            return

        def coords(e):
            if "lat" in e:
                return e["lat"], e["lon"]
            c = e.get("center", {})
            return c.get("lat"), c.get("lon")

        def dist_mi(a, b):
            dlat = (a[0] - b[0]) * 69.0
            dlng = (a[1] - b[1]) * 54.6
            return math.sqrt(dlat ** 2 + dlng ** 2)

        ref  = (lat, lng)
        tags = lambda e: e.get("tags", {})

        groceries = [coords(e) for e in elements
                     if tags(e).get("shop") in ("supermarket", "grocery")
                     or tags(e).get("amenity") in ("supermarket", "marketplace")]
        groceries = [c for c in groceries if c[0] is not None]

        parks = [coords(e) for e in elements
                 if tags(e).get("leisure") == "park"]
        parks = [c for c in parks if c[0] is not None]

        major_roads = [e for e in elements
                       if tags(e).get("highway") in ("motorway", "trunk", "primary")]

        nearest_grocery = min((dist_mi(ref, g) for g in groceries), default=None)
        nearest_park    = min((dist_mi(ref, p) for p in parks),     default=None)
        major_road      = len(major_roads) > 0

        # Composite amenity score 0–10
        score = min(len(groceries), 2) * 2 + min(len(parks), 3) * 1
        if nearest_grocery is not None and nearest_grocery <= 0.5:
            score += 2
        if nearest_park is not None and nearest_park <= 0.25:
            score += 1
        if not major_road:
            score += 1
        score = min(score, 10)

        enriched = {
            "osm_grocery_count":    len(groceries),
            "osm_park_count":       len(parks),
            "osm_amenity_score":    score,
            "osm_major_road_nearby": major_road,
        }
        if nearest_grocery is not None:
            enriched["osm_nearest_grocery"] = round(nearest_grocery, 2)
        if nearest_park is not None:
            enriched["osm_nearest_park"] = round(nearest_park, 2)

        self._osm_cache[grid_key] = enriched
        prop.update(enriched)
