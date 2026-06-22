"""Shared photo gallery — both partners upload pictures, both see them.

Photos are compressed (resized + JPEG) and stored base64-encoded in the shared
vault under the hidden `photos/` namespace, so they live in the same Supabase
table as everything else (no extra storage setup) and sync between both users.
Compression keeps each image small enough to store and load comfortably.

For a very large gallery, migrating to Supabase Storage (object storage + URLs)
would be the next step — noted as Future Work.
"""

from __future__ import annotations

import base64
import io
from datetime import date, datetime

from . import ingest, repo, tools

PHOTO_DIR = "photos/"
_MAX_DIM = 1280       # longest side, px
_JPEG_QUALITY = 82

# Themed albums shown as the clickable cards on the Us page.
ALBUMS = ["us", "for you", "love notes", "our sunsets", "celebrations", "cuddles"]
ALBUM_EMOJI = {
    "us": "💑", "for you": "🌹", "love notes": "💌",
    "our sunsets": "🌅", "celebrations": "🥂", "cuddles": "🧸",
    "general": "📸",
}


def _compress(data: bytes) -> bytes:
    """Resize to <= _MAX_DIM on the long side and re-encode as JPEG."""
    from PIL import Image, ImageOps

    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)        # honor phone rotation EXIF
    img = img.convert("RGB")
    img.thumbnail((_MAX_DIM, _MAX_DIM))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=_JPEG_QUALITY, optimize=True)
    return out.getvalue()


def add_photo(data: bytes, by: str, caption: str = "", album: str = "general") -> str:
    """Add a photo (raw bytes) to a themed album. Returns the note path.

    The album is encoded into the path (photos/<album>/...) so albums can be
    listed and counted cheaply without downloading image data.
    """
    if not data:
        raise ValueError("Empty image.")
    album = (album or "general").strip()
    album_slug = tools._slugify(album)
    jpeg = _compress(data)
    b64 = base64.b64encode(jpeg).decode("ascii")
    stamp = datetime.now().strftime("%H%M%S%f")
    rel = (
        f"{PHOTO_DIR}{album_slug}/"
        f"{date.today().isoformat()}-{tools._slugify(by)}-{stamp}.md"
    )
    safe_caption = " ".join(caption.split())  # keep front-matter single-line
    content = (
        f"---\ntype: photo\nby: {by}\ncategory: {album}\ncaption: {safe_caption}\n"
        f"date: {date.today().isoformat()}\nmime: image/jpeg\n---\n\n{b64}\n"
    )
    return repo.get_repo().save(rel, content)


def list_photos(limit: int | None = None, album: str | None = None) -> list[dict]:
    """Gallery photos newest-first: {path, by, caption, album, date, data(bytes)}.

    `album` filters to one themed album; `limit` fetches only the most recent N
    (used by the Us-page preview so it doesn't pull the whole gallery's data).
    """
    prefix = PHOTO_DIR
    if album:
        prefix = f"{PHOTO_DIR}{tools._slugify(album)}/"
    out: list[dict] = []
    # notes_under already returns newest-first (by modified time).
    for rec in repo.get_repo().notes_under(prefix, limit=limit, newest_first=True):
        f = tools._front_matter_fields(rec.content)
        b64 = ingest._strip_frontmatter(rec.content).strip()
        try:
            data = base64.b64decode(b64)
        except (ValueError, base64.binascii.Error):
            continue
        out.append(
            {
                "path": rec.path,
                "by": f.get("by", "?"),
                "caption": f.get("caption", ""),
                "album": f.get("category", ""),
                "date": f.get("date", ""),
                "data": data,
            }
        )
    return out


def album_counts() -> dict:
    """Photo count per album — cheap (uses path list only, no image data)."""
    paths = repo.get_repo().list_paths()
    counts: dict = {}
    for name in ALBUMS + ["general"]:
        pre = f"{PHOTO_DIR}{tools._slugify(name)}/"
        counts[name] = sum(1 for p in paths if p.startswith(pre))
    return counts


def delete_photo(path: str) -> None:
    repo.get_repo().delete(path)
