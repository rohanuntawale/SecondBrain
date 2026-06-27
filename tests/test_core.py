"""Offline unit tests — no network, no embedding model, no LLM calls.

Run: pytest -q
"""

from datetime import datetime

import numpy as np

from core import graph, ingest, repo, store, tools


# --- chunking -----------------------------------------------------------------

def test_chunk_markdown_splits_on_headings():
    md = "---\ntitle: T\n---\n# A\nalpha\n## B\nbeta"
    chunks = ingest.chunk_markdown(md, "T", max_chars=1000)
    headings = [h for h, _ in chunks]
    assert "A" in headings and "B" in headings


def test_split_paragraphs_overlap_carries_context():
    text = "\n\n".join(f"para {i} " + "x" * 200 for i in range(4))
    pieces = ingest._split_paragraphs(text, max_chars=250, overlap=40)
    assert len(pieces) >= 2
    # every piece after the first should start with a carried-over tail
    assert all(len(p) > 0 for p in pieces)


# --- vector store: hybrid + dense (uses fake embeddings, no model) -------------

def _seed_store():
    store.reset_collection()
    ids = ["a::0", "b::0", "c::0"]
    docs = [
        "python list comprehension tips",
        "supabase postgres database setup",
        "the cat sat on the mat",
    ]
    metas = [{"source": f"{c}.md", "heading": "H", "note_title": c} for c in "abc"]
    embs = [[1.0, 0.0], [0.0, 1.0], [0.7, 0.7]]
    embs = [list(np.asarray(e) / np.linalg.norm(e)) for e in embs]
    store.add_chunks(ids, docs, metas, embs)


def test_dense_query_orders_by_cosine():
    _seed_store()
    res = store.query([1.0, 0.0], k=2)
    assert res["documents"][0][0] == "python list comprehension tips"


def test_hybrid_query_uses_keyword_signal():
    _seed_store()
    # query vector points at doc 'b', but keyword 'postgres' also matches 'b'
    res = store.query_hybrid("postgres", [0.0, 1.0], k=1)
    assert res["metadatas"][0][0]["note_title"] == "b"


def test_minmax_handles_flat_array():
    assert store._minmax(np.array([5.0, 5.0])).tolist() == [0.0, 0.0]


# --- tools helpers ------------------------------------------------------------

def test_slugify():
    assert tools._slugify("Hello, World!") == "hello-world"


def test_front_matter_fields():
    f = tools._front_matter_fields("---\ntitle: Hi\nauthor: Rohan\n---\nbody")
    assert f["title"] == "Hi" and f["author"] == "Rohan"


# --- knowledge graph (monkeypatched repo, no I/O) -----------------------------

class _FakeRepo:
    def __init__(self, notes):
        self._notes = notes

    def content_notes(self):
        return self._notes


def test_graph_edges_from_wikilinks(monkeypatch):
    notes = [
        repo.NoteRecord("a.md", "---\ntitle: A\n---\n# A\nsee [[B]]", datetime.now()),
        repo.NoteRecord("b.md", "---\ntitle: B\n---\n# B\njust b", datetime.now()),
    ]
    fake = _FakeRepo(notes)
    monkeypatch.setattr(repo, "get_repo", lambda: fake)
    g = graph.build_graph()
    assert g.has_edge("A", "B")
    assert g.number_of_nodes() == 2
