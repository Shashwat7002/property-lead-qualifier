"""
GSCCCA (Georgia Superior Court Clerks' Cooperative Authority) deed lookup client.

Searches the statewide real estate deed index by owner name + county to derive:
  - years_owned   : years since most recent deed recording to current owner
  - transfer_type : instrument type (warranty deed, quitclaim, estate deed, etc.)

Free account required — register at https://www.gsccca.org/register
GSCCCA county coverage: all 159 Georgia counties since 1/1/1990.
"""

import re
import time
from datetime import date, datetime
from html.parser import HTMLParser
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

    def lookup_deed(self, owner_name: str, county: str, situs_address: str = "") -> dict:
        """
        Return the most recent deed for this owner in this county, WITH a match
        confidence (P1-08). Result on a confident match:
          {years_owned, transfer_type, gsccca_verified: True,
           gsccca_match_confidence, gsccca_recording_date, gsccca_grantee, ...}
        Ambiguous / weak matches return gsccca_verified=False + gsccca_warning
        (the engine routes those to REVIEW instead of scoring false tenure).
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

        # Stronger cache key: include situs address so two owners with the same name
        # in one county don't collide.
        cache_key = (search_name.upper(), county_id, (situs_address or "").upper().strip())
        if cache_key in self._cache:
            return self._cache[cache_key]

        today = date.today()
        # P1-08: pull live hidden form fields (dtSystemEnd / dtSysGoodThru / etc.)
        # instead of hardcoding stale dates.
        hidden = self._fetch_hidden_fields()
        payload = {
            "txtSearchType":    "0",
            "bolInclude":       "0",
            "txtSearchName":    search_name,
            "txtPartyType":     "0",           # Grantee (current owner received the deed)
            "txtInstrCode":     "ALL",
            "intCountyID":      county_id,
            "MaxRows":          "25",
            "TableType":        "2",           # 1-line compact format
            "txtFromDate":      "01/01/1990",
            "txtToDate":        today.strftime("%m/%d/%Y"),
            "dtCurrSearchTime": today.strftime("%-m/%-d/%Y") + " 12:00:00 PM",
        }
        # Use live hidden values where present; fall back to safe static defaults.
        for k, default in (("dtSystemEnd", today.strftime("%-m/%-d/%Y")),
                           ("dtSystemStart", "12/31/1871"),
                           ("dtSysGoodFrom", "1/1/1990"),
                           ("dtSysGoodThru", today.strftime("%-m/%-d/%Y"))):
            payload[k] = hidden.get(k, default)

        # Bounded retry/backoff for transient network errors.
        last_exc = None
        for attempt in range(3):
            try:
                r = self._session.post(
                    SEARCH_URL, data=payload,
                    headers={**_HEADERS, "Referer": SEARCH_PAGE}, timeout=TIMEOUT,
                )
                if "login.asp" in r.url or ("txtPassword" in r.text and len(r.text) < 5_000):
                    self._logged_in = False
                    return {}
                result = _parse_results(r.text, search_name=search_name)
                self._cache[cache_key] = result
                return result
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(1.5 * (attempt + 1))
        return {}

    def _fetch_hidden_fields(self) -> dict:
        """GET the search page and return its hidden <input> name→value map."""
        try:
            r = self._session.get(SEARCH_PAGE, headers=_HEADERS, timeout=TIMEOUT)
            parser = _HiddenInputParser()
            parser.feed(r.text)
            return parser.fields
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


class _HiddenInputParser(HTMLParser):
    """Collect hidden <input name=... value=...> pairs from a page (P1-08)."""
    def __init__(self):
        super().__init__()
        self.fields: dict[str, str] = {}

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "input":
            return
        a = dict(attrs)
        if a.get("type", "").lower() == "hidden" and a.get("name"):
            self.fields[a["name"]] = a.get("value", "")


def _name_match_confidence(search_name: str, grantee: str) -> float:
    """Score how well a result's grantee matches the searched owner (P1-08)."""
    # Derive last/first from the comma BEFORE stripping punctuation.
    raw = (search_name or "").upper()
    last = first = ""
    if "," in raw:
        l, _, rest = raw.partition(",")
        last = re.sub(r"[^A-Z]", "", l.split()[0]) if l.split() else ""
        first = re.sub(r"[^A-Z]", "", rest.split()[0]) if rest.split() else ""

    s = re.sub(r"[^A-Z ]", "", raw).strip()
    g = re.sub(r"[^A-Z ]", "", (grantee or "").upper()).strip()
    if not s or not g:
        return 0.0
    if s == g:
        return 0.95
    s_tokens, g_tokens = set(s.split()), set(g.split())
    # entity terms (TRUST/ESTATE/LLC) — substring match is meaningful
    if any(t in g for t in ("TRUST", "ESTATE", "HEIRS", "LLC", "INC")) and (s in g or g in s):
        return 0.75
    if not s_tokens:
        return 0.0
    if last and first and last in g_tokens and first in g_tokens:
        return 0.85
    overlap = len(s_tokens & g_tokens) / len(s_tokens)
    if overlap >= 0.5:
        return 0.55
    if last and last in g_tokens:
        return 0.40
    return 0.20


def _parse_results(html: str, search_name: str = "") -> dict:
    """
    Parse GSCCCA 1-line result table HTML with match confidence + ambiguity (P1-08).

    Column order for TableType=2 (1 Line) is typically:
      Grantee | County | Instrument | Recording Date | Book | Page

    Returns a confident match with gsccca_verified=True, OR (on ambiguity / weak
    match) gsccca_verified=False with a gsccca_warning so the engine can route the
    record to REVIEW instead of trusting a possibly-wrong tenure.
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

        row_text = " ".join(cells).upper()
        transfer = "warranty deed"
        for key, mapped in INSTRUMENT_MAP.items():
            if key in row_text:
                transfer = mapped
                break
        if transfer == "security deed":
            continue

        grantee = cells[0] if cells else ""
        book = next((c for c in cells if re.fullmatch(r'\d{3,6}', c)), "")
        years = (today - rec_date.date()).days // 365
        deeds.append({
            "recording_date":  rec_date,
            "years_owned":     max(0, years),
            "transfer_type":   transfer,
            "grantee":         grantee,
            "book":            book,
            "confidence":      _name_match_confidence(search_name, grantee),
        })

    if not deeds:
        return {}

    deeds.sort(key=lambda d: d["recording_date"], reverse=True)
    best = deeds[0]
    top_conf = best["confidence"]

    # Ambiguity: more than one DISTINCT grantee with comparably strong confidence.
    strong = [d for d in deeds if d["confidence"] >= 0.55]
    distinct_grantees = {d["grantee"].upper() for d in strong}
    ambiguous = len(distinct_grantees) > 1

    if top_conf < 0.70 or ambiguous:
        return {
            "gsccca_verified":         False,
            "gsccca_match_confidence": round(top_conf, 2),
            "gsccca_warning":          ("Ambiguous owner match; manual deed verification required"
                                        if ambiguous else
                                        "Low-confidence owner match; manual verification required"),
        }

    return {
        "years_owned":             best["years_owned"],
        "transfer_type":           best["transfer_type"],
        "gsccca_verified":         True,
        "gsccca_match_confidence": round(top_conf, 2),
        "gsccca_recording_date":   best["recording_date"].strftime("%Y-%m-%d"),
        "gsccca_grantee":          best["grantee"],
        "gsccca_book":             best["book"],
        "gsccca_warning":          None,
    }
