"""
GSCCCA (Georgia Superior Court Clerks' Cooperative Authority) deed lookup client.

Searches the statewide real estate deed index by owner name + county to derive:
  - years_owned   : years since most recent deed recording to current owner
  - transfer_type : instrument type (warranty deed, quitclaim, estate deed, etc.)

Free account required — register at https://www.gsccca.org/register
GSCCCA county coverage: all 159 Georgia counties since 1/1/1990.
"""

import re
from datetime import date, datetime
from typing import Optional

import requests

LOGIN_URL    = "https://apps.gsccca.org/login.asp"
SEARCH_PAGE  = "https://search.gsccca.org/RealEstate/namesearch.asp"
SEARCH_URL   = "https://search.gsccca.org/RealEstate/names.asp?Type=0"

# Sequential county IDs used by GSCCCA (confirmed via live form scrape)
COUNTY_IDS: dict[str, str] = {
    "fulton":       "60",
    "north fulton": "60",
    "forsyth":      "58",
}

# GSCCCA instrument labels → our transfer_type vocabulary (used by lead_engine.py)
INSTRUMENT_MAP: dict[str, str] = {
    "WARRANTY DEED":         "warranty deed",
    "QUIT CLAIM DEED":       "quitclaim deed",
    "QUITCLAIM DEED":        "quitclaim deed",
    "TRUSTEE'S DEED":        "trust transfer",
    "DEED - FROM ESTATE":    "estate deed",
    "DEED - FORECLOSURE":    "sheriff deed",
    "SHERIFF'S DEED":        "sheriff deed",
    "TAX SALE DEED":         "tax sale",
    "DEED OF GIFT":          "family transfer",
    "SECURITY DEED":         "security deed",  # mortgage recording
}

_HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/125.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

TIMEOUT = 20


class GsccaClient:
    """
    Session-based GSCCCA deed index client.
    Call login() once at the start of each scan, then lookup_deed() per property.
    Results are cached by (search_name, county_id) to avoid duplicate calls
    when the same owner appears on multiple properties.
    """

    def __init__(self, username: str = "", password: str = ""):
        self.username = username.strip()
        self.password = password.strip()
        self._session: Optional[requests.Session] = None
        self._logged_in = False
        self._cache: dict[tuple, dict] = {}

    # ── Public ───────────────────────────────────────────────────────────────

    @property
    def configured(self) -> bool:
        return bool(self.username and self.password)

    def login(self) -> bool:
        """Establish an authenticated GSCCCA session. Returns True on success."""
        if not self.configured:
            return False
        self._session = requests.Session()
        try:
            self._session.get(LOGIN_URL, headers=_HEADERS, timeout=TIMEOUT)
            r = self._session.post(
                LOGIN_URL,
                data={
                    "txtUserID":      self.username,
                    "txtPassword":    self.password,
                    "Redirect":       "https://www.gsccca.org/",
                    "FormSubmission": "True",
                    "ShowCaptcha":    "False",
                    "Referer":        "",
                },
                headers={
                    **_HEADERS,
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer":      LOGIN_URL,
                    "Origin":       "https://apps.gsccca.org",
                },
                timeout=TIMEOUT,
                allow_redirects=True,
            )
            # Still on login page with a password field = failed login
            if "txtPassword" in r.text and len(r.text) < 30_000:
                self._logged_in = False
                return False
            self._logged_in = True
            return True
        except Exception:
            self._logged_in = False
            return False

    def lookup_deed(self, owner_name: str, county: str) -> dict:
        """
        Return the most recent deed for this owner in this county.
        Result: {years_owned, transfer_type, gsccca_verified: True}
        Returns {} on failure, no match, or unconfigured.
        """
        if not self._logged_in or not self._session:
            return {}

        county_id = COUNTY_IDS.get(county.lower().strip())
        if not county_id:
            return {}

        search_name = _normalize_name(owner_name)
        if len(search_name) < 2:
            return {}

        cache_key = (search_name.upper(), county_id)
        if cache_key in self._cache:
            return self._cache[cache_key]

        today = date.today()
        payload = {
            "txtSearchType":    "0",
            "bolInclude":       "0",
            "txtSearchName":    search_name,
            "txtPartyType":     "0",           # Grantee (current owner received the deed)
            "txtInstrCode":     "ALL",
            "intCountyID":      county_id,
            "MaxRows":          "10",
            "TableType":        "2",           # 1-line compact format
            "txtFromDate":      "01/01/1990",
            "txtToDate":        today.strftime("%m/%d/%Y"),
            "dtSystemEnd":      "6/25/2026",
            "dtSystemStart":    "12/31/1871",
            "dtSysGoodFrom":    "1/1/1990",
            "dtSysGoodThru":    "5/13/2026",
            "dtCurrSearchTime": today.strftime("%-m/%-d/%Y") + " 12:00:00 PM",
        }

        try:
            r = self._session.post(
                SEARCH_URL,
                data=payload,
                headers={**_HEADERS, "Referer": SEARCH_PAGE},
                timeout=TIMEOUT,
            )
            # Session expired → GSCCCA redirects to login
            if "login.asp" in r.url or (
                "txtPassword" in r.text and len(r.text) < 5_000
            ):
                self._logged_in = False
                return {}

            result = _parse_results(r.text)
            self._cache[cache_key] = result
            return result

        except Exception:
            return {}


# ── Module-level helpers ──────────────────────────────────────────────────────

def _normalize_name(owner_name: str) -> str:
    """
    Convert raw owner_name to the best GSCCCA search term.
    GSCCCA stores individual names as 'LAST, FIRST' and uses starts-with matching.

    Examples:
      'SMITH, JAMES M'          → 'SMITH, JAMES'   (exact last + first, drop middle)
      'JAMES SMITH'             → 'JAMES SMITH'    (no comma — search verbatim)
      'JOHNSON PROPERTIES LLC'  → 'JOHNSON PROPERTIES'  (strip legal suffix)
      'ESTATE OF JOHN SMITH'    → 'ESTATE OF JOHN SMITH'
      'SMITH FAMILY TRUST'      → 'SMITH FAMILY TRUST'
    """
    name = owner_name.strip().upper()

    # Strip trailing legal suffixes for entity names
    name = re.sub(
        r'\s+(LLC|L\.L\.C\.?|INC\.?|INCORPORATED|CORP\.?|CORPORATION|'
        r'L\.P\.?|LLP|LTD\.?|CO\.)$',
        '', name, flags=re.I
    ).strip()

    if "," in name:
        parts = [p.strip() for p in name.split(",", 1)]
        last  = parts[0]
        first = parts[1].split()[0] if parts[1] else ""   # first word only, drop middle
        return f"{last}, {first}".rstrip(", ") if first else last

    # No comma — return verbatim (entity name or "FIRST LAST" personal name)
    return name[:50].strip()


def _parse_results(html: str) -> dict:
    """
    Parse GSCCCA 1-line result table HTML.
    Returns the most recent non-security-deed entry as:
      {years_owned, transfer_type, gsccca_verified: True}

    Column order for TableType=2 (1 Line) is typically:
      Grantee | County | Instrument | Recording Date | Book | Page
    """
    rows = re.findall(r'<tr[^>]*>(.*?)</tr>', html, re.S | re.I)
    today = date.today()
    deeds = []

    for row in rows:
        cells = re.findall(r'<td[^>]*>(.*?)</td>', row, re.S | re.I)
        cells = [re.sub(r'<[^>]+>', '', c).strip() for c in cells]
        cells = [c for c in cells if c]
        if len(cells) < 3:
            continue

        # Extract recording date (MM/DD/YYYY anywhere in the row)
        rec_date: Optional[datetime] = None
        for cell in cells:
            m = re.search(r'\b(\d{1,2}/\d{1,2}/\d{4})\b', cell)
            if m:
                try:
                    rec_date = datetime.strptime(m.group(1), "%m/%d/%Y")
                    break
                except ValueError:
                    pass
        if rec_date is None:
            continue

        # Extract instrument type
        row_text = " ".join(cells).upper()
        transfer = "warranty deed"   # default assumption
        for key, mapped in INSTRUMENT_MAP.items():
            if key in row_text:
                transfer = mapped
                break

        # Skip security deeds (mortgage recordings) — not an ownership transfer
        if transfer == "security deed":
            continue

        years = (today - rec_date.date()).days // 365
        deeds.append({
            "recording_date":  rec_date,
            "years_owned":     max(0, years),
            "transfer_type":   transfer,
        })

    if not deeds:
        return {}

    # Most recent ownership deed
    deeds.sort(key=lambda d: d["recording_date"], reverse=True)
    best = deeds[0]
    return {
        "years_owned":      best["years_owned"],
        "transfer_type":    best["transfer_type"],
        "gsccca_verified":  True,
    }
