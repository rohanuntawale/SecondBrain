"""Note repository — the shared source of truth for note content.

Two interchangeable backends, chosen by STORAGE_BACKEND:

- "local"    : Markdown files under NOTES_DIR (default; single machine).
- "supabase" : a Postgres `notes` table so multiple people share ONE vault
               (e.g. you + your partner both see each other's notes & diary).

Both expose the same small NoteRecord API. The rest of core/ never touches the
filesystem or SQL directly — it goes through get_repo(). The vector index
(ChromaDB) is always a LOCAL cache rebuilt from whatever the repo returns, so in
Supabase mode every client re-embeds the same shared content identically.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from functools import lru_cache
from pathlib import Path

from . import config


@dataclass
class NoteRecord:
    """One note: a logical path id, its full Markdown, and last-modified time."""

    path: str  # e.g. "welcome.md" or "diary/2026-06-22-rohan-114331.md"
    content: str  # full Markdown including YAML front-matter
    updated: datetime


def _validate_rel(path: str) -> str:
    """Validate a logical note path (works for both backends). Blocks traversal."""
    p = path.replace("\\", "/").lstrip("/")
    parts = p.split("/")
    if not p or ".." in parts or ":" in p:
        raise ValueError(f"Unsafe note path: {path!r}")
    if not p.endswith(".md"):
        raise ValueError("Note path must end with .md")
    return p


# --- Local filesystem backend -------------------------------------------------

class FileRepo:
    """Notes are Markdown files under NOTES_DIR (the original behavior)."""

    def __init__(self) -> None:
        self.root = config.NOTES_DIR

    def _abs(self, path: str) -> Path:
        rel = _validate_rel(path)
        root = self.root.resolve()
        cand = (root / rel).resolve()
        if root not in cand.parents and cand != root:
            raise ValueError(f"Refusing to access path outside notes vault: {path}")
        return cand

    def all_notes(self) -> list[NoteRecord]:
        out: list[NoteRecord] = []
        if not self.root.exists():
            return out
        for p in sorted(self.root.rglob("*.md")):
            rel = str(p.relative_to(self.root)).replace("\\", "/")
            out.append(
                NoteRecord(
                    rel,
                    p.read_text(encoding="utf-8"),
                    datetime.fromtimestamp(p.stat().st_mtime),
                )
            )
        return out

    def get(self, path: str) -> NoteRecord | None:
        p = self._abs(path)
        if not p.exists():
            return None
        return NoteRecord(
            _validate_rel(path),
            p.read_text(encoding="utf-8"),
            datetime.fromtimestamp(p.stat().st_mtime),
        )

    def exists(self, path: str) -> bool:
        return self._abs(path).exists()

    def save(self, path: str, content: str) -> str:
        p = self._abs(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return _validate_rel(path)

    def delete(self, path: str) -> None:
        p = self._abs(path)
        if p.exists():
            p.unlink()

    def list_paths(self) -> list[str]:
        return sorted(n.path for n in self.all_notes())


# --- Supabase (shared cloud) backend ------------------------------------------

class SupabaseRepo:
    """Notes live in a Postgres table so multiple users share one vault.

    Schema (see docs/SUPABASE_SETUP.md):
        notes(path text primary key, content text, updated_at timestamptz)
    """

    TABLE = "notes"

    def __init__(self) -> None:
        if not (config.SUPABASE_URL and config.SUPABASE_KEY):
            raise ValueError(
                "STORAGE_BACKEND=supabase but SUPABASE_URL / SUPABASE_KEY are not set."
            )
        from supabase import create_client  # lazy: only needed in this mode

        self.client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)

    def _row(self, row: dict) -> NoteRecord:
        return NoteRecord(
            row["path"], row.get("content", ""), _parse_ts(row.get("updated_at"))
        )

    def all_notes(self) -> list[NoteRecord]:
        res = self.client.table(self.TABLE).select("*").order("path").execute()
        return [self._row(r) for r in (res.data or [])]

    def get(self, path: str) -> NoteRecord | None:
        rel = _validate_rel(path)
        res = (
            self.client.table(self.TABLE)
            .select("*")
            .eq("path", rel)
            .limit(1)
            .execute()
        )
        rows = res.data or []
        return self._row(rows[0]) if rows else None

    def exists(self, path: str) -> bool:
        return self.get(path) is not None

    def save(self, path: str, content: str) -> str:
        rel = _validate_rel(path)
        self.client.table(self.TABLE).upsert(
            {"path": rel, "content": content, "updated_at": datetime.now().isoformat()},
            on_conflict="path",
        ).execute()
        return rel

    def delete(self, path: str) -> None:
        self.client.table(self.TABLE).delete().eq(
            "path", _validate_rel(path)
        ).execute()

    def list_paths(self) -> list[str]:
        res = self.client.table(self.TABLE).select("path").order("path").execute()
        return sorted(r["path"] for r in (res.data or []))


def _parse_ts(value) -> datetime:
    """Parse an ISO timestamp from Supabase into a naive local-ish datetime."""
    if not value:
        return datetime.now()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(
            tzinfo=None
        )
    except ValueError:
        return datetime.now()


@lru_cache(maxsize=1)
def get_repo():
    """Return the configured repository (cached). Switch via STORAGE_BACKEND."""
    if config.STORAGE_BACKEND == "supabase":
        return SupabaseRepo()
    return FileRepo()
