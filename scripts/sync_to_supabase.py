"""One-time seed/migration: push local notes/*.md into the shared Supabase vault.

Run this AFTER creating the `notes` table (see docs/SUPABASE_SETUP.md) and
setting SUPABASE_URL / SUPABASE_KEY in .env. It uploads every Markdown file under
NOTES_DIR (including diary/) so the shared cloud vault starts with your existing
notes.

    python scripts/sync_to_supabase.py

It does NOT require STORAGE_BACKEND=supabase — it always reads local files and
writes to Supabase, so you can seed the cloud while still running locally.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config  # noqa: E402
from core.repo import SupabaseRepo, _validate_rel  # noqa: E402


def main() -> None:
    if not (config.SUPABASE_URL and config.SUPABASE_KEY):
        raise SystemExit("Set SUPABASE_URL and SUPABASE_KEY in .env first.")

    repo = SupabaseRepo()
    root = config.NOTES_DIR
    files = sorted(root.rglob("*.md"))
    if not files:
        raise SystemExit(f"No .md files found under {root}.")

    pushed = 0
    for p in files:
        rel = _validate_rel(str(p.relative_to(root)).replace("\\", "/"))
        repo.save(rel, p.read_text(encoding="utf-8"))
        print(f"  ↑ {rel}")
        pushed += 1

    print(f"\nUploaded {pushed} note(s) to Supabase table '{SupabaseRepo.TABLE}'.")
    print("Now set STORAGE_BACKEND=supabase to use the shared vault.")


if __name__ == "__main__":
    main()
