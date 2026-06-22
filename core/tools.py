"""Note-action functions. These plain functions are wrapped by mcp_server.py as
MCP tools and called directly by app.py. One implementation, two faces.

SAFETY: every write resolves its path and verifies it stays inside NOTES_DIR
(prevents path traversal). This is a deliberate security control.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from pathlib import Path

from . import ingest, llm, repo, store

_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

# Internal/config notes (e.g. meta/couple.json.md) are hidden from listings.
_HIDDEN_PREFIX = "meta/"


def _content_notes():
    """All real content notes (excludes internal config under meta/)."""
    return [r for r in repo.get_repo().all_notes() if not r.path.startswith(_HIDDEN_PREFIX)]


def _slugify(title: str) -> str:
    slug = re.sub(r"[^\w\s-]", "", title).strip().lower()
    slug = re.sub(r"[\s_]+", "-", slug)
    return slug or "untitled"


# --- Read tools ---------------------------------------------------------------

def search_notes(query: str, k: int = 4) -> list[dict]:
    """Semantic search over notes — the RAG<->MCP bridge."""
    q_emb = store.embed([query])[0]
    res = store.query(q_emb, k)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]
    out = []
    for doc, meta, dist in zip(docs, metas, dists):
        out.append(
            {
                "text": doc,
                "source": meta.get("source"),
                "heading": meta.get("heading"),
                "note_title": meta.get("note_title"),
                "score": round(1 - dist, 4),  # cosine distance -> similarity
            }
        )
    return out


def read_note(path: str) -> str:
    """Return the full text of a note (path relative to the vault)."""
    rec = repo.get_repo().get(path)
    if rec is None:
        raise ValueError(f"Note not found: {path}")
    return rec.content


def list_notes() -> list[str]:
    """All note paths in the vault (excludes internal config notes)."""
    return sorted(
        p for p in repo.get_repo().list_paths() if not p.startswith(_HIDDEN_PREFIX)
    )


# --- Write tools (validated, then re-index) -----------------------------------

def create_note(
    title: str, body: str, tags: list[str] | None = None, author: str = ""
) -> str:
    """Create a new .md note with YAML front-matter, then re-index. Returns path.

    `author` (optional) attributes the note to a person so it can be filtered
    later; leave empty for a shared/unattributed note.
    """
    tags = tags or []
    rel = f"{_slugify(title)}.md"
    r = repo.get_repo()
    if r.exists(rel):
        raise ValueError(f"Note already exists: {rel}")
    tag_line = "[" + ", ".join(tags) + "]"
    author_line = f"author: {author}\n" if author.strip() else ""
    content = (
        f"---\ntitle: {title}\n{author_line}tags: {tag_line}\n---\n\n"
        f"# {title}\n\n{body}\n"
    )
    saved = r.save(rel, content)
    ingest.build_index()
    return saved


def import_file(filename: str, data: bytes) -> str:
    """Import an uploaded .md or .pdf into the vault as a note (via the repo).

    PDFs have their text extracted and wrapped as a Markdown note, so they are
    searchable, citable, and browsable like any other note. Returns the path.
    Does NOT re-index — the caller re-indexes once after a batch.
    """
    name = Path(filename).name
    ext = Path(name).suffix.lower()
    stem = Path(name).stem

    if ext == ".md":
        rel = name  # preserve the original .md filename
        content = data.decode("utf-8", errors="replace")
    elif ext == ".pdf":
        text = ingest.pdf_to_text(data)
        if not text.strip():
            raise ValueError(
                f"No extractable text in {name} (a scanned/image PDF needs OCR)."
            )
        rel = f"{_slugify(stem)}.md"
        content = (
            f"---\ntitle: {stem}\nsource_file: {name}\ntags: [imported]\n---\n\n"
            f"# {stem}\n\n{text}\n"
        )
    else:
        raise ValueError(f"Unsupported file type '{ext}'. Use .md or .pdf.")

    return repo.get_repo().save(rel, content)


def list_notes_detailed() -> list[dict]:
    """All notes with metadata for per-author browsing.

    Each item: {path, title, author, type}. `type` is "diary" for diary entries,
    else "note"; `author` is "" for shared/unattributed notes.
    """
    out: list[dict] = []
    for rec in _content_notes():
        meta = _front_matter_fields(rec.content)
        out.append(
            {
                "path": rec.path,
                "title": meta.get("title")
                or ingest._front_matter_title(rec.content, fallback=Path(rec.path).stem),
                "author": meta.get("author", ""),
                "type": meta.get("type", "note"),
            }
        )
    return sorted(out, key=lambda n: n["path"])


def append_to_note(path: str, text: str) -> str:
    """Append text to an existing note, then re-index."""
    r = repo.get_repo()
    rec = r.get(path)
    if rec is None:
        raise ValueError(f"Note not found: {path}")
    sep = "" if rec.content.endswith("\n") else "\n"
    saved = r.save(path, f"{rec.content}{sep}\n{text}\n")
    ingest.build_index()
    return saved


def suggest_tags(path: str) -> list[str]:
    """Ask the LLM to propose tags drawn from the existing tag vocabulary."""
    text = read_note(path)
    vocab = sorted(_collect_tag_vocabulary())
    system = (
        "You suggest 3-6 short lowercase tags for a note. Prefer reusing tags from "
        "the existing vocabulary when they fit. Return ONLY a comma-separated list."
    )
    user = f"Existing tags: {', '.join(vocab) or '(none)'}\n\nNote:\n{text[:2000]}"
    raw = llm.chat(system, user)
    tags = [t.strip().lower() for t in re.split(r"[,\n]", raw) if t.strip()]
    # keep them tidy: short, no spaces
    return [re.sub(r"\s+", "-", t) for t in tags if len(t) <= 30][:6]


def add_link(from_path: str, to_title: str) -> str:
    """Insert a [[to_title]] wiki-link into a note if not already present."""
    r = repo.get_repo()
    rec = r.get(from_path)
    if rec is None:
        raise ValueError(f"Note not found: {from_path}")
    if f"[[{to_title}]]" in rec.content:
        return "Link already present."
    sep = "" if rec.content.endswith("\n") else "\n"
    r.save(from_path, f"{rec.content}{sep}\nRelated: [[{to_title}]]\n")
    ingest.build_index()
    return f"Added [[{to_title}]] to {from_path}"


def find_orphans() -> list[str]:
    """Notes whose title is never referenced by any [[wiki-link]]."""
    linked_titles: set[str] = set()
    titles_by_path: dict[str, str] = {}

    for rec in _content_notes():
        title = ingest._front_matter_title(rec.content, fallback=Path(rec.path).stem)
        titles_by_path[rec.path] = title
        for m in _LINK_RE.findall(rec.content):
            linked_titles.add(m.strip().lower())

    return sorted(
        rel
        for rel, title in titles_by_path.items()
        if title.lower() not in linked_titles
    )


# --- Bonus features (step 10): auto-link + daily digest -----------------------

def suggest_links(path: str, k: int = 3, min_score: float = 0.25) -> list[dict]:
    """Suggest [[wiki-links]] to notes that are semantically related to `path`.

    Embeds the source note, retrieves the nearest chunks, then aggregates them
    by their owning note. Excludes the note itself and any title it already
    links to. Returns up to `k` suggestions sorted by similarity (highest first).
    """
    text = read_note(path)
    self_title = ingest._front_matter_title(text, fallback=Path(path).stem)
    already_linked = {m.strip().lower() for m in _LINK_RE.findall(text)}
    already_linked.add(self_title.lower())

    # Embed the source note (cap length so very long notes stay cheap) and pull
    # a generous candidate set — we collapse chunks back to notes afterwards.
    q_emb = store.embed([text[:4000]])[0]
    res = store.query(q_emb, max(k * 4, 12))
    metas = res.get("metadatas", [[]])[0]
    dists = res.get("distances", [[]])[0]

    best: dict[str, dict] = {}
    for meta, dist in zip(metas, dists):
        title = (meta.get("note_title") or "").strip()
        score = round(1 - dist, 4)  # cosine distance -> similarity
        if not title or title.lower() in already_linked:
            continue
        if score < min_score:
            continue
        prev = best.get(title.lower())
        if prev is None or score > prev["score"]:
            best[title.lower()] = {
                "note_title": title,
                "source": meta.get("source"),
                "score": score,
            }

    return sorted(best.values(), key=lambda d: d["score"], reverse=True)[:k]


def auto_link(path: str, k: int = 3, min_score: float = 0.25) -> str:
    """Insert [[wiki-links]] to the top related notes for `path`. Re-indexes.

    Writes a single `Related:` line with the new links and skips any already
    present. Returns a human-readable summary of what was added.
    """
    titles = [s["note_title"] for s in suggest_links(path, k=k, min_score=min_score)]
    if not titles:
        return "No sufficiently related notes found to link."
    r = repo.get_repo()
    rec = r.get(path)
    if rec is None:
        raise ValueError(f"Note not found: {path}")
    text = rec.content
    fresh = [t for t in titles if f"[[{t}]]" not in text]
    if not fresh:
        return f"{path} already links to all of: " + ", ".join(titles)
    sep = "" if text.endswith("\n") else "\n"
    line = "Related: " + " ".join(f"[[{t}]]" for t in fresh)
    r.save(path, f"{text}{sep}\n{line}\n")
    ingest.build_index()
    return f"Linked {path} -> " + ", ".join(f"[[{t}]]" for t in fresh)


def daily_digest(on: str | None = None) -> dict:
    """Summarize notes created or edited on a given day (default: today).

    `on` is an ISO date string (YYYY-MM-DD); omit for today's date. Returns
    {"date", "notes": [{path, title, modified}], "summary"}. The summary is
    LLM-generated; if no model is reachable, falls back to a plain list.
    """
    target = date.fromisoformat(on) if on else date.today()

    touched: list[dict] = []
    for rec in sorted(_content_notes(), key=lambda r: r.path):
        if rec.updated.date() != target:
            continue
        touched.append(
            {
                "path": rec.path,
                "title": ingest._front_matter_title(
                    rec.content, fallback=Path(rec.path).stem
                ),
                "modified": rec.updated.strftime("%H:%M"),
                "_body": ingest._strip_frontmatter(rec.content).strip(),
            }
        )

    if not touched:
        return {
            "date": target.isoformat(),
            "notes": [],
            "summary": f"No notes were created or edited on {target.isoformat()}.",
        }

    excerpts = "\n\n".join(
        f"## {n['title']}\n{n['_body'][:800]}" for n in touched
    )
    system = (
        "You write a brief daily digest of a person's notes. Summarize the key "
        "themes and takeaways across the notes below in 3-5 sentences. Be concise "
        "and do not invent details."
    )
    try:
        summary = llm.chat(system, excerpts)
    except llm.LLMError as e:
        summary = (
            "[LLM unavailable] "
            + "; ".join(n["title"] for n in touched)
            + f" (set up Ollama or Groq for a written digest). Details: {e}"
        )

    for n in touched:
        n.pop("_body", None)  # internal field, not part of the public result
    return {"date": target.isoformat(), "notes": touched, "summary": summary}


# --- Diary (dated personal entries, shared by multiple authors) ---------------

DIARY_SUBDIR = "diary"


def add_diary_entry(
    body: str,
    author: str = "You",
    mood: str = "",
    title: str = "",
    on: str | None = None,
) -> str:
    """Add a dated diary entry under notes/diary/, then re-index.

    Entries are ordinary Markdown notes (so they're searchable + show up in the
    daily digest) tagged with `type: diary`, an author, an optional mood, and a
    date. Returns the new note's path relative to the vault.
    """
    if not body.strip():
        raise ValueError("Diary entry body cannot be empty.")
    entry_date = date.fromisoformat(on) if on else date.today()
    stamp = datetime.now().strftime("%H%M%S")
    author_slug = _slugify(author) or "anon"
    rel = f"{DIARY_SUBDIR}/{entry_date.isoformat()}-{author_slug}-{stamp}.md"

    heading = title.strip() or f"{author} — {entry_date.isoformat()}"
    mood_line = f"mood: {mood}\n" if mood.strip() else ""
    content = (
        f"---\ntitle: {heading}\ntype: diary\nauthor: {author}\n"
        f"date: {entry_date.isoformat()}\n{mood_line}tags: [diary]\n---\n\n"
        f"# {heading}\n\n{body.strip()}\n"
    )
    saved = repo.get_repo().save(rel, content)
    ingest.build_index()
    return saved


def list_diary_entries(author: str | None = None) -> list[dict]:
    """List diary entries newest-first.

    Each item: {path, title, author, date, mood, preview}. Optionally filter to
    a single author (case-insensitive).
    """
    prefix = f"{DIARY_SUBDIR}/"
    entries: list[dict] = []
    for rec in repo.get_repo().all_notes():
        if not rec.path.startswith(prefix):
            continue
        meta = _front_matter_fields(rec.content)
        if author and meta.get("author", "").lower() != author.lower():
            continue
        body = ingest._strip_frontmatter(rec.content).strip()
        # Drop a leading "# heading" line from the preview.
        body = re.sub(r"^#\s+.*\n+", "", body, count=1)
        entries.append(
            {
                "path": rec.path,
                "title": meta.get("title", Path(rec.path).stem),
                "author": meta.get("author", "Unknown"),
                "date": meta.get("date", ""),
                "mood": meta.get("mood", ""),
                "preview": body[:280],
            }
        )
    entries.sort(key=lambda e: (e["date"], e["path"]), reverse=True)
    return entries


def diary_authors() -> list[str]:
    """Distinct author names that have written diary entries."""
    seen = {e["author"] for e in list_diary_entries()}
    return sorted(seen)


def _front_matter_fields(text: str) -> dict:
    """Parse simple `key: value` pairs from a note's YAML front-matter block."""
    fields: dict[str, str] = {}
    m = re.match(r"^---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if not m:
        return fields
    for line in m.group(1).splitlines():
        kv = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", line)
        if kv:
            fields[kv.group(1).strip()] = kv.group(2).strip().strip("'\"")
    return fields


# --- helpers ------------------------------------------------------------------

def _collect_tag_vocabulary() -> set[str]:
    vocab: set[str] = set()
    for rec in _content_notes():
        m = re.search(r"^tags:\s*\[(.*?)\]", rec.content, re.MULTILINE)
        if m:
            vocab.update(t.strip().lower() for t in m.group(1).split(",") if t.strip())
    return vocab
