"""
Outcome tracking + calibration foundation (P2-11).

A local SQLite store that records every scored lead and any outreach outcomes the
agent logs (mailed → contacted → appointment → signed / lost / bad-data). This is
the data substrate needed to eventually CALIBRATE the (currently expert-assumed)
weights into measured conversion — precision@K and signed-rate by tier. The model
weights are NOT changed automatically; this just makes the data available.
"""

import hashlib
import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

_DB_PATH = Path(__file__).resolve().parent / "outcomes.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS lead_scores (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_key TEXT NOT NULL,
    scored_at TEXT NOT NULL,
    source_mode TEXT,
    score INTEGER,
    tier TEXT,
    operational_priority REAL,
    motivation_score INTEGER,
    fit_score INTEGER,
    confidence_score INTEGER,
    contactability_score INTEGER,
    motivation_raw INTEGER,
    fit_raw INTEGER,
    confidence_raw INTEGER,
    hot_evidence_ok INTEGER,
    payload_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS outreach_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    lead_key TEXT NOT NULL,
    event_at TEXT NOT NULL,
    event_type TEXT NOT NULL,
    channel TEXT,
    outcome TEXT,
    notes TEXT,
    payload_json TEXT
);
CREATE INDEX IF NOT EXISTS idx_scores_key ON lead_scores(lead_key);
CREATE INDEX IF NOT EXISTS idx_events_key ON outreach_events(lead_key);
"""


def _now():
    return datetime.now(timezone.utc).isoformat()


def _connect():
    conn = sqlite3.connect(_DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def lead_key(lead: dict) -> str:
    raw = "|".join(str(lead.get(k, "")) for k in
                   ("parcel_id", "address", "owner_name", "county")).lower()
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def record_scores(leads: list[dict], source_mode: str = "") -> int:
    """Persist a batch of scored leads. Returns the number written."""
    if not leads:
        return 0
    conn = _connect()
    ts = _now()
    rows = []
    for l in leads:
        rows.append((
            lead_key(l), ts, source_mode,
            l.get("score"), l.get("tier"), l.get("operational_priority"),
            l.get("motivation_score"), l.get("fit_score"), l.get("confidence_score"),
            l.get("contactability_score"), l.get("motivation_raw"), l.get("fit_raw"),
            l.get("confidence_raw"), 1 if l.get("hot_evidence_ok") else 0,
            json.dumps(l, default=str),
        ))
    conn.executemany(
        """INSERT INTO lead_scores
           (lead_key, scored_at, source_mode, score, tier, operational_priority,
            motivation_score, fit_score, confidence_score, contactability_score,
            motivation_raw, fit_raw, confidence_raw, hot_evidence_ok, payload_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""", rows)
    conn.commit()
    conn.close()
    return len(rows)


def record_event(lead_key_val: str, event_type: str, channel: str = "",
                 outcome: str = "", notes: str = "") -> int:
    conn = _connect()
    cur = conn.execute(
        """INSERT INTO outreach_events
           (lead_key, event_at, event_type, channel, outcome, notes, payload_json)
           VALUES (?,?,?,?,?,?,?)""",
        (lead_key_val, _now(), event_type, channel, outcome, notes, "{}"))
    conn.commit()
    rid = cur.lastrowid
    conn.close()
    return rid


def lead_history(lead_key_val: str) -> dict:
    conn = _connect()
    scores = [dict(zip([c[0] for c in cur.description], row))
              for cur in [conn.execute(
                  "SELECT scored_at, tier, score, operational_priority FROM lead_scores "
                  "WHERE lead_key=? ORDER BY scored_at DESC", (lead_key_val,))]
              for row in cur.fetchall()]
    events = [dict(zip([c[0] for c in cur.description], row))
              for cur in [conn.execute(
                  "SELECT event_at, event_type, channel, outcome, notes FROM outreach_events "
                  "WHERE lead_key=? ORDER BY event_at", (lead_key_val,))]
              for row in cur.fetchall()]
    conn.close()
    return {"lead_key": lead_key_val, "scores": scores, "events": events}


def calibration_summary() -> list[dict]:
    """Per-tier appointment/signed rates from logged outcomes (empty until data lands)."""
    conn = _connect()
    out = []
    for (tier,) in conn.execute("SELECT DISTINCT tier FROM lead_scores").fetchall():
        scored = conn.execute("SELECT COUNT(DISTINCT lead_key) FROM lead_scores WHERE tier=?", (tier,)).fetchone()[0]

        def _count(event_type):
            return conn.execute(
                """SELECT COUNT(DISTINCT e.lead_key) FROM outreach_events e
                   JOIN lead_scores s ON s.lead_key = e.lead_key
                   WHERE s.tier=? AND e.event_type=?""", (tier, event_type)).fetchone()[0]

        contacted = _count("contacted")
        appts = _count("appointment")
        signed = _count("signed")
        out.append({
            "tier": tier, "scored_count": scored, "contacted_count": contacted,
            "appointments": appts, "signed_listings": signed,
            "appointment_rate": round(appts / scored, 4) if scored else 0,
            "signed_rate": round(signed / scored, 4) if scored else 0,
        })
    conn.close()
    return out
