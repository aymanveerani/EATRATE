import hmac
import os

ADMIN_SECRET = os.environ.get("ADMIN_SECRET")

# First N reward redemptions are held for a human to eyeball before the gift
# card is issued — the fraud check the pilot runs by hand anyway.
MANUAL_REVIEW_LIMIT = 30
