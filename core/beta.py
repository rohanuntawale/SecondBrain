"""Beta feature layer — experimental-but-functional extras.

These build on the existing brain (notes, diary, photos, couple data) without
disturbing the core pipeline. Everything here degrades gracefully when an LLM
or optional model is unavailable, so the page stays usable on the low-RAM
cloud deploy. Surfaced in the app's 🧪 Beta page and over MCP.

Grouped into two families:

  💞 For the two of you  — time capsules, gratitude jar, mood correlation,
                           "how well do you know me" quiz, year-in-review,
                           journaling prompts.
  🧠 Smarter brain       — weekly retrospective, stale-note resurfacing,
                           unified note+photo search, calendar (.ics) export,
                           AI photo-caption suggestions.

Storage reuses the shared vault (Markdown notes with YAML front-matter) under
hidden namespaces (capsule/, gratitude/) so nothing leaks into RAG or listings.
"""

from __future__ import annotations

import json
import math
import re
from datetime import date, datetime, timedelta, timezone

from . import couple, ingest, llm, photos, repo, store, tools

# ============================================================================
# 💞  FOR THE TWO OF YOU
# ============================================================================

# --- Time capsule: write a note that stays sealed until a future date --------

CAPSULE_DIR = "capsule/"


def add_time_capsule(
    sender: str, recipient: str, message: str, unlock_date: str
) -> str:
    """Seal a message that only opens on/after `unlock_date` (ISO YYYY-MM-DD).

    Stored under the hidden capsule/ namespace so it never shows up in search or
    note listings. The recipient can read it once the unlock date arrives.
    Returns the note path.
    """
    message = message.strip()
    if not message:
        raise ValueError("Write something to seal away first 💌")
    try:
        unlock = date.fromisoformat(unlock_date)
    except ValueError as e:
        raise ValueError(f"Unlock date must be YYYY-MM-DD: {e}") from e
    stamp = datetime.now().strftime("%H%M%S")
    rel = (
        f"{CAPSULE_DIR}{unlock.isoformat()}-{tools._slugify(sender)}-{stamp}.md"
    )
    content = (
        f"---\ntype: capsule\nfrom: {sender}\nto: {recipient}\n"
        f"unlock: {unlock.isoformat()}\ncreated: {date.today().isoformat()}\n---\n\n"
        f"{message}\n"
    )
    return repo.get_repo().save(rel, content)


def list_time_capsules(
    recipient: str | None = None,
    include_sealed: bool = True,
    today: date | None = None,
) -> list[dict]:
    """Time capsules. Unlocked ones expose their message; sealed ones do not.

    Each item: {path, from, to, unlock, created, unlocked(bool), days_left,
    message}. The `message` is "" while still sealed (so the surprise is kept).
    Set `include_sealed=False` to return only opened capsules.
    """
    today = today or date.today()
    out: list[dict] = []
    for rec in repo.get_repo().notes_under(CAPSULE_DIR):
        f = tools._front_matter_fields(rec.content)
        if recipient and f.get("to", "").lower() != recipient.lower():
            continue
        try:
            unlock = date.fromisoformat(f.get("unlock", ""))
        except ValueError:
            continue
        unlocked = today >= unlock
        if not unlocked and not include_sealed:
            continue
        out.append(
            {
                "path": rec.path,
                "from": f.get("from", "?"),
                "to": f.get("to", "?"),
                "unlock": unlock.isoformat(),
                "created": f.get("created", ""),
                "unlocked": unlocked,
                "days_left": max((unlock - today).days, 0),
                "message": ingest._strip_frontmatter(rec.content).strip()
                if unlocked
                else "",
            }
        )
    out.sort(key=lambda c: c["unlock"])
    return out


# --- Gratitude jar: a running list of little appreciations --------------------

GRATITUDE_DIR = "gratitude/"


def add_gratitude(author: str, text: str) -> str:
    """Drop one appreciation into the shared gratitude jar. Returns the path."""
    text = text.strip()
    if not text:
        raise ValueError("Add something you're grateful for 💛")
    stamp = datetime.now().strftime("%H%M%S")
    rel = (
        f"{GRATITUDE_DIR}{date.today().isoformat()}-"
        f"{tools._slugify(author)}-{stamp}.md"
    )
    content = (
        f"---\ntype: gratitude\nby: {author}\n"
        f"date: {date.today().isoformat()}\n---\n\n{text}\n"
    )
    return repo.get_repo().save(rel, content)


def list_gratitude(limit: int | None = None) -> list[dict]:
    """Gratitude entries newest-first: {path, by, date, text}."""
    out: list[dict] = []
    for rec in repo.get_repo().notes_under(GRATITUDE_DIR, newest_first=True):
        f = tools._front_matter_fields(rec.content)
        out.append(
            {
                "path": rec.path,
                "by": f.get("by", "?"),
                "date": f.get("date", ""),
                "text": ingest._strip_frontmatter(rec.content).strip(),
            }
        )
    return out[:limit] if limit else out


# --- Mood correlation: do your moods move together? ---------------------------

_WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    """Pearson correlation of two equal-length series, or None if undefined."""
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def mood_correlation() -> dict:
    """Cross-author mood stats over diary moods (no LLM — always works).

    Returns {by_author, by_weekday, correlation, n_shared, happiest_weekday,
    summary}. `correlation` is Pearson r over days both partners logged a mood.
    """
    rows = couple.mood_series()  # [{date, author, score}]
    if not rows:
        return {
            "by_author": {},
            "by_weekday": {},
            "correlation": None,
            "n_shared": 0,
            "happiest_weekday": None,
            "summary": "No moods logged yet — add a mood to diary entries to "
            "see how your weeks (and each other) trend. 💞",
        }

    # Per-author average.
    by_author: dict[str, list[float]] = {}
    by_weekday: dict[str, list[float]] = {}
    per_day: dict[str, dict[str, list[float]]] = {}  # date -> author -> [scores]
    for r in rows:
        by_author.setdefault(r["author"], []).append(r["score"])
        try:
            wd = _WEEKDAYS[date.fromisoformat(r["date"]).weekday()]
            by_weekday.setdefault(wd, []).append(r["score"])
        except ValueError:
            pass
        per_day.setdefault(r["date"], {}).setdefault(r["author"], []).append(
            r["score"]
        )

    author_avg = {a: round(sum(v) / len(v), 2) for a, v in by_author.items()}
    weekday_avg = {
        wd: round(sum(by_weekday[wd]) / len(by_weekday[wd]), 2)
        for wd in _WEEKDAYS
        if wd in by_weekday
    }

    # Correlation between the two most active authors on their shared days.
    authors = sorted(by_author, key=lambda a: len(by_author[a]), reverse=True)
    correlation, n_shared = None, 0
    if len(authors) >= 2:
        a, b = authors[0], authors[1]
        xs, ys = [], []
        for day, who in per_day.items():
            if a in who and b in who:
                xs.append(sum(who[a]) / len(who[a]))
                ys.append(sum(who[b]) / len(who[b]))
        n_shared = len(xs)
        correlation = _pearson(xs, ys)

    happiest = max(weekday_avg, key=weekday_avg.get) if weekday_avg else None

    parts = []
    if happiest:
        parts.append(f"Your happiest days tend to be **{happiest}**.")
    if correlation is not None:
        if correlation > 0.45:
            parts.append(
                f"Your moods move **together** (r={correlation:.2f}) — when one "
                "of you is up, the other usually is too. 💞"
            )
        elif correlation < -0.45:
            parts.append(
                f"Your moods often **counterbalance** (r={correlation:.2f}) — "
                "one of you tends to lift the other on harder days."
            )
        else:
            parts.append(
                f"Your moods are fairly **independent** (r={correlation:.2f})."
            )
    summary = " ".join(parts) or "Keep logging moods to unlock trends. 💛"

    return {
        "by_author": author_avg,
        "by_weekday": weekday_avg,
        "correlation": None if correlation is None else round(correlation, 3),
        "n_shared": n_shared,
        "happiest_weekday": happiest,
        "summary": summary,
    }


# --- "How well do you know me" quiz, generated from a partner's diary ----------

def partner_quiz(about_author: str, n: int = 5) -> list[dict]:
    """Generate up to `n` quiz questions about `about_author` from their diary.

    Returns [{question, answer}]. The other partner can self-test. Returns [] if
    there isn't enough material or no LLM is reachable.
    """
    entries = tools.list_diary_entries(author=about_author)
    if len(entries) < 2:
        return []
    digest = "\n".join(
        f"- {e['date']}: {e['preview']}" for e in entries[:40]
    )
    system = (
        "From the diary excerpts of one person below, write quiz questions that "
        "their partner could try to answer about them (favourite moments, "
        "feelings, little facts). Return ONLY a JSON array of objects with "
        '"question" and "answer" string fields. Keep answers short and grounded '
        "strictly in the excerpts. No preamble, no markdown fences."
    )
    user = f"Person: {about_author}\nDiary:\n{digest}\n\nMake {max(1, n)} questions."
    try:
        raw = llm.chat(system, user).strip()
    except llm.LLMError:
        return []
    return _parse_quiz(raw, n)


def _parse_quiz(raw: str, n: int) -> list[dict]:
    """Best-effort parse of an LLM quiz reply into [{question, answer}]."""
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.MULTILINE).strip()
    try:
        data = json.loads(raw)
        out = [
            {"question": str(q.get("question", "")).strip(),
             "answer": str(q.get("answer", "")).strip()}
            for q in data
            if isinstance(q, dict) and q.get("question")
        ]
        if out:
            return out[:n]
    except (ValueError, TypeError, AttributeError):
        pass
    # Fallback: parse "Q: ... A: ..." style lines.
    out, q = [], None
    for line in raw.splitlines():
        line = line.strip()
        qm = re.match(r"(?:Q\d*[:.)]|\d+[.)])\s*(.+)", line, re.I)
        am = re.match(r"A\d*[:.)]\s*(.+)", line, re.I)
        if qm:
            q = qm.group(1).strip()
        elif am and q:
            out.append({"question": q, "answer": am.group(1).strip()})
            q = None
    return out[:n]


# --- Year in review: highlights from a year of diary + photos -----------------

def year_in_review(year: int | None = None) -> dict:
    """Compile a year of memories: entry/photo counts, authors, AI highlights.

    Returns {year, entry_count, photo_count, authors, top_moods, highlights}.
    `highlights` is an LLM-written recap (or a graceful fallback string).
    """
    year = year or date.today().year
    prefix = f"{year}-"

    entries = [
        e for e in tools.list_diary_entries()
        if str(e.get("date", "")).startswith(prefix)
    ]
    photo_paths = [
        p for p in repo.get_repo().list_paths()
        if p.startswith(photos.PHOTO_DIR) and f"/{prefix}" in p
    ]

    authors = sorted({e["author"] for e in entries})
    moods = [e["mood"] for e in entries if e.get("mood")]
    top_moods = sorted(
        {m: moods.count(m) for m in set(moods)}.items(),
        key=lambda kv: kv[1],
        reverse=True,
    )[:3]

    if not entries:
        return {
            "year": year,
            "entry_count": 0,
            "photo_count": len(photo_paths),
            "authors": authors,
            "top_moods": top_moods,
            "highlights": f"No diary entries from {year} yet — your story is "
            "still being written. 💞",
        }

    digest = "\n".join(f"- {e['date']} · {e['author']}: {e['preview']}" for e in entries[:60])
    system = (
        "You are a warm storyteller. From this couple's diary entries for the "
        f"year {year}, write a heartfelt 5-7 sentence 'year in review' — the "
        "highlights, the moods, the growth, and one sweet closing line. Be "
        "specific and uplifting; never negative."
    )
    try:
        highlights = llm.chat(system, digest)
    except llm.LLMError as e:
        highlights = (
            f"{len(entries)} entries and {len(photo_paths)} photos from {year}. "
            f"(Set up an LLM for a written recap.) Details: {e}"
        )
    return {
        "year": year,
        "entry_count": len(entries),
        "photo_count": len(photo_paths),
        "authors": authors,
        "top_moods": top_moods,
        "highlights": highlights,
    }


# --- Journaling prompt: a personalized nudge to write -------------------------

_FALLBACK_PROMPTS = [
    "What's one small thing that made you smile today?",
    "What are you looking forward to this week?",
    "Describe a moment from today you'd want to remember in a year.",
    "What's something you appreciated about your partner recently?",
    "What felt hard today, and how did you get through it?",
]


def journal_prompt() -> str:
    """A single reflective journaling prompt, tailored to recent entries.

    Uses the last few diary entries for context when an LLM is available; falls
    back to a rotating evergreen prompt otherwise (always returns something).
    """
    recent = tools.list_diary_entries()[:8]
    if not recent:
        return _FALLBACK_PROMPTS[date.today().day % len(_FALLBACK_PROMPTS)]
    digest = "\n".join(f"- {e['date']}: {e['preview']}" for e in recent)
    system = (
        "You are a gentle journaling companion. Based on the recent diary "
        "excerpts, write ONE short, open-ended journaling prompt (a single "
        "question, under 25 words) that invites reflection. Output only the "
        "question, no preamble or quotes."
    )
    try:
        return llm.chat(system, digest).strip().strip('"')
    except llm.LLMError:
        return _FALLBACK_PROMPTS[date.today().day % len(_FALLBACK_PROMPTS)]


# ============================================================================
# 🧠  SMARTER BRAIN
# ============================================================================

# --- Weekly retrospective: reflect over the last N days -----------------------

def weekly_retrospective(days: int = 7) -> dict:
    """Reflect over notes & diary touched in the last `days` days.

    Returns {since, until, items: [{path, title, when}], reflection}. The
    reflection (LLM) surfaces themes, recurring topics, and gentle suggestions;
    falls back to a plain list when no model is reachable.
    """
    until = date.today()
    since = until - timedelta(days=max(1, days))
    cutoff = datetime.combine(since, datetime.min.time())

    items: list[dict] = []
    for rec in repo.get_repo().content_notes():
        if rec.updated < cutoff:
            continue
        from pathlib import Path

        items.append(
            {
                "path": rec.path,
                "title": ingest._front_matter_title(
                    rec.content, fallback=Path(rec.path).stem
                ),
                "when": rec.updated.strftime("%Y-%m-%d"),
                "_body": ingest._strip_frontmatter(rec.content).strip(),
            }
        )
    items.sort(key=lambda n: n["when"], reverse=True)

    base = {
        "since": since.isoformat(),
        "until": until.isoformat(),
        "items": [{k: v for k, v in n.items() if k != "_body"} for n in items],
    }
    if not items:
        base["reflection"] = (
            f"Nothing was written between {since.isoformat()} and "
            f"{until.isoformat()}. A fresh page awaits. ✨"
        )
        return base

    excerpts = "\n\n".join(f"## {n['title']} ({n['when']})\n{n['_body'][:600]}" for n in items)
    system = (
        "You are a thoughtful weekly-review companion. From the notes and diary "
        "entries below (the past week), write a short reflection (5-7 sentences): "
        "the main themes, anything recurring, any open loops or to-dos worth "
        "revisiting, and one encouraging takeaway. Be specific and kind."
    )
    try:
        base["reflection"] = llm.chat(system, excerpts)
    except llm.LLMError as e:
        titles = "; ".join(n["title"] for n in items)
        base["reflection"] = (
            f"[LLM unavailable] You touched: {titles}. Set up Ollama or Groq for "
            f"a written reflection. Details: {e}"
        )
    return base


# --- Resurface: bring back a relevant note you haven't touched in a while ------

def resurface(seed_text: str = "", days: int = 14, k: int = 3) -> list[dict]:
    """Surface notes untouched for >= `days` that relate to `seed_text`.

    With no seed, uses your most recently edited note as the anchor — a "you
    wrote about X today; remember this older note?" nudge. Returns
    [{path, title, score, age_days, preview}] sorted by relevance.
    """
    recs = repo.get_repo().content_notes()
    if len(recs) < 2:
        return []
    by_path = {r.path: r for r in recs}
    newest = max(recs, key=lambda r: r.updated)

    seed = seed_text.strip() or ingest._strip_frontmatter(newest.content).strip()
    if not seed:
        return []

    now = datetime.now()
    q_emb = store.embed([seed[:4000]])[0]
    res = store.query(q_emb, max(k * 6, 24))
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]

    best: dict[str, dict] = {}
    for meta, dist in zip(metas, dists):
        src = meta.get("source")
        rec = by_path.get(src)
        if rec is None or (not seed_text.strip() and src == newest.path):
            continue
        age = (now - rec.updated).days
        if age < days:
            continue
        score = round(1 - dist, 4)
        prev = best.get(src)
        if prev is None or score > prev["score"]:
            from pathlib import Path

            best[src] = {
                "path": src,
                "title": meta.get("note_title")
                or ingest._front_matter_title(rec.content, fallback=Path(src).stem),
                "score": score,
                "age_days": age,
                "preview": ingest._strip_frontmatter(rec.content).strip()[:240],
            }
    return sorted(best.values(), key=lambda d: d["score"], reverse=True)[:k]


# --- Unified search: notes AND photos in one query ----------------------------

def unified_search(query: str, k: int = 5) -> dict:
    """One query across both notes and the photo gallery.

    Returns {"notes": [...], "photos": [...]}. Notes come from semantic note
    search; photos from CLIP (when PHOTO_SEARCH=1) or caption matching.
    """
    query = query.strip()
    if not query:
        return {"notes": [], "photos": []}
    try:
        note_hits = tools.search_notes(query, k)
    except Exception:
        note_hits = []
    try:
        photo_hits = photos.search_photos(query, k)
    except Exception:
        photo_hits = []
    return {"notes": note_hits, "photos": photo_hits}


# --- Calendar export (.ics): turn tasks & dates into real reminders -----------

def _ics_escape(text: str) -> str:
    return (
        text.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _ics_wrap(lines: list[str]) -> str:
    body = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//SecondBrain//Beta//EN"]
    body += lines
    body.append("END:VCALENDAR")
    return "\r\n".join(body) + "\r\n"


def action_items_to_ics(path: str) -> str:
    """Export a note's action items as VTODOs (imports into reminder/task apps).

    Returns an iCalendar string. Each extracted to-do becomes a VTODO so it can
    be dropped straight into Apple Reminders, Thunderbird, etc.
    """
    items = tools.extract_action_items(path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines: list[str] = []
    for i, item in enumerate(items):
        lines += [
            "BEGIN:VTODO",
            f"UID:sb-{tools._slugify(path)}-{i}-{stamp}@secondbrain",
            f"DTSTAMP:{stamp}",
            f"SUMMARY:{_ics_escape(item)}",
            f"DESCRIPTION:{_ics_escape('From note: ' + path)}",
            "STATUS:NEEDS-ACTION",
            "END:VTODO",
        ]
    return _ics_wrap(lines)


def dates_to_ics() -> str:
    """Export the couple's important dates as yearly-recurring all-day VEVENTs.

    Imports into Google Calendar et al. so anniversaries/birthdays show up with
    advance reminders, not just inside the app.
    """
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    lines: list[str] = []
    for i, u in enumerate(couple.upcoming_dates(within_days=400)):
        try:
            start = date.fromisoformat(u["next"])
        except (ValueError, KeyError):
            continue
        dt = start.strftime("%Y%m%d")
        dt_end = (start + timedelta(days=1)).strftime("%Y%m%d")
        lines += [
            "BEGIN:VEVENT",
            f"UID:sb-date-{i}-{stamp}@secondbrain",
            f"DTSTAMP:{stamp}",
            f"DTSTART;VALUE=DATE:{dt}",
            f"DTEND;VALUE=DATE:{dt_end}",
            "RRULE:FREQ=YEARLY",
            f"SUMMARY:{_ics_escape('💞 ' + u['label'])}",
            "BEGIN:VALARM",
            "TRIGGER:-P2D",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{_ics_escape(u['label'] + ' in 2 days')}",
            "END:VALARM",
            "END:VEVENT",
        ]
    return _ics_wrap(lines)


# --- AI photo-caption suggestion (CLIP zero-shot, best-effort) -----------------

# A small vocabulary of scene phrases for zero-shot CLIP captioning. Cheap and
# offline once the model is loaded; only used when PHOTO_SEARCH is enabled.
_CAPTION_VOCAB = [
    "a couple smiling together", "a romantic sunset", "a birthday celebration",
    "a cozy moment at home", "a plate of delicious food", "a scenic landscape",
    "a city street at night", "friends having fun", "a cute pet",
    "a beach by the sea", "mountains and nature", "a selfie portrait",
    "a festive party with lights", "a quiet coffee date", "a road trip",
    "flowers and a gift", "a hug between two people", "a starry night sky",
]


def suggest_photo_caption(data: bytes) -> str:
    """Suggest a caption for an image via zero-shot CLIP. Best-effort.

    Returns "" when PHOTO_SEARCH is off or the model/image can't be processed,
    so callers can fall back to a manual caption.
    """
    from . import config

    if not config.PHOTO_SEARCH or not data:
        return ""
    try:
        import io

        import numpy as np
        from PIL import Image

        model = photos._clip()
        img = Image.open(io.BytesIO(data)).convert("RGB")
        img_emb = np.asarray(
            model.encode([img], normalize_embeddings=True)[0], "float32"
        )
        txt_embs = np.asarray(
            model.encode(_CAPTION_VOCAB, normalize_embeddings=True), "float32"
        )
        scores = txt_embs @ img_emb
        return _CAPTION_VOCAB[int(np.argmax(scores))]
    except Exception:
        return ""
