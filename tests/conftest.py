"""Pytest config: force the offline, local backend before core/ is imported.

Tests must not hit Supabase or download/run an LLM, so we pin a local, all-flags
sane environment here (config.py reads env at import time).
"""

import os

os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("VECTOR_BACKEND", "memory")
os.environ.setdefault("HYBRID_SEARCH", "1")
os.environ.setdefault("HYDE", "0")
os.environ.setdefault("RERANK", "0")
os.environ.setdefault("AGENTIC_RAG", "0")
os.environ.setdefault("CONTEXTUAL_RETRIEVAL", "0")

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
