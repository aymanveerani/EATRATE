import hmac
import os

ADMIN_SECRET = os.environ.get("ADMIN_SECRET")

# First N reward redemptions are held for a human to eyeball before the gift
# card is issued — the fraud check the pilot runs by hand anyway.
MANUAL_REVIEW_LIMIT = 30

# Redemption is switched off until the soft-launch partner restaurant list is
# decided — set REDEMPTION_ENABLED=true when that's ready. Users still earn
# and see rewards; they just can't redeem one yet. Set via env var so this
# can flip on later without a code change.
REDEMPTION_ENABLED = os.environ.get("REDEMPTION_ENABLED", "false").strip().lower() == "true"
