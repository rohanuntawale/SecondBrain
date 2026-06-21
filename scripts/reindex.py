"""CLI: rebuild the whole ChromaDB index from the notes/ folder.

Usage:
    python scripts/reindex.py
"""

import sys
from pathlib import Path

# Allow running as a plain script (add project root to sys.path).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import ingest, store  # noqa: E402


def main():
    stats = ingest.build_index()
    print(f"Re-indexed {stats['chunks']} chunks from {stats['files']} notes.")
    print(f"ChromaDB now holds {store.count()} chunks.")


if __name__ == "__main__":
    main()
