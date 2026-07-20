"""
Gift card issuance.

Runs in SIMULATED mode by default (no external API calls, no credentials
needed) so the app is fully testable offline. To go live, plug a real
provider (e.g. Tango Card / Tremendous) into `issue_gift_card` below and
set GIFT_CARD_MODE=live via environment variable.
"""

import os
import secrets

GIFT_CARD_MODE = os.environ.get("GIFT_CARD_MODE", "simulated")


def issue_gift_card(restaurant_name: str, amount_cents: int) -> dict:
    if GIFT_CARD_MODE == "live":
        raise NotImplementedError(
            "Live gift card issuance is not configured. Wire up a provider "
            "(Tango Card / Tremendous API) here before setting GIFT_CARD_MODE=live."
        )

    code = "SIM-" + secrets.token_hex(4).upper()
    return {
        "mode": "simulated",
        "code": code,
        "amount_cents": amount_cents,
        "restaurant_name": restaurant_name,
        "note": "Simulated reward — no real money moved. Swap in a live provider for production.",
    }
