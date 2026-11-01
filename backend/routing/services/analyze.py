from datetime import datetime, timedelta, timezone

from routing.services.errors import UpstreamError
from routing.services.geo import (
    haversine_miles,
    interpolate_profile,
    local_bearing,
    offset_point,
    sample_miles,
    simplify_latlon,
)
from routing.services.risk import (
    LEVEL_CODE,
    classify_checkpoint,
    rank_routes,
    recommendation_reason,
    summarize_checkpoints,
)
from routing.services.router import driving_routes
from routing.services.weather import fetch_hourly, point_key, sample_at

FORECAST_HOURS = 49
CORRIDOR_MILES = 8


def analyze_trip(payload):
    origin = _place(payload, "origin")
    destination = _place(payload, "destination")
    departure = _departure(payload.get("departure"))
    load_lb = _load(payload.get("load_weight_lb"))
    interval = _interval(payload.get("interval_miles"))
    if haversine_miles((origin["lat"], origin["lon"]), (destination["lat"], destination["lon"])) < 1:
        raise ValueError("Origin and destination need to be different places.")

    routes = driving_routes(
        (origin["lat"], origin["lon"]),
        (destination["lat"], destination["lon"]),
    )

    prepared = []
    weather_points = []
    for route in routes:
        profile = route["profile"]
        total = route["distance_miles"]
        checkpoints = _checkpoints(profile, total, interval, departure)
        heat = _corridor(profile, total)
        for checkpoint in checkpoints:
            weather_points.append((checkpoint["lat"], checkpoint["lon"]))
        for point in heat:
            weather_points.append((point["lat"], point["lon"]))
        prepared.append({"route": route, "checkpoints": checkpoints, "heat": heat})

    forecasts = fetch_hourly(weather_points)
    _ensure_departure_is_covered(forecasts, departure)

    scored = []
    for item in prepared:
        scored.append(_score_route(item, forecasts, departure, load_lb))

    ranked = rank_routes(scored)
    reason = recommendation_reason(ranked)
    letters = "ABC"
    output_routes = []
    for index, route in enumerate(ranked):
        output_routes.append(_public_route(route, letters[index], index == 0, reason if index == 0 else None))

    note = None
    if len(output_routes) < 3:
        count = len(output_routes)
        noun = "route" if count == 1 else "routes"
        note = f"Only {count} distinct driving {noun} available for this trip."

    return {
        "origin": origin,
        "destination": destination,
        "departure": _iso(departure),
        "load_weight_lb": load_lb,
        "interval_miles": interval,
        "note": note,
        "routes": output_routes,
    }


def _checkpoints(profile, total, interval, departure):
    marks = sample_miles(total, interval)
    checkpoints = []
    previous = 0.0
    for index, mile in enumerate(marks):
        lat, lon, seconds = interpolate_profile(profile, mile)
        checkpoints.append(
            {
                "mile": mile,
                "segment_miles": 0.0 if index == 0 else mile - previous,
                "lat": lat,
                "lon": lon,
                "eta": departure + timedelta(seconds=seconds),
            }
        )
        previous = mile
    return checkpoints


def _corridor(profile, total):
    step = 15 if total <= 200 else 30 if total <= 600 else 45
    miles = []
    mile = 0.0
    while mile <= total:
        miles.append(mile)
        mile += step
    if not miles or total - miles[-1] > 0.5:
        miles.append(total)
    points = []
    for mile in miles:
        lat, lon, _seconds = interpolate_profile(profile, mile)
        points.append({"lat": lat, "lon": lon})
        bearing = local_bearing(profile, mile)
        for turn in (90, -90):
            olat, olon = offset_point(lat, lon, bearing + turn, CORRIDOR_MILES)
            points.append({"lat": olat, "lon": olon})
    return points


def _score_route(item, forecasts, departure, load_lb):
    route = item["route"]
    checkpoints = []
    for raw in item["checkpoints"]:
        reading = _reading(forecasts, raw["lat"], raw["lon"], raw["eta"])
        if reading is None:
            raise ValueError(
                "This trip runs past the 7-day forecast. Choose an earlier departure."
            )
        risk = classify_checkpoint(
            reading["wind_mph"], reading["rain_in_hr"], reading["snow_in_hr"], load_lb
        )
        checkpoints.append(
            {
                "mile": raw["mile"],
                "segment_miles": raw["segment_miles"],
                "lat": raw["lat"],
                "lon": raw["lon"],
                "eta": raw["eta"],
                "wind_mph": reading["wind_mph"],
                "rain_in_hr": reading["rain_in_hr"],
                "snow_in_hr": reading["snow_in_hr"],
                **risk,
            }
        )
    summary = summarize_checkpoints(checkpoints)
    heat = []
    for point in item["heat"]:
        codes = []
        for hour in range(FORECAST_HOURS):
            moment = departure + timedelta(hours=hour)
            reading = _reading(forecasts, point["lat"], point["lon"], moment)
            if reading is None:
                codes.append("X")
                continue
            risk = classify_checkpoint(
                reading["wind_mph"], reading["rain_in_hr"], reading["snow_in_hr"], load_lb
            )
            codes.append(LEVEL_CODE[risk["level"]])
        heat.append({"lat": point["lat"], "lon": point["lon"], "levels": "".join(codes)})
    return {
        "distance_miles": route["distance_miles"],
        "duration_seconds": route["duration_seconds"],
        "geometry": simplify_latlon(route["geometry"]),
        "checkpoints": checkpoints,
        "heatmap": heat,
        **summary,
    }


def _reading(forecasts, lat, lon, moment):
    series = forecasts.get(point_key(lat, lon))
    if series is None:
        raise UpstreamError("Weather data is missing for part of this trip.")
    return sample_at(series, moment)


def _ensure_departure_is_covered(forecasts, departure):
    series = next(iter(forecasts.values()), None)
    if series is None or sample_at(series, departure) is None:
        raise ValueError(
            "Departure is outside the available forecast. Choose a time within the next 7 days."
        )


def _public_route(route, letter, recommended, reason):
    return {
        "id": letter,
        "name": f"Option {letter}",
        "recommended": recommended,
        "reason": reason,
        "distance_miles": round(route["distance_miles"], 1),
        "duration_seconds": round(route["duration_seconds"]),
        "low_miles": round(route["low_miles"], 1),
        "moderate_miles": round(route["moderate_miles"], 1),
        "high_miles": round(route["high_miles"], 1),
        "severe_miles": round(route["severe_miles"], 1),
        "no_travel_miles": round(route["no_travel_miles"], 1),
        "average_risk": round(route["average_risk"], 2),
        "geometry": [[round(lat, 5), round(lon, 5)] for lat, lon in route["geometry"]],
        "checkpoints": [_public_checkpoint(item) for item in route["checkpoints"]],
        "heatmap": [
            {
                "lat": round(point["lat"], 5),
                "lon": round(point["lon"], 5),
                "levels": point["levels"],
            }
            for point in route["heatmap"]
        ],
    }


def _public_checkpoint(item):
    return {
        "mile": round(item["mile"], 1),
        "segment_miles": round(item["segment_miles"], 1),
        "lat": round(item["lat"], 5),
        "lon": round(item["lon"], 5),
        "eta": _iso(item["eta"]),
        "wind_mph": round(item["wind_mph"], 1),
        "rain_in_hr": round(item["rain_in_hr"], 3),
        "snow_in_hr": round(item["snow_in_hr"], 2),
        "wind_level": item["wind_level"],
        "rain_level": item["rain_level"],
        "snow_level": item["snow_level"],
        "level": item["level"],
    }


def _place(payload, key):
    raw = payload.get(key) if isinstance(payload, dict) else None
    if not isinstance(raw, dict):
        raise ValueError(f"Choose a {key} from the suggestions.")
    try:
        lat = float(raw["lat"])
        lon = float(raw["lon"])
    except (KeyError, TypeError, ValueError):
        raise ValueError(f"Choose a {key} from the suggestions.")
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise ValueError(f"The {key} coordinates are out of range.")
    label = str(raw.get("label") or "").strip() or f"{lat:.4f}, {lon:.4f}"
    return {"label": label, "lat": lat, "lon": lon}


def _departure(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Choose a departure date and time.")
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        raise ValueError("Departure time is not a valid date.")
    if parsed.tzinfo is None:
        raise ValueError("Departure time needs a timezone.")
    return parsed.astimezone(timezone.utc)


def _load(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError("Enter a load weight in pounds.")
    if number <= 0 or number > 250000:
        raise ValueError("Enter a load weight between 1 and 250,000 lb.")
    return number


def _interval(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = None
    if number not in (10, 25, 50):
        raise ValueError("Sample weather every 10, 25, or 50 miles.")
    return number


def _iso(moment):
    return moment.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
