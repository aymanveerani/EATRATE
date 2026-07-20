"""
Live restaurant data from OpenStreetMap via the public Overpass API — free,
no account or API key needed, unlike Google Places / Yelp.

There's no "download all restaurants in America" here: that's neither free
nor something Overpass's fair-use policy wants from any single client, and
loading millions of rows into a SQLite file isn't how map apps actually
work anyway. Instead, this fetches restaurants for the map viewport the user
is currently looking at (same approach Yelp/Google Maps use), grouped into
a coarse grid so repeated pans over the same area reuse cached results
instead of re-querying Overpass every time.

Every fetched place becomes a real row in the `restaurants` table (matched
on OSM's node id so re-fetching doesn't duplicate it), so it's the same
restaurant entity users can post about, rate, and businesses can claim.
"""

import json
import math
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
CELL_SIZE_DEGREES = 0.02  # ~2x2km grid cells — small enough that dense areas
# (e.g. Manhattan) don't make a single cell's Overpass query time out
MAX_CELLS_PER_REQUEST = 64  # caps a single viewport fetch to a ~16x16km area
MAX_RESULTS_PER_CELL = 200
CACHE_TTL_DAYS = 7
REQUEST_TIMEOUT = 8  # Overpass is a shared free public instance; fail fast
# and let the next request retry rather than let one dense cell hang the page
MAX_NEW_FETCHES_PER_REQUEST = 3  # bounds one HTTP response to ~24s worst
# case; any remaining uncached cells in the viewport get picked up by a
# subsequent request (the frontend polls again shortly after)
AMENITIES = ("restaurant", "cafe", "fast_food")


class OsmError(Exception):
    pass


def _cell_key(cell_y, cell_x):
    return f"{cell_y}:{cell_x}"


def _fetch_cell_from_overpass(min_lat, min_lng, max_lat, max_lng):
    clauses = "\n".join(
        f'  node["amenity"="{a}"]({min_lat},{min_lng},{max_lat},{max_lng});' for a in AMENITIES
    )
    query = f"[out:json][timeout:{REQUEST_TIMEOUT}];\n(\n{clauses}\n);\nout body {MAX_RESULTS_PER_CELL};"

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
        places.append(
            {
                "osm_id": f"node/{el['id']}",
                "name": name.strip()[:200],
                "cuisine": (tags.get("cuisine") or "").replace("_", " ")[:100],
                "address": address[:300],
                "lat": el["lat"],
                "lng": el["lon"],
            }
        )
    return places


def sync_bbox(conn, min_lat, min_lng, max_lat, max_lng):
    """Fetches any not-yet-cached grid cells touching this bbox from
    Overpass, upserts them into `restaurants`, and returns every geolocated
    restaurant in our DB within the bbox (cached ones included)."""
    if max_lat <= min_lat or max_lng <= min_lng:
        raise OsmError("Invalid bounding box.")

    y0, y1 = math.floor(min_lat / CELL_SIZE_DEGREES), math.floor(max_lat / CELL_SIZE_DEGREES)
    x0, x1 = math.floor(min_lng / CELL_SIZE_DEGREES), math.floor(max_lng / CELL_SIZE_DEGREES)
    cell_count = (y1 - y0 + 1) * (x1 - x0 + 1)
    if cell_count > MAX_CELLS_PER_REQUEST:
        raise OsmError("Zoom in to see restaurants — this area is too large to load at once.")

    cutoff = (datetime.utcnow() - timedelta(days=CACHE_TTL_DAYS)).isoformat()
    fetches_attempted = 0

    for cy in range(y0, y1 + 1):
        for cx in range(x0, x1 + 1):
            if fetches_attempted >= MAX_NEW_FETCHES_PER_REQUEST:
                break

            key = _cell_key(cy, cx)
            cached = conn.execute(
                "SELECT fetched_at FROM map_cache WHERE cell_key = ?", (key,)
            ).fetchone()
            if cached and cached["fetched_at"] > cutoff:
                continue

            fetches_attempted += 1
            cell_min_lat, cell_max_lat = cy * CELL_SIZE_DEGREES, (cy + 1) * CELL_SIZE_DEGREES
            cell_min_lng, cell_max_lng = cx * CELL_SIZE_DEGREES, (cx + 1) * CELL_SIZE_DEGREES
            try:
                places = _fetch_cell_from_overpass(cell_min_lat, cell_min_lng, cell_max_lat, cell_max_lng)
            except OsmError:
                # Leave this cell uncached so a later request retries it;
                # still serve whatever's already cached from other cells.
                continue

            for place in places:
                conn.execute(
                    "INSERT OR IGNORE INTO restaurants (name, cuisine, address, lat, lng, osm_id, source) "
                    "VALUES (?, ?, ?, ?, ?, ?, 'osm')",
                    (place["name"], place["cuisine"], place["address"], place["lat"], place["lng"], place["osm_id"]),
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
