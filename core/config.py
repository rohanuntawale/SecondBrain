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

# Collection name inside ChromaDB.
COLLECTION_NAME: str = "notes"


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
        ]
    )


if __name__ == "__main__":
    print(summary())
