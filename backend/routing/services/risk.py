"""Weather and load rules from the Spotter assessment.

Boundary policy: a value that sits on two printed ranges takes the more
severe range. The No Travel column is open on the high side (">" / "≥"),
so 1.00 in/hr of rain and 3.0 in/hr of snow stay Severe, and 55 mph is
No Travel.
"""

LEVELS = ("low", "moderate", "high", "severe", "no_travel")
SCORE = {"low": 1, "moderate": 2, "high": 3, "severe": 4, "no_travel": 5}
LEVEL_CODE = {"low": "L", "moderate": "M", "high": "H", "severe": "S", "no_travel": "N"}

# No Travel is sorted first. It is the worst class in the risk table, so a
# route that crosses it cannot beat a route that only reaches Severe.
RANK_KEYS = (
    ("no_travel_miles", "Fewest no-travel miles"),
    ("severe_miles", "Fewest severe miles"),
    ("high_miles", "Fewest high-risk miles"),
    ("average_risk", "Lowest average risk"),
    ("duration_seconds", "Shortest travel time"),
)


def classify_wind(mph):
    if mph >= 55:
        return "no_travel"
    if mph >= 45:
        return "severe"
    if mph >= 35:
        return "high"
    if mph >= 25:
        return "moderate"
    return "low"


def classify_rain(inches_per_hour):
    if inches_per_hour > 1:
        return "no_travel"
    if inches_per_hour >= 0.50:
        return "severe"
    if inches_per_hour >= 0.25:
        return "high"
    if inches_per_hour >= 0.10:
        return "moderate"
    return "low"


def classify_snow(inches_per_hour):
    if inches_per_hour > 3:
        return "no_travel"
    if inches_per_hour >= 2:
        return "severe"
    if inches_per_hour >= 1:
        return "high"
    if inches_per_hour >= 0.5:
        return "moderate"
    return "low"


def apply_load_to_wind(mph, level, load_lb):
    """Load rules only raise wind risk. They never lower it."""
    if mph >= 55:
        return "no_travel"
    # 45–54 mph is the Severe wind bin, which ends at 55.
    if 45 <= mph < 55 and load_lb > 30000:
        return "no_travel"
    # 35–44 mph is the High wind bin, which ends at 45.
    if 35 <= mph < 45 and load_lb > 40000:
        return "severe"
    return level


def _worse(left, right):
    if SCORE[left] >= SCORE[right]:
        return left
    return right


def classify_checkpoint(wind_mph, rain_in_hr, snow_in_hr, load_lb):
    wind_level = apply_load_to_wind(wind_mph, classify_wind(wind_mph), load_lb)
    rain_level = classify_rain(rain_in_hr)
    snow_level = classify_snow(snow_in_hr)
    level = _worse(wind_level, _worse(rain_level, snow_level))
    return {
        "wind_level": wind_level,
        "rain_level": rain_level,
        "snow_level": snow_level,
        "level": level,
    }


def summarize_checkpoints(checkpoints):
    totals = {level: 0.0 for level in LEVELS}
    weighted = 0.0
    counted = 0.0
    for checkpoint in checkpoints:
        miles = checkpoint["segment_miles"]
        if miles <= 0:
            continue
        totals[checkpoint["level"]] += miles
        weighted += miles * SCORE[checkpoint["level"]]
        counted += miles
    return {
        "low_miles": totals["low"],
        "moderate_miles": totals["moderate"],
        "high_miles": totals["high"],
        "severe_miles": totals["severe"],
        "no_travel_miles": totals["no_travel"],
        "average_risk": (weighted / counted) if counted else 0.0,
    }


def rank_routes(routes):
    return sorted(
        routes,
        key=lambda route: tuple(route[key] for key, _phrase in RANK_KEYS),
    )


def recommendation_reason(ranked):
    if len(ranked) < 2:
        return "Only distinct driving route"
    best = ranked[0]
    contenders = list(ranked[1:])
    for key, phrase in RANK_KEYS:
        contenders = [
            other for other in contenders if abs(best[key] - other[key]) <= 1e-9
        ]
        if not contenders:
            return phrase
    return "Tied on risk and travel time"
