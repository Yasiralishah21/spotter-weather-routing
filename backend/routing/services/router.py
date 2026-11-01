import requests

from routing.services.errors import UpstreamError
from routing.services.geo import (
    haversine_miles,
    interpolate_profile,
    local_bearing,
    offset_point,
    profiles_overlap,
)
from routing.services.http import session

OSRM_SERVERS = (
    "https://router.project-osrm.org",
    "https://routing.openstreetmap.de/routed-car",
)


def driving_routes(origin, destination):
    """Up to three distinct driving routes between two lat/lon points."""
    last_error = None
    primary_routes = []
    chosen = None
    for base in OSRM_SERVERS:
        try:
            primary_routes = _request(base, (origin, destination), alternatives=True)
            chosen = base
            break
        except UpstreamError as exc:
            last_error = exc
    if not primary_routes or chosen is None:
        raise last_error or UpstreamError("Routing service is unavailable.")

    chosen_routes = []
    profiles = []
    for route in primary_routes:
        profile = build_profile(route)
        if any(profiles_overlap(profile, existing) for existing in profiles):
            continue
        chosen_routes.append(route)
        profiles.append(profile)
        if len(chosen_routes) == 3:
            return _pack(chosen_routes, profiles)

    total = profiles[0][-1][0]
    offset_miles = max(8.0, min(35.0, total * 0.12))
    for fraction, turn in ((0.5, 90), (0.5, -90), (0.34, 90), (0.66, -90)):
        if len(chosen_routes) >= 3:
            break
        lat, lon, _seconds = interpolate_profile(profiles[0], total * fraction)
        via = offset_point(lat, lon, local_bearing(profiles[0], total * fraction) + turn, offset_miles)
        if haversine_miles(origin, via) < 3 or haversine_miles(destination, via) < 3:
            continue
        try:
            via_routes = _request(chosen, (origin, via, destination), alternatives=False)
        except (UpstreamError, ValueError):
            continue
        candidate = via_routes[0]
        profile = build_profile(candidate)
        if profile[-1][0] > total * 2.4:
            continue
        if any(profiles_overlap(profile, existing) for existing in profiles):
            continue
        chosen_routes.append(candidate)
        profiles.append(profile)

    if not chosen_routes:
        raise ValueError("No driving route found between those places.")
    return _pack(chosen_routes, profiles)


def build_profile(route):
    coordinates = route["geometry"]["coordinates"]
    latlon = [(lat, lon) for lon, lat in coordinates]
    if len(latlon) < 2:
        raise ValueError("Routing service returned an unusable path.")
    distances = []
    durations = []
    for leg in route.get("legs") or []:
        annotation = leg.get("annotation") or {}
        distances.extend(annotation.get("distance") or [])
        durations.extend(annotation.get("duration") or [])
    if len(distances) == len(latlon) - 1 and len(durations) == len(latlon) - 1:
        profile = [(0.0, 0.0, latlon[0][0], latlon[0][1])]
        mile = 0.0
        seconds = 0.0
        for index, (meters, dur) in enumerate(zip(distances, durations)):
            mile += meters / 1609.344
            seconds += dur
            lat, lon = latlon[index + 1]
            profile.append((mile, seconds, lat, lon))
        return profile

    walked = [(0.0, latlon[0][0], latlon[0][1])]
    total_hav = 0.0
    for left, right in zip(latlon, latlon[1:]):
        total_hav += haversine_miles(left, right)
        walked.append((total_hav, right[0], right[1]))
    hav = walked[-1][0] or 1.0
    road_miles = route["distance"] / 1609.344
    road_seconds = route["duration"]
    return [
        (mile / hav * road_miles, mile / hav * road_seconds, lat, lon)
        for mile, lat, lon in walked
    ]


def _pack(routes, profiles):
    packed = []
    for route, profile in zip(routes, profiles):
        latlon = [(item[2], item[3]) for item in profile]
        packed.append(
            {
                "profile": profile,
                "geometry": latlon,
                "distance_miles": profile[-1][0],
                "duration_seconds": profile[-1][1],
            }
        )
    return packed


def _request(base, points, alternatives):
    coord = ";".join(f"{lon:.6f},{lat:.6f}" for lat, lon in points)
    url = f"{base}/route/v1/driving/{coord}"
    params = {
        "alternatives": "true" if alternatives else "false",
        "overview": "full",
        "geometries": "geojson",
        "annotations": "duration,distance",
        "steps": "false",
    }
    try:
        response = session.get(url, params=params, timeout=(5, 40))
        response.raise_for_status()
        payload = response.json()
    except (requests.RequestException, ValueError) as exc:
        raise UpstreamError("Routing service did not respond. Try again in a moment.") from exc
    if payload.get("code") == "NoRoute":
        raise ValueError("No driving route found between those places.")
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise UpstreamError("Routing service could not plan that trip.")
    return payload["routes"]
