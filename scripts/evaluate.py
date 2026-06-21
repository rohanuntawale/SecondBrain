"""Evaluation harness for the report's Results chapter.

Fill `GROUND_TRUTH` with ~30 questions and the note file you expect the answer to
come from. This measures retrieval hit-rate@k and per-query latency. Answer
correctness / citation accuracy are scored manually (print-out helps).

    python scripts/evaluate.py
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core import config, rag  # noqa: E402

# (question, expected_source_substring). Add ~30 entries from your notes.
GROUND_TRUTH = [
    ("What does RAG stand for?", "rag-basics.md"),
    ("Why does RAG reduce hallucination?", "rag-basics.md"),
    ("What is MCP?", "mcp-basics.md"),
    ("What tools does the MCP server expose?", "mcp-basics.md"),
    ("Where do RAG and MCP meet in SecondBrain?", "mcp-basics.md"),
    ("How do I use SecondBrain?", "welcome.md"),
]


def hit_at_k(question: str, expected: str, k: int) -> bool:
    docs, metas = rag.retrieve(question, k=k)
    return any(expected in (m.get("source") or "") for m in metas)


def main():
    print(f"Provider: {config.LLM_PROVIDER} | Eval set: {len(GROUND_TRUTH)} questions\n")

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
    print("\n(Answer correctness & citation accuracy: score manually.)")


if __name__ == "__main__":
    main()
