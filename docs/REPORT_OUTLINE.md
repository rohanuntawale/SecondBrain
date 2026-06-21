# SecondBrain — Thesis / Report Outline

A chapter skeleton for the final-year report. Fill each section using the code in
`core/` and the evaluation results from your 30-question test set.

## 1. Introduction
- Problem: notes pile up; static search and read-only chatbots don't help organize.
- Idea: a *second brain* that both answers from your notes and acts on them.
- Contributions: (1) RAG with citations over a personal vault, (2) an MCP server
  exposing note actions, (3) the bidirectional read/write loop where retrieval
  itself is an MCP tool.

## 2. Background
- **RAG**: embeddings, vector similarity, retrieval + generation, grounding,
  hallucination reduction, citations.
- **MCP**: open standard, tools as typed functions, stdio transport, clients.
- **Vector databases & embeddings**: ChromaDB, `all-MiniLM-L6-v2`, cosine space.

## 3. System Design / Architecture
- The `core/` shared-brain pattern; two faces (Streamlit + MCP).
- Provider abstraction (`llm.chat()`), swappable via `LLM_PROVIDER`.
- Data flow diagram (notes -> chunk -> embed -> store -> retrieve -> generate).
- Chunking strategy: by Markdown heading, paragraph sub-split over a char cap.

## 4. Implementation
- Module-by-module walkthrough (config, store, ingest, rag, tools, mcp_server, app).
- The note-action tools and their MCP wrappers.
- **Security**: path-traversal guard on all writes (`_safe_path`), notes confined
  to the vault.

## 5. Deployment
- Local (Ollama, offline) vs hosted (Groq free tier) and *why* the split exists.
- Streamlit Community Cloud, secrets, the ephemeral-filesystem limitation.

## 6. Evaluation / Results
- 30-question ground-truth set.
- Metrics table: retrieval hit-rate@k (k=3,5), answer correctness,
  citation accuracy, tag-suggestion precision, latency (Ollama vs Groq).
- Discussion of failure cases.

## 7. Limitations & Future Work
- Persistent multi-user storage (e.g. Supabase free tier).
- Hybrid (keyword + vector) retrieval; better chunking.
- Auth for the deployed app; larger corpus evaluation.

## 8. Conclusion
- Recap the bidirectional read/write loop as the core novelty.

## Appendices
- Viva cheat-sheet (see PROJECT_CONTEXT.md §11).
- Setup & run instructions.
- Selected source listings.
