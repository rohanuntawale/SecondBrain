"""Embed every note chunk and upsert the vectors into Supabase pgvector.

Run after creating the schema in docs/PGVECTOR_SETUP.md and setting
VECTOR_BACKEND=pgvector in .env:

    python scripts/sync_pgvector.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config, ingest  # noqa: E402


def main():
    if config.VECTOR_BACKEND != "pgvector":
        print("VECTOR_BACKEND is not 'pgvector' — set it in .env first. Aborting.")
        return
    stats = ingest.build_index()  # routes through store -> pgvector when enabled
    print(f"Synced {stats['chunks']} chunks from {stats['files']} notes to pgvector.")


if __name__ == "__main__":
    main()
