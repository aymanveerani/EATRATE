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
credential to actually fetch an image, so we never build a client-facing
URL straight to Google for it — that would leak the secret key to every
visitor's browser. Instead we store just the photo's resource name here,
and GET /api/restaurants/:id/photo (server/app.py) fetches the actual
image bytes server-side (via fetch_photo_bytes below) and serves them from
our own domain, caching the result to disk so it's a one-time cost per
restaurant rather than a live Google call on every page view.
"""

import json
import math
import os
import urllib.request
from datetime import datetime, timedelta

GOOGLE_PLACES_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
SEARCH_URL = "https://places.googleapis.com/v1/places:searchNearby"
PHOTO_MEDIA_URL = "https://places.googleapis.com/v1/{photo_name}/media"
PHOTO_MAX_WIDTH_PX = 400
MAX_RESULTS = 20  # Google's per-request cap for Nearby Search (New)
MAX_RADIUS_METERS = 50000  # Google's hard limit
REQUEST_TIMEOUT = 10
CACHE_TTL_DAYS = 7
CACHE_SNAP_DEGREES = 0.03  # ~3.3km — see server/osm.py for why this exists
QUERY_VERSION = 2  # bumped: now also fetches places.photos

FIELD_MASK = (
    "places.id,places.displayName,places.location,places.formattedAddress,"
    "places.primaryTypeDisplayName,places.photos"
)


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
        photos = p.get("photos") or []
        # Not truncated like the other fields below — this is an opaque
        # resource token, not display text, and truncating it corrupts it
        # into an invalid reference rather than a shorter-but-valid one.
        photo_name = (photos[0].get("name") or "") if photos else ""
        places.append(
            {
                "google_place_id": p["id"],
                "name": name.strip()[:200],
                "cuisine": (p.get("primaryTypeDisplayName") or {}).get("text", "")[:100],
                "address": (p.get("formattedAddress") or "")[:300],
                "lat": loc["latitude"],
                "lng": loc["longitude"],
                "photo_name": photo_name,
            }
        )
    return places


def fetch_photo_bytes(photo_name):
    """Fetches actual image bytes for a stored photo resource name (e.g.
    "places/ABC123/photos/XYZ") server-side, using the API key as a request
    credential the client never sees. Returns (content_type, bytes).
    Raises GooglePlacesError on any failure."""
    if not GOOGLE_PLACES_API_KEY:
        raise GooglePlacesError("No Google Places API key configured.")

    url = f"{PHOTO_MEDIA_URL.format(photo_name=photo_name)}?maxWidthPx={PHOTO_MAX_WIDTH_PX}&skipHttpRedirect=true"
    req = urllib.request.Request(url, headers={"X-Goog-Api-Key": GOOGLE_PLACES_API_KEY})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            meta = json.loads(resp.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise GooglePlacesError(f"Couldn't reach Google Places photo endpoint: {e}")

    photo_uri = meta.get("photoUri")
    if not photo_uri:
        raise GooglePlacesError("No photoUri in Google Places photo response.")

    try:
        with urllib.request.urlopen(photo_uri, timeout=REQUEST_TIMEOUT) as resp:
            content_type = resp.headers.get("Content-Type", "image/jpeg")
            data = resp.read()
    except OSError as e:
        raise GooglePlacesError(f"Couldn't download Google Places photo: {e}")

    return content_type, data


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
                "INSERT INTO restaurants (name, cuisine, address, lat, lng, google_place_id, source, google_photo_name) "
                "VALUES (?, ?, ?, ?, ?, ?, 'google', ?) "
                "ON CONFLICT(google_place_id) WHERE google_place_id IS NOT NULL DO UPDATE SET "
                "name = excluded.name, cuisine = excluded.cuisine, address = excluded.address, "
                "lat = excluded.lat, lng = excluded.lng, "
                "google_photo_name = CASE WHEN excluded.google_photo_name != '' THEN excluded.google_photo_name ELSE restaurants.google_photo_name END",
                (
                    place["name"],
                    place["cuisine"],
                    place["address"],
                    place["lat"],
                    place["lng"],
                    place["google_place_id"],
                    place["photo_name"],
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
