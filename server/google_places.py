"""
Live restaurant data from the Google Places API (New) — the most complete
US business listings among the sources this app supports, but the only one
that requires a Google Cloud project with billing enabled (a monthly free
credit covers light usage at pilot scale, then it's pay-per-request).

Tried first when GOOGLE_PLACES_API_KEY is set, falling back to Yelp
(server/yelp.py) and then OpenStreetMap (server/osm.py) if it's not
configured or a call fails — the app works with any subset of these three
turned on.

Google's Places photo media endpoint requires the API key as a request
credential to actually fetch an image, so unlike Yelp's plain image_url we
deliberately don't build a client-facing photo URL here — putting one in an
<img src> would leak the secret key to every visitor's browser. Google-
sourced restaurants just fall back to the favicon/cuisine-icon chain
client-side like any place with no external photo.
"""

import json
import math
import os
import urllib.request
from datetime import datetime, timedelta

GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
MAX_RESULTS = 20  # Google's per-request cap for Nearby Search (New)
MAX_RADIUS_METERS = 50000  # Google's hard limit
REQUEST_TIMEOUT = 10
CACHE_TTL_DAYS = 7
CACHE_SNAP_DEGREES = 0.03  # ~3.3km — see server/osm.py for why this exists
QUERY_VERSION = 1

FIELD_MASK = "places.id,places.displayName,places.location,places.formattedAddress,places.primaryTypeDisplayName"


class GooglePlacesError(Exception):
    pass


def _snap_key(lat, lng):
    # Prefixed and independently versioned so this never collides with
    # Yelp's or OSM's cache keys in the shared map_cache table.
    return f"google:{QUERY_VERSION}:{round(lat / CACHE_SNAP_DEGREES)}:{round(lng / CACHE_SNAP_DEGREES)}"


def _fetch_from_google(lat, lng, radius_m):
    body = json.dumps(
        {
            "includedTypes": ["restaurant"],
            "maxResultCount": MAX_RESULTS,
            "locationRestriction": {
                "circle": {
                    "center": {"latitude": lat, "longitude": lng},
                    "radius": min(radius_m, MAX_RADIUS_METERS),
                }
            },
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        SEARCH_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Goog-Api-Key": GOOGLE_PLACES_API_KEY,
            "X-Goog-FieldMask": FIELD_MASK,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        # Covers urllib.error.HTTPError (bad/unbilled key, quota exceeded),
        # URLError, socket timeouts, and malformed responses — any of these
        # should trigger the Yelp/OSM fallback, not crash the request.
        raise GooglePlacesError(f"Couldn't reach Google Places: {e}")

    places = []
    for p in data.get("places", []):
        name = (p.get("displayName") or {}).get("text")
        loc = p.get("location") or {}
        if not name or loc.get("latitude") is None or loc.get("longitude") is None:
            continue
        places.append(
            {
                "google_place_id": p["id"],
                "name": name.strip()[:200],
                "cuisine": (p.get("primaryTypeDisplayName") or {}).get("text", "")[:100],
                "address": (p.get("formattedAddress") or "")[:300],
                "lat": loc["latitude"],
                "lng": loc["longitude"],
            }
        )
    return places


def sync_nearby(conn, lat, lng, radius_km):
    """Ensures Google Places results for this area are fetched (cached by a
    coarse location snap) and returns every Google-sourced restaurant we
    have within the radius. Raises GooglePlacesError if no key is
    configured or the call fails — callers should fall back to
    server.yelp.sync_nearby or server.osm.sync_bbox in that case."""
    if not GOOGLE_PLACES_API_KEY:
        raise GooglePlacesError("No Google Places API key configured.")

    key = _snap_key(lat, lng)
    cutoff = (datetime.utcnow() - timedelta(days=CACHE_TTL_DAYS)).isoformat()
    cached = conn.execute("SELECT fetched_at FROM map_cache WHERE cell_key = ?", (key,)).fetchone()

    if not cached or cached["fetched_at"] <= cutoff:
        places = _fetch_from_google(lat, lng, radius_km * 1000)
        for place in places:
            conn.execute(
                "INSERT INTO restaurants (name, cuisine, address, lat, lng, google_place_id, source) "
                "VALUES (?, ?, ?, ?, ?, ?, 'google') "
                "ON CONFLICT(google_place_id) WHERE google_place_id IS NOT NULL DO UPDATE SET "
                "name = excluded.name, cuisine = excluded.cuisine, address = excluded.address, "
                "lat = excluded.lat, lng = excluded.lng",
                (
                    place["name"],
                    place["cuisine"],
                    place["address"],
                    place["lat"],
                    place["lng"],
                    place["google_place_id"],
                ),
            )
        conn.execute(
            "INSERT INTO map_cache (cell_key, fetched_at) VALUES (?, datetime('now')) "
            "ON CONFLICT(cell_key) DO UPDATE SET fetched_at = datetime('now')",
            (key,),
        )
        conn.commit()

    lat_delta = radius_km / 111.0
    lng_delta = radius_km / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    return conn.execute(
        """
        SELECT * FROM restaurants
        WHERE lat IS NOT NULL AND lng IS NOT NULL
          AND lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?
        LIMIT 300
        """,
        (lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta),
    ).fetchall()
