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


from functools import lru_cache


@lru_cache(maxsize=1)
def _reranker():
    """Load the cross-encoder reranker once (lazy; ~80MB)."""
    from sentence_transformers import CrossEncoder

    return CrossEncoder(config.RERANK_MODEL)


def _hyde_query(question: str) -> str:
    """HyDE: draft a hypothetical answer to embed instead of the bare question.

    A passage-shaped query sits closer to real note chunks in embedding space
    than a terse question does, improving recall. Falls back to the original
    question if no LLM is reachable.
    """
    system = (
        "Write a short, factual paragraph (2-3 sentences) that would plausibly "
        "answer the user's question, as if excerpted from their personal notes. "
        "Do not say you are unsure; just write the passage."
    )
    try:
        draft = llm.chat(system, question).strip()
    except llm.LLMError:
        return question
    # Keep the original question terms too, so keyword signal isn't lost.
    return f"{question}\n{draft}" if draft else question


def _rerank(question: str, docs: list, metas: list, k: int):
    """Re-score (doc, meta) pairs with a cross-encoder and keep the top k."""
    if not docs:
        return docs, metas
    try:
        scores = _reranker().predict([(question, d) for d in docs])
    except Exception:
        return docs[:k], metas[:k]  # degrade gracefully to retrieval order
    order = sorted(range(len(docs)), key=lambda i: float(scores[i]), reverse=True)[:k]
    return [docs[i] for i in order], [metas[i] for i in order]


def retrieve(question: str, k: int | None = None):
    """Return (documents, metadatas) for the top chunks for `question`.

    Pipeline (each stage is config-flagged): optional HyDE query expansion ->
    hybrid dense+sparse retrieval of a wide candidate set -> optional
    cross-encoder reranking down to k.
    """
    k = k or config.TOP_K

    search_text = _hyde_query(question) if config.HYDE else question
    q_emb = store.embed_query(search_text)

    # Pull a wider candidate set when reranking, so the reranker has choices.
    n = max(k, config.RERANK_CANDIDATES) if config.RERANK else k
    if config.HYBRID_SEARCH:
        res = store.query_hybrid(search_text, q_emb, n)
    else:
        res = store.query(q_emb, n)
    docs = res.get("documents", [[]])[0]
    metas = res.get("metadatas", [[]])[0]

    if config.RERANK:
        docs, metas = _rerank(question, docs, metas, k)
    else:
        docs, metas = docs[:k], metas[:k]

    _log_retrieval(question, metas)
    return docs, metas


def _log_retrieval(question: str, metas: list) -> None:
    """Append a one-line JSONL retrieval trace (free observability), if enabled."""
    if not config.RETRIEVAL_LOG:
        return
    import json
    from datetime import datetime

    try:
        config.RETRIEVAL_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        row = {
            "ts": datetime.now().isoformat(timespec="seconds"),
            "q": question,
            "hits": [m.get("source") for m in metas],
            "flags": {
                "hybrid": config.HYBRID_SEARCH,
                "rerank": config.RERANK,
                "hyde": config.HYDE,
            },
        }
        with config.RETRIEVAL_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
    except OSError:
        pass


def _dedupe(docs, metas):
    """Drop duplicate chunks (same source+heading) while preserving order."""
    seen, d_out, m_out = set(), [], []
    for d, m in zip(docs, metas):
        key = (m.get("source"), m.get("heading"), d[:60])
        if key in seen:
            continue
        seen.add(key)
        d_out.append(d)
        m_out.append(m)
    return d_out, m_out


def agentic_retrieve(question: str, k: int | None = None):
    """Multi-hop retrieval: if the first pass looks thin, let the LLM propose a
    follow-up search and merge the results.

    Up to config.AGENTIC_MAX_STEPS extra hops. The LLM either replies DONE (the
    context already answers the question) or emits a single refined search query.
    Degrades to a single retrieve() if no LLM is reachable.
    """
    k = k or config.TOP_K
    docs, metas = retrieve(question, k)
    asked = {question}

    for _ in range(max(0, config.AGENTIC_MAX_STEPS)):
        context = _format_context(docs, metas) if docs else "(nothing retrieved yet)"
        system = (
            "You are a retrieval planner. Given the question and the notes "
            "retrieved so far, decide if they are enough to answer well. Reply "
            "with exactly 'DONE' if so. Otherwise reply with ONE short search "
            "query (different from previous ones) that would find the missing "
            "information. Output only 'DONE' or the query."
        )
        user = f"Question: {question}\n\nRetrieved so far:\n{context}"
        try:
            decision = llm.chat(system, user).strip()
        except llm.LLMError:
            break
        if not decision or decision.upper().startswith("DONE"):
            break
        follow = decision.splitlines()[0].strip().strip('"')
        if follow in asked:
            break
        asked.add(follow)
        more_d, more_m = retrieve(follow, k)
        docs, metas = _dedupe(docs + more_d, metas + more_m)

    # Cap to a sensible context size (k * hops can grow).
    limit = k * (config.AGENTIC_MAX_STEPS + 1)
    return docs[:limit], metas[:limit]


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
        docs, metas = (
            agentic_retrieve(question) if config.AGENTIC_RAG else retrieve(question)
        )
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

    docs, metas = (
        agentic_retrieve(question) if config.AGENTIC_RAG else retrieve(question)
    )

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
