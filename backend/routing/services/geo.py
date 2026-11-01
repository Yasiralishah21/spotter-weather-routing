import math

EARTH_MILES = 3958.7613


def haversine_miles(a, b):
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 2 * EARTH_MILES * math.asin(math.sqrt(h))


def bearing_degrees(a, b):
    lat1, lon1 = math.radians(a[0]), math.radians(a[1])
    lat2, lon2 = math.radians(b[0]), math.radians(b[1])
    dlon = lon2 - lon1
    x = math.sin(dlon) * math.cos(lat2)
    y = math.cos(lat1) * math.sin(lat2) - math.sin(lat1) * math.cos(lat2) * math.cos(dlon)
    return (math.degrees(math.atan2(x, y)) + 360) % 360


def offset_point(lat, lon, bearing_deg, miles):
    angular = miles / EARTH_MILES
    br = math.radians(bearing_deg)
    lat1 = math.radians(lat)
    lon1 = math.radians(lon)
    lat2 = math.asin(
        math.sin(lat1) * math.cos(angular) + math.cos(lat1) * math.sin(angular) * math.cos(br)
    )
    lon2 = lon1 + math.atan2(
        math.sin(br) * math.sin(angular) * math.cos(lat1),
        math.cos(angular) - math.sin(lat1) * math.sin(lat2),
    )
    return math.degrees(lat2), (math.degrees(lon2) + 540) % 360 - 180


def sample_miles(total_miles, interval):
    """Mile marks at 0, every interval, and the destination."""
    if total_miles <= 0:
        return [0.0]
    marks = [0.0]
    mile = float(interval)
    while mile < total_miles - 0.05:
        marks.append(mile)
        mile += interval
    if total_miles - marks[-1] > 0.05:
        marks.append(total_miles)
    return marks


def interpolate_profile(profile, mile):
    """profile items are (mile, seconds, lat, lon)."""
    if not profile:
        raise ValueError("Route geometry is empty.")
    if mile <= profile[0][0]:
        return profile[0][2], profile[0][3], profile[0][1]
    if mile >= profile[-1][0]:
        return profile[-1][2], profile[-1][3], profile[-1][1]
    for left, right in zip(profile, profile[1:]):
        if left[0] <= mile <= right[0]:
            span = right[0] - left[0]
            t = 0.0 if span == 0 else (mile - left[0]) / span
            lat = left[2] + (right[2] - left[2]) * t
            lon = left[3] + (right[3] - left[3]) * t
            seconds = left[1] + (right[1] - left[1]) * t
            return lat, lon, seconds
    last = profile[-1]
    return last[2], last[3], last[1]


def local_bearing(profile, mile):
    ahead = min(profile[-1][0], mile + 1.0)
    behind = max(0.0, mile - 1.0)
    lat1, lon1, _ = interpolate_profile(profile, behind)
    lat2, lon2, _ = interpolate_profile(profile, ahead)
    if haversine_miles((lat1, lon1), (lat2, lon2)) < 0.01:
        return 0.0
    return bearing_degrees((lat1, lon1), (lat2, lon2))


def _to_xy(lat, lon, lat0):
    x = math.radians(lon) * EARTH_MILES * math.cos(math.radians(lat0))
    y = math.radians(lat) * EARTH_MILES
    return x, y


def distance_to_profile_miles(lat, lon, profile):
    best = float("inf")
    lat0 = lat
    px, py = _to_xy(lat, lon, lat0)
    step = max(1, len(profile) // 350)
    thinned = profile[::step]
    if thinned[-1] is not profile[-1]:
        thinned = [*thinned, profile[-1]]
    for left, right in zip(thinned, thinned[1:]):
        ax, ay = _to_xy(left[2], left[3], lat0)
        bx, by = _to_xy(right[2], right[3], lat0)
        dx, dy = bx - ax, by - ay
        denom = dx * dx + dy * dy
        if denom == 0:
            dist = math.hypot(px - ax, py - ay)
        else:
            t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / denom))
            dist = math.hypot(px - (ax + t * dx), py - (ay + t * dy))
        if dist < best:
            best = dist
    return best


def profiles_overlap(left, right, threshold_miles=2.0, share=0.85):
    total = left[-1][0]
    if total <= 0 or right[-1][0] <= 0:
        return False
    samples = 12
    close = 0
    for i in range(samples):
        mile = total * i / (samples - 1)
        lat, lon, _ = interpolate_profile(left, mile)
        if distance_to_profile_miles(lat, lon, right) <= threshold_miles:
            close += 1
    return close / samples >= share


def simplify_latlon(points, max_points=1200):
    if len(points) <= max_points:
        return points
    stride = math.ceil(len(points) / max_points)
    slim = points[::stride]
    if slim[-1] != points[-1]:
        slim.append(points[-1])
    return slim
