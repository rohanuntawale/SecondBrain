"""Offline tests for the beta feature layer — no network, no LLM, no models.

Uses an in-memory fake repo so storage-backed features (time capsule, gratitude)
are exercised end-to-end without touching the filesystem or Supabase.
"""

from datetime import date, datetime

from core import beta, config, repo


class _MemRepo:
    """Minimal in-memory NoteRecord store implementing the repo surface beta uses."""

    def __init__(self):
        self.data: dict[str, tuple[str, datetime]] = {}

    def save(self, path, content):
        self.data[path] = (content, datetime.now())
        return path

    def get(self, path):
        if path in self.data:
            c, u = self.data[path]
            return repo.NoteRecord(path, c, u)
        return None

    def all_notes(self):
        return [repo.NoteRecord(p, c, u) for p, (c, u) in sorted(self.data.items())]

    def list_paths(self):
        return sorted(self.data)

    def content_notes(self):
        return [
            n for n in self.all_notes()
            if not n.path.startswith(config.HIDDEN_PREFIXES)
        ]

    def notes_under(self, prefix, limit=None, newest_first=False):
        items = [n for n in self.all_notes() if n.path.startswith(prefix)]
        items.sort(key=lambda n: n.updated if newest_first else n.path,
                   reverse=newest_first)
        return items[:limit] if limit else items


# --- pure helpers -------------------------------------------------------------

def test_pearson_perfect_and_undefined():
    assert round(beta._pearson([1, 2, 3], [2, 4, 6]), 3) == 1.0
    assert beta._pearson([1, 1, 1], [2, 3, 4]) is None  # zero variance


def test_parse_quiz_json():
    raw = '[{"question": "Fav food?", "answer": "pasta"}]'
    out = beta._parse_quiz(raw, 5)
    assert out == [{"question": "Fav food?", "answer": "pasta"}]


def test_parse_quiz_fallback_lines():
    raw = "Q1: What city?\nA1: Pune\nQ2: What month?\nA2: June"
    out = beta._parse_quiz(raw, 5)
    assert {"question": "What city?", "answer": "Pune"} in out


def test_ics_escape_specials():
    assert beta._ics_escape("a;b,c\nd") == "a\\;b\\,c\\nd"


# --- time capsule (sealed vs opened) ------------------------------------------

def test_time_capsule_seal_and_unlock(monkeypatch):
    mem = _MemRepo()
    monkeypatch.setattr(repo, "get_repo", lambda: mem)

    beta.add_time_capsule("Rohan", "Pooja", "open me later", "2999-01-01")
    beta.add_time_capsule("Pooja", "Rohan", "already openable", "2000-01-01")

    sealed = beta.list_time_capsules("Pooja", today=date(2026, 1, 1))
    assert len(sealed) == 1
    assert sealed[0]["unlocked"] is False
    assert sealed[0]["message"] == ""  # surprise kept until unlock

    opened = beta.list_time_capsules("Rohan", today=date(2026, 1, 1))
    assert opened[0]["unlocked"] is True
    assert "already openable" in opened[0]["message"]


def test_capsules_live_in_hidden_namespace(monkeypatch):
    mem = _MemRepo()
    monkeypatch.setattr(repo, "get_repo", lambda: mem)
    beta.add_time_capsule("Rohan", "Pooja", "secret", "2999-01-01")
    # Hidden from ordinary content listings (won't pollute RAG / Notes).
    assert mem.content_notes() == []


# --- gratitude jar ------------------------------------------------------------

def test_gratitude_add_and_list(monkeypatch):
    mem = _MemRepo()
    monkeypatch.setattr(repo, "get_repo", lambda: mem)
    beta.add_gratitude("Rohan", "morning coffee")
    grats = beta.list_gratitude()
    assert len(grats) == 1
    assert grats[0]["by"] == "Rohan"
    assert grats[0]["text"] == "morning coffee"


# --- mood correlation (no moods -> graceful) ----------------------------------

def test_mood_correlation_empty(monkeypatch):
    mem = _MemRepo()
    monkeypatch.setattr(repo, "get_repo", lambda: mem)
    mc = beta.mood_correlation()
    assert mc["correlation"] is None
    assert mc["by_author"] == {}
    assert "No moods" in mc["summary"]


# --- calendar export ----------------------------------------------------------

def test_dates_to_ics_wraps_calendar(monkeypatch):
    mem = _MemRepo()
    monkeypatch.setattr(repo, "get_repo", lambda: mem)
    ics = beta.dates_to_ics()
    assert ics.startswith("BEGIN:VCALENDAR")
    assert ics.rstrip().endswith("END:VCALENDAR")
