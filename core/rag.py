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

# Three answering modes. "notes" stays strictly grounded (the original RAG
# behavior); "hybrid" prefers notes but may fall back to general knowledge;
# "general" skips retrieval entirely for everyday chit-chat.
_SYSTEM_NOTES = (
    "You are SecondBrain, answering questions about the user's personal notes. "
    "Answer ONLY using the provided context. Cite sources inline as "
    "[note_title › heading]. If the answer is not in the context, say you "
    "don't have that in the notes. Be concise."
)

_SYSTEM_HYBRID = (
    "You are SecondBrain, a warm personal assistant. Prefer the user's notes "
    "below when they are relevant, and cite them inline as [note_title › heading]. "
    "If the notes do not cover the question, you may answer from general "
    "knowledge — but make clear when you are going beyond the notes. Be friendly "
    "and concise."
)

_SYSTEM_GENERAL = (
    "You are SecondBrain, a warm and friendly personal assistant. Answer "
    "everyday questions helpfully and concisely. You are not limited to the "
    "user's notes in this mode."
)

MODES = ("notes", "hybrid", "general")


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


def build_chat_messages(question: str, mode: str = "notes", history=None):
    """Assemble a streaming chat turn: returns (messages, sources).

    `history` is prior turns as [{"role": "user"|"assistant", "content": str}].
    For notes/hybrid modes the freshly retrieved context is injected into the
    current user turn; `sources` lists the cited chunks (empty in general mode).
    """
    mode = mode if mode in MODES else "notes"
    history = history or []
    sources: list[dict] = []

    if mode == "general":
        system = _SYSTEM_GENERAL
        user_content = question
    else:
        docs, metas = retrieve(question)
        sources = [
            {
                "source": m.get("source"),
                "heading": m.get("heading"),
                "note_title": m.get("note_title"),
            }
            for m in metas
        ]
        system = _SYSTEM_NOTES if mode == "notes" else _SYSTEM_HYBRID
        if docs:
            context = _format_context(docs, metas)
            user_content = f"Context:\n\n{context}\n\nQuestion: {question}"
        elif mode == "notes":
            user_content = f"(No relevant notes found.)\n\nQuestion: {question}"
        else:
            user_content = f"(No relevant notes found.)\n\nQuestion: {question}"

    messages = (
        [{"role": "system", "content": system}]
        + list(history)
        + [{"role": "user", "content": user_content}]
    )
    return messages, sources


def answer(question: str, mode: str = "notes") -> dict:
    """Answer a question in one of three modes.

    - "notes":   strictly grounded in retrieved notes, with citations (RAG).
    - "hybrid":  prefers notes but may use general knowledge as a fallback.
    - "general": no retrieval — a plain friendly assistant for everyday questions.

    Returns: {"answer": str, "sources": [{source, heading, note_title}],
              "context_found": bool, "mode": str}
    """
    if mode not in MODES:
        mode = "notes"

    # General mode skips retrieval entirely.
    if mode == "general":
        try:
            text = llm.chat(_SYSTEM_GENERAL, question)
        except llm.LLMError as e:
            text = f"[LLM unavailable] Set up Ollama or Groq to chat.\n\nDetails: {e}"
        return {"answer": text, "sources": [], "context_found": False, "mode": mode}

    docs, metas = retrieve(question)

    if not docs and mode == "notes":
        return {
            "answer": "No notes are indexed yet. Run the re-index step first.",
            "sources": [],
            "context_found": False,
            "mode": mode,
        }

    system = _SYSTEM_NOTES if mode == "notes" else _SYSTEM_HYBRID
    if docs:
        context = _format_context(docs, metas)
        user_msg = f"Context:\n\n{context}\n\nQuestion: {question}"
    else:
        # hybrid with nothing retrieved — answer from general knowledge.
        user_msg = f"(No relevant notes found.)\n\nQuestion: {question}"

    try:
        text = llm.chat(system, user_msg)
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
    return {
        "answer": text,
        "sources": sources,
        "context_found": bool(docs),
        "mode": mode,
    }


if __name__ == "__main__":
    out = answer("What is RAG and why use it?")
    print(out["answer"])
    print("\nSources:")
    for s in out["sources"]:
        print(f"  - {s['note_title']} › {s['heading']}  ({s['source']})")
