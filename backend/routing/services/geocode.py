import requests

from routing.services.errors import UpstreamError
from routing.services.http import session

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_cache = {}


def search_places(query):
    cleaned = " ".join(query.split())
    if len(cleaned) < 3:
        return []
    key = cleaned.lower()
    if key in _cache:
        return _cache[key]
    try:
        response = session.get(
            NOMINATIM_URL,
            params={"q": cleaned, "format": "jsonv2", "limit": 5},
            timeout=(5, 20),
        )
        response.raise_for_status()
        payload = response.json()
    except requests.RequestException as exc:
        raise UpstreamError("Place search is unavailable. Try again in a moment.") from exc
    results = []
    for item in payload:
        try:
            results.append(
                {
                    "label": item["display_name"],
                    "lat": float(item["lat"]),
                    "lon": float(item["lon"]),
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    if len(_cache) > 200:
        _cache.clear()
    _cache[key] = results
    return results
