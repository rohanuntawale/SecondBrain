"""In-memory vector store + BM25 keyword index + a shared embedder.

Note-chunk embeddings are kept in a NumPy matrix and searched with cosine
similarity. Alongside them we keep a BM25 sparse index over the same chunks so
retrieval can fuse dense (semantic) and sparse (keyword) scores — "hybrid
search", which catches exact terms (names, dates, jargon) that pure embeddings
miss. The index is rebuilt from the source of truth (local files or the shared
Supabase vault) on each startup via ingest.build_index(), so no persistence
layer is needed.

Why not ChromaDB? It pulls in sqlite/protobuf/gRPC/opentelemetry, which is heavy
and fragile to deploy (e.g. Streamlit Cloud). For a personal-scale corpus a
direct NumPy search is simpler, lighter, and behaves identically. We still
compute embeddings ourselves so local and deployed retrieval match.
"""

from __future__ import annotations

import re
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


@lru_cache(maxsize=1024)
def _embed_one_cached(text: str) -> tuple:
    """Cache single-string embeddings — query embeddings repeat across reruns."""
    vec = _embedder().encode([text], normalize_embeddings=True)[0]
    return tuple(float(x) for x in vec)


def embed_query(text: str) -> list[float]:
    """Embed one query string, served from an LRU cache when seen before."""
    return list(_embed_one_cached(text))


# --- BM25 sparse index --------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall(text.lower())


# In-memory index, shared across Streamlit reruns within a process.
_INDEX: dict = {"ids": [], "docs": [], "metas": [], "embs": None, "bm25": None}


def _use_pg() -> bool:
    """True when the persistent Supabase pgvector backend is selected."""
    return config.VECTOR_BACKEND == "pgvector"


def get_collection() -> dict:
    """Return the in-memory index (kept for interface parity)."""
    return _INDEX


def reset_collection() -> dict:
    """Clear the index (called before a full re-index)."""
    if _use_pg():
        from . import pgvector

        pgvector.reset_collection()
    _INDEX["ids"] = []
    _INDEX["docs"] = []
    _INDEX["metas"] = []
    _INDEX["embs"] = None
    _INDEX["bm25"] = None
    return _INDEX


def add_chunks(ids, texts, metadatas, embeddings) -> None:
    """Append pre-embedded chunks to the index and (re)build the BM25 index."""
    if _use_pg():
        from . import pgvector

        pgvector.add_chunks(ids, texts, metadatas, embeddings)
        return
    _INDEX["ids"].extend(ids)
    _INDEX["docs"].extend(texts)
    _INDEX["metas"].extend(metadatas)
    arr = np.asarray(embeddings, dtype="float32")
    _INDEX["embs"] = arr if _INDEX["embs"] is None else np.vstack([_INDEX["embs"], arr])
    _rebuild_bm25()


def _rebuild_bm25() -> None:
    """Rebuild the BM25 index over all current docs (no-op if lib missing)."""
    if not _INDEX["docs"]:
        _INDEX["bm25"] = None
        return
    try:
        from rank_bm25 import BM25Okapi
    except ImportError:
        _INDEX["bm25"] = None  # hybrid search silently degrades to dense-only
        return
    _INDEX["bm25"] = BM25Okapi([_tokenize(d) for d in _INDEX["docs"]])


def _shape(order, sims_by_idx) -> dict:
    """Build a ChromaDB-shaped result from ranked indices + a sim lookup."""
    docs = [_INDEX["docs"][i] for i in order]
    metas = [_INDEX["metas"][i] for i in order]
    dists = [float(1.0 - sims_by_idx[i]) for i in order]
    return {"documents": [docs], "metadatas": [metas], "distances": [dists]}


def _dense_sims(embedding: list[float]) -> np.ndarray:
    q = np.asarray(embedding, dtype="float32")
    return _INDEX["embs"] @ q  # unit-normalized vectors -> dot product == cosine


def query(embedding: list[float], k: int) -> dict:
    """Return the top-k nearest chunks for a single query embedding (dense only).

    Mirrors ChromaDB's result shape: lists wrapped one level deep, with cosine
    *distance* (1 - similarity) so callers compute similarity as 1 - distance.
    """
    if _use_pg():
        from . import pgvector

        return pgvector.query(embedding, k)

    embs = _INDEX["embs"]
    if embs is None or not _INDEX["ids"]:
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    sims = _dense_sims(embedding)
    k = min(k, sims.shape[0])
    top = np.argpartition(-sims, k - 1)[:k]
    top = top[np.argsort(-sims[top])]
    return _shape(top, sims)


def _minmax(x: np.ndarray) -> np.ndarray:
    """Scale an array into [0, 1]; flat arrays map to all-zeros."""
    lo, hi = float(x.min()), float(x.max())
    if hi - lo < 1e-9:
        return np.zeros_like(x)
    return (x - lo) / (hi - lo)


def query_hybrid(
    query_text: str, embedding: list[float], k: int, alpha: float | None = None
) -> dict:
    """Hybrid dense+sparse retrieval.

    Fuses min-max-normalized cosine similarity (weight `alpha`) with BM25
    keyword scores (weight `1 - alpha`). Falls back to dense-only if the BM25
    index is unavailable. The returned `distances` encode the *fused* score as
    `1 - fused` so existing callers ("similarity = 1 - distance") keep working.
    """
    if _use_pg():
        return query(embedding, k)  # pgvector path is dense-only (no in-RAM BM25)

    embs = _INDEX["embs"]
    if embs is None or not _INDEX["ids"]:
        return {"documents": [[]], "metadatas": [[]], "distances": [[]]}

    alpha = config.HYBRID_ALPHA if alpha is None else alpha
    dense = _dense_sims(embedding)
    bm25 = _INDEX.get("bm25")
    if bm25 is None:
        return query(embedding, k)

    sparse = np.asarray(bm25.get_scores(_tokenize(query_text)), dtype="float32")
    fused = alpha * _minmax(dense) + (1.0 - alpha) * _minmax(sparse)

    k = min(k, fused.shape[0])
    top = np.argpartition(-fused, k - 1)[:k]
    top = top[np.argsort(-fused[top])]
    return _shape(top, fused)


def get_doc(idx: int) -> tuple[str, dict]:
    """Return (text, metadata) for a chunk by its position (for reranking)."""
    return _INDEX["docs"][idx], _INDEX["metas"][idx]


def count() -> int:
    """Number of chunks currently indexed."""
    return len(_INDEX["ids"])
