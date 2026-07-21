"""
Live restaurant data from the Yelp Fusion API — free tier, no billing
required (unlike Google Places), and restaurant-specific data (real names,
categories, and photos) rather than general-purpose map POIs.

Used as the primary "nearby restaurants" source when YELP_API_KEY is set
(see README for how to get one). Falls back to OpenStreetMap
(server/osm.py) if no key is configured, or if a Yelp call fails, since
OSM needs no API key or account at all.
"""

import json
import math
import os
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

YELP_API_KEY = os.environ.get("YELP_API_KEY", "")
YELP_SEARCH_URL = "https://api.yelp.com/v3/businesses/search"
MAX_RESULTS = 50  # Yelp's per-request cap
MAX_RADIUS_METERS = 40000  # Yelp's hard limit (~24.8mi), well over our 5mi search
REQUEST_TIMEOUT = 10
CACHE_TTL_DAYS = 7
CACHE_SNAP_DEGREES = 0.03  # ~3.3km — see server/osm.py for why this exists
QUERY_VERSION = 2  # bumped: now excludes grocery/wholesale category aliases

# The "food" category we search under is broad enough to include grocery
# and wholesale-club listings alongside actual restaurants — Yelp's search
# doesn't support excluding categories server-side, so filter afterward by
# category alias instead.
EXCLUDED_CATEGORY_ALIASES = {"grocery", "convenience", "wholesale_stores", "discountstore"}


class YelpError(Exception):
    pass


def _snap_key(lat, lng):
    # Prefixed and independently versioned from OSM's cache keys so the two
    # sources never collide or invalidate each other in the shared map_cache
    # table.
    return f"yelp:{QUERY_VERSION}:{round(lat / CACHE_SNAP_DEGREES)}:{round(lng / CACHE_SNAP_DEGREES)}"


def _fetch_from_yelp(lat, lng, radius_m):
    params = {
        "latitude": lat,
        "longitude": lng,
        "radius": min(int(radius_m), MAX_RADIUS_METERS),
        "categories": "restaurants,food",
        "limit": MAX_RESULTS,
        "sort_by": "distance",
    }
    url = f"{YELP_SEARCH_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {YELP_API_KEY}"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        # Covers urllib.error.URLError/HTTPError (bad key, rate limit, etc),
        # socket timeouts, and malformed responses — any of these should
        # just trigger the OSM fallback, not crash the request.
        raise YelpError(f"Couldn't reach Yelp: {e}")

    places = []
    for biz in body.get("businesses", []):
        if biz.get("is_closed") or not biz.get("name"):
            continue
        categories = biz.get("categories", [])
        if any(c.get("alias") in EXCLUDED_CATEGORY_ALIASES for c in categories):
            continue
        coords = biz.get("coordinates") or {}
        if coords.get("latitude") is None or coords.get("longitude") is None:
            continue
        loc = biz.get("location") or {}
        address = ", ".join(b for b in [loc.get("address1"), loc.get("city")] if b)
        cuisine = ", ".join(c["title"] for c in biz.get("categories", []))[:100]
        places.append(
            {
                "yelp_id": biz["id"],
                "name": biz["name"].strip()[:200],
                "cuisine": cuisine,
                "address": address[:300],
                "lat": coords["latitude"],
                "lng": coords["longitude"],
                "image": (biz.get("image_url") or "")[:500],
            }
        )
    return places


def sync_nearby(conn, lat, lng, radius_km):
    """Ensures Yelp results for this area are fetched (cached by a coarse
    location snap, like OSM's grid) and returns every Yelp-sourced
    restaurant we have within the radius. Raises YelpError if no key is
    configured or the call fails — callers should fall back to
    server.osm.sync_bbox in that case."""
    if not YELP_API_KEY:
        raise YelpError("No Yelp API key configured.")

    key = _snap_key(lat, lng)
    cutoff = (datetime.utcnow() - timedelta(days=CACHE_TTL_DAYS)).isoformat()
    cached = conn.execute("SELECT fetched_at FROM map_cache WHERE cell_key = ?", (key,)).fetchone()

    if not cached or cached["fetched_at"] <= cutoff:
        places = _fetch_from_yelp(lat, lng, radius_km * 1000)
        for place in places:
            conn.execute(
                "INSERT INTO restaurants (name, cuisine, address, lat, lng, yelp_id, source, osm_image) "
                "VALUES (?, ?, ?, ?, ?, ?, 'yelp', ?) "
                "ON CONFLICT(yelp_id) WHERE yelp_id IS NOT NULL DO UPDATE SET "
                "name = excluded.name, cuisine = excluded.cuisine, address = excluded.address, "
                "lat = excluded.lat, lng = excluded.lng, "
                "osm_image = CASE WHEN excluded.osm_image != '' THEN excluded.osm_image ELSE restaurants.osm_image END",
                (
                    place["name"],
                    place["cuisine"],
                    place["address"],
                    place["lat"],
                    place["lng"],
                    place["yelp_id"],
                    place["image"],
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
