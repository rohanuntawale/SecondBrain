"""Central configuration: loads .env and exposes paths, model names, and knobs.

This is the single place that reads environment variables. Everything else in
core/ imports its settings from here.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Load .env from the project root (parent of this core/ package).
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _path(env_value: str) -> Path:
    """Resolve a path from .env relative to the project root if not absolute."""
    p = Path(env_value)
    return p if p.is_absolute() else (PROJECT_ROOT / p)


# --- Paths ---
NOTES_DIR: Path = _path(os.getenv("NOTES_DIR", "notes"))
CHROMA_DIR: Path = _path(os.getenv("CHROMA_DIR", ".chroma"))

# --- Models ---
EMBED_MODEL: str = os.getenv("EMBED_MODEL", "all-MiniLM-L6-v2")
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
OLLAMA_MODEL: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
GROQ_MODEL: str = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")

# --- Retrieval knobs ---
TOP_K: int = int(os.getenv("TOP_K", "4"))
CHUNK_MAX_CHARS: int = int(os.getenv("CHUNK_MAX_CHARS", "1200"))
CHUNK_OVERLAP_CHARS: int = int(os.getenv("CHUNK_OVERLAP_CHARS", "150"))


def _flag(name: str, default: str = "0") -> bool:
    """Read a boolean feature flag from the environment ('1'/'true'/'yes')."""
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


# --- Advanced retrieval features (all free; heavier ones default OFF so the
# 1GB Streamlit Cloud deploy keeps working — turn them on locally via .env). ---

# Hybrid search: fuse dense (embedding) + sparse (BM25 keyword) scores. Light,
# pure-Python, safe to leave on everywhere.
HYBRID_SEARCH: bool = _flag("HYBRID_SEARCH", "1")
# Weight of the dense score in the fusion (0..1); the sparse weight is 1 - this.
HYBRID_ALPHA: float = float(os.getenv("HYBRID_ALPHA", "0.6"))

# Cross-encoder reranking: retrieve a wide candidate set, then re-score the top
# with a small cross-encoder. Big quality win but loads a ~80MB model -> OFF by
# default to protect the low-RAM cloud deploy.
RERANK: bool = _flag("RERANK", "0")
RERANK_MODEL: str = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
RERANK_CANDIDATES: int = int(os.getenv("RERANK_CANDIDATES", "20"))

# HyDE / query expansion: ask the LLM for a hypothetical answer and embed THAT
# for retrieval. One extra cheap LLM call per query -> default ON when an LLM is
# configured (it degrades gracefully if the call fails).
HYDE: bool = _flag("HYDE", "0")

# Contextual retrieval (Anthropic): prepend an LLM-written one-line context to
# each chunk before embedding. Improves recall a lot but costs one LLM call per
# chunk at index time -> default OFF; results are cached by content hash.
CONTEXTUAL_RETRIEVAL: bool = _flag("CONTEXTUAL_RETRIEVAL", "0")

# Agentic RAG: let the model issue follow-up searches when the first hit is weak.
AGENTIC_RAG: bool = _flag("AGENTIC_RAG", "0")
AGENTIC_MAX_STEPS: int = int(os.getenv("AGENTIC_MAX_STEPS", "2"))

# Semantic photo search via CLIP. Loads a separate model -> default OFF (RAM).
PHOTO_SEARCH: bool = _flag("PHOTO_SEARCH", "0")
CLIP_MODEL: str = os.getenv("CLIP_MODEL", "clip-ViT-B-32")

# Lightweight retrieval/answer logging to a JSONL file (free observability).
RETRIEVAL_LOG: bool = _flag("RETRIEVAL_LOG", "0")
RETRIEVAL_LOG_PATH: Path = _path(os.getenv("RETRIEVAL_LOG_PATH", "logs/retrieval.jsonl"))

# --- Storage backend: "local" (files) or "supabase" (shared cloud vault) ---
STORAGE_BACKEND: str = os.getenv("STORAGE_BACKEND", "local").strip().lower()

# --- Vector backend: "memory" (in-RAM NumPy, default) or "pgvector"
# (persistent Supabase pgvector; needs the one-time SQL in docs/PGVECTOR_SETUP.md).
VECTOR_BACKEND: str = os.getenv("VECTOR_BACKEND", "memory").strip().lower()
SUPABASE_URL: str = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "").strip()

# Collection name inside ChromaDB.
COLLECTION_NAME: str = "notes"

# Internal note namespaces excluded from search/indexing and normal listings:
#   meta/ → app config, love/ → private love notes, photos/ → gallery images,
#   capsule/ → sealed time-capsule notes, gratitude/ → gratitude-jar entries.
# (capsule/ + gratitude/ added by the beta feature layer — see core/beta.py.)
HIDDEN_PREFIXES: tuple[str, ...] = (
    "meta/", "love/", "photos/", "capsule/", "gratitude/",
)

# --- Beta features (core/beta.py): experimental but functional extras. Default
# ON so they work out of the box; set BETA_FEATURES=0 in .env to hide the page.
BETA_FEATURES: bool = _flag("BETA_FEATURES", "1")


def summary() -> str:
    """Human-readable config dump (used by `python -m core.config`)."""
    return "\n".join(
        [
            "SecondBrain config",
            "------------------",
            f"PROJECT_ROOT   = {PROJECT_ROOT}",
            f"NOTES_DIR      = {NOTES_DIR}",
            f"CHROMA_DIR     = {CHROMA_DIR}",
            f"EMBED_MODEL    = {EMBED_MODEL}",
            f"LLM_PROVIDER   = {LLM_PROVIDER}",
            f"OLLAMA_MODEL   = {OLLAMA_MODEL}",
            f"GROQ_MODEL     = {GROQ_MODEL}",
            f"GROQ_API_KEY   = {'<set>' if GROQ_API_KEY else '<empty>'}",
            f"TOP_K          = {TOP_K}",
            f"CHUNK_MAX_CHARS= {CHUNK_MAX_CHARS}",
            f"HYBRID_SEARCH  = {HYBRID_SEARCH} (alpha={HYBRID_ALPHA})",
            f"RERANK         = {RERANK} ({RERANK_MODEL if RERANK else '-'})",
            f"HYDE           = {HYDE}",
            f"CONTEXTUAL_RET = {CONTEXTUAL_RETRIEVAL}",
            f"AGENTIC_RAG    = {AGENTIC_RAG} (max_steps={AGENTIC_MAX_STEPS})",
            f"PHOTO_SEARCH   = {PHOTO_SEARCH}",
            f"STORAGE_BACKEND= {STORAGE_BACKEND}",
            f"SUPABASE_URL   = {SUPABASE_URL or '<empty>'}",
            f"SUPABASE_KEY   = {'<set>' if SUPABASE_KEY else '<empty>'}",
        ]
    )


if __name__ == "__main__":
    print(summary())
