"""
Scrapes a restaurant's own website for its real logo, since that's
consistently better than a generic favicon lookup — most sites declare a
proper icon via <link rel="apple-touch-icon"> (sized for actual use, unlike
the 16x16 .ico browsers historically used for tab icons) or an og:image
social-share image, either of which tends to be the real brand mark rather
than whatever a favicon-guessing service can find.

Used by GET /api/restaurants/:id/logo (server/app.py), which caches the
result to disk so this scrape happens once per restaurant, not on every
page view. Raises LogoFetchError (caller falls back to the Google favicon
lookup client-side) if the site can't be reached in time or has no
discoverable icon — this is a best-effort upgrade, not a required source.
"""

import urllib.parse
import urllib.request
from html.parser import HTMLParser

REQUEST_TIMEOUT = 2.5  # scraping an arbitrary restaurant's website is
# best-effort — fail fast so one slow site doesn't hang the request; the
# client falls back to the favicon lookup on any failure anyway. A single
# logo fetch can make up to 2 requests (HTML page, then the image itself)
# against up to 2 domain candidates (see _get_or_fetch_logo's base-domain
# retry in server/app.py), so this bounds a single live user-facing image
# load to at most ~4x this value even in the worst case
MAX_HTML_BYTES = 300_000  # the icon we want is always in <head>; no need
# to download an entire bloated page to find it
MAX_IMAGE_BYTES = 2_000_000


class LogoFetchError(Exception):
    pass


class _IconParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.apple_touch_icon = None
        self.og_image = None
        self.icon = None
        self._done = False

    def handle_starttag(self, tag, attrs):
        if self._done:
            return
        attrs = dict(attrs)
        if tag == "body":
            self._done = True
        elif tag == "link":
            rel = (attrs.get("rel") or "").lower()
            href = attrs.get("href")
            if href and "apple-touch-icon" in rel and not self.apple_touch_icon:
                self.apple_touch_icon = href
            elif href and rel == "icon" and not self.icon:
                self.icon = href
        elif tag == "meta":
            prop = (attrs.get("property") or attrs.get("name") or "").lower()
            content = attrs.get("content")
            if prop == "og:image" and content and not self.og_image:
                self.og_image = content

    def handle_endtag(self, tag):
        if tag == "head":
            self._done = True


def _get(url, accept_html=False):
    req = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0 (compatible; EatRateLogoFetcher/1.0)"}
    )
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            data = resp.read(MAX_HTML_BYTES if accept_html else MAX_IMAGE_BYTES)
            return resp.geturl(), resp.headers.get("Content-Type", ""), data
    except (OSError, ValueError) as e:
        raise LogoFetchError(str(e))


def fetch_logo_bytes(domain):
    """Returns (content_type, image_bytes) for the best icon found on
    https://{domain}. Raises LogoFetchError if the site is unreachable or
    has no apple-touch-icon, og:image, or icon link in its <head>."""
    final_url, _, html_bytes = _get(f"https://{domain}", accept_html=True)
    html = html_bytes.decode("utf-8", errors="ignore")

    parser = _IconParser()
    try:
        parser.feed(html)
    except Exception:
        pass  # malformed HTML — use whatever was parsed before it broke

    candidate = parser.apple_touch_icon or parser.og_image or parser.icon
    if not candidate:
        raise LogoFetchError(f"No logo/icon declared on {domain}")

    image_url = urllib.parse.urljoin(final_url, candidate)
    _, content_type, data = _get(image_url)
    if not content_type.startswith("image/") or len(data) < 100:
        raise LogoFetchError(f"Logo URL for {domain} wasn't a usable image")

    return content_type, data
