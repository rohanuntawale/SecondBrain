"""In-memory vector store + a shared sentence-transformers embedder.

Note-chunk embeddings are kept in a NumPy matrix and searched with cosine
similarity directly. The index is rebuilt from the source of truth (local files
or the shared Supabase vault) on each startup via ingest.build_index(), so no
persistence layer is needed.

Why not ChromaDB? It pulls in sqlite/protobuf/gRPC/opentelemetry, which is heavy
and fragile to deploy (e.g. Streamlit Cloud). For a personal-scale corpus a
direct NumPy search is simpler, lighter, and behaves identically. We still
compute embeddings ourselves so local and deployed retrieval match.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from . import config


@lru_cache(maxsize=1)
def _embedder():
    """Load the embedding model once and cache it (it is ~80MB)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(config.EMBED_MODEL)


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings into unit-normalized vectors."""
    model = _embedder()
    return model.encode(texts, normalize_embeddings=True).tolist()


# In-memory index, shared across Streamlit reruns within a process.
_INDEX: dict = {"ids": [], "docs": [], "metas": [], "embs": None}


def get_collection() -> dict:
    """Return the in-memory index (kept for interface parity)."""
    return _INDEX


def reset_collection() -> dict:
    """Clear the index (called before a full re-index)."""
    _INDEX["ids"] = []
    _INDEX["docs"] = []
    _INDEX["metas"] = []
    _INDEX["embs"] = None
    return _INDEX


def add_chunks(ids, texts, metadatas, embeddings) -> None:
    """Append pre-embedded chunks to the index."""
    _INDEX["ids"].extend(ids)
    _INDEX["docs"].extend(texts)
    _INDEX["metas"].extend(metadatas)
    arr = np.asarray(embeddings, dtype="float32")
    _INDEX["embs"] = arr if _INDEX["embs"] is None else np.vstack([_INDEX["embs"], arr])


def query(embedding: list[float], k: int) -> dict:
    """Return the top-k nearest chunks for a single query embedding.

    Mirrors ChromaDB's result shape: lists wrapped one level deep, with cosine
    *distance* (1 - similarity) so callers compute similarity as 1 - distance.
    """
    embs = _INDEX["embs"]
    if embs is None or not _INDEX["ids"]:
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    q = np.asarray(embedding, dtype="float32")
    sims = embs @ q  # vectors are unit-normalized -> dot product == cosine sim
    k = min(k, sims.shape[0])
    top = np.argpartition(-sims, k - 1)[:k]
    top = top[np.argsort(-sims[top])]

    docs = [_INDEX["docs"][i] for i in top]
    metas = [_INDEX["metas"][i] for i in top]
    dists = [float(1.0 - sims[i]) for i in top]
    return {"documents": [docs], "metadatas": [metas], "distances": [dists]}


def count() -> int:
    """Number of chunks currently indexed."""
    return len(_INDEX["ids"])
