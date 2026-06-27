"""Evaluation harness for the report's Results chapter.

Two layers, both free:

1. Retrieval metrics — hit-rate@k and latency over a labelled question set.
2. LLM-as-judge (``--judge``) — for each question, generate the RAG answer and
   have the LLM score it 1-5 on:
       * faithfulness     — is every claim supported by the retrieved context?
       * answer_relevance — does it actually answer the question?
       * context_precision— were the retrieved chunks on-topic?
   This is the standard RAGAS-style rubric without the heavy RAGAS dependency.

Usage:
    python scripts/evaluate.py              # retrieval metrics only
    python scripts/evaluate.py --judge      # + LLM-as-judge scoring
"""

import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config, llm, rag  # noqa: E402

# (question, expected_source_substring). Add ~30 entries from your notes.
GROUND_TRUTH = [
    ("What does RAG stand for?", "rag-basics.md"),
    ("Why does RAG reduce hallucination?", "rag-basics.md"),
    ("What is MCP?", "mcp-basics.md"),
    ("What tools does the MCP server expose?", "mcp-basics.md"),
    ("Where do RAG and MCP meet in SecondBrain?", "mcp-basics.md"),
    ("How do I use SecondBrain?", "welcome.md"),
]

_JUDGE_SYSTEM = (
    "You are a strict RAG evaluator. Given a question, the retrieved context, and "
    "an answer, score 1-5 (5=best) on three axes:\n"
    "- faithfulness: every claim in the answer is supported by the context.\n"
    "- answer_relevance: the answer addresses the question.\n"
    "- context_precision: the context is relevant to the question.\n"
    'Reply ONLY with compact JSON: {"faithfulness":N,"answer_relevance":N,'
    '"context_precision":N}.'
)


def hit_at_k(question: str, expected: str, k: int) -> bool:
    _docs, metas = rag.retrieve(question, k=k)
    return any(expected in (m.get("source") or "") for m in metas)


def judge_one(question: str) -> dict:
    """Generate an answer, then LLM-judge it. Returns the score dict (or {})."""
    docs, metas = rag.retrieve(question)
    context = rag._format_context(docs, metas) if docs else "(no context)"
    out = rag.answer(question, mode="notes")
    user = (
        f"Question: {question}\n\nContext:\n{context}\n\nAnswer:\n{out['answer']}"
    )
    try:
        raw = llm.chat(_JUDGE_SYSTEM, user)
    except llm.LLMError:
        return {}
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    try:
        return json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}


def main():
    use_judge = "--judge" in sys.argv
    print(
        f"Provider: {config.LLM_PROVIDER} | Eval set: {len(GROUND_TRUTH)} questions | "
        f"hybrid={config.HYBRID_SEARCH} rerank={config.RERANK} hyde={config.HYDE}\n"
    )

    hits3 = hits5 = 0
    latencies = []
    for q, expected in GROUND_TRUTH:
        if hit_at_k(q, expected, 3):
            hits3 += 1
        if hit_at_k(q, expected, 5):
            hits5 += 1
        t0 = time.perf_counter()
        rag.retrieve(q, k=config.TOP_K)
        latencies.append(time.perf_counter() - t0)

    n = len(GROUND_TRUTH)
    print(f"Retrieval hit-rate@3: {hits3}/{n} = {hits3 / n:.0%}")
    print(f"Retrieval hit-rate@5: {hits5}/{n} = {hits5 / n:.0%}")
    print(f"Avg retrieval latency: {sum(latencies) / n * 1000:.1f} ms")

    if not use_judge:
        print("\n(Run with --judge for LLM-scored faithfulness/relevance.)")
        return

    print("\nLLM-as-judge (1-5):")
    totals: dict[str, float] = {}
    scored = 0
    for q, _ in GROUND_TRUTH:
        s = judge_one(q)
        if not s:
            print(f"  ? {q[:50]:50}  (no score)")
            continue
        scored += 1
        for k, v in s.items():
            totals[k] = totals.get(k, 0) + float(v)
        line = "  ".join(f"{k}={s.get(k)}" for k in sorted(s))
        print(f"  • {q[:48]:48}  {line}")
    if scored:
        print("\nAverages:")
        for k in sorted(totals):
            print(f"  {k:18}: {totals[k] / scored:.2f} / 5")


if __name__ == "__main__":
    main()
