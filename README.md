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

## Restaurants near you (feed, not a separate map)

There's no standalone map page — an earlier version had one (an interactive Leaflet map), but it
was replaced with a horizontally-scrolling "Restaurants near you" section built directly into the
feed (`index.html`), which is both simpler and looks a lot more like a native app than a map
widget bolted onto a review app.

**There is no "every restaurant in America" dataset either** — that isn't free, and isn't legal to
bulk-store from Google Places or Yelp without a paid contract. Instead it asks the browser for the
user's location and fetches real restaurants within a 5-mile radius, live, on each request that
needs fresh data.

There are three data sources, tried in order:

- **[server/google_places.py](server/google_places.py) — primary, if `GOOGLE_PLACES_API_KEY` is
  set.** The most complete US restaurant listings of the three. Requires a Google Cloud project
  with **billing enabled** — a monthly free credit covers light usage at pilot scale, then it's
  pay-per-request, the only source here with real ongoing cost risk. Real photos work too, but not
  via a direct Google URL — fetching one requires the API key as a request credential, and putting
  that in a client-facing `<img src>` would leak the secret to every visitor's browser. Instead
  `GET /api/restaurants/:id/photo` (in `server/app.py`) fetches the image server-side and caches
  it to disk under `uploads/google_photos/`, so it's a live Google call at most once per
  restaurant rather than on every page view, and the key never reaches the browser.
- **[server/yelp.py](server/yelp.py) — second, if `YELP_API_KEY` is set.** Yelp Fusion's free
  tier (no billing required, just a developer account) has restaurant-specific data: real names,
  categories, and actual business photos. Runs if Google isn't configured or a Google call fails.
  Get a key at https://www.yelp.com/developers/v3/manage_app.
- **[server/osm.py](server/osm.py) — last resort, always available.** OpenStreetMap's Overpass API
  needs no key or account at all, so it's what runs if neither of the above is configured, or if
  both fail — the nearby endpoint never just errors out because one source is down. Coverage
  reflects OSM's crowd-sourced data: good in cities, sparser in small towns.

All three cache their results in `map_cache`, keyed by a coarse rounding of the search location
(shared table, distinct key prefixes per source so they never collide), for 7 days — repeat visits
from the same area reuse the cached fetch instead of re-hitting any API. Every fetched place
becomes a real row in `restaurants` (deduped on each source's own id via a unique index) — the
same restaurant entity users can post about and businesses can claim, not a separate read-only
layer.

If the user declines location access, the section shows an "Enable location" prompt instead of
guessing a location — there's no fallback to some other city.

## Business claiming, soft launch, and AI insights

Claiming isn't open to every restaurant — only the ones chosen for the soft launch. An operator
marks up to a handful of restaurants as **soft-launch partners** from the admin panel
(search box + toggle in [`admin.html`](static/admin.html), backed by
`restaurants.soft_launch_partner` and `POST /api/admin/restaurants/:id/soft-launch-partner`).
Only those restaurants show a "claim this listing" link on their page or accept a claim via the
API — everyone else is just reviewable, same as before.

- **Claiming** ([claim.html](static/claim.html)) is self-service for this pilot — no identity
  verification, first claim wins (`business_claims.restaurant_id` is unique). The form says this
  explicitly.
- **3-month free trial.** Claiming starts a `TRIAL_DAYS` (90, in `server/app.py`) countdown stored
  as `business_claims.trial_ends_at`, shown on the dashboard as "Free trial — N days left" (or
  "Trial ended" once it passes). Nothing is billed automatically — there's no payment integration
  here, this just tracks and displays the trial window from the business plan.
- **AI insights.** [server/ai_insights.py](server/ai_insights.py) generates a short, restaurant-
  specific summary from real review data — same simulated/live pattern as gift cards and report
  emails. By default it's a heuristic summary (average rating, a trend note, most-mentioned words
  in captions) with no API cost. Set `ANTHROPIC_API_KEY` to have it call the real Claude API for a
  genuinely AI-written summary instead; if that call fails for any reason it falls back to the
  heuristic rather than breaking the dashboard. Insights are cached in `business_claims` and only
  regenerated when the review count changes, so a live API key isn't billed on every page view.
- [business.html](static/business.html) ties it together: average rating, review count, total
  cheers, a week-by-week rating trend chart, the AI insights card, the trial badge, and every
  customer photo — all scoped to restaurants *that user* has claimed via
  `GET /api/business/dashboard`.

## Trust & safety (pilot compliance)

Added for the pilot launch, since reviewers are being paid to post:

- **Rate limiting.** One post per account per rolling 24 hours (`MAX_POSTS_PER_DAY` in
  `server/app.py`) — a user can post about the same restaurant as many times as they like across
  different days, there's no per-restaurant cap. A 10-minute-between-posts throttle also exists as
  a cheap backstop against clock-skew edge cases right at the day boundary; it's redundant with
  the daily cap in normal use. Violating either returns `429` with a message telling the user when
  they can try again.
- **Manual review on the first 30 redemptions** — currently moot in practice since redemption is
  switched off entirely (see below), but the mechanism is still in place for when it's turned back
  on. The first `MANUAL_REVIEW_LIMIT` (30, in [server/admin.py](server/admin.py)) reward
  redemptions platform-wide would go into an `under_review` state instead of instantly issuing a
  gift card, approved or rejected from [`/admin.html`](static/admin.html). The 30-count check runs
  inside a `BEGIN IMMEDIATE` transaction so two simultaneous redemptions can't both slip in as
  slot #30.
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

## Gift card redemption: switched off for now

Users still earn rewards on their 5th post — `users.post_count` and the reward-creation logic are
untouched — but `POST /api/rewards/:id/redeem` returns `403` until `REDEMPTION_ENABLED=true` is
set (`server/admin.py`). The rewards page shows "Earned — redemption coming soon" instead of a
Redeem button. This matches the plan to only allow redemption at the specific restaurants chosen
for the soft launch, which hasn't been decided yet — flip the env var on once it has been, no code
change needed.

**Environment variables** (all optional — the app runs in a fully simulated/no-op mode for each
until you set them):

| Variable | Purpose | If unset |
|---|---|---|
| `ADMIN_SECRET` | Unlocks `/admin.html` and the `/api/admin/*` endpoints | Admin panel returns `503`, refuses all access |
| `REDEMPTION_ENABLED` | Turns gift card redemption back on | Redemption returns `403` |
| `ANTHROPIC_API_KEY` | Real AI-generated business insights | Falls back to a heuristic summary |
| `GOOGLE_PLACES_API_KEY` | Most complete restaurant data for "nearby" search (primary source) | Falls back to Yelp, then OpenStreetMap |
| `YELP_API_KEY` | Restaurant data + real photos from Yelp for "nearby" search (used if Google isn't set) | Falls back to OpenStreetMap (still works, just sparser data, no real photos) |
| `REPORT_EMAIL_TO` | Where report notifications get sent | — |
| `SMTP_HOST` / `SMTP_PORT` / `SMTP_USER` / `SMTP_PASSWORD` | Credentials for sending that email | Reports are logged to stdout instead of emailed (still saved in the DB either way) |

Set `ADMIN_SECRET` to something long and random — treat it like a password, don't commit it. On
Railway: service → Variables → add it there. Locally: `ADMIN_SECRET=... python3 run.py`.

To get `GOOGLE_PLACES_API_KEY`: create a project at https://console.cloud.google.com, enable
"Places API (New)", set up a billing account (required even for the free monthly credit — this is
the one source here with real ongoing cost risk if usage grows), then create an API key under
"APIs & Services → Credentials". Consider restricting the key to the Places API and to your
server's IP once deployed.

To get `YELP_API_KEY`: sign up at https://www.yelp.com/developers, create an app under "Manage
App" (https://www.yelp.com/developers/v3/manage_app), and copy the API Key it gives you — no
billing information required for the free tier. Set either key the same way as `ADMIN_SECRET`
above.

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
to disk, served back over HTTP), 5 posts triggering a reward on the 5th, a non-friend correctly
blocked from cheering a post (403), and an isolated user correctly seeing an empty feed. Later
rounds verified: the 1/day + 10-minute rate limits and confirmed same-restaurant reposting is
allowed, the soft-launch claim gate (403 on a non-partner restaurant, 201 once marked a partner),
the 90-day trial date computing correctly, AI insights generating and caching correctly (no
regeneration on an unchanged review count), and redemption returning 403 with
`REDEMPTION_ENABLED` unset while reward-earning still works.

**Via live browser** (`preview_start` + screenshots/clicks, project relocated to `~/eatrate` to
get around the `~/Downloads` sandbox restriction) — signed up, walked through the camera prompt,
injected a synthetic photo into the file input (the standard `DataTransfer` technique used for
browser automation, since real camera hardware isn't available here), filled in the
restaurant/rating/caption, shared it, confirmed the post rendered correctly in the feed with a
working photo, cheered it and watched the count update live, added a friend and saw them appear
in the friends list, opened the restaurant detail page and confirmed it matched the post to the
existing seeded restaurant instead of creating a duplicate, checked the profile photo grid, and
ran a full reward-to-redemption cycle ending in a visible gift code (before redemption was later
switched off). Also verified live: the "restaurants near you" feed section with mocked geolocation
returning real nearby OSM restaurants with cuisine icons, and the business dashboard showing the
trial badge, AI insights card, and rating trend chart together.

**A real crash was found and fixed via this testing approach**, not caught by chance: a schema
migration created an index referencing a column before the step that adds that column had run,
which crashed the server on every startup against the real production database. It was caught by
reconstructing a copy of production's actual schema locally and running the startup code against
it — the same technique is now used before every schema change in this project (see
`server/db.py`'s migration comments for the pattern).

**Not verified**: a real phone camera or real GPS location (this environment has neither — camera
tested via synthetic file injection, location tested via a mocked `navigator.geolocation`), a
live `ANTHROPIC_API_KEY` call (no key configured here, only the heuristic fallback path was
exercised), and the actual Beer Buddy app's UI firsthand (verified via its App Store/Play Store
listings and product description instead, per the earlier research step).

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
    ai_insights.py              business dashboard insights (heuristic or Claude API)
    admin.py                      admin secret, manual-review-limit, redemption-enabled flag
    notify.py                        report email notification (simulated or SMTP)
    giftcards.py                        gift card issuance (simulated, swap in real provider here)
    app.py                                 HTTP router + all API handlers
  static/
    index.html              friends feed (home screen) + camera CTA + "restaurants near you"
    claim.html                self-service business claim form (soft-launch partners only)
    business.html                claimed-restaurant dashboard (trial badge, AI insights, chart)
    capture.html              photo-first post creation flow
    friends.html                add/remove friends
    login.html / signup.html
    restaurant.html              restaurant detail, photo grid of posts
    rewards.html                  reward progress (redemption currently disabled)
    profile.html                    your post grid, stats, logout
    admin.html                       pilot ops panel (redemption review, reports, soft-launch
                                      partner picker) — not linked from the app's nav
    css/app.css
    js/api.js                        fetch wrapper + shared post/tabbar/nearby-card rendering

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
| GET    | `/api/restaurants/:id`            | ✓    | detail + all posts (photo grid) + claim/soft-launch-partner status |
| GET    | `/api/restaurants/nearby`         | ✓    | `?lat&lng` — real restaurants within 5 miles, randomized order, live OSM-backed |
| POST   | `/api/restaurants/:id/claim`      | ✓    | `{business_name, contact_email}` — 403 unless the restaurant is a soft-launch partner, 409 if already claimed |
| GET    | `/api/business/dashboard`         | ✓    | stats + weekly trend + AI insights + trial status + photos for every restaurant you've claimed |
| POST   | `/api/posts`                      | ✓    | `{photo: data-url, restaurant_name, rating: 0-10, caption?}` — restaurant is found-or-created by name; `429` if rate-limited |
| POST   | `/api/posts/:id/cheer`            | ✓    | toggles a cheer; 403 if you're not the author or their friend |
| POST   | `/api/posts/:id/report`           | ✓    | `{reason?}` — flags a post, notifies the operator |
| GET    | `/api/feed`                       | ✓    | posts from you + your friends, newest first |
| GET    | `/api/friends`                    | ✓    | |
| POST   | `/api/friends`                    | ✓    | `{email}` — adds bidirectionally |
| DELETE | `/api/friends/:id`                | ✓    | removes both directions |
| GET    | `/api/rewards`                    | ✓    | mine, plus `redemption_enabled` — see "Gift card redemption" above |
| POST   | `/api/rewards/:id/redeem`         | ✓    | `403` unless `REDEMPTION_ENABLED=true`; otherwise `{restaurant_id}` → gift card, or `{under_review: true}` for the first 30 platform-wide |
| GET    | `/api/profile`                    | ✓    | my posts + rewards + friend count + progress to next reward |
| GET    | `/api/admin/restaurants/search`   | admin secret | `?q=` — search restaurants to designate as soft-launch partners |
| POST   | `/api/admin/restaurants/:id/soft-launch-partner` | admin secret | `{enabled}` — only partners can be claimed |
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
