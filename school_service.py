"""
School attendance-zone scoring (P1-07).

Buyers buy attendance zones, not ZIP codes. This resolves a property's elementary /
middle / high zone (point-in-polygon over GeoJSON in data/school_zones/ when present)
and blends a marketability score weighted toward the high school. When no zone data
or coordinates are available it falls back to a ZIP-level score, clearly LABELED as
a fallback with reduced boundary confidence so the engine doesn't imply false
precision.

Drop GeoJSON files named like `fulton_high.geojson`, `forsyth_high.geojson`, etc.
into data/school_zones/ (with a numeric "score" property per feature) to enable
attendance-zone resolution. `shapely` is used for point-in-polygon if installed.
"""

import json
from pathlib import Path

_ZONES_DIR = Path(__file__).resolve().parent / "data" / "school_zones"

# ZIP fallback (was GOSA_BY_ZIP) — coarse, last resort only.
ZIP_SCHOOL_FALLBACK = {
    "30004": 94.2, "30005": 96.1, "30009": 90.8, "30022": 91.7, "30097": 89.4,
    "30075": 84.3, "30076": 81.9, "30327": 82.1, "30328": 79.8, "30350": 85.6,
    "30040": 90.1, "30041": 92.8, "30028": 85.4, "30042": 87.9, "30024": 88.6,
}

_LEVEL_WEIGHTS = {"high": 0.50, "middle": 0.30, "elementary": 0.20}


def _load_zone_features():
    """Lazy-load any GeoJSON zone files. Returns {level: [features]} or {} if none."""
    if not _ZONES_DIR.exists():
        return {}
    out = {}
    for path in _ZONES_DIR.glob("*.geojson"):
        level = "high" if "high" in path.stem else "middle" if "middle" in path.stem else "elementary"
        try:
            gj = json.loads(path.read_text())
            out.setdefault(level, []).extend(gj.get("features", []))
        except Exception:
            continue
    return out


def _point_in_zone(lat, lng, features):
    """Return the best-matching feature for a point, or None. Requires shapely."""
    try:
        from shapely.geometry import shape, Point
    except Exception:
        return None
    pt = Point(lng, lat)
    for feat in features:
        try:
            if shape(feat["geometry"]).contains(pt):
                return feat
        except Exception:
            continue
    return None


def lookup_school_zone(lat: float, lng: float) -> dict:
    """Resolve attendance zones for coordinates. Empty dict if unavailable."""
    if lat is None or lng is None:
        return {}
    features = _load_zone_features()
    if not features:
        return {}
    out = {}
    for level, feats in features.items():
        match = _point_in_zone(lat, lng, feats)
        if match:
            props = match.get("properties", {})
            out[f"school_{level}_name"] = props.get("name")
            out[f"school_{level}_score"] = props.get("score")
    return out


def compute_school_fields(prop: dict) -> dict:
    """
    Produce the P1-07 school fields for a property:
      attendance-zone scores when resolvable, else a ZIP fallback (labeled).
    Never overwrites an explicitly provided demo/manual score.
    """
    if prop.get("school_marketability_score") is not None:
        return {}

    lat, lng = prop.get("latitude"), prop.get("longitude")
    zone = lookup_school_zone(lat, lng)
    if zone:
        hi = zone.get("school_high_score")
        mid = zone.get("school_middle_score")
        el = zone.get("school_elementary_score")
        present = [(lvl, s) for lvl, s in (("high", hi), ("middle", mid), ("elementary", el)) if s is not None]
        if present:
            wsum = sum(_LEVEL_WEIGHTS[lvl] for lvl, _ in present)
            score = round(sum(_LEVEL_WEIGHTS[lvl] * s for lvl, s in present) / wsum, 1)
            conf = 0.90 if hi is not None else 0.70
            return {
                **zone,
                "school_marketability_score": score,
                "school_boundary_confidence": conf,
                "school_redistricting_risk": "unknown",
                "school_score_source": "attendance_zone",
            }

    # ZIP fallback
    zip_ = (prop.get("zip_code") or "")[:5]
    fallback = ZIP_SCHOOL_FALLBACK.get(zip_) or prop.get("school_performance_score")
    if fallback is not None:
        return {
            "school_marketability_score": float(fallback),
            "school_boundary_confidence": 0.50,
            "school_redistricting_risk": "unknown",
            "school_score_source": "zip_fallback",
        }
    return {"school_score_source": "unknown", "school_boundary_confidence": 0.0}
