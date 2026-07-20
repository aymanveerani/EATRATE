import sqlite3
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# DATA_DIR points at where the database and uploaded photos live. Locally this
# defaults to the project folder. In production it should be set to a mounted
# persistent volume (e.g. Railway) so data survives deploys/restarts, since
# everything else in the container filesystem is ephemeral.
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
DB_PATH = os.path.join(DATA_DIR, "eatrate.db")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")

SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    password_salt TEXT NOT NULL,
    post_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sessions (
    token TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS restaurants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    cuisine TEXT NOT NULL DEFAULT '',
    address TEXT NOT NULL DEFAULT '',
    lat REAL,
    lng REAL,
    osm_id TEXT,
    source TEXT NOT NULL DEFAULT 'user',
    soft_launch_partner INTEGER NOT NULL DEFAULT 0,
    website_domain TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS business_claims (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    restaurant_id INTEGER NOT NULL UNIQUE,
    user_id INTEGER NOT NULL,
    business_name TEXT NOT NULL,
    contact_email TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    trial_ends_at TEXT,
    cached_insights TEXT,
    insights_generated_at TEXT,
    insights_post_count INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS map_cache (
    cell_key TEXT PRIMARY KEY,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    restaurant_id INTEGER NOT NULL,
    photo_path TEXT NOT NULL,
    rating INTEGER NOT NULL CHECK (rating >= 0 AND rating <= 10),
    caption TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
);

CREATE TABLE IF NOT EXISTS friendships (
    user_id INTEGER NOT NULL,
    friend_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, friend_id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (friend_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS cheers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (post_id, user_id),
    FOREIGN KEY (post_id) REFERENCES posts(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE IF NOT EXISTS rewards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    amount_cents INTEGER NOT NULL DEFAULT 1000,
    restaurant_id INTEGER,
    gift_code TEXT,
    trigger_post_count INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    redeemed_at TEXT,
    manual_review_required INTEGER NOT NULL DEFAULT 0,
    manual_review_status TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (restaurant_id) REFERENCES restaurants(id)
);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    reporter_user_id INTEGER NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    resolved_at TEXT,
    FOREIGN KEY (post_id) REFERENCES posts(id),
    FOREIGN KEY (reporter_user_id) REFERENCES users(id)
);
"""

# Columns added after the original tables were created. CREATE TABLE IF NOT
# EXISTS won't retrofit these onto an existing eatrate.db, so migrate
# explicitly and ignore "duplicate column" if it's already been applied.
MIGRATIONS = [
    "ALTER TABLE rewards ADD COLUMN manual_review_required INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE rewards ADD COLUMN manual_review_status TEXT",
    "ALTER TABLE restaurants ADD COLUMN lat REAL",
    "ALTER TABLE restaurants ADD COLUMN lng REAL",
    "ALTER TABLE restaurants ADD COLUMN osm_id TEXT",
    "ALTER TABLE restaurants ADD COLUMN source TEXT NOT NULL DEFAULT 'user'",
    "ALTER TABLE restaurants ADD COLUMN soft_launch_partner INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE restaurants ADD COLUMN website_domain TEXT NOT NULL DEFAULT ''",
    "ALTER TABLE business_claims ADD COLUMN trial_ends_at TEXT",
    "ALTER TABLE business_claims ADD COLUMN cached_insights TEXT",
    "ALTER TABLE business_claims ADD COLUMN insights_generated_at TEXT",
    "ALTER TABLE business_claims ADD COLUMN insights_post_count INTEGER NOT NULL DEFAULT 0",
]

# Must run *after* MIGRATIONS: this index references restaurants.osm_id,
# which doesn't exist yet on a pre-existing database until the ALTER TABLE
# above has run. Running it as part of SCHEMA's executescript (before
# migrations) crashes on any database that predates the osm_id column.
#
# Each of these is executed individually and any failure is logged rather
# than raised (see init_db), so a bad statement here is never fatal.
#
# Note: there is deliberately no unique constraint on posts(user_id,
# restaurant_id) — users are allowed to review the same restaurant multiple
# times, so nothing should ever enforce one-review-per-restaurant here.
POST_MIGRATION_STATEMENTS = [
    "CREATE UNIQUE INDEX IF NOT EXISTS idx_restaurants_osm_id ON restaurants(osm_id) WHERE osm_id IS NOT NULL",
]


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    conn = get_connection()
    conn.executescript(SCHEMA)
    for migration in MIGRATIONS:
        try:
            conn.execute(migration)
        except sqlite3.OperationalError as e:
            if "duplicate column" not in str(e).lower():
                raise
    for statement in POST_MIGRATION_STATEMENTS:
        try:
            conn.execute(statement)
        except sqlite3.Error as e:
            # Covers OperationalError (e.g. missing column) and
            # IntegrityError (e.g. pre-existing duplicate rows that violate
            # a new UNIQUE index) — these are advisory indexes, not the only
            # thing enforcing their rule, so a failure here is never fatal.
            print(f"[WARN] Skipping post-migration statement (non-fatal): {statement} -> {e}", flush=True)
    conn.commit()
    conn.close()
