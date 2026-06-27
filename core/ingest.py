"""Markdown -> heading chunks -> embeddings -> ChromaDB.

Chunking strategy: split each note on Markdown headings (#, ##, ###). If a single
section is longer than CHUNK_MAX_CHARS, sub-split it on paragraph boundaries.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    from . import config, repo, store
except ImportError:  # allow running directly: python core/ingest.py
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core import config, repo, store

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)

# Re-exported for callers that filter on note namespaces (defined in config to
# avoid an import cycle with repo).
HIDDEN_PREFIXES = config.HIDDEN_PREFIXES


def pdf_to_text(data: bytes) -> str:
    """Extract plain text from a PDF's bytes (page-by-page, blank-line joined)."""
    import io

    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    parts = [(page.extract_text() or "").strip() for page in reader.pages]
    return "\n\n".join(p for p in parts if p).strip()


def _strip_frontmatter(text: str) -> str:
    return _FRONTMATTER_RE.sub("", text, count=1)


def _front_matter_title(text: str, fallback: str) -> str:
    """Pull `title:` from YAML front-matter, else the first H1, else fallback."""
    m = _FRONTMATTER_RE.match(text)
    if m:
        tm = re.search(r"^title:\s*(.+)$", m.group(0), re.MULTILINE)
        if tm:
            return tm.group(1).strip().strip("'\"")
    h1 = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
    if h1:
        return h1.group(1).strip()
    return fallback


def _split_paragraphs(
    text: str, max_chars: int, overlap: int | None = None
) -> list[str]:
    """Greedily pack paragraphs into pieces no longer than max_chars.

    Consecutive pieces share a trailing/leading `overlap` characters so context
    that straddles a chunk boundary is not lost at retrieval time (a standard
    sliding-window technique). Overlap defaults to config.CHUNK_OVERLAP_CHARS.
    """
    overlap = config.CHUNK_OVERLAP_CHARS if overlap is None else overlap
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    pieces, buf = [], ""
    for p in paras:
        if len(buf) + len(p) + 2 <= max_chars:
            buf = f"{buf}\n\n{p}" if buf else p
        else:
            if buf:
                pieces.append(buf)
            buf = p
    if buf:
        pieces.append(buf)
    pieces = pieces or [text.strip()]

    if overlap <= 0 or len(pieces) < 2:
        return pieces
    # Prepend the tail of each piece to the next one (sliding-window overlap).
    out = [pieces[0]]
    for prev, cur in zip(pieces, pieces[1:]):
        tail = prev[-overlap:].lstrip()
        out.append(f"{tail}\n\n{cur}" if tail else cur)
    return out


def chunk_markdown(text: str, note_title: str, max_chars: int) -> list[tuple[str, str]]:
    """Return a list of (heading, chunk_text) for one note's body."""
    body = _strip_frontmatter(text)
    lines = body.splitlines()

    sections: list[tuple[str, list[str]]] = []
    current_heading = note_title
    current_lines: list[str] = []

    for line in lines:
        m = _HEADING_RE.match(line)
        if m:
            if current_lines:
                sections.append((current_heading, current_lines))
            current_heading = m.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines:
        sections.append((current_heading, current_lines))

    chunks: list[tuple[str, str]] = []
    for heading, sec_lines in sections:
        sec_text = "\n".join(sec_lines).strip()
        if not sec_text:
            continue
        if len(sec_text) <= max_chars:
            chunks.append((heading, sec_text))
        else:
            for piece in _split_paragraphs(sec_text, max_chars):
                chunks.append((heading, piece))
    return chunks


def build_index() -> dict:
    """Re-index every note from the repository into the local vector store.

    Pulls note content from the active backend (local files or the shared
    Supabase vault), so in Supabase mode each client rebuilds the same index
    from the same shared content. Returns a small stats dict.

    When config.CONTEXTUAL_RETRIEVAL is on, each chunk is prefixed with a short
    LLM-written line situating it within its note (Anthropic's "contextual
    retrieval") before embedding — this is embedded, but the original chunk text
    is what gets stored and shown, so citations stay clean.
    """
    store.reset_collection()

    ids, texts, embed_texts, metadatas = [], [], [], []
    # Only real content notes (hidden namespaces excluded server-side).
    notes = repo.get_repo().content_notes()

    for rec in notes:
        rel = rec.path
        raw = rec.content
        title = _front_matter_title(raw, fallback=Path(rel).stem)
        chunks = chunk_markdown(raw, title, config.CHUNK_MAX_CHARS)
        for i, (heading, chunk_text) in enumerate(chunks):
            ids.append(f"{rel}::{i}")
            texts.append(chunk_text)  # stored & shown verbatim
            metadatas.append({"source": rel, "heading": heading, "note_title": title})
            if config.CONTEXTUAL_RETRIEVAL:
                ctx = _contextualize(title, raw, chunk_text)
                embed_texts.append(f"{ctx}\n\n{chunk_text}" if ctx else chunk_text)
            else:
                embed_texts.append(chunk_text)

    if texts:
        embeddings = store.embed(embed_texts)
        store.add_chunks(ids, texts, metadatas, embeddings)

    return {"files": len(notes), "chunks": len(texts)}


# --- Contextual retrieval (optional, cached) ----------------------------------

_CONTEXT_CACHE_PATH = config.PROJECT_ROOT / ".cache" / "context.json"
_context_cache: dict | None = None


def _load_context_cache() -> dict:
    global _context_cache
    if _context_cache is None:
        import json

        try:
            _context_cache = json.loads(_CONTEXT_CACHE_PATH.read_text("utf-8"))
        except (OSError, ValueError):
            _context_cache = {}
    return _context_cache


def _save_context_cache() -> None:
    import json

    _CONTEXT_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONTEXT_CACHE_PATH.write_text(
        json.dumps(_context_cache or {}), encoding="utf-8"
    )


def _contextualize(title: str, full_note: str, chunk: str) -> str:
    """Return a one-line context for `chunk` within `full_note` (LLM, cached).

    Cached by a hash of (note + chunk) so re-indexing unchanged notes is free
    and never re-calls the LLM. Degrades to "" if no model is reachable.
    """
    import hashlib

    from . import llm

    key = hashlib.sha1(f"{full_note} {chunk}".encode("utf-8")).hexdigest()
    cache = _load_context_cache()
    if key in cache:
        return cache[key]

    body = _strip_frontmatter(full_note)[:3000]
    system = (
        "Give a single short sentence (max 20 words) that situates the following "
        "excerpt within its document, to improve search retrieval. Output only the "
        "sentence, no preamble."
    )
    user = f"Document '{title}':\n{body}\n\nExcerpt:\n{chunk[:800]}"
    try:
        ctx = llm.chat(system, user).strip().replace("\n", " ")
    except llm.LLMError:
        ctx = ""
    cache[key] = ctx
    _save_context_cache()
    return ctx


if __name__ == "__main__":
    stats = build_index()
    print(f"Indexed {stats['chunks']} chunks from {stats['files']} notes.")
