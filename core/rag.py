"""Retrieval-Augmented Generation: retrieve top-k chunks, build a grounded
prompt, call the LLM, and return the answer plus its sources (citations).
"""

from __future__ import annotations

try:
    from . import config, llm, store
except ImportError:  # allow running directly: python core/rag.py
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from core import config, llm, store

_SYSTEM = (
    "You are SecondBrain, answering questions about the user's personal notes. "
    "Answer ONLY using the provided context. Cite sources inline as "
    "[note_title › heading]. If the answer is not in the context, say you "
    "don't have that in the notes. Be concise."
)


def _format_context(docs, metas) -> str:
    blocks = []
    for doc, meta in zip(docs, metas):
        tag = f"[{meta.get('note_title', '?')} › {meta.get('heading', '?')}]"
        blocks.append(f"{tag}\n{doc}")
    return "\n\n---\n\n".join(blocks)


def retrieve(question: str, k: int | None = None):
    """Return (documents, metadatas) for the top-k chunks for `question`."""
    k = k or config.TOP_K
    q_emb = store.embed([question])[0]
    res = store.query(q_emb, k)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]
    return docs, metas


def answer(question: str) -> dict:
    """Full RAG answer with citations.

    Returns: {"answer": str, "sources": [{source, heading, note_title}], "context_found": bool}
    """
    docs, metas = retrieve(question)

    if not docs:
        return {
            "answer": "No notes are indexed yet. Run the re-index step first.",
            "sources": [],
            "context_found": False,
        }

    context = _format_context(docs, metas)
    user_msg = f"Context:\n\n{context}\n\nQuestion: {question}"

    try:
        text = llm.chat(_SYSTEM, user_msg)
    except llm.LLMError as e:
        text = (
            "[LLM unavailable] Retrieval worked, but no language model is reachable "
            f"yet. Set up Ollama or Groq to get generated answers.\n\nDetails: {e}"
        )

    sources = [
        {
            "source": m.get("source"),
            "heading": m.get("heading"),
            "note_title": m.get("note_title"),
        }
        for m in metas
    ]
    return {"answer": text, "sources": sources, "context_found": True}


if __name__ == "__main__":
    out = answer("What is RAG and why use it?")
    print(out["answer"])
    print("\nSources:")
    for s in out["sources"]:
        print(f"  - {s['note_title']} › {s['heading']}  ({s['source']})")
