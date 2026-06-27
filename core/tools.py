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

def _content_notes():
    """All real content notes (excludes internal namespaces: config/love/photos)."""
    return repo.get_repo().content_notes()


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
        p for p in repo.get_repo().list_paths()
        if not p.startswith(ingest.HIDDEN_PREFIXES)
    )


# --- Write tools (validated, then re-index) -----------------------------------

def create_note(
    title: str,
    body: str,
    tags: list[str] | None = None,
    author: str = "",
    auto: bool = False,
) -> str:
    """Create a new .md note with YAML front-matter, then re-index. Returns path.

    `author` (optional) attributes the note to a person so it can be filtered
    later; leave empty for a shared/unattributed note.

    `auto` (optional) enriches the note with the LLM at creation time: it fills
    in tags when none are given and prepends a one-line **TL;DR** to the body.
    Degrades silently to a plain note if no model is reachable.
    """
    tags = tags or []
    rel = f"{_slugify(title)}.md"
    r = repo.get_repo()
    if r.exists(rel):
        raise ValueError(f"Note already exists: {rel}")

    if auto:
        if not tags:
            try:
                tags = _suggest_tags_for_text(f"{title}\n\n{body}")
            except llm.LLMError:
                tags = []
        try:
            tldr = summarize_one(f"{title}\n\n{body}", sentences=1)
            if tldr:
                body = f"> **TL;DR:** {tldr}\n\n{body}"
        except llm.LLMError:
            pass

    tag_line = "[" + ", ".join(tags) + "]"
    author_line = f"author: {author}\n" if author.strip() else ""
    content = (
        f"---\ntitle: {title}\n{author_line}tags: {tag_line}\n---\n\n"
        f"# {title}\n\n{body}\n"
    )
    saved = r.save(rel, content)
    ingest.build_index()
    return saved


def summarize_one(text: str, sentences: int = 3) -> str:
    """Summarize raw text in N sentences (LLM). Shared by create_note/summarize."""
    system = (
        f"Summarize the following in {max(1, sentences)} sentence(s). Be faithful; "
        "do not invent. Output only the summary."
    )
    return llm.chat(system, text[:4000]).strip()


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


def _suggest_tags_for_text(text: str) -> list[str]:
    """Core tag suggester over raw note text (shared by suggest_tags + create)."""
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


def suggest_tags(path: str) -> list[str]:
    """Ask the LLM to propose tags drawn from the existing tag vocabulary."""
    return _suggest_tags_for_text(read_note(path))


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


# --- Knowledge tools: summarize, action items, dedupe, web search -------------

def summarize_note(path: str, sentences: int = 3) -> str:
    """Return a short LLM summary (TL;DR) of a note."""
    body = ingest._strip_frontmatter(read_note(path)).strip()
    try:
        return summarize_one(body, sentences=sentences)
    except llm.LLMError as e:
        return f"[LLM unavailable] Could not summarize. Details: {e}"


def extract_action_items(path: str) -> list[str]:
    """Pull actionable to-dos out of a note (LLM). Returns a list of strings."""
    text = read_note(path)
    body = ingest._strip_frontmatter(text).strip()
    system = (
        "Extract concrete action items / tasks from the note. Return ONE per line, "
        "each starting with '- '. If there are none, return the single line "
        "'(none)'. Do not invent tasks that are not implied by the text."
    )
    try:
        raw = llm.chat(system, body[:4000])
    except llm.LLMError:
        return []
    items = [
        re.sub(r"^[-*\d.\s]+", "", ln).strip()
        for ln in raw.splitlines()
        if ln.strip()
    ]
    items = [i for i in items if i and i.lower() != "(none)"]
    return items


def find_duplicate_notes(threshold: float = 0.8) -> list[dict]:
    """Find pairs of notes that are near-duplicates by embedding similarity.

    Embeds each note's body once, then reports pairs whose cosine similarity is
    >= `threshold`. Returns [{a, b, score}] sorted by score (highest first).
    """
    import numpy as np

    recs = _content_notes()
    if len(recs) < 2:
        return []
    bodies = [ingest._strip_frontmatter(r.content).strip()[:4000] for r in recs]
    embs = np.asarray(store.embed(bodies), dtype="float32")
    sims = embs @ embs.T  # unit-normalized -> cosine
    pairs: list[dict] = []
    for i in range(len(recs)):
        for j in range(i + 1, len(recs)):
            score = float(sims[i, j])
            if score >= threshold:
                pairs.append(
                    {"a": recs[i].path, "b": recs[j].path, "score": round(score, 4)}
                )
    return sorted(pairs, key=lambda p: p["score"], reverse=True)


def merge_notes(primary: str, secondary: str, delete_secondary: bool = False) -> str:
    """Append `secondary`'s body under the `primary` note (manual de-dup helper).

    Adds a divider and the secondary note's content to the primary note. If
    `delete_secondary` is True, removes the secondary note afterward. Re-indexes.
    """
    r = repo.get_repo()
    prim, sec = r.get(primary), r.get(secondary)
    if prim is None:
        raise ValueError(f"Note not found: {primary}")
    if sec is None:
        raise ValueError(f"Note not found: {secondary}")
    sec_title = ingest._front_matter_title(sec.content, fallback=Path(secondary).stem)
    sec_body = ingest._strip_frontmatter(sec.content).strip()
    sep = "" if prim.content.endswith("\n") else "\n"
    merged = f"{prim.content}{sep}\n---\n\n## Merged from {sec_title}\n\n{sec_body}\n"
    r.save(primary, merged)
    if delete_secondary:
        r.delete(secondary)
    ingest.build_index()
    action = "merged + deleted" if delete_secondary else "merged"
    return f"{action}: {secondary} -> {primary}"


def web_search(query: str, k: int = 5) -> list[dict]:
    """Free web search (no API key) via DuckDuckGo's HTML endpoint.

    Best-effort: returns up to `k` {title, url, snippet}. Returns [] on any
    network/parse error so callers never crash. Use to ground answers in fresh
    info the notes don't contain.
    """
    import html as _html
    import urllib.parse
    import urllib.request

    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            page = resp.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    out: list[dict] = []
    for m in re.finditer(
        r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.DOTALL
    ):
        href, title = m.group(1), re.sub(r"<[^>]+>", "", m.group(2))
        # DuckDuckGo wraps the real URL in a redirect; pull out uddg=.
        q = urllib.parse.urlparse(href).query
        real = urllib.parse.parse_qs(q).get("uddg", [href])[0]
        out.append(
            {"title": _html.unescape(title).strip(), "url": real, "snippet": ""}
        )
        if len(out) >= k:
            break
    return out


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
