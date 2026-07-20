import base64
import re
import uuid

from server.db import UPLOADS_DIR

MAX_PHOTO_BYTES = 8 * 1024 * 1024  # 8MB
DATA_URL_RE = re.compile(r"^data:image/(?P<ext>jpeg|jpg|png|webp|gif);base64,(?P<data>.+)$", re.S)


class PhotoError(Exception):
    pass


def save_photo(data_url: str) -> str:
    """Decode a data: URL image and save it to static/uploads. Returns the
    web-servable relative path (e.g. "uploads/abc123.jpg")."""
    if not data_url or not isinstance(data_url, str):
        raise PhotoError("A photo is required.")

    match = DATA_URL_RE.match(data_url.strip())
    if not match:
        raise PhotoError("Photo must be a base64-encoded image (jpeg/png/webp/gif).")

    ext = match.group("ext")
    if ext == "jpg":
        ext = "jpeg"

    try:
        raw = base64.b64decode(match.group("data"), validate=True)
    except Exception:
        raise PhotoError("Photo data is not valid base64.")

    if len(raw) == 0:
        raise PhotoError("Photo is empty.")
    if len(raw) > MAX_PHOTO_BYTES:
        raise PhotoError("Photo is too large (max 8MB).")

    filename = f"{uuid.uuid4().hex}.{ext}"
    with open(f"{UPLOADS_DIR}/{filename}", "wb") as f:
        f.write(raw)

    return f"uploads/{filename}"
