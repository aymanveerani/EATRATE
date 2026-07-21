"""
Live restaurant data from OpenStreetMap via the public Overpass API — free,
no account or API key needed, unlike Google Places / Yelp.

The "nearby restaurants" feature searches a fixed 5-mile radius around the
user, so this fetches that whole area in a single Overpass query per
request rather than tiling it into many small grid cells — there's no
pannable map anymore that would benefit from incremental tile caching, and
tiling meant a full radius took many repeated page loads to fully populate
(only a handful of new tiles fetched per request). A single query also
means results appear in one round-trip.

Every fetched place becomes a real row in the `restaurants` table (matched
on OSM's node id so re-fetching doesn't duplicate it), so it's the same
restaurant entity users can post about, rate, and businesses can claim.

Repeat requests from users in roughly the same area reuse a cached result
(keyed by a coarse rounding of the search center) for CACHE_TTL_DAYS,
instead of hitting Overpass on every single page load.
"""

import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
MAX_RESULTS = 300
CACHE_TTL_DAYS = 7
CACHE_SNAP_DEGREES = 0.03  # ~3.3km — search centers within this snap grid
# share a cached fetch instead of re-querying Overpass; small enough that a
# 5-mile-radius search from the snapped center still covers the real request
MAX_BBOX_DEGREES = 0.5  # ~55km — sanity cap against absurdly large requests
REQUEST_TIMEOUT = 15  # a single query over a ~16km bbox takes longer than a
# small tile did; Overpass is a shared free public instance, so fail fast
# and let the next request retry rather than hang the page indefinitely

# OSM tags a real place-you'd-eat-at can carry a place under. Restaurants
# aren't only amenity=restaurant — bars/pubs that serve food, bakeries,
# delis, and ice cream shops are commonly tagged under `shop` instead of
# `amenity`, and were missing places from results entirely.
# amenity=food_court is ambiguous — it's just as often a mall or big-box
# store's shared food court (Costco, Sam's Club) as an actual dining
# destination, so it's deliberately not included here.
AMENITY_TAGS = ("restaurant", "cafe", "fast_food", "bar", "pub", "ice_cream", "biergarten")
SHOP_TAGS = ("bakery", "deli", "confectionery")

# Bump this whenever AMENITY_TAGS/SHOP_TAGS change so previously-cached
# areas re-fetch with the new query instead of serving a stale, narrower
# result set for up to CACHE_TTL_DAYS.
QUERY_VERSION = 3


class OsmError(Exception):
    pass


def _snap_key(lat, lng):
    return f"{QUERY_VERSION}:{round(lat / CACHE_SNAP_DEGREES)}:{round(lng / CACHE_SNAP_DEGREES)}"


def _fetch_bbox_from_overpass(min_lat, min_lng, max_lat, max_lng):
    bbox = f"({min_lat},{min_lng},{max_lat},{max_lng})"
    clauses = "\n".join(
        [f'  node["amenity"="{a}"]{bbox};' for a in AMENITY_TAGS]
        + [f'  node["shop"="{s}"]{bbox};' for s in SHOP_TAGS]
    )
    query = f"[out:json][timeout:{REQUEST_TIMEOUT}];\n(\n{clauses}\n);\nout body {MAX_RESULTS};"

    data = urllib.parse.urlencode({"data": query}).encode("utf-8")
    req = urllib.request.Request(
        OVERPASS_URL,
        data=data,
        headers={"User-Agent": "EatRate/1.0 (pilot food-sharing app; contact via GitHub repo)"},
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        # Covers urllib.error.URLError, socket.timeout, and TimeoutError —
        # all OSError subclasses, but socket.timeout isn't unified with
        # TimeoutError until Python 3.10, so catch the common base instead.
        raise OsmError(f"Couldn't reach OpenStreetMap: {e}")

    places = []
    for el in body.get("elements", []):
        tags = el.get("tags", {})
        name = tags.get("name")
        if not name or "lat" not in el or "lon" not in el:
            continue
        address_bits = [tags.get("addr:housenumber"), tags.get("addr:street")]
        address = " ".join(b for b in address_bits if b)
        if tags.get("addr:city"):
            address = f"{address}, {tags['addr:city']}" if address else tags["addr:city"]

        website = tags.get("website") or tags.get("contact:website") or ""
        domain = ""
        if website:
            parsed = urllib.parse.urlparse(website if "//" in website else f"//{website}")
            domain = (parsed.netloc or parsed.path).split("/")[0]
            if domain.startswith("www."):
                domain = domain[4:]
            domain = domain[:200]

        # A minority of OSM nodes carry a direct photo URL — a real picture
        # of the actual place when it's there, used as a photo fallback for
        # restaurants nobody has reviewed on EatRate yet.
        osm_image = (tags.get("image") or "")[:500]

        places.append(
            {
                "osm_id": f"node/{el['id']}",
                "name": name.strip()[:200],
                "cuisine": (tags.get("cuisine") or "").replace("_", " ")[:100],
                "address": address[:300],
                "lat": el["lat"],
                "lng": el["lon"],
                "website_domain": domain,
                "osm_image": osm_image,
            }
        )
    return places


def sync_bbox(conn, min_lat, min_lng, max_lat, max_lng):
    """Ensures the given bbox's restaurants are fetched (via one Overpass
    call, reused across nearby requests within CACHE_TTL_DAYS) and returns
    every geolocated restaurant in our DB within it."""
    if max_lat <= min_lat or max_lng <= min_lng:
        raise OsmError("Invalid bounding box.")
    if (max_lat - min_lat) > MAX_BBOX_DEGREES or (max_lng - min_lng) > MAX_BBOX_DEGREES:
        raise OsmError("This area is too large to search at once.")

    center_lat = (min_lat + max_lat) / 2
    center_lng = (min_lng + max_lng) / 2
    key = _snap_key(center_lat, center_lng)

    cutoff = (datetime.utcnow() - timedelta(days=CACHE_TTL_DAYS)).isoformat()
    cached = conn.execute(
        "SELECT fetched_at FROM map_cache WHERE cell_key = ?", (key,)
    ).fetchone()

    if not cached or cached["fetched_at"] <= cutoff:
        try:
            places = _fetch_bbox_from_overpass(min_lat, min_lng, max_lat, max_lng)
        except OsmError:
            # Leave uncached so the next request retries; still serve
            # whatever's already in the DB for this area.
            places = None

        if places is not None:
            for place in places:
                conn.execute(
                    "INSERT OR IGNORE INTO restaurants "
                    "(name, cuisine, address, lat, lng, osm_id, source, website_domain, osm_image) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'osm', ?, ?)",
                    (
                        place["name"],
                        place["cuisine"],
                        place["address"],
                        place["lat"],
                        place["lng"],
                        place["osm_id"],
                        place["website_domain"],
                        place["osm_image"],
                    ),
                )
            conn.execute(
                "INSERT INTO map_cache (cell_key, fetched_at) VALUES (?, datetime('now')) "
                "ON CONFLICT(cell_key) DO UPDATE SET fetched_at = datetime('now')",
                (key,),
            )
            conn.commit()

    return conn.execute(
        """
        SELECT * FROM restaurants
        WHERE lat IS NOT NULL AND lng IS NOT NULL
          AND lat BETWEEN ? AND ? AND lng BETWEEN ? AND ?
        LIMIT 300
        """,
        (min_lat, max_lat, min_lng, max_lng),
    ).fetchall()
