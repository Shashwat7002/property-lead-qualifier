"""
First MLS (FMLS) API Client
----------------------------
Uses the RESO Web API (OData) standard.

Demo mode generates realistic synthetic data for Forsyth and North Fulton
counties so the app works out-of-the-box without API credentials.
"""

import random
import requests


class FMLSClient:

    BASE_URL  = "https://api.fmls.com/reso/odata"
    TOKEN_URL = "https://api.fmls.com/oauth/token"

    # ── Geography ────────────────────────────────────────────────────────────
    _FORSYTH_CITIES  = ['Cumming', 'Coal Mountain', 'Sawnee', 'Vickery Creek']
    _FULTON_CITIES   = ['Alpharetta', 'Roswell', 'Milton', 'Johns Creek', 'Sandy Springs']
    _FORSYTH_ZIPS    = ['30028', '30040', '30041', '30042']
    _FULTON_ZIPS     = ['30004', '30005', '30022', '30075', '30076']

    _STREETS = [
        'Windward Pkwy', 'Old Milton Pkwy', 'Hwy 9 N', 'Holcomb Bridge Rd',
        'Abbotts Bridge Rd', 'McGinnis Ferry Rd', 'Webb Bridge Rd',
        'Devore Rd', 'Kimball Bridge Rd', 'Jones Bridge Rd', 'Mansell Rd',
        'Haynes Bridge Rd', 'Oxbo Rd', 'Providence Rd', 'Bethelview Rd',
        'Kelly Mill Rd', 'Sharon Rd', 'Pittman Rd', 'Casteel Rd',
    ]

    _FIRST  = ['James','Robert','Michael','William','David','Richard','Joseph',
               'Thomas','Charles','Christopher','Mary','Patricia','Jennifer',
               'Linda','Barbara','Elizabeth','Susan','Jessica','Sarah','Karen',
               'Nancy','Lisa','Betty','Margaret','Sandra','Ashley','Dorothy',
               'Kimberly','Emily','Donna']

    _LAST   = ['Smith','Johnson','Williams','Brown','Jones','Garcia','Miller',
               'Davis','Rodriguez','Martinez','Hernandez','Lopez','Gonzalez',
               'Wilson','Anderson','Thomas','Taylor','Moore','Jackson','Martin',
               'Lee','Perez','Thompson','White','Harris','Sanchez','Clark',
               'Ramirez','Lewis','Robinson']

    _OOS_ADDRS = [
        ('123 Main St',        'Chicago',      'IL'),
        ('456 Oak Ave',        'Dallas',       'TX'),
        ('789 Pine Rd',        'Los Angeles',  'CA'),
        ('321 Maple Dr',       'New York',     'NY'),
        ('654 Cedar Ln',       'Phoenix',      'AZ'),
        ('987 Elm St',         'Charlotte',    'NC'),
        ('147 Birch Ave',      'Nashville',    'TN'),
        ('258 Walnut Rd',      'Austin',       'TX'),
        ('369 Oak Park Dr',    'Denver',       'CO'),
        ('741 River Rd',       'Seattle',      'WA'),
        ('852 Summit Blvd',    'Las Vegas',    'NV'),
        ('963 Harbor View Dr', 'Tampa',        'FL'),
        ('111 Commerce St',    'Columbus',     'OH'),
        ('222 Lakeview Dr',    'Indianapolis', 'IN'),
    ]

    _INSTATE_ADDRS = [
        ('100 Peachtree St NW', 'Atlanta',    'GA'),
        ('200 Spring St SW',    'Marietta',   'GA'),
        ('300 Piedmont Ave',    'Decatur',    'GA'),
        ('400 Ponce de Leon',   'Smyrna',     'GA'),
        ('500 Moreland Ave SE', 'Kennesaw',   'GA'),
        ('600 Windy Hill Rd',   'Lawrenceville', 'GA'),
    ]

    _PROP_TYPES = [
        'Single Family', 'Single Family', 'Single Family',
        'Single Family', 'Townhouse', 'Condo',
    ]

    # Segment mix for demo realism
    # Market-realistic distribution (audit §18.3). A real North Fulton / Forsyth
    # scan is dominated by ordinary owner-occupants, NOT distressed/absentee leads.
    # Motivated archetypes are a deliberate minority so HOT stays a meaningful tier;
    # the bulk are owner-occupants, with a lifecycle subset (long tenure / senior /
    # equity) representing the normal move-up & downsizer sellers a Realtor actually wins.
    _PROFILES = {
        'hot_primary':   0.05,  # out-of-state + long tenure + equity → HOT
        'hot_multi':     0.03,  # out-of-state + distress → HOT
        'warm_probate':  0.05,  # estate / probate → HOT/WARM
        'warm_tax':      0.05,  # tax delinquent → WARM
        'warm_instate':  0.07,  # in-state absentee → WARM
        'warm_mompop':   0.05,  # mom-and-pop landlord → WARM
        'cool_absentee': 0.10,  # newer absentee < 10 yrs → COOL
        'lifecycle_occ': 0.13,  # long-tenure homestead family/senior → WARM/HOT (normal seller)
        'owner_occ':     0.41,  # ordinary owner-occupant → COOL / REVIEW / PASS (the majority)
        'corporate':     0.09,  # LLC / Inc → PASS (institutional) or small-entity
    }

    def __init__(self, api_key='', username='', password=''):
        self.api_key  = api_key
        self.username = username
        self.password = password
        self.last_count = 0
        self._token = None

    # ── Public ───────────────────────────────────────────────────────────────

    def get_properties(self, county: str, mode: str = "market_intelligence") -> list:
        """Fetch records for a county in the given SourceMode.

        seller_prospecting   → off-market owners (NOT Active/Coming Soon).
        market_intelligence  → Active/Coming Soon MLS inventory (comps/intel).
        buyer_opportunity    → Active/Coming Soon for buyer-side ranking.
        """
        from settings import settings as _cfg
        if _cfg.DEMO_MODE:
            return self._demo_data(county, mode=mode)
        if mode in ("market_intelligence", "buyer_opportunity"):
            return self._live_market_inventory(county)
        if mode == "seller_prospecting":
            return self._live_seller_prospects(county)
        raise ValueError(f"Unsupported FMLS source mode: {mode}")

    # ── Live API ─────────────────────────────────────────────────────────────

    # Per-submarket price ceiling (audit §6.3 / §7 P1): a flat $2M cap excludes
    # legitimate high-GCI Milton / Alpharetta / Johns Creek luxury listings.
    # Override via config.FMLS_PRICE_CEILING (single int) if the agent's strategy differs.
    _CITY_PRICE_CEILING = {
        'Milton':        4_000_000,
        'Alpharetta':    2_800_000,
        'Johns Creek':   2_800_000,
        'Sandy Springs': 2_500_000,
        'Roswell':       2_000_000,
    }
    _DEFAULT_PRICE_CEILING = 2_500_000

    def _live_market_inventory(self, county: str) -> list:
        """Active / Coming Soon MLS inventory — market intelligence & buyer-side use.
        These are NOT seller-prospecting records (the owners are represented)."""
        token   = self._get_token()
        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}

        county_code = 'Fulton' if county == 'North Fulton' else county

        # Restrict the Fulton query to the five North Fulton target cities so we
        # don't scan (and later cap) the entire county. Forsyth stays county-wide.
        from settings import settings as _cfg
        override_ceiling = getattr(_cfg, "FMLS_PRICE_CEILING", None)
        if county == 'North Fulton':
            ceiling = override_ceiling or max(self._CITY_PRICE_CEILING.values())
            city_clause = " or ".join(f"City eq '{c}'" for c in self._FULTON_CITIES)
            geo_clause = f"CountyOrParish eq 'Fulton' and ({city_clause})"
        else:
            ceiling = override_ceiling or self._DEFAULT_PRICE_CEILING
            geo_clause = f"CountyOrParish eq '{county_code}'"

        # Skip Registered listings (FMLS Rule 3.1 — not co-op distributable);
        # include Active and ComingSoon (DOM hasn't accrued — highest priority).
        status_clause = "(StandardStatus eq 'Active' or StandardStatus eq 'Coming Soon')"

        odata_filter = (
            f"{geo_clause} and {status_clause} and "
            f"ListPrice ge 200000 and ListPrice le {int(ceiling)}"
        )
        select = ','.join([
            'ListingId','ListPrice','StreetNumber','StreetName','StreetSuffix',
            'City','PostalCode','CountyOrParish','PropertyType','PropertySubType',
            'YearBuilt','ListingContractDate','OwnerName','TaxAnnualAmount',
            'BedroomsTotal','StandardStatus',
        ])

        url = (f"{self.BASE_URL}/Property"
               f"?$filter={odata_filter}&$select={select}&$top=500&$count=true")
        props = []
        while url:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
            props.extend(data.get('value', []))
            url = data.get('@odata.nextLink')

        self.last_count = len(props)
        return [self._normalize(p, county, mode="market_intelligence") for p in props]

    # FMLS RESO status vocabulary for non-active seller-prospect records. Confirm the
    # exact strings your FMLS feed uses before relying on this in production.
    _SELLER_PROSPECT_STATUSES = ("Expired", "Withdrawn", "Canceled", "Cancelled")

    def _live_seller_prospects(self, county: str) -> list:
        """Off-market seller prospects from FMLS (expired / withdrawn / canceled only).

        This is the MINIMAL acceptable seller source per the execution ticket. The
        production-preferred path is a dedicated off-market layer (county assessor,
        deed, equity, contact) — see the `sources/` adapters. If no such source is
        configured, a real install should surface the warning raised by app.py rather
        than fall back to Active/Coming Soon.
        """
        token   = self._get_token()
        headers = {'Authorization': f'Bearer {token}', 'Accept': 'application/json'}
        county_code = 'Fulton' if county == 'North Fulton' else county

        from settings import settings as _cfg
        override_ceiling = getattr(_cfg, "FMLS_PRICE_CEILING", None)
        if county == 'North Fulton':
            ceiling = override_ceiling or max(self._CITY_PRICE_CEILING.values())
            city_clause = " or ".join(f"City eq '{c}'" for c in self._FULTON_CITIES)
            geo_clause = f"CountyOrParish eq 'Fulton' and ({city_clause})"
        else:
            ceiling = override_ceiling or self._DEFAULT_PRICE_CEILING
            geo_clause = f"CountyOrParish eq '{county_code}'"

        status_clause = "(" + " or ".join(
            f"StandardStatus eq '{s}'" for s in self._SELLER_PROSPECT_STATUSES
        ) + ")"
        odata_filter = (
            f"{geo_clause} and {status_clause} and "
            f"ListPrice ge 200000 and ListPrice le {int(ceiling)}"
        )
        select = ','.join([
            'ListingId','ListPrice','StreetNumber','StreetName','StreetSuffix',
            'City','PostalCode','CountyOrParish','PropertyType','PropertySubType',
            'YearBuilt','ListingContractDate','OwnerName','TaxAnnualAmount',
            'BedroomsTotal','StandardStatus',
        ])
        url = (f"{self.BASE_URL}/Property"
               f"?$filter={odata_filter}&$select={select}&$top=500&$count=true")
        props = []
        while url:
            r = requests.get(url, headers=headers, timeout=30)
            r.raise_for_status()
            data = r.json()
            props.extend(data.get('value', []))
            url = data.get('@odata.nextLink')

        self.last_count = len(props)
        return [self._normalize(p, county, mode="seller_prospecting") for p in props]

    def _normalize(self, raw: dict, county: str, mode: str = "market_intelligence") -> dict:
        status = raw.get('StandardStatus', '')
        is_listed = status.lower() in ("active", "coming soon")
        addr = f"{raw.get('StreetNumber','')} {raw.get('StreetName','')} {raw.get('StreetSuffix','')}".strip()
        return {
            'listing_id':              raw.get('ListingId', ''),
            'address':                 addr,
            'city':                    raw.get('City', ''),
            'county':                  county,
            'state':                   'GA',
            'zip_code':                raw.get('PostalCode', ''),
            'property_type':           raw.get('PropertySubType') or raw.get('PropertyType', 'Single Family'),
            'listing_status':          raw.get('StandardStatus', ''),
            'year_built':              raw.get('YearBuilt'),
            'assessed_value':          raw.get('ListPrice', 0),
            'bedrooms':                raw.get('BedroomsTotal', 0),
            'owner_name':              raw.get('OwnerName', ''),
            'owner_mailing_address':   '',
            'owner_city':              '',
            'owner_state':             'GA',
            'is_out_of_state_absentee': False,
            'is_in_state_absentee':    False,
            # P0 (audit §1.2): live FMLS does NOT prove owner tenure or equity.
            # Encode unknowns as None — NOT 0 — so the engine lowers confidence
            # instead of firing the -18 short-tenure penalty on every live lead.
            'years_owned':             None,
            'tenure_verified':         False,
            'tenure_source':           None,
            'tax_delinquent':          False,
            'foreclosure':             False,
            'free_and_clear':          False,
            'estimated_equity_pct':    None,
            'equity_source':           None,
            'total_properties_owned':  1,
            'homestead_exemption':     False,
            'senior_exemption':        False,
            'vacancy':                 False,
            'mortgage_year':           None,
            'school_performance_score': None,
            'transfer_type':           '',
            'phone':                   '',
            'email':                   '',
            # ── Source labels (P0-01) ──────────────────────────────────────────
            'source_system':           'fmls',
            'source_mode':             mode,
            'seller_outreach_allowed': not is_listed,
            'compliance_hold_reason':  ('Active/Coming Soon FMLS listing — already represented'
                                        if is_listed else None),
        }

    def _get_token(self) -> str:
        if self._token:
            return self._token
        r = requests.post(self.TOKEN_URL, data={
            'grant_type': 'password',
            'username':   self.username,
            'password':   self.password,
            'client_id':  self.api_key,
        }, timeout=15)
        r.raise_for_status()
        self._token = r.json()['access_token']
        return self._token

    # ── Demo data ─────────────────────────────────────────────────────────────

    def _demo_data(self, county: str, mode: str = "market_intelligence") -> list:
        seed = 42 if county == 'Forsyth' else 73
        rng  = random.Random(seed)

        cities = self._FORSYTH_CITIES if county == 'Forsyth' else self._FULTON_CITIES
        zips   = self._FORSYTH_ZIPS   if county == 'Forsyth' else self._FULTON_ZIPS

        total = rng.randint(140, 200)
        profiles = []
        for name, pct in self._PROFILES.items():
            profiles.extend([name] * round(total * pct))
        while len(profiles) < total:
            profiles.append('owner_occ')
        rng.shuffle(profiles)

        result = [self._gen(rng, county, cities, zips, p, i, mode)
                  for i, p in enumerate(profiles)]
        self.last_count = len(result)
        return result

    def _school_score(self, rng, county: str, city: str) -> float | None:
        if rng.random() < 0.25:
            return None  # ~25% of records don't have this enrichment
        # North Fulton premium school zones: Milton/Cambridge/Northview/Alpharetta HS
        if city in ('Milton', 'Alpharetta', 'Johns Creek'):
            return round(rng.uniform(88, 98), 1)
        if city in ('Roswell', 'Sandy Springs'):
            return round(rng.uniform(78, 93), 1)
        if county == 'Forsyth':
            return round(rng.uniform(82, 95), 1)  # Denmark/South Forsyth HS zone
        return round(rng.uniform(70, 90), 1)

    def _gen(self, rng, county, cities, zips, profile, idx, mode="market_intelligence"):
        city  = rng.choice(cities)
        zip_  = rng.choice(zips)
        addr  = f"{rng.randint(100, 9999)} {rng.choice(self._STREETS)}"
        value = rng.randint(250, 990) * 1000 + rng.choice([0, 500, 900, 0])
        # P2-18: skew toward the target retail-buyer band (2005–2026) instead of
        # topping out at 2012, so demos reflect the real North Fulton / S. Forsyth pool.
        yr    = rng.choices(
            population=[rng.randint(2005, 2020), rng.randint(2021, 2026),
                        rng.randint(1995, 2004), rng.randint(1985, 1994),
                        rng.randint(1968, 1984)],
            weights=[0.40, 0.15, 0.22, 0.13, 0.10],
        )[0]
        prop_type = rng.choice(self._PROP_TYPES)
        beds  = rng.randint(2, 3) if prop_type in ('Townhouse', 'Condo') else rng.randint(3, 5)

        # P0-01 / P2-18: listing_status by mode. Market mode shows real MLS inventory
        # (some Active/Coming Soon → COMPLIANCE_HOLD in seller scoring). Seller mode
        # produces off-market records only, so no compliance holds appear as leads.
        if mode in ("market_intelligence", "buyer_opportunity"):
            demo_status = rng.choices(['Active', 'Coming Soon', 'Off Market'],
                                      weights=[0.45, 0.15, 0.40])[0]
        else:
            # Seller mode is mostly off-market, but a small slice is already listed —
            # these must be caught as COMPLIANCE_HOLD (the Art. 16 safety net), so the
            # demo shows the hold queue working rather than presenting them as leads.
            demo_status = rng.choices(['Off Market', 'Active', 'Coming Soon'],
                                      weights=[0.88, 0.08, 0.04])[0]

        fn = rng.choice(self._FIRST)
        ln = rng.choice(self._LAST)

        base = {
            'listing_id':              f'DEMO-{county[:3].upper()}-{idx:04d}',
            'address':                 addr,
            'city':                    city,
            'county':                  county,
            'state':                   'GA',
            'zip_code':                zip_,
            'property_type':           prop_type,
            'year_built':              yr,
            'assessed_value':          value,
            'bedrooms':                beds,
            'owner_name':              f'{ln.upper()}, {fn}',
            'owner_mailing_address':   addr,
            'owner_city':              city,
            'owner_state':             'GA',
            'is_out_of_state_absentee': False,
            'is_in_state_absentee':    False,
            'years_owned':             rng.randint(1, 6),
            'tax_delinquent':          False,
            'foreclosure':             False,
            'free_and_clear':          False,
            'estimated_equity_pct':    rng.randint(10, 40),
            'total_properties_owned':  1,
            'homestead_exemption':     False,
            'senior_exemption':        False,
            'vacancy':                 False,
            'mortgage_year':           rng.randint(2015, 2023),
            'school_performance_score': self._school_score(rng, county, city),
            'transfer_type':           '',
            'phone':                   '',
            'email':                   '',
            'listing_status':          demo_status,
            'source_system':           'demo',
            'source_mode':             mode,
            'seller_outreach_allowed': demo_status not in ('Active', 'Coming Soon'),
            'compliance_hold_reason':  ('Active/Coming Soon listing — already represented'
                                        if demo_status in ('Active', 'Coming Soon') else None),
        }

        if profile == 'hot_primary':
            oos = rng.choice(self._OOS_ADDRS)
            yrs = rng.randint(10, 30)
            base.update({
                'is_out_of_state_absentee': True,
                'owner_mailing_address':    f'{oos[0]}, {oos[1]}, {oos[2]}',
                'owner_city':               oos[1],
                'owner_state':              oos[2],
                'years_owned':              yrs,
                'estimated_equity_pct':     rng.randint(52, 92),
                'free_and_clear':           yrs >= 22,
                'year_built':               rng.randint(1968, 1994),
                'bedrooms':                 rng.randint(3, 5),
                'total_properties_owned':   rng.choice([1, 2, 3]),
                'mortgage_year':            None,
                'homestead_exemption':      False,
            })

        elif profile == 'hot_multi':
            oos = rng.choice(self._OOS_ADDRS)
            yrs = rng.randint(11, 22)
            base.update({
                'is_out_of_state_absentee': True,
                'owner_mailing_address':    f'{oos[0]}, {oos[1]}, {oos[2]}',
                'owner_city':               oos[1],
                'owner_state':              oos[2],
                'years_owned':              yrs,
                'tax_delinquent':           True,
                'foreclosure':              rng.random() < 0.35,
                'estimated_equity_pct':     rng.randint(55, 85),
                'year_built':               rng.randint(1970, 1993),
                'bedrooms':                 rng.randint(3, 5),
                'total_properties_owned':   rng.randint(2, 4),
                'homestead_exemption':      False,
                'mortgage_year':            None,
            })

        elif profile == 'warm_tax':
            ia = rng.choice(self._INSTATE_ADDRS) if rng.random() > 0.5 else None
            base.update({
                'tax_delinquent':        True,
                'years_owned':           rng.randint(5, 18),
                'estimated_equity_pct':  rng.randint(30, 65),
                'is_in_state_absentee':  ia is not None,
                'owner_mailing_address': f'{ia[0]}, {ia[1]}, {ia[2]}' if ia else addr,
                'owner_city':            ia[1] if ia else city,
                'homestead_exemption':   ia is None and rng.random() < 0.4,
            })

        elif profile == 'warm_probate':
            templates = [
                f'ESTATE OF {rng.choice(self._FIRST).upper()} {rng.choice(self._LAST).upper()}',
                f'HEIRS OF {rng.choice(self._LAST).upper()}',
                f'{rng.choice(self._LAST).upper()} FAMILY TRUST',
                f'TRUSTEE {rng.choice(self._LAST).upper()}',
            ]
            yrs = rng.randint(10, 32)
            fc  = rng.random() > 0.35
            base.update({
                'owner_name':            rng.choice(templates),
                'years_owned':           yrs,
                'estimated_equity_pct':  rng.randint(65, 96),
                'free_and_clear':        fc,
                'year_built':            rng.randint(1965, 1995),
                'bedrooms':              rng.randint(3, 5),
                'senior_exemption':      rng.random() < 0.45,
                'transfer_type':         'estate',
                'homestead_exemption':   False,
                'mortgage_year':         None if fc else rng.randint(2005, 2018),
            })

        elif profile == 'warm_instate':
            ia = rng.choice(self._INSTATE_ADDRS)
            base.update({
                'is_in_state_absentee':  True,
                'owner_mailing_address': f'{ia[0]}, {ia[1]}, {ia[2]}',
                'owner_city':            ia[1],
                'years_owned':           rng.randint(5, 18),
                'estimated_equity_pct':  rng.randint(35, 72),
                'total_properties_owned': rng.randint(1, 4),
                'homestead_exemption':   False,
            })

        elif profile == 'warm_mompop':
            ia = rng.choice(self._INSTATE_ADDRS)
            base.update({
                'is_in_state_absentee':   True,
                'owner_mailing_address':  f'{ia[0]}, {ia[1]}, {ia[2]}',
                'owner_city':             ia[1],
                'total_properties_owned': rng.randint(2, 5),
                'years_owned':            rng.randint(5, 16),
                'estimated_equity_pct':   rng.randint(40, 78),
                'homestead_exemption':    False,
            })

        elif profile == 'cool_absentee':
            if rng.random() > 0.5:
                oos = rng.choice(self._OOS_ADDRS)
                base.update({
                    'is_out_of_state_absentee': True,
                    'owner_mailing_address':    f'{oos[0]}, {oos[1]}, {oos[2]}',
                    'owner_city':               oos[1],
                    'owner_state':              oos[2],
                    'years_owned':              rng.randint(1, 8),
                    'homestead_exemption':      False,
                })
            else:
                ia = rng.choice(self._INSTATE_ADDRS)
                base.update({
                    'is_in_state_absentee':  True,
                    'owner_mailing_address': f'{ia[0]}, {ia[1]}, {ia[2]}',
                    'owner_city':            ia[1],
                    'years_owned':           rng.randint(2, 7),
                    'homestead_exemption':   False,
                })

        elif profile == 'corporate':
            sfx = rng.choice([' LLC', ' INC', ' HOLDINGS LLC',
                              ' PROPERTIES LLC', ' INVESTMENTS LP', ' GROUP INC'])
            base['owner_name'] = f"{rng.choice(self._LAST).upper()}{sfx}"
            base['homestead_exemption'] = False

        elif profile == 'lifecycle_occ':
            # The normal owner-occupant seller (audit §4.1/§6.6): long-tenure family
            # or senior with real equity, entering a move-up / downsize window. This
            # is the bulk of a Realtor's actual listing business — should rank WARM/HOT.
            yrs = rng.randint(12, 28)
            senior = rng.random() < 0.35
            base.update({
                'homestead_exemption': True,
                'years_owned':         yrs,
                'mortgage_year':       None if rng.random() < 0.4 else rng.randint(2002, 2014),
                'estimated_equity_pct': rng.randint(45, 88),
                'free_and_clear':      yrs >= 22 and rng.random() < 0.5,
                'senior_exemption':    senior,
                'bedrooms':            rng.randint(3, 5),
                'year_built':          rng.randint(1995, 2016),
                'vacancy':             False,
            })

        elif profile == 'owner_occ':
            # Ordinary owner-occupant, recent-to-mid tenure, modest equity, no
            # transition signal. Most should land COOL / REVIEW / PASS. ~30% have
            # unknown tenure (None) to exercise the missing-data path realistically.
            mort_yr = rng.choice([2017, 2018, 2019, 2020, 2020, 2021, 2021, 2022, 2023, 2024])
            yrs = max(1, 2026 - mort_yr + rng.randint(0, 2))
            base.update({
                'homestead_exemption': True,
                'years_owned':         None if rng.random() < 0.30 else yrs,
                'mortgage_year':       mort_yr,
                'estimated_equity_pct': rng.randint(8, 35),
                'senior_exemption':    rng.random() < 0.08,
                'vacancy':             False,
            })

        return base
