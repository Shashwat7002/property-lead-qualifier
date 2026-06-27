"""
Continuous distance-decay geo features (P2-13).

Replaces crude boolean/count amenity logic with smooth distance-decay so a home 40m
from a highway is penalized far more than one 300m away, and grocery/park/GA-400
proximity contribute proportionally. Missing distances contribute nothing (a record
is never punished for un-enriched OSM data — only confidence is affected upstream).
"""

import math


def road_noise_penalty(distance_m) -> float:
    """Negative fit penalty that decays with distance from a major road.
       0m≈-5.0, 50m≈-3.3, 150m≈-1.4, 300m≈-0.4."""
    if distance_m is None:
        return 0.0
    return -5.0 * math.exp(-float(distance_m) / 120.0)


def amenity_score(grocery_mi=None, park_mi=None, ga400_mi=None, key_amenity_mi=None) -> int:
    """0–100 amenity marketability from distance-decay of nearby amenities (baseline 50)."""
    score = 50.0
    if grocery_mi is not None:
        score += 15 * math.exp(-float(grocery_mi) / 1.0)
    if park_mi is not None:
        score += 10 * math.exp(-float(park_mi) / 1.5)
    if ga400_mi is not None:
        score += 10 * math.exp(-float(ga400_mi) / 3.0)
    if key_amenity_mi is not None:
        score += 10 * math.exp(-float(key_amenity_mi) / 3.0)
    return max(0, min(100, round(score)))


def compute_geo_fields(prop: dict) -> dict:
    """Populate amenity_marketability_score / road_noise_penalty when distances exist."""
    out = {}
    has_amenity = any(prop.get(k) is not None for k in
                      ("distance_to_grocery_mi", "distance_to_park_mi",
                       "distance_to_ga400_mi", "distance_to_key_amenity_mi"))
    if has_amenity:
        out["amenity_marketability_score"] = amenity_score(
            prop.get("distance_to_grocery_mi"), prop.get("distance_to_park_mi"),
            prop.get("distance_to_ga400_mi"), prop.get("distance_to_key_amenity_mi"),
        )
    if prop.get("distance_to_major_road_m") is not None:
        out["road_noise_penalty"] = round(road_noise_penalty(prop["distance_to_major_road_m"]), 2)
    return out
