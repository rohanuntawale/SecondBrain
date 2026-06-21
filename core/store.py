"""ChromaDB access + a single shared sentence-transformers embedder.

We deliberately compute embeddings ourselves (not Chroma's default embedder) so
that local dev (Ollama) and deployment (Groq) retrieve identically.
"""

from __future__ import annotations

from functools import lru_cache

import chromadb

from . import config


@lru_cache(maxsize=1)
def _embedder():
    """Load the embedding model once and cache it (it is ~80MB)."""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(config.EMBED_MODEL)


def embed(texts: list[str]) -> list[list[float]]:
    """Embed a list of strings into vectors."""
    model = _embedder()
    return model.encode(texts, normalize_embeddings=True).tolist()


@lru_cache(maxsize=1)
def _client():
    config.CHROMA_DIR.mkdir(parents=True, exist_ok=True)
    return chromadb.PersistentClient(path=str(config.CHROMA_DIR))


def get_collection():
    """Return the persistent `notes` collection, creating it if needed."""
    return _client().get_or_create_collection(
        name=config.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def reset_collection():
    """Drop and recreate the collection (used before a full re-index)."""
    client = _client()
    try:
        client.delete_collection(config.COLLECTION_NAME)
    except Exception:
        # Collection may not exist yet — that's fine.
        pass
    return client.get_or_create_collection(
        name=config.COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def add_chunks(ids, texts, metadatas, embeddings):
    """Add pre-embedded chunks to the collection."""
    get_collection().add(
        ids=ids,
        documents=texts,
        metadatas=metadatas,
        embeddings=embeddings,
    )


def query(embedding: list[float], k: int):
    """Return the top-k nearest chunks for a single query embedding."""
    return get_collection().query(
        query_embeddings=[embedding],
        n_results=k,
        include=["documents", "metadatas", "distances"],
    )


def count() -> int:
    """Number of chunks currently stored."""
    return get_collection().count()
