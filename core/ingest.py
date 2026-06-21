"""Markdown -> heading chunks -> embeddings -> ChromaDB.

Chunking strategy: split each note on Markdown headings (#, ##, ###). If a single
section is longer than CHUNK_MAX_CHARS, sub-split it on paragraph boundaries.
"""

from __future__ import annotations

import re
from pathlib import Path

try:
    from . import config, store
except ImportError:  # allow running directly: python core/ingest.py
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core import config, store

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_FRONTMATTER_RE = re.compile(r"^---\s*\n.*?\n---\s*\n", re.DOTALL)


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


def _split_paragraphs(text: str, max_chars: int) -> list[str]:
    """Greedily pack paragraphs into pieces no longer than max_chars."""
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
    return pieces or [text.strip()]


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
    """Re-index the whole notes/ folder. Returns a small stats dict."""
    notes_dir: Path = config.NOTES_DIR
    notes_dir.mkdir(parents=True, exist_ok=True)

    store.reset_collection()

    ids, texts, metadatas = [], [], []
    files = sorted(notes_dir.rglob("*.md"))

    for path in files:
        raw = path.read_text(encoding="utf-8")
        rel = str(path.relative_to(notes_dir)).replace("\\", "/")
        title = _front_matter_title(raw, fallback=path.stem)
        for i, (heading, chunk_text) in enumerate(
            chunk_markdown(raw, title, config.CHUNK_MAX_CHARS)
        ):
            ids.append(f"{rel}::{i}")
            texts.append(chunk_text)
            metadatas.append(
                {"source": rel, "heading": heading, "note_title": title}
            )

    if texts:
        embeddings = store.embed(texts)
        store.add_chunks(ids, texts, metadatas, embeddings)

    return {"files": len(files), "chunks": len(texts)}


if __name__ == "__main__":
    stats = build_index()
    print(f"Indexed {stats['chunks']} chunks from {stats['files']} notes.")
