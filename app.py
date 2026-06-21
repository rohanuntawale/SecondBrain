"""SecondBrain — Streamlit web UI (deployed, friend-facing).

One brain, two faces: this UI calls the same core/ logic as the MCP server.

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

# On Streamlit Cloud, secrets arrive via st.secrets — mirror them into the
# environment BEFORE importing core (which reads env at import time).
for key in ("LLM_PROVIDER", "GROQ_API_KEY", "GROQ_MODEL", "OLLAMA_MODEL"):
    if key in st.secrets:
        os.environ[key] = str(st.secrets[key])

from core import config, ingest, rag, store, tools  # noqa: E402

st.set_page_config(page_title="SecondBrain", page_icon="🧠", layout="wide")


# --- Sidebar ------------------------------------------------------------------
with st.sidebar:
    st.title("🧠 SecondBrain")
    st.caption("RAG + MCP smart notes assistant")
    st.markdown(f"**LLM provider:** `{config.LLM_PROVIDER}`")
    try:
        st.markdown(f"**Indexed chunks:** {store.count()}")
    except Exception:
        st.markdown("**Indexed chunks:** _(not indexed yet)_")

    if st.button("🔄 Re-index notes"):
        with st.spinner("Re-indexing..."):
            stats = ingest.build_index()
        st.success(f"Indexed {stats['chunks']} chunks from {stats['files']} notes.")

    if config.LLM_PROVIDER == "groq" and not config.GROQ_API_KEY:
        st.warning("No GROQ_API_KEY set — retrieval works, but answers need a key.")


# --- Tabs ---------------------------------------------------------------------
tab_ask, tab_notes, tab_create, tab_upload = st.tabs(
    ["💬 Ask", "📚 Notes", "✍️ Create", "⬆️ Upload"]
)

# Ask -------------------------------------------------------------------------
with tab_ask:
    st.subheader("Ask your notes")
    question = st.text_input("Question", placeholder="What is RAG and why use it?")
    if st.button("Ask", type="primary") and question.strip():
        with st.spinner("Thinking..."):
            result = rag.answer(question)
        st.markdown(result["answer"])
        if result["sources"]:
            with st.expander("Sources"):
                for s in result["sources"]:
                    st.markdown(
                        f"- **{s['note_title']} › {s['heading']}** "
                        f"(`{s['source']}`)"
                    )

# Notes -----------------------------------------------------------------------
with tab_notes:
    st.subheader("Browse notes")
    note_paths = tools.list_notes()
    if not note_paths:
        st.info("No notes yet. Add some on the Upload tab.")
    else:
        chosen = st.selectbox("Pick a note", note_paths)
        col1, col2 = st.columns(2)
        with col1:
            if st.button("🏷️ Suggest tags"):
                try:
                    tags = tools.suggest_tags(chosen)
                    st.success(", ".join(tags) if tags else "No tags suggested.")
                except Exception as e:
                    st.error(str(e))
        with col2:
            if st.button("🔗 Find orphans"):
                orphans = tools.find_orphans()
                st.write(orphans or "No orphan notes 🎉")
        st.markdown("---")
        st.code(tools.read_note(chosen), language="markdown")

# Create ----------------------------------------------------------------------
with tab_create:
    st.subheader("Create a note")
    title = st.text_input("Title")
    tags_raw = st.text_input("Tags (comma-separated)", "")
    body = st.text_area("Body", height=200)
    if st.button("Create note", type="primary"):
        if not title.strip():
            st.error("Title is required.")
        else:
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
            try:
                path = tools.create_note(title, body, tags)
                st.success(f"Created `{path}` and re-indexed.")
            except Exception as e:
                st.error(str(e))

# Upload ----------------------------------------------------------------------
with tab_upload:
    st.subheader("Upload Markdown notes")
    st.caption("Upload .md files into the vault, then re-index to query them.")
    uploaded = st.file_uploader(
        "Choose .md files", type=["md"], accept_multiple_files=True
    )
    if uploaded and st.button("Save & re-index", type="primary"):
        config.NOTES_DIR.mkdir(parents=True, exist_ok=True)
        for f in uploaded:
            safe_name = Path(f.name).name  # strip any path components
            (config.NOTES_DIR / safe_name).write_bytes(f.getvalue())
        stats = ingest.build_index()
        st.success(
            f"Saved {len(uploaded)} file(s); indexed {stats['chunks']} chunks."
        )
