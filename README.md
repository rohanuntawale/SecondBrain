# SecondBrain — RAG + MCP Smart Notes Assistant

A personal knowledge assistant that **reads** your Markdown notes (RAG with
citations) and **acts** on them (create notes, suggest tags, add `[[wiki-links]]`,
find orphans). One shared `core/` brain is exposed two ways: a **Streamlit web
app** and an **MCP server** for Claude Desktop.

> Retrieval grounds the answers; the MCP server lets the agent act on the
> knowledge base — an *active* second brain, not a read-only chatbot.

## Quick start (Windows / PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env          # then edit .env if needed
```

### Choose an LLM provider

Edit `.env`:

- **Cloud / free (default):** get a free key at
  [console.groq.com](https://console.groq.com), set `LLM_PROVIDER=groq` and
  `GROQ_API_KEY=gsk_...`. No local model download needed.
- **Local / offline:** install [Ollama](https://ollama.com), then
  `ollama pull llama3.2:3b`, and set `LLM_PROVIDER=ollama`.

> Retrieval works without any LLM — you just won't get a generated answer until a
> provider is configured.

### Index your notes and try it

```powershell
python scripts\reindex.py        # build the vector index from notes/
python -m core.rag               # ask a sample question end-to-end
streamlit run app.py             # launch the web UI at http://localhost:8501
```

## Project layout

```
core/        one brain: config, llm (provider switch), store (ChromaDB),
             ingest (md -> chunks -> embeddings), rag (Q&A + citations),
             tools (note actions)
notes/       the Markdown vault (source of truth)
mcp_server.py  FastMCP server (Claude Desktop)
app.py         Streamlit web UI (deployed)
scripts/     reindex.py, evaluate.py
docs/        project context, report outline, deploy guide
```

## Advanced features (all free)

Beyond basic RAG, SecondBrain now includes:

- **Hybrid search** — fuses dense embeddings with BM25 keyword scoring so exact
  terms (names, dates) aren't missed. On by default (`HYBRID_SEARCH=1`).
- **Cross-encoder reranking** — retrieve wide, then re-score the top with a small
  cross-encoder for sharper citations (`RERANK=1`).
- **HyDE query expansion** — embeds a hypothetical answer for better recall
  (`HYDE=1`).
- **Contextual retrieval** — Anthropic's technique; an LLM-written context line
  is prepended to each chunk before embedding, cached by hash
  (`CONTEXTUAL_RETRIEVAL=1`).
- **Agentic multi-hop RAG** — the model issues follow-up searches when the first
  pass is thin (`AGENTIC_RAG=1`).
- **Overlapping chunking** + **embedding/answer caching** for quality and speed.
- **Knowledge graph** (🕸️ Graph page) — interactive `[[wiki-link]]` graph with
  hub/orphan analysis (networkx + pyvis).
- **More tools** — `summarize_note`, `extract_action_items`,
  `find_duplicate_notes`, `merge_notes`, `web_search` (DuckDuckGo, no key), plus
  AI auto-tagging + TL;DR on note creation. All exposed over MCP.
- **Semantic photo search** — find pictures by description via CLIP
  (`PHOTO_SEARCH=1`); falls back to caption search.
- **Voice I/O** — speak answers (browser TTS) + mic dictation (local Whisper).
- **Evaluation harness** — `python scripts/evaluate.py --judge` scores
  faithfulness / relevance / context-precision with a free LLM-as-judge.
- **Persistent vectors (optional)** — Supabase pgvector backend
  (`VECTOR_BACKEND=pgvector`, see `docs/PGVECTOR_SETUP.md`).
- **Observability + CI** — JSONL retrieval logging (`RETRIEVAL_LOG=1`), a pytest
  suite, GitHub Actions CI, and a scheduled daily-digest email workflow.

### 🧪 Beta features (`core/beta.py`, the **🧪 Beta** page)

Experimental but fully working; all degrade gracefully with no LLM. Default on
(`BETA_FEATURES=1`), also exposed over MCP.

- **💞 For the two of you** — **time capsules** (seal a message until a future
  date), a **gratitude jar**, **mood correlation** (do your moods move
  together?), a **"how well do you know me" quiz** generated from a partner's
  diary, an AI **year-in-review**, and AI **journaling prompts** (🪄 on Diary).
- **🧠 Smarter brain** — a **weekly retrospective** over recent notes/diary,
  **stale-note resurfacing** (spaced-repetition nudges), **unified search**
  across notes *and* photos in one query, and **calendar (`.ics`) export** of
  important dates and a note's action items into real reminders.

Heavy models (reranker, CLIP, Whisper) are lazy-loaded and **default off** so the
low-RAM Streamlit Cloud deploy keeps working; enable them locally via `.env` and
`pip install -r requirements-extra.txt`. All knobs are documented in
`.env.example`.

## Status

- [x] Scaffold, sample notes, config
- [x] ChromaDB store + heading-based ingest
- [x] Provider switch (Ollama | Groq)
- [x] RAG answer with citations
- [x] Note-action tools (search/create/suggest_tags/link/orphans)
- [x] `mcp_server.py` (FastMCP wrappers)
- [x] `app.py` (Streamlit UI)
- [ ] Deploy to Streamlit Community Cloud

See `docs/PROJECT_CONTEXT.md` for the full specification and `docs/DEPLOY.md` for
deployment steps.
