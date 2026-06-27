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

from functools import lru_cache

from . import config, ingest, repo, tools

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


# --- Semantic photo search (CLIP) ---------------------------------------------
# Search the gallery by description ("us at the beach") using a free CLIP model
# that maps images and text into one space. Flag-gated (PHOTO_SEARCH) + lazy +
# cached, so it never loads on the low-RAM cloud deploy unless turned on. When
# off/unavailable it gracefully falls back to caption keyword matching.

@lru_cache(maxsize=1)
def _clip():
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(config.CLIP_MODEL)


# path -> image embedding (kept across reruns within a process).
_PHOTO_EMB: dict[str, list[float]] = {}


def _caption_search(query: str, photos: list[dict], k: int) -> list[dict]:
    terms = [t for t in query.lower().split() if t]
    scored = []
    for p in photos:
        hay = f"{p['caption']} {p['album']} {p['by']}".lower()
        score = sum(1 for t in terms if t in hay)
        if score:
            scored.append((score, p))
    scored.sort(key=lambda s: s[0], reverse=True)
    return [p for _, p in scored[:k]]


def search_photos(query: str, k: int = 12) -> list[dict]:
    """Find photos matching a text description. Returns the photo dicts + score.

    Uses CLIP when PHOTO_SEARCH is enabled; otherwise (or if the model can't
    load) falls back to matching the query against captions/albums.
    """
    photos = list_photos()
    if not photos:
        return []

    if not config.PHOTO_SEARCH:
        return _caption_search(query, photos, k)

    try:
        import numpy as np
        from PIL import Image

        model = _clip()
        # Embed any photos we haven't seen yet (cached by path).
        todo = [p for p in photos if p["path"] not in _PHOTO_EMB]
        if todo:
            imgs = [Image.open(io.BytesIO(p["data"])).convert("RGB") for p in todo]
            vecs = model.encode(imgs, normalize_embeddings=True)
            for p, v in zip(todo, vecs):
                _PHOTO_EMB[p["path"]] = [float(x) for x in v]

        q = np.asarray(model.encode([query], normalize_embeddings=True)[0], "float32")
        ranked = sorted(
            photos,
            key=lambda p: float(np.asarray(_PHOTO_EMB[p["path"]], "float32") @ q),
            reverse=True,
        )
        out = []
        for p in ranked[:k]:
            p = dict(p)
            p["score"] = round(
                float(np.asarray(_PHOTO_EMB[p["path"]], "float32") @ q), 4
            )
            out.append(p)
        return out
    except Exception:
        return _caption_search(query, photos, k)
