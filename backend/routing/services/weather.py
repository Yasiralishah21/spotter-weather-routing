import time
from datetime import datetime, timedelta, timezone

import requests

from routing.services.errors import UpstreamError
from routing.services.http import session

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
BATCH_SIZE = 80


def point_key(lat, lon):
    return (round(lat, 3), round(lon, 3))


def fetch_hourly(points):
    """Return {rounded lat/lon: hourly series} for every requested point."""
    unique = []
    seen = set()
    for lat, lon in points:
        key = point_key(lat, lon)
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)
    found = {}
    for start in range(0, len(unique), BATCH_SIZE):
        chunk = unique[start : start + BATCH_SIZE]
        found.update(_fetch_chunk(chunk))
    missing = [key for key in unique if key not in found]
    if missing:
        raise UpstreamError("Weather data is missing for part of this trip.")
    return found


def sample_at(series, moment):
    times = series["times"]
    if not times:
        return None
    if moment < times[0] - timedelta(minutes=45) or moment > times[-1] + timedelta(minutes=45):
        return None
    lo = 0
    hi = len(times) - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if times[mid] < moment:
            lo = mid + 1
        else:
            hi = mid
    choices = [lo]
    if lo > 0:
        choices.append(lo - 1)
    index = min(choices, key=lambda i: abs(times[i] - moment))
    return {
        "time": times[index],
        "wind_mph": series["wind"][index],
        "rain_in_hr": series["rain"][index],
        "snow_in_hr": series["snow"][index],
    }


def _fetch_chunk(keys):
    params = {
        "latitude": ",".join(str(lat) for lat, _lon in keys),
        "longitude": ",".join(str(lon) for _lat, lon in keys),
        "hourly": "wind_speed_10m,rain,snowfall",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "UTC",
        "forecast_days": 7,
    }
    payload = None
    last_error = None
    for attempt in range(3):
        try:
            response = session.get(FORECAST_URL, params=params, timeout=(5, 45))
            if response.status_code == 429:
                time.sleep(1.2 * (attempt + 1))
                continue
            response.raise_for_status()
            payload = response.json()
            break
        except requests.RequestException as exc:
            last_error = exc
            time.sleep(0.6 * (attempt + 1))
    if payload is None:
        raise UpstreamError("Weather service did not respond. Try again in a moment.") from last_error
    rows = payload if isinstance(payload, list) else [payload]
    if len(rows) != len(keys):
        raise UpstreamError("Weather service returned an unexpected forecast.")
    found = {}
    for key, row in zip(keys, rows):
        parsed = _parse_row(row)
        if parsed is not None:
            found[key] = parsed
    return found


def _parse_row(row):
    hourly = row.get("hourly") or {}
    times_raw = hourly.get("time") or []
    wind_raw = hourly.get("wind_speed_10m") or []
    rain_raw = hourly.get("rain") or []
    snow_raw = hourly.get("snowfall") or []
    units = row.get("hourly_units") or {}
    count = min(len(times_raw), len(wind_raw), len(rain_raw), len(snow_raw))
    if count == 0:
        return None
    times = []
    wind = []
    rain = []
    snow = []
    for index in range(count):
        try:
            times.append(datetime.fromisoformat(times_raw[index]).replace(tzinfo=timezone.utc))
        except ValueError:
            continue
        wind.append(_speed_mph(wind_raw[index], units.get("wind_speed_10m")))
        rain.append(_length_inches(rain_raw[index], units.get("rain")))
        snow.append(_length_inches(snow_raw[index], units.get("snowfall")))
    if not times:
        return None
    return {"times": times, "wind": wind, "rain": rain, "snow": snow}


def _number(value):
    if value is None:
        return 0.0
    return float(value)


def _speed_mph(value, unit):
    number = _number(value)
    label = (unit or "").lower()
    if label in {"km/h", "kmh"}:
        return number * 0.621371
    if label in {"m/s", "ms"}:
        return number * 2.23694
    return number


def _length_inches(value, unit):
    number = _number(value)
    label = (unit or "").lower()
    if label in {"cm", "centimeter", "centimeters"}:
        return number / 2.54
    if label in {"mm", "millimeter", "millimeters"}:
        return number / 25.4
    return number
