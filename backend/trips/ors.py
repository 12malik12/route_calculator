"""OpenRouteService geocoding + routing helpers.

If an ORS_API_KEY is configured the real OpenRouteService API is used. If the
key is missing or a request fails, the module falls back to a small built-in
geocoder plus great-circle distance estimation so the app keeps working.
"""
from __future__ import annotations

import math
import re
from typing import List, Optional, Tuple

import requests
from django.conf import settings

ORS_BASE = "https://api.openrouteservice.org"
NOMINATIM_BASE = "https://nominatim.openstreetmap.org"
# Nominatim's usage policy requires a descriptive User-Agent identifying the app.
USER_AGENT = "TruckLogix/1.0 (HOS trip planner)"
METERS_PER_MILE = 1609.34
TIMEOUT = 20

# Ambiguous single-name cities: when the user types just the bare name with no
# state, these are the intended (most prominent) US match. Used to bias results
# so e.g. "Washington" resolves to Washington, DC rather than Washington State.
AMBIGUOUS_OVERRIDES = {
    "washington": (-77.0369, 38.9072),       # Washington, DC
    "washington dc": (-77.0369, 38.9072),
    "columbus": (-82.9988, 39.9612),         # Columbus, OH
    "springfield": (-89.6501, 39.7817),      # Springfield, IL
    "portland": (-122.6765, 45.5231),        # Portland, OR
    "kansas city": (-94.5786, 39.0997),      # Kansas City, MO
    "albany": (-73.7562, 42.6526),           # Albany, NY
    "richmond": (-77.4360, 37.5407),         # Richmond, VA
    "jacksonville": (-81.6557, 30.3322),     # Jacksonville, FL
    "aurora": (-104.8319, 39.7294),          # Aurora, CO
    "charleston": (-79.9311, 32.7765),       # Charleston, SC
    "manchester": (-71.4548, 42.9956),       # Manchester, NH
    "salem": (-123.0351, 44.9429),           # Salem, OR
}

# Offline geocoder used as a last-resort fallback (lon, lat). Includes the
# commonly requested / ambiguous cities so the app stays usable with no network.
FALLBACK_CITIES = {
    "chicago": (-87.6298, 41.8781),
    "memphis": (-90.0490, 35.1495),
    "jacksonville": (-81.6557, 30.3322),
    "nashville": (-86.7816, 36.1627),
    "atlanta": (-84.3880, 33.7490),
    "dallas": (-96.7970, 32.7767),
    "houston": (-95.3698, 29.7604),
    "new york": (-74.0060, 40.7128),
    "los angeles": (-118.2437, 34.0522),
    "denver": (-104.9903, 39.7392),
    "kansas city": (-94.5786, 39.0997),
    "st louis": (-90.1994, 38.6270),
    "saint louis": (-90.1994, 38.6270),
    "indianapolis": (-86.1581, 39.7684),
    "louisville": (-85.7585, 38.2527),
    "birmingham": (-86.8025, 33.5186),
    "phoenix": (-112.0740, 33.4484),
    "seattle": (-122.3321, 47.6062),
    "miami": (-80.1918, 25.7617),
    "orlando": (-81.3792, 28.5383),
    # Cities reported as failing + other common metros.
    "washington": (-77.0369, 38.9072),
    "washington dc": (-77.0369, 38.9072),
    "atlantic city": (-74.4229, 39.3643),
    "philadelphia": (-75.1652, 39.9526),
    "baltimore": (-76.6122, 39.2904),
    "boston": (-71.0589, 42.3601),
    "pittsburgh": (-79.9959, 40.4406),
    "cleveland": (-81.6944, 41.4993),
    "columbus": (-82.9988, 39.9612),
    "detroit": (-83.0458, 42.3314),
    "minneapolis": (-93.2650, 44.9778),
    "san francisco": (-122.4194, 37.7749),
    "san diego": (-117.1611, 32.7157),
    "las vegas": (-115.1398, 36.1699),
    "salt lake city": (-111.8910, 40.7608),
    "portland": (-122.6765, 45.5231),
    "san antonio": (-98.4936, 29.4241),
    "austin": (-97.7431, 30.2672),
    "charlotte": (-80.8431, 35.2271),
    "richmond": (-77.4360, 37.5407),
    "oklahoma city": (-97.5164, 35.4676),
    "albuquerque": (-106.6504, 35.0844),
    "omaha": (-95.9345, 41.2565),
    "milwaukee": (-87.9065, 43.0389),
    "cincinnati": (-84.5120, 39.1031),
    "sacramento": (-121.4944, 38.5816),
    "newark": (-74.1724, 40.7357),
    "buffalo": (-78.8784, 42.8864),
    "norfolk": (-76.2859, 36.8508),
    "raleigh": (-78.6382, 35.7796),
    "tampa": (-82.4572, 27.9506),
}


class GeocodeError(Exception):
    pass


def _normalize(address: str) -> str:
    """Lowercase, trim, drop punctuation, collapse whitespace for lookups."""
    text = address.strip().lower()
    text = re.sub(r"[.,]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _haversine_miles(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    """Great-circle distance in miles between two (lon, lat) points."""
    lon1, lat1 = a
    lon2, lat2 = b
    r = 3958.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    h = math.sin(dlat / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


def _fallback_geocode(address: str) -> Tuple[float, float]:
    key = _normalize(address)
    # Exact match first (handles "washington" -> DC, not a substring of another).
    if key in FALLBACK_CITIES:
        return FALLBACK_CITIES[key]
    # Strip a trailing state token (e.g. "philadelphia pa") and retry exact.
    stripped = re.sub(r"\s+[a-z]{2}$", "", key).strip()
    if stripped in FALLBACK_CITIES:
        return FALLBACK_CITIES[stripped]
    # Substring match as a looser fallback (longest city name wins).
    for city in sorted(FALLBACK_CITIES, key=len, reverse=True):
        if city in key:
            return FALLBACK_CITIES[city]
    raise GeocodeError(
        f"'{address}' isn't a valid location. Please enter a valid US city and "
        f"state, for example 'Philadelphia, PA'."
    )


# Approximate geographic centroids (lon, lat) of US states + DC, used to label
# a coordinate with its nearest state when reverse geocoding is unavailable.
STATE_CENTROIDS = {
    "AL": (-86.79, 32.81), "AK": (-152.40, 61.37), "AZ": (-111.43, 33.73),
    "AR": (-92.37, 34.97), "CA": (-119.68, 36.12), "CO": (-105.31, 39.06),
    "CT": (-72.76, 41.60), "DE": (-75.51, 39.32), "DC": (-77.03, 38.90),
    "FL": (-81.69, 27.77), "GA": (-83.64, 33.04), "HI": (-157.50, 21.09),
    "ID": (-114.48, 44.24), "IL": (-88.99, 40.35), "IN": (-86.26, 39.85),
    "IA": (-93.21, 42.01), "KS": (-96.73, 38.53), "KY": (-84.67, 37.67),
    "LA": (-91.87, 31.17), "ME": (-69.38, 44.69), "MD": (-76.80, 39.06),
    "MA": (-71.53, 42.23), "MI": (-84.54, 43.33), "MN": (-93.90, 45.69),
    "MS": (-89.68, 32.74), "MO": (-92.29, 38.46), "MT": (-110.45, 46.92),
    "NE": (-98.27, 41.13), "NV": (-117.06, 38.31), "NH": (-71.56, 43.45),
    "NJ": (-74.52, 40.30), "NM": (-106.25, 34.84), "NY": (-74.95, 42.17),
    "NC": (-79.81, 35.63), "ND": (-99.78, 47.53), "OH": (-82.76, 40.39),
    "OK": (-96.93, 35.57), "OR": (-122.07, 44.57), "PA": (-77.26, 40.59),
    "RI": (-71.51, 41.68), "SC": (-80.95, 33.86), "SD": (-99.44, 44.30),
    "TN": (-86.69, 35.75), "TX": (-99.34, 31.05), "UT": (-111.86, 40.15),
    "VT": (-72.71, 44.05), "VA": (-78.17, 37.77), "WA": (-121.49, 47.40),
    "WV": (-80.95, 38.49), "WI": (-89.62, 44.27), "WY": (-107.30, 42.76),
}


def _nearest_state(lon: float, lat: float) -> str:
    """Return the 2-letter abbreviation of the state nearest to (lon, lat)."""
    best, best_dist = "", float("inf")
    for abbr, c in STATE_CENTROIDS.items():
        d = _haversine_miles((lon, lat), c)
        if d < best_dist:
            best, best_dist = abbr, d
    return best


def reverse_geocode(lon: float, lat: float) -> str:
    """Convert (lon, lat) to a readable 'City, ST' label.

    Uses the OpenRouteService reverse-geocode API when an ORS_API_KEY is set.
    On any failure, falls back to 'En Route, ST' using the nearest state so the
    log sheets never show raw coordinates.
    """
    api_key = settings.ORS_API_KEY
    if api_key:
        try:
            resp = requests.get(
                f"{ORS_BASE}/geocode/reverse",
                params={
                    "api_key": api_key,
                    "point.lon": lon,
                    "point.lat": lat,
                    "boundary.country": "US",
                    "size": 1,
                },
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            features = resp.json().get("features") or []
            if features:
                props = features[0].get("properties", {})
                city = (
                    props.get("locality")
                    or props.get("localadmin")
                    or props.get("county")
                    or props.get("region")
                )
                state = props.get("region_a") or props.get("region")
                if city and state:
                    return f"{city}, {state}"
                if city:
                    return city
        except (requests.RequestException, KeyError, ValueError):
            pass
    return f"En Route, {_nearest_state(lon, lat)}"


# Bounding box for the contiguous US + AK/HI buffer (lon/lat) used to reject
# stray non-US matches that slip past country filtering.
US_BBOX = (-179.9, 18.0, -66.0, 72.0)  # (min_lon, min_lat, max_lon, max_lat)


def _in_us(lon: float, lat: float) -> bool:
    min_lon, min_lat, max_lon, max_lat = US_BBOX
    return min_lon <= lon <= max_lon and min_lat <= lat <= max_lat


def _has_state_context(address: str) -> bool:
    """True if the address appears to include a state (abbrev or full name)."""
    key = _normalize(address)
    tokens = key.split()
    if tokens and tokens[-1] in {s.lower() for s in STATE_CENTROIDS}:
        return True
    state_names = {
        "alabama", "alaska", "arizona", "arkansas", "california", "colorado",
        "connecticut", "delaware", "florida", "georgia", "hawaii", "idaho",
        "illinois", "indiana", "iowa", "kansas", "kentucky", "louisiana",
        "maine", "maryland", "massachusetts", "michigan", "minnesota",
        "mississippi", "missouri", "montana", "nebraska", "nevada",
        "new hampshire", "new jersey", "new mexico", "new york",
        "north carolina", "north dakota", "ohio", "oklahoma", "oregon",
        "pennsylvania", "rhode island", "south carolina", "south dakota",
        "tennessee", "texas", "utah", "vermont", "virginia", "washington",
        "west virginia", "wisconsin", "wyoming",
        "district of columbia", "dc",
    }
    return any(name in key for name in state_names)


def _geocode_ors(address: str, api_key: str) -> Optional[Tuple[float, float]]:
    resp = requests.get(
        f"{ORS_BASE}/geocode/search",
        params={
            "api_key": api_key,
            "text": address,
            "boundary.country": "US",  # restrict to United States
            "size": 1,
        },
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    features = resp.json().get("features") or []
    if features:
        lon, lat = features[0]["geometry"]["coordinates"]
        if _in_us(lon, lat):
            return (lon, lat)
    return None


def _geocode_nominatim(address: str) -> Optional[Tuple[float, float]]:
    """Keyless general-purpose US geocoder (OpenStreetMap Nominatim)."""
    resp = requests.get(
        f"{NOMINATIM_BASE}/search",
        params={
            "q": address,
            "format": "json",
            "countrycodes": "us",   # restrict to United States
            "limit": 1,
            "addressdetails": 0,
        },
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    results = resp.json()
    if results:
        lon = float(results[0]["lon"])
        lat = float(results[0]["lat"])
        if _in_us(lon, lat):
            return (lon, lat)
    return None


def geocode(address: str) -> Tuple[float, float]:
    """Return (lon, lat) for a US address string.

    Resolution order:
      1. ORS geocoder (US-restricted) when an API key is configured.
      2. Keyless OpenStreetMap Nominatim (US-restricted).
      3. Ambiguous-name override table (for bare single-name cities).
      4. Offline fallback table.
    Raises GeocodeError with a field-friendly message if nothing resolves.
    """
    # For bare, ambiguous single-name inputs, prefer the curated override so the
    # most prominent US match wins (e.g. "Washington" -> DC) instead of an API's
    # arbitrary top hit. If the user supplied state context, trust the API.
    key = _normalize(address)
    if not _has_state_context(address) and key in AMBIGUOUS_OVERRIDES:
        return AMBIGUOUS_OVERRIDES[key]

    api_key = settings.ORS_API_KEY
    if api_key:
        try:
            result = _geocode_ors(address, api_key)
            if result:
                return result
        except (requests.RequestException, KeyError, ValueError):
            pass

    try:
        result = _geocode_nominatim(address)
        if result:
            return result
    except (requests.RequestException, KeyError, ValueError):
        pass

    return _fallback_geocode(address)


def _interpolate(points: List[Tuple[float, float]], total_miles: float, frac: int = 60):
    """Build a simple polyline of `frac` points between waypoints."""
    line: List[List[float]] = []
    for i in range(len(points) - 1):
        a, b = points[i], points[i + 1]
        for s in range(frac):
            t = s / frac
            line.append([a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t])
    line.append([points[-1][0], points[-1][1]])
    return line


def directions(waypoints: List[Tuple[float, float]]) -> dict:
    """Return road distances + geometry for an ordered list of (lon, lat).

    Result: {"legs_miles": [..], "total_miles": float, "geometry": [[lon,lat]..]}
    geometry coordinates are returned in [lon, lat] order (GeoJSON).
    """
    api_key = settings.ORS_API_KEY
    if api_key:
        try:
            resp = requests.post(
                f"{ORS_BASE}/v2/directions/driving-hgv/geojson",
                headers={
                    "Authorization": api_key,
                    "Content-Type": "application/json",
                },
                json={"coordinates": [list(w) for w in waypoints]},
                timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            feat = data["features"][0]
            geometry = feat["geometry"]["coordinates"]
            segments = feat["properties"]["segments"]
            legs = [seg["distance"] / METERS_PER_MILE for seg in segments]
            return {
                "legs_miles": legs,
                "total_miles": sum(legs),
                "geometry": geometry,
            }
        except (requests.RequestException, KeyError, ValueError, IndexError):
            pass

    # Keyless fallback: the public OSRM demo server returns real road-following
    # geometry, so the route traces actual roads instead of straight lines.
    try:
        return _osrm_directions(waypoints)
    except (requests.RequestException, KeyError, ValueError, IndexError):
        pass

    # Last resort: straight-line distance scaled by a road-winding factor of 1.2.
    legs = []
    for i in range(len(waypoints) - 1):
        legs.append(_haversine_miles(waypoints[i], waypoints[i + 1]) * 1.2)
    return {
        "legs_miles": legs,
        "total_miles": sum(legs),
        "geometry": _interpolate(waypoints, sum(legs)),
    }


def _osrm_directions(waypoints: List[Tuple[float, float]]) -> dict:
    """Road-following route from the public OSRM server (no API key required).

    Returns geometry as [lon, lat] pairs and per-leg distances in miles.
    """
    coord_str = ";".join(f"{lon},{lat}" for lon, lat in waypoints)
    resp = requests.get(
        f"https://router.project-osrm.org/route/v1/driving/{coord_str}",
        params={"overview": "full", "geometries": "geojson", "steps": "false"},
        timeout=TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    route = data["routes"][0]
    geometry = route["geometry"]["coordinates"]
    legs = [leg["distance"] / METERS_PER_MILE for leg in route["legs"]]
    return {
        "legs_miles": legs,
        "total_miles": sum(legs),
        "geometry": geometry,
    }


def point_at_mile(geometry: List[List[float]], target_mile: float) -> List[float]:
    """Interpolate a [lon, lat] coordinate along the polyline at target_mile."""
    if not geometry:
        return [0.0, 0.0]
    cumulative = 0.0
    for i in range(len(geometry) - 1):
        a = (geometry[i][0], geometry[i][1])
        b = (geometry[i + 1][0], geometry[i + 1][1])
        seg = _haversine_miles(a, b)
        if cumulative + seg >= target_mile and seg > 0:
            t = (target_mile - cumulative) / seg
            return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t]
        cumulative += seg
    return [geometry[-1][0], geometry[-1][1]]
