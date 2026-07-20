"""
Generates a short, restaurant-specific insights summary for the business
dashboard from real review data (ratings + captions).

Runs in a SIMULATED mode by default — a heuristic summary computed straight
from the review data, no API cost, no credentials needed. Set
ANTHROPIC_API_KEY to generate real AI-written insights via the Claude API
instead, the same simulated/live pattern as server/giftcards.py and
server/notify.py.
"""

import json
import os
import urllib.request

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"


def _heuristic_insights(restaurant_name, posts):
    if not posts:
        return "No reviews yet — insights will appear once customers start posting."

    ratings = [p["rating"] for p in posts]
    avg = sum(ratings) / len(ratings)

    trend = ""
    if len(posts) >= 4:
        recent = ratings[: len(ratings) // 2]
        older = ratings[len(ratings) // 2 :]
        recent_avg = sum(recent) / len(recent)
        older_avg = sum(older) / len(older)
        if recent_avg - older_avg >= 0.5:
            trend = " Recent reviews are trending higher than earlier ones."
        elif older_avg - recent_avg >= 0.5:
            trend = " Recent reviews are trending lower than earlier ones — worth a look."

    word_counts = {}
    for p in posts:
        for word in (p["caption"] or "").lower().split():
            word = "".join(c for c in word if c.isalpha())
            if len(word) > 3:
                word_counts[word] = word_counts.get(word, 0) + 1
    top_words = sorted(word_counts.items(), key=lambda kv: -kv[1])[:3]
    mentions = ", ".join(f'"{w}"' for w, _ in top_words) if top_words else None

    summary = (
        f"{restaurant_name} is averaging {avg:.1f}/10 across "
        f"{len(posts)} review{'s' if len(posts) != 1 else ''}.{trend}"
    )
    if mentions:
        summary += f" Frequently mentioned in reviews: {mentions}."
    return summary


def _claude_insights(restaurant_name, posts):
    review_lines = "\n".join(f"- {p['rating']}/10: {p['caption'] or '(no comment)'}" for p in posts[:40])
    prompt = (
        f'You\'re writing a short insights summary for the owner of "{restaurant_name}" based on '
        f"real customer reviews below. In 2-3 sentences, summarize what customers like, flag any "
        f"recurring complaint if there is one, and keep it specific and actionable. Don't invent "
        f"details that aren't in the reviews.\n\nReviews:\n{review_lines}"
    )
    body = json.dumps(
        {"model": ANTHROPIC_MODEL, "max_tokens": 300, "messages": [{"role": "user", "content": prompt}]}
    ).encode("utf-8")
    req = urllib.request.Request(
        ANTHROPIC_URL,
        data=body,
        headers={
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        result = json.loads(resp.read().decode("utf-8"))
    return result["content"][0]["text"].strip()


def generate_insights(restaurant_name, posts):
    """posts: sqlite3.Row list with at least 'rating' and 'caption' columns."""
    if ANTHROPIC_API_KEY:
        try:
            return _claude_insights(restaurant_name, posts)
        except Exception as e:
            print(f"[WARN] AI insights API call failed, falling back to heuristic: {e}", flush=True)
    return _heuristic_insights(restaurant_name, posts)
