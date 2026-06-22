# SecondBrain — Roadmap Status

Build/test order from `PROJECT_CONTEXT.md` §7. Each step gates the next.
Last updated: **2026-06-22**

| # | Step | Status |
|---|------|--------|
| 1 | Scaffold folder structure + `requirements.txt` + `.env.example` + `.gitignore` + 3 sample notes | ✅ Done |
| 2 | `core/config.py` — env loading (verify it prints config) | ✅ Done |
| 3 | `core/store.py` + `core/ingest.py` — index sample notes into ChromaDB | ✅ Done |
| 4 | `core/llm.py` — wire up provider; `chat("be brief","say hi")` | ✅ Done |
| 5 | `core/rag.py` — full Q&A with citations (MVP heartbeat) | ✅ Done |
| 6 | `core/tools.py` — `search_notes`, `create_note`, `suggest_tags` | ✅ Done |
| 7 | `mcp_server.py` — wrap tools; test in Claude Desktop | ✅ Done |
| 8 | `app.py` — Streamlit UI hitting `core/`; run locally | ✅ Done |
| 9 | **Swap test** — `LLM_PROVIDER=groq`, confirm app still works | ✅ Done (verified 2026-06-21) |
| 10 | Bonus features — auto-link, orphans, daily digest | ✅ Done (verified 2026-06-22) |
| 11 | Deploy to Streamlit Community Cloud (public URL) | ⬜ Todo |
| 12 | Write report from `docs/REPORT_OUTLINE.md` + evaluation §9 | ⬜ Todo |

## Verification notes

**Step 9 (Groq swap test) — passed 2026-06-21:**
- `.env`: `LLM_PROVIDER=groq`, `GROQ_MODEL=llama-3.1-8b-instant`
- `python core/llm.py` → returns a Groq-generated greeting ✅
- `python core/rag.py` → retrieves top-k chunks + Groq generates grounded answer with inline `[note › heading]` citations ✅
- LLM vendor is isolated to `core/llm.py` (`chat(system, user)` routes by `LLM_PROVIDER`) — provider swap is config-only, no code change.

**Step 10 (Bonus features) — passed 2026-06-22:**
- New in `core/tools.py`: `suggest_links(path)` (semantic auto-link via cosine similarity, excludes self + already-linked titles), `auto_link(path)` (writes a `Related:` line of `[[links]]` then re-indexes), `daily_digest(on=None)` (notes touched on a day by file mtime + LLM summary, graceful fallback if no LLM).
- Orphan detection (`find_orphans`) already existed from step 6.
- Wired into `mcp_server.py` (now 12 tools: `suggest_links`, `auto_link`, `daily_digest` added) and `app.py` (Notes tab: "Suggest links" + "Auto-link related"; new "📰 Digest" tab).
- Verified: `suggest_links` returns correct scored candidates and correctly hides already-linked notes; `auto_link` writes + re-indexes; `daily_digest` produced a Groq summary for the sample-note date.

## Next steps (remaining)

- **Step 11 — Deploy:** push repo to public GitHub → `share.streamlit.io` → set main file `app.py` → add Streamlit **Secrets** (`LLM_PROVIDER`, `GROQ_API_KEY`, `GROQ_MODEL`). Note: Streamlit Cloud filesystem is ephemeral — commit sample notes or use the Upload page.
- **Step 12 — Report:** follow `docs/REPORT_OUTLINE.md`.

## Run cheatsheet

```bash
python scripts/reindex.py     # rebuild ChromaDB from notes/
streamlit run app.py          # open http://localhost:8501
python core/rag.py            # quick RAG smoke test
```
