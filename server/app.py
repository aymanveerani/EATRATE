import hmac
import json
import math
import mimetypes
import os
import re
import socketserver
from datetime import datetime
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlparse

from server import admin, ai_insights, auth
from server.ai_insights import generate_insights
from server.db import get_connection, init_db, UPLOADS_DIR
from server.giftcards import issue_gift_card
from server.notify import notify_report
from server.google_places import GooglePlacesError
from server.google_places import fetch_photo_bytes as google_fetch_photo_bytes
from server.google_places import sync_nearby as google_sync_nearby
from server.osm import OsmError, sync_bbox
from server.yelp import YelpError
from server.yelp import sync_nearby as yelp_sync_nearby
from server.photos import PhotoError, save_photo

STATIC_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static")
REWARD_EVERY_N_POSTS = 5
REWARD_AMOUNT_CENTS = 1000
TRIAL_DAYS = 90  # free trial length for a newly claimed business dashboard
SOFT_LAUNCH_PARTNER_LIMIT = 5  # advisory only — shown in the admin panel

# Anti-farming: one post per account per rolling 24h. A user can review the
# same restaurant as many times as they like (no per-restaurant limit) — the
# only cap is posting frequency. The 10-minute throttle is redundant with a
# 1/day cap in normal use but kept as a cheap backstop against clock-skew
# edge cases right at the day boundary.
MIN_SECONDS_BETWEEN_POSTS = 10 * 60
MAX_POSTS_PER_DAY = 1

ROUTES = []


def route(method, pattern):
    regex = re.compile("^" + pattern + "$")

    def decorator(fn):
        ROUTES.append((method, regex, fn))
        return fn

    return decorator


def public_user(row):
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row["name"],
        "post_count": row["post_count"],
    }


def public_restaurant(row):
    keys = row.keys()
    # "osm_image" is the generic "a real external photo of this place"
    # slot the frontend falls back to — for Google-sourced restaurants
    # that's our own photo-proxy URl (never a direct Google URL, since
    # fetching one requires the API key as a credential), so it overrides
    # whatever's actually stored in the osm_image column for those rows.
    if "google_photo_name" in keys and row["google_photo_name"]:
        external_image = f"/api/restaurants/{row['id']}/photo"
    else:
        external_image = row["osm_image"] if "osm_image" in keys else ""
    return {
        "id": row["id"],
        "name": row["name"],
        "cuisine": row["cuisine"],
        "address": row["address"],
        "lat": row["lat"] if "lat" in keys else None,
        "lng": row["lng"] if "lng" in keys else None,
        "soft_launch_partner": bool(row["soft_launch_partner"]) if "soft_launch_partner" in keys else False,
        "website_domain": row["website_domain"] if "website_domain" in keys else "",
        "osm_image": external_image,
    }


def public_post(row):
    keys = row.keys()
    return {
        "id": row["id"],
        "user_id": row["user_id"],
        "user_name": row["user_name"] if "user_name" in keys else None,
        "restaurant_id": row["restaurant_id"],
        "restaurant_name": row["restaurant_name"] if "restaurant_name" in keys else None,
        "photo_url": "/" + row["photo_path"],
        "rating": row["rating"],
        "caption": row["caption"],
        "created_at": row["created_at"],
        "cheers_count": row["cheers_count"] if "cheers_count" in keys else 0,
        "cheered_by_me": bool(row["cheered_by_me"]) if "cheered_by_me" in keys else False,
    }


def public_reward(row):
    keys = row.keys()
    if row["status"] == "redeemed":
        review_status = "redeemed"
    elif row["status"] == "rejected":
        review_status = "rejected"
    elif row["manual_review_status"] == "pending":
        review_status = "under_review"
    else:
        review_status = "pending"
    return {
        "id": row["id"],
        "status": row["status"],
        "review_status": review_status,
        "amount_cents": row["amount_cents"],
        "restaurant_id": row["restaurant_id"],
        "restaurant_name": row["restaurant_name"] if "restaurant_name" in keys else None,
        "gift_code": row["gift_code"],
        "created_at": row["created_at"],
        "redeemed_at": row["redeemed_at"],
    }


class ApiError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status = status
        self.message = message


def find_or_create_restaurant(conn, name):
    name = (name or "").strip()
    if not name:
        raise ApiError(400, "A restaurant or place name is required.")
    name = name[:200]
    existing = conn.execute(
        "SELECT id FROM restaurants WHERE lower(name) = lower(?)", (name,)
    ).fetchone()
    if existing:
        return existing["id"]
    cur = conn.execute("INSERT INTO restaurants (name) VALUES (?)", (name,))
    return cur.lastrowid


def friend_ids_of(conn, user_id):
    rows = conn.execute(
        "SELECT friend_id FROM friendships WHERE user_id = ?", (user_id,)
    ).fetchall()
    return [r["friend_id"] for r in rows]


def is_friend_or_self(conn, user_id, other_user_id):
    if user_id == other_user_id:
        return True
    row = conn.execute(
        "SELECT 1 FROM friendships WHERE user_id = ? AND friend_id = ?",
        (user_id, other_user_id),
    ).fetchone()
    return row is not None


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@route("POST", r"/api/signup")
def signup(ctx):
    body = ctx.json_body()
    email = (body.get("email") or "").strip()
    name = (body.get("name") or "").strip()
    password = body.get("password") or ""

    if not email or "@" not in email:
        raise ApiError(400, "A valid email is required.")
    if not name:
        raise ApiError(400, "Name is required.")
    if len(password) < 6:
        raise ApiError(400, "Password must be at least 6 characters.")

    conn = get_connection()
    existing = conn.execute("SELECT id FROM users WHERE email = ?", (email.lower(),)).fetchone()
    if existing:
        conn.close()
        raise ApiError(409, "An account with that email already exists.")

    user_id = auth.create_user(conn, email, name, password)
    token = auth.create_session(conn, user_id)
    user = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    ctx.set_session_cookie(token)
    ctx.send_json(HTTPStatus.CREATED, {"user": public_user(user)})


@route("POST", r"/api/login")
def login(ctx):
    body = ctx.json_body()
    email = body.get("email") or ""
    password = body.get("password") or ""

    conn = get_connection()
    user = auth.authenticate(conn, email, password)
    if user is None:
        conn.close()
        raise ApiError(401, "Invalid email or password.")

    token = auth.create_session(conn, user["id"])
    conn.close()
    ctx.set_session_cookie(token)
    ctx.send_json(HTTPStatus.OK, {"user": public_user(user)})


@route("POST", r"/api/logout")
def logout(ctx):
    token = ctx.session_token()
    if token:
        conn = get_connection()
        auth.destroy_session(conn, token)
        conn.close()
    ctx.clear_session_cookie()
    ctx.send_json(HTTPStatus.OK, {"ok": True})


@route("GET", r"/api/me")
def me(ctx):
    user = ctx.require_user()
    ctx.send_json(HTTPStatus.OK, {"user": public_user(user)})


# ---------------------------------------------------------------------------
# Restaurant routes
# ---------------------------------------------------------------------------

@route("GET", r"/api/restaurants")
def list_restaurants(ctx):
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT restaurants.*,
               COUNT(posts.id) AS post_count,
               COALESCE(AVG(posts.rating), 0) AS avg_rating
        FROM restaurants
        LEFT JOIN posts ON posts.restaurant_id = restaurants.id
        GROUP BY restaurants.id
        ORDER BY restaurants.name COLLATE NOCASE
        """
    ).fetchall()
    conn.close()
    out = []
    for row in rows:
        item = public_restaurant(row)
        item["post_count"] = row["post_count"]
        item["avg_rating"] = round(row["avg_rating"], 1)
        out.append(item)
    ctx.send_json(HTTPStatus.OK, {"restaurants": out})


GOOGLE_PHOTO_CACHE_DIR = os.path.join(UPLOADS_DIR, "google_photos")


@route("GET", r"/api/restaurants/(?P<restaurant_id>\d+)/photo")
def restaurant_photo(ctx, restaurant_id):
    """Proxies a restaurant's Google Places photo. The API key never
    reaches the client — it's only ever used in the server-side call to
    Google — and the result is cached to disk so it's fetched from Google
    at most once per restaurant, not on every page view."""
    ctx.require_user()

    # Google Places photos are served as JPEG in practice, so the cache is
    # keyed/served as .jpg unconditionally rather than tracking each
    # photo's real content type — a live fetch still uses the type Google
    # actually returns for the first response.
    cache_path = os.path.join(GOOGLE_PHOTO_CACHE_DIR, f"{restaurant_id}.jpg")
    if os.path.isfile(cache_path):
        with open(cache_path, "rb") as f:
            data = f.read()
        ctx.send_bytes(HTTPStatus.OK, "image/jpeg", data, cache_seconds=86400)
        return

    conn = get_connection()
    restaurant = conn.execute(
        "SELECT google_photo_name FROM restaurants WHERE id = ?", (restaurant_id,)
    ).fetchone()
    conn.close()
    if restaurant is None or not restaurant["google_photo_name"]:
        raise ApiError(404, "No photo available for this restaurant.")

    try:
        content_type, data = google_fetch_photo_bytes(restaurant["google_photo_name"])
    except GooglePlacesError as e:
        raise ApiError(502, str(e))

    os.makedirs(GOOGLE_PHOTO_CACHE_DIR, exist_ok=True)
    with open(cache_path, "wb") as f:
        f.write(data)
    ctx.send_bytes(HTTPStatus.OK, content_type, data, cache_seconds=86400)


@route("GET", r"/api/restaurants/(?P<restaurant_id>\d+)")
def get_restaurant(ctx, restaurant_id):
    user = ctx.require_user()
    conn = get_connection()
    restaurant = conn.execute(
        "SELECT * FROM restaurants WHERE id = ?", (restaurant_id,)
    ).fetchone()
    if restaurant is None:
        conn.close()
        raise ApiError(404, "Restaurant not found.")

    posts = conn.execute(
        """
        SELECT posts.*, users.name AS user_name,
               (SELECT COUNT(*) FROM cheers WHERE cheers.post_id = posts.id) AS cheers_count,
               EXISTS(SELECT 1 FROM cheers WHERE cheers.post_id = posts.id AND cheers.user_id = ?) AS cheered_by_me
        FROM posts
        JOIN users ON users.id = posts.user_id
        WHERE posts.restaurant_id = ?
        ORDER BY posts.created_at DESC
        """,
        (user["id"], restaurant_id),
    ).fetchall()
    claim = conn.execute(
        "SELECT * FROM business_claims WHERE restaurant_id = ?", (restaurant_id,)
    ).fetchone()
    conn.close()

    data = public_restaurant(restaurant)
    data["posts"] = [public_post(r) for r in posts]
    data["claimed"] = claim is not None
    data["claimed_by_me"] = claim is not None and claim["user_id"] == user["id"]
    data["business_name"] = claim["business_name"] if claim else None
    if posts:
        data["avg_rating"] = round(sum(r["rating"] for r in posts) / len(posts), 1)
    else:
        data["avg_rating"] = 0
    ctx.send_json(HTTPStatus.OK, {"restaurant": data})


# ---------------------------------------------------------------------------
# Nearby restaurants (live OpenStreetMap-backed) + business claims
# ---------------------------------------------------------------------------

NEARBY_RADIUS_KM = 5 * 1.60934  # exactly 5 miles
NEARBY_RESULT_CAP = 10  # shown as a vertical list now, not a horizontal
# scroll — 18 made sense off-screen, 10 keeps the feed from being pushed
# too far down before you reach friends' posts

# Same physical restaurant fetched by two different sources (e.g. cached
# via OSM in an earlier session, now also returned by Google) ends up as
# two separate rows — there's no cross-source unique constraint, only a
# per-source one (osm_id/yelp_id/google_place_id). Left alone, that surfaces
# a stale, lower-quality duplicate (no photo, or a blurry favicon) right
# next to the good one for the same place. Dedup by normalized name +
# proximity and keep whichever source ranks best.
DEDUP_RADIUS_KM = 0.12  # ~2 city blocks — same building, not just "close"
SOURCE_PRIORITY = {"google": 0, "yelp": 1, "osm": 2, "user": 3}


def _haversine_km(lat1, lng1, lat2, lng2):
    r = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _normalize_name(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _dedupe_and_sort_by_distance(rows, lat, lng):
    """Sorts by real distance from (lat, lng) — replaces the old
    random.shuffle, which is why "nearest to you" wasn't actually nearest —
    and collapses same-place duplicates across sources, preferring the
    highest-priority source's row (see SOURCE_PRIORITY)."""
    scored = [(_haversine_km(lat, lng, r["lat"], r["lng"]), r) for r in rows]
    scored.sort(key=lambda t: t[0])

    kept = []  # list of [distance, row, normalized_name]
    for dist, row in scored:
        norm = _normalize_name(row["name"])
        match = None
        for entry in kept:
            if entry[2] == norm and _haversine_km(row["lat"], row["lng"], entry[1]["lat"], entry[1]["lng"]) < DEDUP_RADIUS_KM:
                match = entry
                break
        if match is None:
            kept.append([dist, row, norm])
        elif SOURCE_PRIORITY.get(row["source"], 99) < SOURCE_PRIORITY.get(match[1]["source"], 99):
            match[0], match[1] = dist, row

    kept.sort(key=lambda entry: entry[0])
    return [entry[1] for entry in kept]


POPULAR_RESULT_CAP = 3


def _parse_lat_lng(ctx):
    q = parse_qs(ctx.parsed_url.query)
    try:
        return float(q["lat"][0]), float(q["lng"][0])
    except (KeyError, ValueError, IndexError):
        raise ApiError(400, "lat and lng query params are required.")


def _fetch_nearby_rows(conn, lat, lng):
    """Runs the Google -> Yelp -> OSM fallback chain (see server/app.py
    module docs) and returns raw restaurant rows within NEARBY_RADIUS_KM.
    Shared by the nearby and popular endpoints so both benefit from
    whichever source is actually configured, without duplicating the
    chain."""
    try:
        return google_sync_nearby(conn, lat, lng, NEARBY_RADIUS_KM)
    except GooglePlacesError:
        pass
    try:
        return yelp_sync_nearby(conn, lat, lng, NEARBY_RADIUS_KM)
    except YelpError:
        pass
    lat_delta = NEARBY_RADIUS_KM / 111.0
    lng_delta = NEARBY_RADIUS_KM / (111.0 * max(math.cos(math.radians(lat)), 0.01))
    try:
        return sync_bbox(conn, lat - lat_delta, lng - lng_delta, lat + lat_delta, lng + lng_delta)
    except OsmError as e:
        raise ApiError(400, str(e))


def _serialize_with_stats(conn, rows):
    """Attaches post_count/avg_rating and each restaurant's most recent
    user-submitted photo (used as a fallback image client-side, behind the
    company logo — see nearbyImageCandidates in static/js/api.js)."""
    restaurant_ids = [r["id"] for r in rows]
    stats = {}
    recent_photo = {}
    if restaurant_ids:
        placeholders = ",".join("?" * len(restaurant_ids))
        for r in conn.execute(
            f"SELECT restaurant_id, COUNT(*) AS post_count, AVG(rating) AS avg_rating "
            f"FROM posts WHERE restaurant_id IN ({placeholders}) GROUP BY restaurant_id",
            restaurant_ids,
        ):
            stats[r["restaurant_id"]] = {"post_count": r["post_count"], "avg_rating": round(r["avg_rating"], 1)}
        for r in conn.execute(
            f"SELECT restaurant_id, photo_path FROM posts "
            f"WHERE restaurant_id IN ({placeholders}) ORDER BY created_at DESC",
            restaurant_ids,
        ):
            recent_photo.setdefault(r["restaurant_id"], r["photo_path"])

    out = []
    for r in rows:
        item = public_restaurant(r)
        s = stats.get(r["id"], {"post_count": 0, "avg_rating": 0})
        item["post_count"] = s["post_count"]
        item["avg_rating"] = s["avg_rating"]
        photo_path = recent_photo.get(r["id"])
        item["photo_url"] = "/" + photo_path if photo_path else None
        out.append(item)
    return out


@route("GET", r"/api/restaurants/nearby")
def nearby_restaurants(ctx):
    ctx.require_user()
    lat, lng = _parse_lat_lng(ctx)
    conn = get_connection()
    try:
        rows = _fetch_nearby_rows(conn, lat, lng)
        rows = _dedupe_and_sort_by_distance(list(rows), lat, lng)
        rows = rows[:NEARBY_RESULT_CAP]
        out = _serialize_with_stats(conn, rows)
    finally:
        conn.close()
    ctx.send_json(HTTPStatus.OK, {"restaurants": out})


@route("GET", r"/api/restaurants/popular")
def popular_restaurants(ctx):
    """The top POPULAR_RESULT_CAP nearby restaurants by EatRate activity
    (most posts, ties broken by rating) — a different ranking of the same
    underlying area data as /nearby, not a separate search."""
    ctx.require_user()
    lat, lng = _parse_lat_lng(ctx)
    conn = get_connection()
    try:
        rows = _fetch_nearby_rows(conn, lat, lng)
        deduped = _dedupe_and_sort_by_distance(list(rows), lat, lng)
        out = _serialize_with_stats(conn, deduped)
    finally:
        conn.close()
    out = [r for r in out if r["post_count"] > 0]
    out.sort(key=lambda r: (-r["post_count"], -r["avg_rating"]))
    out = out[:POPULAR_RESULT_CAP]
    ctx.send_json(HTTPStatus.OK, {"restaurants": out})


@route("POST", r"/api/restaurants/(?P<restaurant_id>\d+)/claim")
def claim_restaurant(ctx, restaurant_id):
    user = ctx.require_user()
    body = ctx.json_body()
    business_name = (body.get("business_name") or "").strip()[:200]
    contact_email = (body.get("contact_email") or "").strip().lower()[:200]
    if not business_name:
        raise ApiError(400, "Business name is required.")
    if not contact_email or "@" not in contact_email:
        raise ApiError(400, "A valid contact email is required.")

    conn = get_connection()
    restaurant = conn.execute("SELECT * FROM restaurants WHERE id = ?", (restaurant_id,)).fetchone()
    if restaurant is None:
        conn.close()
        raise ApiError(404, "Restaurant not found.")
    if not restaurant["soft_launch_partner"]:
        conn.close()
        raise ApiError(403, "This restaurant isn't part of our soft launch yet — check back soon!")

    existing = conn.execute(
        "SELECT id FROM business_claims WHERE restaurant_id = ?", (restaurant_id,)
    ).fetchone()
    if existing:
        conn.close()
        raise ApiError(409, "This restaurant has already been claimed.")

    conn.execute(
        "INSERT INTO business_claims (restaurant_id, user_id, business_name, contact_email, trial_ends_at) "
        f"VALUES (?, ?, ?, ?, datetime('now', '+{TRIAL_DAYS} days'))",
        (restaurant_id, user["id"], business_name, contact_email),
    )
    conn.commit()
    conn.close()
    ctx.send_json(HTTPStatus.CREATED, {"ok": True})


@route("GET", r"/api/business/dashboard")
def business_dashboard(ctx):
    user = ctx.require_user()
    conn = get_connection()
    claims = conn.execute(
        """
        SELECT business_claims.*, restaurants.name AS restaurant_name,
               restaurants.cuisine, restaurants.address
        FROM business_claims
        JOIN restaurants ON restaurants.id = business_claims.restaurant_id
        WHERE business_claims.user_id = ?
        ORDER BY business_claims.created_at DESC
        """,
        (user["id"],),
    ).fetchall()

    out = []
    for claim in claims:
        rid = claim["restaurant_id"]
        posts = conn.execute(
            """
            SELECT posts.*, users.name AS user_name,
                   (SELECT COUNT(*) FROM cheers WHERE cheers.post_id = posts.id) AS cheers_count
            FROM posts
            JOIN users ON users.id = posts.user_id
            WHERE posts.restaurant_id = ?
            ORDER BY posts.created_at DESC
            """,
            (rid,),
        ).fetchall()
        weekly = conn.execute(
            """
            SELECT strftime('%Y-%W', created_at) AS week, COUNT(*) AS post_count, AVG(rating) AS avg_rating
            FROM posts WHERE restaurant_id = ? GROUP BY week ORDER BY week ASC
            """,
            (rid,),
        ).fetchall()

        # Insights are regenerated only when the review count has changed
        # since the last generation — avoids paying for an API call (when
        # ANTHROPIC_API_KEY is set) on every dashboard page view.
        if claim["cached_insights"] is None or claim["insights_post_count"] != len(posts):
            insights = generate_insights(claim["restaurant_name"], posts)
            conn.execute(
                "UPDATE business_claims SET cached_insights = ?, insights_generated_at = datetime('now'), "
                "insights_post_count = ? WHERE id = ?",
                (insights, len(posts), claim["id"]),
            )
            conn.commit()
        else:
            insights = claim["cached_insights"]

        out.append(
            {
                "restaurant_id": rid,
                "restaurant_name": claim["restaurant_name"],
                "cuisine": claim["cuisine"],
                "address": claim["address"],
                "business_name": claim["business_name"],
                "post_count": len(posts),
                "avg_rating": round(sum(p["rating"] for p in posts) / len(posts), 1) if posts else 0,
                "total_cheers": sum(p["cheers_count"] for p in posts),
                "trial_ends_at": claim["trial_ends_at"],
                "insights": insights,
                "ai_insights_mode": "live" if ai_insights.ANTHROPIC_API_KEY else "simulated",
                "weekly": [
                    {"week": w["week"], "post_count": w["post_count"], "avg_rating": round(w["avg_rating"], 1)}
                    for w in weekly
                ],
                "posts": [public_post(p) for p in posts][:20],
            }
        )
    conn.close()
    ctx.send_json(HTTPStatus.OK, {"businesses": out})


# ---------------------------------------------------------------------------
# Posts (camera-first sharing)
# ---------------------------------------------------------------------------

@route("POST", r"/api/posts")
def create_post(ctx):
    user = ctx.require_user()
    body = ctx.json_body()

    try:
        rating = int(body.get("rating"))
    except (TypeError, ValueError):
        raise ApiError(400, "Rating must be an integer from 0 to 10.")
    if rating < 0 or rating > 10:
        raise ApiError(400, "Rating must be between 0 and 10.")

    caption = (body.get("caption") or "").strip()[:2000]

    conn = get_connection()

    last_post = conn.execute(
        "SELECT created_at FROM posts WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user["id"],),
    ).fetchone()
    if last_post:
        last_time = datetime.fromisoformat(last_post["created_at"].replace(" ", "T"))
        elapsed = (datetime.utcnow() - last_time).total_seconds()
        if elapsed < MIN_SECONDS_BETWEEN_POSTS:
            conn.close()
            raise ApiError(429, "You're posting too fast — please wait at least 10 minutes between posts.")

    day_count = conn.execute(
        "SELECT COUNT(*) AS c FROM posts WHERE user_id = ? AND created_at > datetime('now', '-1 day')",
        (user["id"],),
    ).fetchone()["c"]
    if day_count >= MAX_POSTS_PER_DAY:
        conn.close()
        raise ApiError(429, "You can only share one post per day. Come back tomorrow!")

    restaurant_id = find_or_create_restaurant(conn, body.get("restaurant_name"))

    try:
        photo_path = save_photo(body.get("photo"))
    except PhotoError as e:
        conn.close()
        raise ApiError(400, str(e))

    conn.execute(
        "INSERT INTO posts (user_id, restaurant_id, photo_path, rating, caption) "
        "VALUES (?, ?, ?, ?, ?)",
        (user["id"], restaurant_id, photo_path, rating, caption),
    )
    new_count = user["post_count"] + 1
    conn.execute("UPDATE users SET post_count = ? WHERE id = ?", (new_count, user["id"]))

    new_reward = None
    if new_count % REWARD_EVERY_N_POSTS == 0:
        cur = conn.execute(
            "INSERT INTO rewards (user_id, status, amount_cents, trigger_post_count) "
            "VALUES (?, 'pending', ?, ?)",
            (user["id"], REWARD_AMOUNT_CENTS, new_count),
        )
        new_reward = cur.lastrowid

    conn.commit()
    conn.close()

    result = {"ok": True, "post_count": new_count}
    if new_reward:
        result["reward_earned"] = {"id": new_reward, "amount_cents": REWARD_AMOUNT_CENTS}
    ctx.send_json(HTTPStatus.CREATED, result)


@route("POST", r"/api/posts/(?P<post_id>\d+)/cheer")
def toggle_cheer(ctx, post_id):
    user = ctx.require_user()
    conn = get_connection()
    post = conn.execute("SELECT * FROM posts WHERE id = ?", (post_id,)).fetchone()
    if post is None:
        conn.close()
        raise ApiError(404, "Post not found.")
    if not is_friend_or_self(conn, user["id"], post["user_id"]):
        conn.close()
        raise ApiError(403, "You can only cheer posts from your friends.")

    existing = conn.execute(
        "SELECT 1 FROM cheers WHERE post_id = ? AND user_id = ?", (post_id, user["id"])
    ).fetchone()
    if existing:
        conn.execute(
            "DELETE FROM cheers WHERE post_id = ? AND user_id = ?", (post_id, user["id"])
        )
        cheered = False
    else:
        conn.execute(
            "INSERT INTO cheers (post_id, user_id) VALUES (?, ?)", (post_id, user["id"])
        )
        cheered = True
    conn.commit()
    count = conn.execute(
        "SELECT COUNT(*) AS c FROM cheers WHERE post_id = ?", (post_id,)
    ).fetchone()["c"]
    conn.close()
    ctx.send_json(HTTPStatus.OK, {"cheered": cheered, "cheers_count": count})


@route("POST", r"/api/posts/(?P<post_id>\d+)/report")
def report_post(ctx, post_id):
    user = ctx.require_user()
    body = ctx.json_body()
    reason = (body.get("reason") or "").strip()[:2000]

    conn = get_connection()
    post = conn.execute("SELECT id FROM posts WHERE id = ?", (post_id,)).fetchone()
    if post is None:
        conn.close()
        raise ApiError(404, "Post not found.")

    conn.execute(
        "INSERT INTO reports (post_id, reporter_user_id, reason) VALUES (?, ?, ?)",
        (post_id, user["id"], reason),
    )
    conn.commit()
    conn.close()

    notify_report(post_id, user["email"], reason)
    ctx.send_json(HTTPStatus.CREATED, {"ok": True})


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------

@route("GET", r"/api/feed")
def feed(ctx):
    """Shows what people are posting at restaurants near the user — not just
    friends — so the feed has content from day one instead of depending on
    a friends list. Falls back to a friends-only feed if location isn't
    available (permission denied, or no lat/lng passed)."""
    user = ctx.require_user()
    q = parse_qs(ctx.parsed_url.query)
    try:
        lat = float(q["lat"][0])
        lng = float(q["lng"][0])
    except (KeyError, ValueError, IndexError):
        lat = lng = None

    conn = get_connection()
    if lat is not None and lng is not None:
        lat_delta = NEARBY_RADIUS_KM / 111.0
        lng_delta = NEARBY_RADIUS_KM / (111.0 * max(math.cos(math.radians(lat)), 0.01))
        rows = conn.execute(
            """
            SELECT posts.*, users.name AS user_name, restaurants.name AS restaurant_name,
                   (SELECT COUNT(*) FROM cheers WHERE cheers.post_id = posts.id) AS cheers_count,
                   EXISTS(SELECT 1 FROM cheers WHERE cheers.post_id = posts.id AND cheers.user_id = ?) AS cheered_by_me
            FROM posts
            JOIN users ON users.id = posts.user_id
            JOIN restaurants ON restaurants.id = posts.restaurant_id
            WHERE restaurants.lat BETWEEN ? AND ? AND restaurants.lng BETWEEN ? AND ?
            ORDER BY posts.created_at DESC
            LIMIT 50
            """,
            (user["id"], lat - lat_delta, lat + lat_delta, lng - lng_delta, lng + lng_delta),
        ).fetchall()
    else:
        ids = friend_ids_of(conn, user["id"]) + [user["id"]]
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"""
            SELECT posts.*, users.name AS user_name, restaurants.name AS restaurant_name,
                   (SELECT COUNT(*) FROM cheers WHERE cheers.post_id = posts.id) AS cheers_count,
                   EXISTS(SELECT 1 FROM cheers WHERE cheers.post_id = posts.id AND cheers.user_id = ?) AS cheered_by_me
            FROM posts
            JOIN users ON users.id = posts.user_id
            JOIN restaurants ON restaurants.id = posts.restaurant_id
            WHERE posts.user_id IN ({placeholders})
            ORDER BY posts.created_at DESC
            LIMIT 50
            """,
            [user["id"]] + ids,
        ).fetchall()
    conn.close()
    ctx.send_json(HTTPStatus.OK, {"posts": [public_post(r) for r in rows]})


# ---------------------------------------------------------------------------
# Friends
# ---------------------------------------------------------------------------

@route("GET", r"/api/friends")
def list_friends(ctx):
    user = ctx.require_user()
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT users.id, users.name, users.email, users.post_count
        FROM friendships
        JOIN users ON users.id = friendships.friend_id
        WHERE friendships.user_id = ?
        ORDER BY users.name COLLATE NOCASE
        """,
        (user["id"],),
    ).fetchall()
    conn.close()
    ctx.send_json(
        HTTPStatus.OK,
        {"friends": [{"id": r["id"], "name": r["name"], "email": r["email"], "post_count": r["post_count"]} for r in rows]},
    )


@route("POST", r"/api/friends")
def add_friend(ctx):
    user = ctx.require_user()
    body = ctx.json_body()
    email = (body.get("email") or "").strip().lower()
    if not email:
        raise ApiError(400, "An email is required.")

    conn = get_connection()
    friend = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
    if friend is None:
        conn.close()
        raise ApiError(404, "No EatRate user with that email.")
    if friend["id"] == user["id"]:
        conn.close()
        raise ApiError(400, "You can't add yourself as a friend.")

    existing = conn.execute(
        "SELECT 1 FROM friendships WHERE user_id = ? AND friend_id = ?",
        (user["id"], friend["id"]),
    ).fetchone()
    if existing:
        conn.close()
        raise ApiError(409, "You're already friends.")

    conn.execute(
        "INSERT INTO friendships (user_id, friend_id) VALUES (?, ?), (?, ?)",
        (user["id"], friend["id"], friend["id"], user["id"]),
    )
    conn.commit()
    conn.close()
    ctx.send_json(
        HTTPStatus.CREATED,
        {"friend": {"id": friend["id"], "name": friend["name"], "email": friend["email"], "post_count": friend["post_count"]}},
    )


@route("DELETE", r"/api/friends/(?P<friend_id>\d+)")
def remove_friend(ctx, friend_id):
    user = ctx.require_user()
    conn = get_connection()
    conn.execute(
        "DELETE FROM friendships WHERE (user_id = ? AND friend_id = ?) OR (user_id = ? AND friend_id = ?)",
        (user["id"], friend_id, friend_id, user["id"]),
    )
    conn.commit()
    conn.close()
    ctx.send_json(HTTPStatus.OK, {"ok": True})


# ---------------------------------------------------------------------------
# Rewards
# ---------------------------------------------------------------------------

@route("GET", r"/api/rewards")
def list_rewards(ctx):
    user = ctx.require_user()
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT rewards.*, restaurants.name AS restaurant_name
        FROM rewards
        LEFT JOIN restaurants ON restaurants.id = rewards.restaurant_id
        WHERE rewards.user_id = ?
        ORDER BY rewards.created_at DESC
        """,
        (user["id"],),
    ).fetchall()
    conn.close()
    ctx.send_json(
        HTTPStatus.OK,
        {"rewards": [public_reward(r) for r in rows], "redemption_enabled": admin.REDEMPTION_ENABLED},
    )


@route("POST", r"/api/rewards/(?P<reward_id>\d+)/redeem")
def redeem_reward(ctx, reward_id):
    user = ctx.require_user()
    if not admin.REDEMPTION_ENABLED:
        raise ApiError(
            403,
            "Gift card redemption isn't open yet — it launches with our soft-launch partner "
            "restaurants. Your reward is saved and you'll be able to redeem it soon.",
        )
    body = ctx.json_body()
    try:
        restaurant_id = int(body.get("restaurant_id"))
    except (TypeError, ValueError):
        raise ApiError(400, "restaurant_id is required.")

    conn = get_connection()
    reward = conn.execute(
        "SELECT * FROM rewards WHERE id = ? AND user_id = ?", (reward_id, user["id"])
    ).fetchone()
    if reward is None:
        conn.close()
        raise ApiError(404, "Reward not found.")
    if reward["status"] != "pending":
        conn.close()
        raise ApiError(409, "This reward has already been redeemed.")

    restaurant = conn.execute(
        "SELECT * FROM restaurants WHERE id = ?", (restaurant_id,)
    ).fetchone()
    if restaurant is None:
        conn.close()
        raise ApiError(404, "Restaurant not found.")

    # First MANUAL_REVIEW_LIMIT redemptions platform-wide are held for a human
    # to approve before the card is issued — the pilot's fraud check. BEGIN
    # IMMEDIATE serializes concurrent redeem calls so two requests can't both
    # slip in as, say, the 30th slot.
    conn.execute("BEGIN IMMEDIATE")
    try:
        reviewed_count = conn.execute(
            "SELECT COUNT(*) AS c FROM rewards WHERE manual_review_required = 1"
        ).fetchone()["c"]

        if reviewed_count < admin.MANUAL_REVIEW_LIMIT:
            conn.execute(
                "UPDATE rewards SET manual_review_required = 1, manual_review_status = 'pending', "
                "restaurant_id = ? WHERE id = ?",
                (restaurant_id, reward_id),
            )
            conn.commit()
            updated = conn.execute(
                """
                SELECT rewards.*, restaurants.name AS restaurant_name
                FROM rewards LEFT JOIN restaurants ON restaurants.id = rewards.restaurant_id
                WHERE rewards.id = ?
                """,
                (reward_id,),
            ).fetchone()
            conn.close()
            ctx.send_json(HTTPStatus.OK, {"reward": public_reward(updated), "under_review": True})
            return

        card = issue_gift_card(restaurant["name"], reward["amount_cents"])
        conn.execute(
            "UPDATE rewards SET status = 'redeemed', restaurant_id = ?, gift_code = ?, "
            "redeemed_at = datetime('now') WHERE id = ?",
            (restaurant_id, card["code"], reward_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        conn.close()
        raise

    updated = conn.execute(
        """
        SELECT rewards.*, restaurants.name AS restaurant_name
        FROM rewards LEFT JOIN restaurants ON restaurants.id = rewards.restaurant_id
        WHERE rewards.id = ?
        """,
        (reward_id,),
    ).fetchone()
    conn.close()
    ctx.send_json(HTTPStatus.OK, {"reward": public_reward(updated), "gift_card": card})


# ---------------------------------------------------------------------------
# Admin (pilot fraud review — gated by the ADMIN_SECRET env var, not by user
# login, since this is an operator tool rather than a user-facing feature)
# ---------------------------------------------------------------------------

def require_admin(ctx):
    if not admin.ADMIN_SECRET:
        raise ApiError(503, "Admin panel is not configured (ADMIN_SECRET not set on the server).")
    provided = ctx.handler.headers.get("X-Admin-Secret", "")
    if not hmac.compare_digest(provided, admin.ADMIN_SECRET):
        raise ApiError(401, "Invalid admin secret.")


@route("GET", r"/api/admin/restaurants/search")
def admin_search_restaurants(ctx):
    require_admin(ctx)
    q = parse_qs(ctx.parsed_url.query)
    query = (q.get("q", [""])[0] or "").strip()

    conn = get_connection()
    if query:
        rows = conn.execute(
            "SELECT * FROM restaurants WHERE name LIKE ? ORDER BY name COLLATE NOCASE LIMIT 25",
            (f"%{query}%",),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM restaurants ORDER BY soft_launch_partner DESC, name COLLATE NOCASE LIMIT 25"
        ).fetchall()
    partner_count = conn.execute(
        "SELECT COUNT(*) AS c FROM restaurants WHERE soft_launch_partner = 1"
    ).fetchone()["c"]
    conn.close()
    ctx.send_json(
        HTTPStatus.OK,
        {
            "restaurants": [public_restaurant(r) for r in rows],
            "soft_launch_partner_count": partner_count,
            "soft_launch_partner_limit": SOFT_LAUNCH_PARTNER_LIMIT,
        },
    )


@route("POST", r"/api/admin/restaurants/(?P<restaurant_id>\d+)/soft-launch-partner")
def admin_set_soft_launch_partner(ctx, restaurant_id):
    require_admin(ctx)
    body = ctx.json_body()
    enabled = bool(body.get("enabled"))

    conn = get_connection()
    restaurant = conn.execute("SELECT * FROM restaurants WHERE id = ?", (restaurant_id,)).fetchone()
    if restaurant is None:
        conn.close()
        raise ApiError(404, "Restaurant not found.")

    conn.execute(
        "UPDATE restaurants SET soft_launch_partner = ? WHERE id = ?", (1 if enabled else 0, restaurant_id)
    )
    conn.commit()
    conn.close()
    ctx.send_json(HTTPStatus.OK, {"ok": True})


@route("GET", r"/api/admin/redemptions")
def admin_list_redemptions(ctx):
    require_admin(ctx)
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT rewards.*, users.name AS user_name, users.email AS user_email,
               restaurants.name AS restaurant_name
        FROM rewards
        JOIN users ON users.id = rewards.user_id
        LEFT JOIN restaurants ON restaurants.id = rewards.restaurant_id
        WHERE rewards.manual_review_required = 1
        ORDER BY rewards.created_at DESC
        """
    ).fetchall()
    used = conn.execute(
        "SELECT COUNT(*) AS c FROM rewards WHERE manual_review_required = 1"
    ).fetchone()["c"]
    conn.close()
    out = []
    for r in rows:
        item = public_reward(r)
        item["user_name"] = r["user_name"]
        item["user_email"] = r["user_email"]
        out.append(item)
    ctx.send_json(
        HTTPStatus.OK,
        {"redemptions": out, "manual_review_used": used, "manual_review_limit": admin.MANUAL_REVIEW_LIMIT},
    )


@route("POST", r"/api/admin/redemptions/(?P<reward_id>\d+)/approve")
def admin_approve_redemption(ctx, reward_id):
    require_admin(ctx)
    conn = get_connection()
    reward = conn.execute("SELECT * FROM rewards WHERE id = ?", (reward_id,)).fetchone()
    if reward is None:
        conn.close()
        raise ApiError(404, "Reward not found.")
    if reward["manual_review_status"] != "pending":
        conn.close()
        raise ApiError(409, "This redemption isn't awaiting review.")

    restaurant = conn.execute(
        "SELECT * FROM restaurants WHERE id = ?", (reward["restaurant_id"],)
    ).fetchone()
    card = issue_gift_card(restaurant["name"], reward["amount_cents"])
    conn.execute(
        "UPDATE rewards SET status = 'redeemed', manual_review_status = 'approved', "
        "gift_code = ?, redeemed_at = datetime('now') WHERE id = ?",
        (card["code"], reward_id),
    )
    conn.commit()
    conn.close()
    ctx.send_json(HTTPStatus.OK, {"ok": True, "gift_card": card})


@route("POST", r"/api/admin/redemptions/(?P<reward_id>\d+)/reject")
def admin_reject_redemption(ctx, reward_id):
    require_admin(ctx)
    conn = get_connection()
    reward = conn.execute("SELECT * FROM rewards WHERE id = ?", (reward_id,)).fetchone()
    if reward is None:
        conn.close()
        raise ApiError(404, "Reward not found.")
    if reward["manual_review_status"] != "pending":
        conn.close()
        raise ApiError(409, "This redemption isn't awaiting review.")

    conn.execute(
        "UPDATE rewards SET status = 'rejected', manual_review_status = 'rejected' WHERE id = ?",
        (reward_id,),
    )
    conn.commit()
    conn.close()
    ctx.send_json(HTTPStatus.OK, {"ok": True})


@route("GET", r"/api/admin/reports")
def admin_list_reports(ctx):
    require_admin(ctx)
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT reports.*, users.name AS reporter_name, users.email AS reporter_email,
               posts.photo_path AS post_photo_path, posts.caption AS post_caption,
               posts.rating AS post_rating, post_authors.name AS post_author_name
        FROM reports
        JOIN users ON users.id = reports.reporter_user_id
        JOIN posts ON posts.id = reports.post_id
        JOIN users AS post_authors ON post_authors.id = posts.user_id
        WHERE reports.status = 'open'
        ORDER BY reports.created_at DESC
        """
    ).fetchall()
    conn.close()
    out = [
        {
            "id": r["id"],
            "post_id": r["post_id"],
            "reason": r["reason"],
            "created_at": r["created_at"],
            "reporter_name": r["reporter_name"],
            "reporter_email": r["reporter_email"],
            "post_photo_url": "/" + r["post_photo_path"],
            "post_caption": r["post_caption"],
            "post_rating": r["post_rating"],
            "post_author_name": r["post_author_name"],
        }
        for r in rows
    ]
    ctx.send_json(HTTPStatus.OK, {"reports": out})


@route("POST", r"/api/admin/reports/(?P<report_id>\d+)/resolve")
def admin_resolve_report(ctx, report_id):
    require_admin(ctx)
    conn = get_connection()
    conn.execute(
        "UPDATE reports SET status = 'resolved', resolved_at = datetime('now') WHERE id = ?",
        (report_id,),
    )
    conn.commit()
    conn.close()
    ctx.send_json(HTTPStatus.OK, {"ok": True})


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@route("GET", r"/api/profile")
def profile(ctx):
    user = ctx.require_user()
    conn = get_connection()
    posts = conn.execute(
        """
        SELECT posts.*, restaurants.name AS restaurant_name,
               (SELECT COUNT(*) FROM cheers WHERE cheers.post_id = posts.id) AS cheers_count,
               EXISTS(SELECT 1 FROM cheers WHERE cheers.post_id = posts.id AND cheers.user_id = ?) AS cheered_by_me
        FROM posts
        JOIN restaurants ON restaurants.id = posts.restaurant_id
        WHERE posts.user_id = ?
        ORDER BY posts.created_at DESC
        """,
        (user["id"], user["id"]),
    ).fetchall()
    rewards = conn.execute(
        "SELECT * FROM rewards WHERE user_id = ? ORDER BY created_at DESC", (user["id"],)
    ).fetchall()
    friend_count = conn.execute(
        "SELECT COUNT(*) AS c FROM friendships WHERE user_id = ?", (user["id"],)
    ).fetchone()["c"]
    conn.close()

    next_reward_in = REWARD_EVERY_N_POSTS - (user["post_count"] % REWARD_EVERY_N_POSTS)
    if next_reward_in == REWARD_EVERY_N_POSTS:
        next_reward_in = 0

    ctx.send_json(
        HTTPStatus.OK,
        {
            "user": public_user(user),
            "posts": [public_post(r) for r in posts],
            "rewards": [public_reward(r) for r in rewards],
            "friend_count": friend_count,
            "posts_until_next_reward": next_reward_in,
        },
    )


# ---------------------------------------------------------------------------
# HTTP plumbing
# ---------------------------------------------------------------------------

class RequestContext:
    def __init__(self, handler, method, parsed_url):
        self.handler = handler
        self.method = method
        self.parsed_url = parsed_url
        self._body_cache = None
        self._cookies = SimpleCookie(handler.headers.get("Cookie", ""))
        self._user_cache = "unset"
        self._pending_headers = []

    def json_body(self):
        if self._body_cache is None:
            length = int(self.handler.headers.get("Content-Length", 0) or 0)
            raw = self.handler.rfile.read(length) if length else b""
            if not raw:
                self._body_cache = {}
            else:
                try:
                    self._body_cache = json.loads(raw.decode("utf-8"))
                except json.JSONDecodeError:
                    raise ApiError(400, "Invalid JSON body.")
        return self._body_cache

    def session_token(self):
        morsel = self._cookies.get("session")
        return morsel.value if morsel else None

    def require_user(self):
        if self._user_cache == "unset":
            conn = get_connection()
            self._user_cache = auth.get_user_by_session(conn, self.session_token())
            conn.close()
        if self._user_cache is None:
            raise ApiError(401, "You must be logged in.")
        return self._user_cache

    def set_session_cookie(self, token):
        self._pending_headers.append((
            "Set-Cookie",
            f"session={token}; Path=/; HttpOnly; SameSite=Lax; Max-Age={30 * 24 * 3600}",
        ))

    def clear_session_cookie(self):
        self._pending_headers.append(("Set-Cookie", "session=; Path=/; HttpOnly; Max-Age=0"))

    def send_json(self, status, obj):
        payload = json.dumps(obj).encode("utf-8")
        self.handler.send_response(status)
        self.handler.send_header("Content-Type", "application/json")
        self.handler.send_header("Content-Length", str(len(payload)))
        for name, value in self._pending_headers:
            self.handler.send_header(name, value)
        self.handler.end_headers()
        self.handler.wfile.write(payload)

    def send_bytes(self, status, content_type, data, cache_seconds=None):
        self.handler.send_response(status)
        self.handler.send_header("Content-Type", content_type)
        self.handler.send_header("Content-Length", str(len(data)))
        if cache_seconds:
            self.handler.send_header("Cache-Control", f"public, max-age={cache_seconds}")
        for name, value in self._pending_headers:
            self.handler.send_header(name, value)
        self.handler.end_headers()
        self.handler.wfile.write(data)


class Handler(BaseHTTPRequestHandler):
    server_version = "EatRate/0.2"

    def log_message(self, fmt, *args):
        pass

    def _dispatch(self, method):
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            ctx = RequestContext(self, method, parsed)
            for route_method, regex, fn in ROUTES:
                if route_method != method:
                    continue
                match = regex.match(path)
                if match:
                    try:
                        fn(ctx, **match.groupdict())
                    except ApiError as e:
                        ctx.send_json(e.status, {"error": e.message})
                    except Exception as e:
                        ctx.send_json(500, {"error": f"Internal error: {e}"})
                    return
            ctx.send_json(HTTPStatus.NOT_FOUND, {"error": "Not found."})
            return

        if method == "GET":
            self._serve_static(path)
            return

        self.send_response(HTTPStatus.NOT_FOUND)
        self.end_headers()

    def _serve_static(self, path):
        # Uploaded photos live on persistent storage (UPLOADS_DIR), separate
        # from the app's own static/ folder, so they survive redeploys.
        if path.startswith("/uploads/"):
            self._serve_from_dir(UPLOADS_DIR, path[len("/uploads/"):], allow_index_fallback=False)
            return

        if path == "/":
            path = "/index.html"
        self._serve_from_dir(STATIC_DIR, path.lstrip("/"), allow_index_fallback=True)

    def _serve_from_dir(self, base_dir, relative_path, allow_index_fallback):
        safe_path = os.path.normpath(relative_path).lstrip("/")
        full_path = os.path.join(base_dir, safe_path)

        if not full_path.startswith(base_dir):
            self.send_response(HTTPStatus.FORBIDDEN)
            self.end_headers()
            return

        if not os.path.isfile(full_path):
            if allow_index_fallback:
                full_path = os.path.join(base_dir, "index.html")
            if not allow_index_fallback or not os.path.isfile(full_path):
                self.send_response(HTTPStatus.NOT_FOUND)
                self.end_headers()
                return

        content_type, _ = mimetypes.guess_type(full_path)
        with open(full_path, "rb") as f:
            data = f.read()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type or "application/octet-stream")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        self._dispatch("GET")

    def do_POST(self):
        self._dispatch("POST")

    def do_PUT(self):
        self._dispatch("PUT")

    def do_DELETE(self):
        self._dispatch("DELETE")


class ThreadingHTTPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def run(port=3000):
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print(f"EatRate server running on http://localhost:{port}")
    server.serve_forever()
