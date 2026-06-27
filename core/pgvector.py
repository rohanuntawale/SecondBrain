"""Optional persistent vector store backed by Supabase pgvector.

The default store (core/store.py) holds embeddings in memory and rebuilds them
from the vault on every boot. That is simple and free, but re-embeds the whole
corpus each startup. With VECTOR_BACKEND=pgvector the embeddings live in a
Postgres `note_chunks` table (pgvector extension), so retrieval is persistent
and scales past what fits in RAM — and a cold start no longer re-embeds.

This module mirrors the small store.py interface (reset/add_chunks/query) so
ingest.build_index() and rag.retrieve() can use it interchangeably. Dense-only:
BM25 hybrid still runs in-memory in store.py, so when pgvector is on hybrid
search is skipped (reranking still applies). See docs/PGVECTOR_SETUP.md for the
one-time SQL (table + ivfflat index + match_note_chunks RPC).
"""

from __future__ import annotations

from functools import lru_cache

from . import config


@lru_cache(maxsize=1)
def _client():
    if not (config.SUPABASE_URL and config.SUPABASE_KEY):
        raise ValueError("VECTOR_BACKEND=pgvector needs SUPABASE_URL / SUPABASE_KEY.")
    from supabase import create_client

    return create_client(config.SUPABASE_URL, config.SUPABASE_KEY)


TABLE = "note_chunks"


def reset_collection() -> None:
    """Delete all stored chunks (full re-index)."""
    # delete-all needs a predicate; id >= 0 matches every row.
    _client().table(TABLE).delete().gte("id", 0).execute()


def add_chunks(ids, texts, metadatas, embeddings) -> None:
    """Upsert pre-embedded chunks. `embeddings` are plain float lists."""
    rows = []
    for cid, text, meta, emb in zip(ids, texts, metadatas, embeddings):
        rows.append(
            {
                "chunk_id": cid,
                "content": text,
                "source": meta.get("source"),
                "heading": meta.get("heading"),
                "note_title": meta.get("note_title"),
                "embedding": list(emb),
            }
        )
    # Batch to keep request sizes reasonable.
    client = _client()
    for i in range(0, len(rows), 100):
        client.table(TABLE).upsert(rows[i : i + 100], on_conflict="chunk_id").execute()


def query(embedding: list[float], k: int) -> dict:
    """Top-k nearest chunks via the match_note_chunks RPC. ChromaDB-shaped."""
    res = _client().rpc(
        "match_note_chunks",
        {"query_embedding": list(embedding), "match_count": k},
    ).execute()
    rows = res.data or []
    docs = [r["content"] for r in rows]
    metas = [
        {
            "source": r.get("source"),
            "heading": r.get("heading"),
            "note_title": r.get("note_title"),
        }
        for r in rows
    ]
    # RPC returns cosine similarity; convert to distance for caller parity.
    dists = [float(1.0 - r.get("similarity", 0.0)) for r in rows]
    return {"documents": [docs], "metadatas": [metas], "distances": [dists]}


def count() -> int:
    res = _client().table(TABLE).select("id", count="exact").limit(1).execute()
    return res.count or 0
