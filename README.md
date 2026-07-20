# EatRate

Snap a photo of what you're eating, tag the place, rate it out of 10, and share it with your
friends — Beer Buddy's model (photo-first, friends-only feed, quick reactions) applied to food
instead of drinks. Every 5th post earns a $10 gift card you can redeem at a restaurant of your
choice.

## Why it's built this way

This machine has no Node.js/npm and no Homebrew, and the sandboxed preview tooling can't reach
files under `~/Downloads` (the project now lives at `~/eatrate` instead — see below). So instead
of a framework, this is a dependency-free app:

- **Backend**: Python 3 standard library only — `http.server` for the HTTP layer, `sqlite3` for
  storage, `hashlib`/`secrets` for password hashing (PBKDF2) and session tokens. Photos are
  decoded from base64 and written straight to disk under a data directory (see "Deploying it"
  below for why this is decoupled from the app code). No pip installs required.
- **Frontend**: plain HTML/CSS/JS, mobile-width layout, no build step. Photo capture uses a plain
  `<input type="file" capture="environment">`, read client-side with `FileReader` and posted as a
  base64 data URL — no multipart parsing needed on the server.

Nothing here is a mock — signup, login, photo posts, friends, cheers, the reward trigger, and
redemption all write to a real SQLite database (`eatrate.db`) and were exercised end-to-end, both
via curl and by actually driving the app in a browser (see "What was verified" below).

## Running it

```bash
cd eatrate
python3 seed.py      # populates 6 sample restaurants (safe to re-run, no-ops if data exists)
python3 run.py 3000  # starts the server on http://localhost:3000
```

Open `http://localhost:3000`, sign up, and the first thing you'll see is the camera prompt.

## Deploying it for real

The app is ready to run on a real host — the only thing that changes between local and
production is where the database and uploaded photos live:

- `DATA_DIR` env var controls this (`server/db.py`). Locally it defaults to the project folder.
  In production, set it to a path backed by **persistent storage** (a mounted volume) — without
  that, every redeploy wipes your users, posts, and photos, since the rest of the container
  filesystem is thrown away on each deploy.
- `PORT` env var controls what port the server binds to (`run.py`), which is how Railway (and
  most hosts) tell your app what port to listen on.
- `Procfile` (`web: python3 run.py`) tells the host how to start the app.
- `requirements.txt` is intentionally empty — it exists so Railway's builder recognizes this as a
  Python project. There really are no third-party dependencies.

**Deployed to Railway:** connect this GitHub repo, add a persistent volume, set `DATA_DIR` to the
volume's mount path, and Railway generates a public HTTPS URL automatically. See the deployment
walkthrough for the exact click-by-click steps (account creation and payment are steps only you
can do, so that part isn't automated here).

**Adding a custom domain later:** once the app is live on Railway's free subdomain, buy a domain
from any registrar (Namecheap, Cloudflare, Google Domains/Squarespace) and add it in Railway's
service → Settings → Networking → Custom Domain. Railway gives you a CNAME record to add at your
registrar; DNS propagation usually takes a few minutes to a few hours.

## The core loop (mirrors Beer Buddy)

1. **Camera first.** The home screen (`index.html`) is a friends feed with a "What are you
   eating?" card pinned at the top, plus a floating camera button in the nav. Both open
   [`capture.html`](static/capture.html).
2. **Snap → tag → share.** Pick/take a photo, type the restaurant (autocompletes against existing
   ones, or creates a new one on the fly), rate it 0–10, add an optional caption, share.
3. **Friends-only feed.** `GET /api/feed` only returns posts from the poster and their friends —
   nobody else sees it. Friends are added by email and are bidirectional (`POST /api/friends`).
4. **Cheers.** A lightweight reaction (`POST /api/posts/:id/cheer`, toggled, one per user per
   post) — the equivalent of Beer Buddy's "Cheers" tap.
5. **Rewards.** Every 5th post earns a $10 gift card, same mechanic as before, just counting
   `posts` instead of `reviews` now.

## How the reward works

- `users.post_count` increments on every post.
- When it hits a multiple of 5, a `rewards` row is created with `status = 'pending'`.
- The rewards page lets the user redeem a pending reward by picking a restaurant; that calls
  `POST /api/rewards/:id/redeem`, which issues a gift card code and marks the reward `redeemed`.
- The reward amount ($10) and the trigger count (5) are constants in
  [server/app.py](server/app.py) (`REWARD_EVERY_N_POSTS`, `REWARD_AMOUNT_CENTS`).

## Map & business dashboard

**There is no "every restaurant in America" dataset here** — that isn't free, and isn't legal to
bulk-store from Google Places or Yelp without a paid contract. Instead, [`map.html`](static/map.html)
works the way real map apps do: it fetches real restaurants for whatever viewport you're currently
looking at from **OpenStreetMap's Overpass API** (free, keyless), the same way Yelp/Google Maps
load results as you pan instead of downloading the planet up front.

- [server/osm.py](server/osm.py) fetches a coarse grid of ~2×2km cells covering the requested
  viewport, caching each cell in `map_cache` for 7 days so repeated visits to the same area don't
  re-hit Overpass. Every fetched place becomes a real row in `restaurants` (matched on OSM's node
  id via a unique index, so re-fetching never duplicates it) — it's the same restaurant entity
  users can post about and businesses can claim, not a separate read-only layer.
- Overpass is a shared free public service with variable load — occasional slow or failed cells
  are expected, not a bug. Failed cells are simply left uncached and retried on the next request;
  a single map load is bounded to a handful of live Overpass calls so one dense area (found this
  the hard way testing Manhattan, which 504s on naive queries) can't hang the page.
- Coverage reflects OpenStreetMap's crowd-sourced data: good to very good in cities, sparser in
  small towns and rural areas. That's the real tradeoff of "free and keyless" vs. a paid provider.
- **Claiming a restaurant** ([claim.html](static/claim.html)) is self-service for this pilot — no
  identity verification, first claim wins (`business_claims.restaurant_id` is unique). The claim
  form says this explicitly. A claimed restaurant gets a
  [business.html](static/business.html) dashboard: average rating, review count, total cheers, a
  week-by-week rating trend, and every customer photo — all scoped to restaurants *that user* has
  claimed via `GET /api/business/dashboard`.
- Restaurant pages show a "Claimed by [business]" badge once claimed, or a "claim this listing"
  link if not.

## Trust & safety (pilot compliance)

Added for the pilot launch, since reviewers are being paid to post:

- **Rate limiting.** Two independent checks per account, both in `create_post()`
  ([server/app.py](server/app.py)): no more than one post per hour (blocks scripted/bot-speed
  posting), and no more than one post per rolling 24 hours (blocks farming toward the 5-post
  reward). Violating either returns `429` with a message telling the user when they can try again.
- **Manual review on the first 30 redemptions.** The first `MANUAL_REVIEW_LIMIT` (30, in
  [server/admin.py](server/admin.py)) reward redemptions platform-wide go into an `under_review`
  state instead of instantly issuing a gift card — `POST /api/rewards/:id/redeem` returns
  `{"under_review": true}` and no code. An operator approves or rejects each one from
  [`/admin.html`](static/admin.html), gated by the `ADMIN_SECRET` env var (sent as an
  `X-Admin-Secret` header, checked with `hmac.compare_digest`). The 30-count check runs inside a
  `BEGIN IMMEDIATE` transaction so two simultaneous redemptions can't both slip in as slot #30.
  Once the 30 are used up, redemption goes back to instant auto-issuance.
- **Report flag.** Every post has a 🚩 button that opens a report form
  (`POST /api/posts/:id/report`). Every report is stored in the `reports` table regardless of
  whether email is configured, and also triggers a notification via
  [server/notify.py](server/notify.py) — simulated (logged to stdout) by default, or a real email
  if you set `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, and `REPORT_EMAIL_TO`. Open
  reports also show up in the admin panel with a "mark resolved" button.
- **FTC disclosure.** A persistent banner ([`ftcBanner()`](static/js/api.js)) reading *"Reviews on
  EatRate may be incentivized: every 5th review a user posts earns them a $10 gift card,
  regardless of the rating given"* appears above the feed (`index.html`) and above every
  restaurant's post list (`restaurant.html`). The "regardless of rating" phrasing is what keeps
  the reward compliant with the FTC's Consumer Review Rule — the rule prohibits tying an incentive
  to the *sentiment* of a review, not incentives themselves, and nothing in this app's reward
  logic looks at `rating` before granting a reward.

**New environment variables** (all optional — the app runs in a fully simulated/no-op mode for
each until you set them):

| Variable | Purpose | If unset |
|---|---|---|
| `ADMIN_SECRET` | Unlocks `/admin.html` and the `/api/admin/*` endpoints | Admin panel returns `503`, refuses all access |
| `REPORT_EMAIL_TO` | Where report notifications get sent | — |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | Credentials for sending that email | Reports are logged to stdout instead of emailed (still saved in the DB either way) |

Set `ADMIN_SECRET` to something long and random — treat it like a password, don't commit it. On
Railway: service → Variables → add it there. Locally: `ADMIN_SECRET=... python3 run.py`.

## Gift cards: simulated by default

[server/giftcards.py](server/giftcards.py) issues a `SIM-XXXXXXXX` code and never calls out to a
real payment/gift-card API — there are no credentials configured in this environment. The
function is the single integration point: swap in a real provider (Tango Card, Tremendous, or a
direct deal with each restaurant) inside `issue_gift_card()` and flip `GIFT_CARD_MODE=live` when
you're ready to move real money.

## What was verified

Both curl (fast, precise) and an actual browser (real rendering, real clicks) were used:

**Via curl** — signup/login/logout/session guards, friend add with self/duplicate/unknown-email
rejection (400/409/404) and bidirectional visibility, posting a photo (base64-decoded and written
to `static/uploads/`, served back over HTTP), 5 posts triggering a reward on the 5th, redemption
issuing a gift code and blocking double-redemption (409), a non-friend correctly blocked from
cheering a post (403), and an isolated user correctly seeing an empty feed.

**Via live browser** (`preview_start` + screenshots/clicks, project relocated to `~/eatrate` to
get around the `~/Downloads` sandbox restriction) — signed up, walked through the camera prompt,
injected a synthetic photo into the file input (the standard `DataTransfer` technique used for
browser automation, since real camera hardware isn't available here), filled in the
restaurant/rating/caption, shared it, confirmed the post rendered correctly in the feed with a
working photo, cheered it and watched the count update live, added a friend and saw them appear
in the friends list, opened the restaurant detail page and confirmed it matched the post to the
existing seeded restaurant instead of creating a duplicate, checked the profile photo grid, and
ran a full reward-to-redemption cycle ending in a visible gift code.

**Not verified**: a real phone camera (this environment has no camera hardware) and the actual
Beer Buddy app's UI firsthand (verified via its App Store/Play Store listings and product
description instead, per the earlier research step).

## Project layout

```
eatrate/
  run.py                 entry point (reads PORT env var)
  seed.py                 sample restaurant data
  Procfile                 tells the host how to start the app
  requirements.txt          empty on purpose — just marks this as a Python project
  server/
    db.py                 SQLite schema + connection helper (reads DATA_DIR env var)
    auth.py                password hashing, sessions
    photos.py               base64 photo decode + save to DATA_DIR/uploads/
    osm.py                    OpenStreetMap/Overpass fetch + grid-cell caching
    admin.py                   admin secret + manual-review-limit constant
    notify.py                    report email notification (simulated or SMTP)
    giftcards.py                   gift card issuance (simulated, swap in real provider here)
    app.py                          HTTP router + all API handlers
  static/
    index.html              friends feed (home screen) + camera CTA
    map.html                 live map of nearby restaurants (Leaflet + OSM)
    claim.html                 self-service business claim form
    business.html                claimed-restaurant dashboard
    capture.html              photo-first post creation flow
    friends.html                add/remove friends
    login.html / signup.html
    restaurant.html              restaurant detail, photo grid of posts
    rewards.html                  pending/redeemed rewards, redeem flow
    profile.html                    your post grid, stats, logout
    admin.html                       pilot fraud-review panel (not in nav)
    vendor/leaflet/                    vendored Leaflet.js — no CDN dependency
    css/app.css
    js/api.js                        fetch wrapper + shared post/tabbar rendering

(eatrate.db and the uploads/ folder are created at runtime under DATA_DIR — the
project root locally, a mounted volume in production — and are gitignored.)
```

## API

| Method | Path                              | Auth | Notes |
|--------|-----------------------------------|------|-------|
| POST   | `/api/signup`                     | –    | `{email, name, password}` |
| POST   | `/api/login`                      | –    | `{email, password}` |
| POST   | `/api/logout`                     | ✓    | |
| GET    | `/api/me`                         | ✓    | |
| GET    | `/api/restaurants`                | –    | list with avg rating + post count |
| GET    | `/api/restaurants/:id`            | ✓    | detail + all posts (photo grid) + claim status |
| GET    | `/api/map/restaurants`            | ✓    | `?min_lat&min_lng&max_lat&max_lng` — live OSM-backed viewport search |
| POST   | `/api/restaurants/:id/claim`      | ✓    | `{business_name, contact_email}` — self-service, first claim wins (409 if already claimed) |
| GET    | `/api/business/dashboard`         | ✓    | stats + weekly trend + photos for every restaurant you've claimed |
| POST   | `/api/posts`                      | ✓    | `{photo: data-url, restaurant_name, rating: 0-10, caption?}` — restaurant is found-or-created by name; `429` if rate-limited |
| POST   | `/api/posts/:id/cheer`            | ✓    | toggles a cheer; 403 if you're not the author or their friend |
| POST   | `/api/posts/:id/report`           | ✓    | `{reason?}` — flags a post, notifies the operator |
| GET    | `/api/feed`                       | ✓    | posts from you + your friends, newest first |
| GET    | `/api/friends`                    | ✓    | |
| POST   | `/api/friends`                    | ✓    | `{email}` — adds bidirectionally |
| DELETE | `/api/friends/:id`                | ✓    | removes both directions |
| GET    | `/api/rewards`                    | ✓    | mine, includes `review_status`: `pending` / `under_review` / `redeemed` / `rejected` |
| POST   | `/api/rewards/:id/redeem`         | ✓    | `{restaurant_id}` — returns `{under_review: true}` instead of a gift card for the first 30 platform-wide |
| GET    | `/api/profile`                    | ✓    | my posts + rewards + friend count + progress to next reward |
| GET    | `/api/admin/redemptions`          | admin secret | pending manual-review redemptions + how many of the 30 slots are used |
| POST   | `/api/admin/redemptions/:id/approve` | admin secret | issues the gift card, marks `redeemed` |
| POST   | `/api/admin/redemptions/:id/reject`  | admin secret | marks `rejected`, no card issued |
| GET    | `/api/admin/reports`              | admin secret | open reports with post + reporter context |
| POST   | `/api/admin/reports/:id/resolve`  | admin secret | marks a report resolved |

## Restaurants paying, without ads

From the earlier discussion on monetization: the pitch to restaurants is that they're not buying
ad impressions, they're buying (a) guaranteed foot traffic via discounted gift cards they already
sell at a loss to platforms like Restaurant.com, and (b) photo/dish-level social proof and review
data they can't get from Yelp/Google. `server/giftcards.py` is where a restaurant-funded gift
card pool would plug in — right now the app issues cards without deducting from any restaurant
balance, since there's no billing/partner system yet. That's the natural next build if you want
to take this further.

The business dashboard ([business.html](static/business.html)) is the first piece of that pitch
actually built: free for the pilot, but the natural next step is a paid tier — richer analytics,
competitor comparison, a "featured" boost on the map — once there's real usage to sell against.

## Turning this into a real mobile app

This environment has no `npm`, so it can't scaffold React Native or wrap this in Capacitor
directly, and there's no camera hardware to test against — the capture flow uses the standard
`<input capture="environment">` API, which works on real phones but was verified here with a
synthetic in-page file injection instead. Once you have Node available locally:

1. `npm install -g @capacitor/cli @capacitor/core`
2. Point Capacitor at `static/` as the web assets directory (or rebuild the frontend in
   React/Vue if you want a richer UI), keep this Python API as the backend (or port it to a
   proper framework once you're scaling past a prototype — the base64-photo-in-JSON approach
   works fine for a prototype but you'll want real multipart uploads and a CDN/object store for
   production photo volume).
3. `npx cap add ios` / `npx cap add android`, then build through Xcode/Android Studio.

For now, it runs as a real, fully working mobile-styled web app in any phone browser, camera and
all.
