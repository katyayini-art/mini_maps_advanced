"""Thin client for the HeiGIT OpenRouteService (directions) and Pelias (geocoding) APIs."""

from urllib.parse import urlencode
from xml.sax.saxutils import escape

import requests

GEOCODE_URL = "https://api.heigit.org/pelias/v1/search"
ROUTE_URL = "https://api.heigit.org/openrouteservice/v2/directions/{profile}/geojson"

PROFILES = {
    "Car": "driving-car",
    "Heavy vehicle": "driving-hgv",
    "Bike": "cycling-regular",
    "Walking": "foot-walking",
}

GOOGLE_MODES = {
    "driving-car": "driving",
    "driving-hgv": "driving",
    "cycling-regular": "bicycling",
    "foot-walking": "walking",
}


class ORSError(Exception):
    """Raised with a user-friendly message when an API call fails."""


def _headers(api_key):
    return {"Authorization": api_key, "Content-Type": "application/json"}


def _check(resp):
    if resp.ok:
        return
    if resp.status_code in (401, 403):
        raise ORSError("The API key was rejected. Check ORS_API_KEY in your .env file.")
    if resp.status_code == 429:
        raise ORSError("Rate limit reached (free plan). Wait a minute and try again.")
    try:
        detail = resp.json().get("error")
        if isinstance(detail, dict):
            detail = detail.get("message")
    except ValueError:
        detail = resp.text[:200]
    raise ORSError(f"Routing service error ({resp.status_code}): {detail}")


def geocode(api_key, text, size=5, country="IND"):
    """Return up to `size` matches: [{'label': str, 'coords': [lon, lat]}]."""
    params = {"text": text, "size": size}
    if country:
        params["boundary.country"] = country
    try:
        resp = requests.get(GEOCODE_URL, headers=_headers(api_key), params=params, timeout=30)
    except requests.RequestException as exc:
        raise ORSError(f"Network problem while searching places: {exc}") from exc
    _check(resp)
    matches = []
    for feature in resp.json().get("features", []):
        matches.append(
            {
                "label": feature.get("properties", {}).get("label", text),
                "coords": feature["geometry"]["coordinates"][:2],
            }
        )
    return matches


def directions(api_key, coords, profile="driving-car", preference="recommended",
               alternatives=False):
    """Return a list of GeoJSON route features for the given [lon, lat] points."""
    payload = {
        "coordinates": coords,
        "units": "km",
        "preference": preference,
        "instructions": True,
        "language": "en",
        "radiuses": [-1] * len(coords),  # snap to the nearest road, however far
    }
    if alternatives:
        payload["alternative_routes"] = {
            "target_count": 3,
            "weight_factor": 1.4,
            "share_factor": 0.6,
        }
    try:
        resp = requests.post(
            ROUTE_URL.format(profile=profile),
            headers=_headers(api_key),
            json=payload,
            timeout=60,
        )
    except requests.RequestException as exc:
        raise ORSError(f"Network problem while finding routes: {exc}") from exc
    _check(resp)
    features = resp.json().get("features", [])
    if not features:
        raise ORSError("No route found between these places.")
    return features


def google_maps_url(points, profile="driving-car"):
    """Link that opens the trip (origin, via-stops, destination) in Google Maps."""
    latlng = [f"{lat},{lon}" for lon, lat in points]
    params = {
        "api": 1,
        "origin": latlng[0],
        "destination": latlng[-1],
        "travelmode": GOOGLE_MODES.get(profile, "driving"),
    }
    if len(latlng) > 2:
        params["waypoints"] = "|".join(latlng[1:-1])
    return "https://www.google.com/maps/dir/?" + urlencode(params)


def to_gpx(feature, name):
    """Convert a route feature to GPX text (opens in Garmin, Strava, OsmAnd...)."""
    points = "\n".join(
        f'      <trkpt lat="{c[1]}" lon="{c[0]}"></trkpt>'
        for c in feature["geometry"]["coordinates"]
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<gpx version="1.1" creator="Mini Maps" xmlns="http://www.topografix.com/GPX/1/1">\n'
        f"  <trk>\n    <name>{escape(name)}</name>\n    <trkseg>\n{points}\n"
        "    </trkseg>\n  </trk>\n</gpx>\n"
    )
