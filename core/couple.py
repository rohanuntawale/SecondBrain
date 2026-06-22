"""Couple dashboard logic for the two people sharing this vault.

Powers the "Us" tab: relationship counter, date countdowns, "on this day"
memories, mood trends, an AI daily love note, and a date-idea jar.

Settings (start date, important dates, saved date ideas) live in the SHARED
vault as a JSON note at meta/couple.json.md so both partners see the same data.
That `meta/` path is excluded from indexing and note listings (see ingest.py /
tools.py), so it never pollutes search results.
"""

from __future__ import annotations

import json
from datetime import date

from . import llm, repo, tools

SETTINGS_PATH = "meta/couple.json.md"

_DEFAULTS: dict = {
    "start_date": "",        # ISO date the relationship started
    "important_dates": [],   # [{"label": str, "date": "MM-DD"}]
    "date_jar": [],          # list of saved date-idea strings
}

# Mood presets (label -> 1..5 valence) used by the diary form and mood chart.
MOODS = ["🥰 Loved", "😊 Happy", "🙂 Good", "😐 Okay", "😕 Low", "😢 Sad"]
_MOOD_SCORES = {
    "🥰 Loved": 5, "😊 Happy": 5, "🙂 Good": 4,
    "😐 Okay": 3, "😕 Low": 2, "😢 Sad": 1,
}


# --- settings persistence -----------------------------------------------------

def load_settings() -> dict:
    rec = repo.get_repo().get(SETTINGS_PATH)
    data = dict(_DEFAULTS)
    if rec:
        try:
            data.update(json.loads(rec.content))
        except (json.JSONDecodeError, TypeError):
            pass
    return data


def save_settings(settings: dict) -> None:
    merged = dict(_DEFAULTS)
    merged.update(settings or {})
    repo.get_repo().save(SETTINGS_PATH, json.dumps(merged, indent=2))


# --- relationship counter & countdowns ---------------------------------------

def days_together(today: date | None = None) -> dict | None:
    """Return {'days', 'years', 'months', 'rem_days', 'start'} or None if unset."""
    s = load_settings().get("start_date", "")
    if not s:
        return None
    try:
        start = date.fromisoformat(s)
    except ValueError:
        return None
    today = today or date.today()
    total = (today - start).days
    years = today.year - start.year
    months = today.month - start.month
    days = today.day - start.day
    if days < 0:
        months -= 1
        days += 30
    if months < 0:
        years -= 1
        months += 12
    return {
        "days": total,
        "years": max(years, 0),
        "months": max(months, 0),
        "rem_days": max(days, 0),
        "start": s,
    }


def upcoming_dates(today: date | None = None, within_days: int = 365) -> list[dict]:
    """Important dates sorted by how soon they recur. date stored as 'MM-DD'."""
    today = today or date.today()
    out: list[dict] = []
    for item in load_settings().get("important_dates", []):
        raw = str(item.get("date", "")).strip()
        try:
            mm, dd = (int(x) for x in raw.split("-")[-2:])
            nxt = date(today.year, mm, dd)
            if nxt < today:
                nxt = date(today.year + 1, mm, dd)
        except (ValueError, TypeError):
            continue
        days_until = (nxt - today).days
        if days_until <= within_days:
            out.append(
                {
                    "label": item.get("label", "Special day"),
                    "date": raw,
                    "next": nxt.isoformat(),
                    "days_until": days_until,
                }
            )
    return sorted(out, key=lambda d: d["days_until"])


# --- "on this day" memories ---------------------------------------------------

def on_this_day(today: date | None = None) -> list[dict]:
    """Diary entries from the same month+day in the past (a 'remember this?')."""
    today = today or date.today()
    out: list[dict] = []
    for e in tools.list_diary_entries():
        try:
            d = date.fromisoformat(e["date"])
        except (ValueError, KeyError):
            continue
        if d.month == today.month and d.day == today.day and d < today:
            out.append(e)
    return out


# --- mood trends --------------------------------------------------------------

def mood_score(mood: str) -> int | None:
    if not mood:
        return None
    if mood in _MOOD_SCORES:
        return _MOOD_SCORES[mood]
    for label, score in _MOOD_SCORES.items():
        token = label.split(" ", 1)[-1].lower()
        if token in mood.lower() or label.split(" ", 1)[0] in mood:
            return score
    return None


def mood_series() -> list[dict]:
    """[{date, author, score}] for diary entries that carry a recognizable mood."""
    rows: list[dict] = []
    for e in tools.list_diary_entries():
        score = mood_score(e.get("mood", ""))
        if score is None or not e.get("date"):
            continue
        rows.append({"date": e["date"], "author": e["author"], "score": score})
    return rows


# --- AI daily love note & date ideas -----------------------------------------

def love_note(sender: str, recipient: str) -> str:
    """A short, sweet AI-generated note from `sender` to `recipient`."""
    system = (
        "You write a single warm, sweet, original one-sentence love note. "
        "Keep it under 25 words, sincere, not cheesy or clichéd. No quotation marks."
    )
    user = f"Write a love note from {sender} to {recipient}."
    try:
        return llm.chat(system, user).strip().strip('"')
    except llm.LLMError as e:
        return f"[Set up an LLM to generate notes] ({e})"


def date_idea(context: str = "") -> str:
    """Generate one creative date idea (optionally themed by `context`)."""
    system = (
        "Suggest ONE creative, doable date idea in one sentence (under 30 words). "
        "Be specific and a little romantic. No preamble, just the idea."
    )
    user = f"Theme/notes: {context}" if context.strip() else "Surprise us."
    try:
        return llm.chat(system, user).strip().strip('"')
    except llm.LLMError as e:
        return f"[Set up an LLM to generate ideas] ({e})"


def add_date_idea(idea: str) -> None:
    idea = idea.strip()
    if not idea:
        return
    s = load_settings()
    jar = s.get("date_jar", [])
    if idea not in jar:
        jar.append(idea)
    s["date_jar"] = jar
    save_settings(s)


def list_date_ideas() -> list[str]:
    return list(load_settings().get("date_jar", []))


def pick_date_idea(index: int | None = None) -> str | None:
    """Return a saved idea by index (caller chooses randomness), or None if empty."""
    jar = list_date_ideas()
    if not jar:
        return None
    if index is None:
        index = 0
    return jar[index % len(jar)]
