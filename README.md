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
