"""Note-action functions. These plain functions are wrapped by mcp_server.py as
MCP tools and called directly by app.py. One implementation, two faces.

SAFETY: every write resolves its path and verifies it stays inside NOTES_DIR
(prevents path traversal). This is a deliberate security control.
"""

from __future__ import annotations

import re
from pathlib import Path

from . import config, ingest, llm, store

_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


def _safe_path(rel_or_name: str) -> Path:
    """Resolve a note path and guarantee it stays within NOTES_DIR."""
    notes_root = config.NOTES_DIR.resolve()
    candidate = (notes_root / rel_or_name).resolve()
    if notes_root not in candidate.parents and candidate != notes_root:
        raise ValueError(f"Refusing to access path outside notes vault: {rel_or_name}")
    return candidate


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
    return _safe_path(path).read_text(encoding="utf-8")


def list_notes() -> list[str]:
    """All note paths relative to the vault."""
    root = config.NOTES_DIR
    return sorted(
        str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*.md")
    )


# --- Write tools (validated, then re-index) -----------------------------------

def create_note(title: str, body: str, tags: list[str] | None = None) -> str:
    """Create a new .md note with YAML front-matter, then re-index. Returns path."""
    tags = tags or []
    path = _safe_path(f"{_slugify(title)}.md")
    if path.exists():
        raise ValueError(f"Note already exists: {path.name}")
    tag_line = "[" + ", ".join(tags) + "]"
    content = f"---\ntitle: {title}\ntags: {tag_line}\n---\n\n# {title}\n\n{body}\n"
    path.write_text(content, encoding="utf-8")
    ingest.build_index()
    return str(path.relative_to(config.NOTES_DIR)).replace("\\", "/")


def append_to_note(path: str, text: str) -> str:
    """Append text to an existing note, then re-index."""
    p = _safe_path(path)
    existing = p.read_text(encoding="utf-8")
    sep = "" if existing.endswith("\n") else "\n"
    p.write_text(f"{existing}{sep}\n{text}\n", encoding="utf-8")
    ingest.build_index()
    return str(p.relative_to(config.NOTES_DIR)).replace("\\", "/")


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
    p = _safe_path(from_path)
    text = p.read_text(encoding="utf-8")
    if f"[[{to_title}]]" in text:
        return "Link already present."
    sep = "" if text.endswith("\n") else "\n"
    p.write_text(f"{text}{sep}\nRelated: [[{to_title}]]\n", encoding="utf-8")
    ingest.build_index()
    return f"Added [[{to_title}]] to {p.name}"


def find_orphans() -> list[str]:
    """Notes whose title is never referenced by any [[wiki-link]]."""
    root = config.NOTES_DIR
    linked_titles: set[str] = set()
    titles_by_path: dict[str, str] = {}

    for path in root.rglob("*.md"):
        rel = str(path.relative_to(root)).replace("\\", "/")
        text = path.read_text(encoding="utf-8")
        title = ingest._front_matter_title(text, fallback=path.stem)
        titles_by_path[rel] = title
        for m in _LINK_RE.findall(text):
            linked_titles.add(m.strip().lower())

    return sorted(
        rel
        for rel, title in titles_by_path.items()
        if title.lower() not in linked_titles
    )


# --- helpers ------------------------------------------------------------------

def _collect_tag_vocabulary() -> set[str]:
    vocab: set[str] = set()
    for path in config.NOTES_DIR.rglob("*.md"):
        text = path.read_text(encoding="utf-8")
        m = re.search(r"^tags:\s*\[(.*?)\]", text, re.MULTILINE)
        if m:
            vocab.update(t.strip().lower() for t in m.group(1).split(",") if t.strip())
    return vocab
