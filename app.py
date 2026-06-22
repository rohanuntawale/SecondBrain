"""SecondBrain — Streamlit web UI (deployed, friend-facing).

One brain, two faces: this UI calls the same core/ logic as the MCP server.

Run locally:
    streamlit run app.py
"""

from __future__ import annotations

import os
import random
from datetime import date

import streamlit as st

# On Streamlit Cloud, secrets arrive via st.secrets — mirror them into the
# environment BEFORE importing core (which reads env at import time).
# Locally there is no secrets.toml (config comes from .env), and touching
# st.secrets then raises StreamlitSecretNotFoundError — so guard it.
try:
    for key in (
        "LLM_PROVIDER", "GROQ_API_KEY", "GROQ_MODEL", "OLLAMA_MODEL",
        "STORAGE_BACKEND", "SUPABASE_URL", "SUPABASE_KEY",
    ):
        if key in st.secrets:
            os.environ[key] = str(st.secrets[key])
except Exception:
    pass  # no secrets.toml found locally — fall back to .env / environment

import pandas as pd  # noqa: E402

from core import config, couple, ingest, rag, store, tools  # noqa: E402

st.set_page_config(page_title="SecondBrain", page_icon="🧠", layout="wide")


# --- White & gold styling -----------------------------------------------------
GOLD = "#C8A227"
GOLD_DARK = "#A67C00"

# The two people sharing this vault (used for note/diary attribution).
USERS = ["Rohan", "Pooja"]
# A distinct color per person so "mine" and "hers" read differently at a glance.
AUTHOR_COLORS = {"Rohan": "#A67C00", "Pooja": "#D6336C"}
SHARED_COLOR = "#6B7280"


def author_color(author: str) -> str:
    return AUTHOR_COLORS.get(author, SHARED_COLOR)


def author_chip(author: str) -> str:
    """A small colored pill labeling who a note belongs to."""
    label = author or "shared"
    return (
        f'<span style="background:{author_color(author)};color:#fff;'
        f'padding:1px 9px;border-radius:11px;font-size:.74rem;'
        f'font-weight:600;white-space:nowrap;">{label}</span>'
    )

st.markdown(
    f"""
    <style>
    /* ---- Motion keyframes ---- */
    @keyframes sbFadeUp   {{ from {{opacity:0; transform:translateY(14px);}} to {{opacity:1; transform:translateY(0);}} }}
    @keyframes sbGradient {{ 0% {{background-position:0% 50%;}} 50% {{background-position:100% 50%;}} 100% {{background-position:0% 50%;}} }}
    @keyframes sbShimmer  {{ 0% {{transform:translateX(-120%);}} 60%,100% {{transform:translateX(220%);}} }}
    @keyframes sbFloat    {{ 0%,100% {{transform:translateY(0) rotate(0);}} 50% {{transform:translateY(-7px) rotate(-6deg);}} }}
    @keyframes sbSheen    {{ 0% {{background-position:-200% 0;}} 100% {{background-position:200% 0;}} }}

    /* Page + sidebar background */
    .stApp {{ background: #FFFFFF; }}
    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, #FFFDF7 0%, #FBF6E9 100%);
        border-right: 1px solid #EAD9A0;
    }}

    /* Animated gold gradient header banner */
    .sb-hero {{
        position: relative;
        overflow: hidden;
        background: linear-gradient(110deg, {GOLD} 0%, #F0D87A 30%, #FFF7DD 55%, #E7C95B 80%, {GOLD} 100%);
        background-size: 250% 250%;
        animation: sbGradient 9s ease infinite, sbFadeUp .7s ease both;
        border: 1px solid #EAD9A0;
        border-radius: 16px;
        padding: 1.5rem 1.9rem;
        margin-bottom: 1.2rem;
        box-shadow: 0 6px 22px rgba(200,162,39,0.22);
    }}
    /* Light sweep that glides across the hero */
    .sb-hero::after {{
        content: "";
        position: absolute; top: 0; left: 0; height: 100%; width: 40%;
        background: linear-gradient(100deg, transparent, rgba(255,255,255,.55), transparent);
        transform: translateX(-120%);
        animation: sbShimmer 5.5s ease-in-out infinite;
    }}
    .sb-hero h1 {{ margin: 0; color: #3A2E00; font-size: 2.1rem; position: relative; z-index: 1; }}
    .sb-hero p  {{ margin: .25rem 0 0; color: #5C4A12; font-size: 1rem; position: relative; z-index: 1; }}
    .sb-brain {{ display: inline-block; animation: sbFloat 3.2s ease-in-out infinite; transform-origin: 70% 70%; }}

    /* Buttons → gold, with lift + sheen on hover */
    .stButton > button {{
        background: linear-gradient(180deg, #E7C95B 0%, {GOLD} 100%);
        color: #3A2E00;
        border: 1px solid {GOLD_DARK};
        border-radius: 10px;
        font-weight: 600;
        transition: transform .15s ease, box-shadow .15s ease, background .2s ease;
    }}
    .stButton > button:hover {{
        background: linear-gradient(180deg, {GOLD} 0%, {GOLD_DARK} 100%);
        color: #FFFFFF;
        border-color: {GOLD_DARK};
        transform: translateY(-2px);
        box-shadow: 0 6px 16px rgba(166,124,0,0.35);
    }}
    .stButton > button:active {{ transform: translateY(0); }}

    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {{ gap: .4rem; }}
    .stTabs [data-baseweb="tab"] {{
        background: #FBF6E9;
        border-radius: 10px 10px 0 0;
        padding: .35rem 1rem;
        transition: background .2s ease, transform .15s ease;
    }}
    .stTabs [data-baseweb="tab"]:hover {{ transform: translateY(-2px); }}
    .stTabs [aria-selected="true"] {{
        background: linear-gradient(90deg, {GOLD}, #E7C95B, {GOLD});
        background-size: 200% 100%;
        animation: sbSheen 6s linear infinite;
        color: #3A2E00 !important;
    }}

    /* Diary entry card — fades up on render, lifts on hover */
    .sb-card {{
        background: #FFFDF7;
        border: 1px solid #EAD9A0;
        border-left: 5px solid {GOLD};
        border-radius: 12px;
        padding: .9rem 1.1rem;
        margin-bottom: .8rem;
        box-shadow: 0 2px 8px rgba(200,162,39,0.10);
        animation: sbFadeUp .5s ease both;
        transition: transform .15s ease, box-shadow .15s ease;
    }}
    .sb-card:hover {{ transform: translateY(-3px); box-shadow: 0 8px 20px rgba(200,162,39,0.20); }}
    .sb-card .meta {{ color: {GOLD_DARK}; font-size: .85rem; font-weight: 600; }}
    .sb-card .body {{ color: #2B2B2B; margin-top: .35rem; }}

    /* Spinner tinted gold */
    .stSpinner > div {{ border-top-color: {GOLD} !important; }}

    /* Radio groups (nav bar, mode & author pickers) wrap on narrow screens
       instead of overflowing, so every option stays reachable on a phone. */
    div[role="radiogroup"] {{ flex-wrap: wrap; gap: .25rem .7rem; }}

    /* The top nav radio styled as tappable pills. */
    div[data-testid="stHorizontalBlock"] {{ gap: .6rem; }}
    div.row-widget.stRadio > div[role="radiogroup"] > label {{
        margin: 0 !important;
        padding: .15rem .15rem;
    }}

    /* ---- Mobile tweaks ---- */
    @media (max-width: 640px) {{
        .block-container {{
            padding: 1rem .8rem 3rem .8rem !important;
        }}
        .sb-hero {{ padding: 1.05rem 1.15rem; border-radius: 13px; }}
        .sb-hero h1 {{ font-size: 1.55rem; }}
        .sb-hero p  {{ font-size: .88rem; }}
        /* Full-width, comfortably tappable buttons on phones. */
        .stButton > button {{ width: 100%; padding: .55rem 1rem; }}
        /* Stack any side-by-side columns vertically. */
        div[data-testid="stHorizontalBlock"] {{ flex-direction: column; }}
        .stTabs [data-baseweb="tab"] {{ padding: .3rem .6rem; }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="sb-hero">
        <h1><span class="sb-brain">🧠</span> SecondBrain</h1>
        <p>Your shared second brain — ask your notes, chat freely, and keep a diary.</p>
    </div>
    """,
    unsafe_allow_html=True,
)


# --- Sidebar ------------------------------------------------------------------
with st.sidebar:
    st.title("🧠 SecondBrain")
    st.caption("RAG + MCP smart notes assistant")
    st.markdown(f"**LLM provider:** `{config.LLM_PROVIDER}`")

    _is_cloud = config.STORAGE_BACKEND == "supabase"
    st.markdown(
        f"**Storage:** `{config.STORAGE_BACKEND}`"
        + (" ☁️ _(shared vault)_" if _is_cloud else " 💾 _(this machine)_")
    )

    try:
        chunk_count = store.count()
    except Exception:
        chunk_count = 0

    # In shared (Supabase) mode the local vector cache may be empty on a fresh
    # session — pull the shared notes and build the index once automatically.
    if _is_cloud and chunk_count == 0:
        with st.spinner("Syncing shared vault…"):
            try:
                stats = ingest.build_index()
                chunk_count = stats["chunks"]
            except Exception as e:
                st.error(f"Could not reach the shared vault: {e}")

    st.markdown(
        f"**Indexed chunks:** {chunk_count}"
        if chunk_count
        else "**Indexed chunks:** _(not indexed yet)_"
    )

    sync_label = "☁️ Sync from cloud" if _is_cloud else "🔄 Re-index notes"
    if st.button(sync_label):
        with st.spinner("Re-indexing..."):
            stats = ingest.build_index()
        st.success(f"Indexed {stats['chunks']} chunks from {stats['files']} notes.")

    if config.LLM_PROVIDER == "groq" and not config.GROQ_API_KEY:
        st.warning("No GROQ_API_KEY set — retrieval works, but answers need a key.")


# --- Tabs ---------------------------------------------------------------------
PAGES = [
    "💬 Ask", "💞 Us", "📔 Diary", "📚 Notes", "✍️ Create", "📰 Digest", "⬆️ Upload"
]
# A wrapping radio "nav bar" instead of st.tabs — tabs scroll off-screen on
# phones, hiding pages; a horizontal radio wraps to multiple rows on narrow
# screens so every page stays reachable.
page = st.radio(
    "Go to", PAGES, horizontal=True, label_visibility="collapsed", key="nav"
)

# Ask -------------------------------------------------------------------------
if page == "💬 Ask":
    st.subheader("Ask anything")
    _MODE_LABELS = {
        "notes": "📚 Notes only (grounded + citations)",
        "hybrid": "✨ Hybrid (notes first, then general knowledge)",
        "general": "💭 General chat (no notes)",
    }
    mode_label = st.radio(
        "Mode",
        list(_MODE_LABELS.values()),
        horizontal=True,
        help="Notes = strictly from your vault. Hybrid = notes first, falls back "
        "to general knowledge. General = a normal assistant, ignores your notes.",
    )
    mode = next(k for k, v in _MODE_LABELS.items() if v == mode_label)

    placeholder = (
        "What is RAG and why use it?"
        if mode == "notes"
        else "Ask me anything — e.g. 'suggest a cute date idea'"
    )
    question = st.text_input("Question", placeholder=placeholder)
    if st.button("Ask", type="primary") and question.strip():
        with st.spinner("Thinking..."):
            result = rag.answer(question, mode=mode)
        st.markdown(result["answer"])
        if result["sources"]:
            with st.expander("Sources"):
                for s in result["sources"]:
                    st.markdown(
                        f"- **{s['note_title']} › {s['heading']}** "
                        f"(`{s['source']}`)"
                    )

# Us (couple dashboard) -------------------------------------------------------
elif page == "💞 Us":
    st.subheader("💞 Us")
    settings = couple.load_settings()

    # --- Relationship counter + upcoming countdowns ---
    dt = couple.days_together()
    col_a, col_b = st.columns([1, 1])
    with col_a:
        if dt:
            st.markdown(
                f"""
                <div class="sb-card" style="border-left-color:{GOLD};">
                    <div class="meta">Together since {dt['start']}</div>
                    <div class="body" style="font-size:1.5rem;">
                        💛 <b>{dt['days']}</b> days
                        <span style="font-size:.95rem;color:#5C4A12;">
                        ({dt['years']}y {dt['months']}m {dt['rem_days']}d)</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.info("Set your start date in **⚙️ Setup** below to start the counter.")
    with col_b:
        ups = couple.upcoming_dates()
        if ups:
            lines = "".join(
                f"<div class='body'>🎉 <b>{u['label']}</b> in "
                f"<b>{u['days_until']}</b> day(s) <span style='color:#888'>"
                f"({u['next']})</span></div>"
                for u in ups[:4]
            )
            st.markdown(
                f'<div class="sb-card" style="border-left-color:{AUTHOR_COLORS["Pooja"]};">'
                f'<div class="meta">Upcoming</div>{lines}</div>',
                unsafe_allow_html=True,
            )
        else:
            st.caption("Add birthdays/anniversaries in ⚙️ Setup for countdowns.")

    # --- On this day ---
    st.markdown("#### 📅 On this day")
    memories = couple.on_this_day()
    if memories:
        for e in memories:
            st.markdown(
                f"{author_chip(e['author'])} &nbsp; *{e['date']}* — "
                f"**{e['title']}**: {e['preview']}",
                unsafe_allow_html=True,
            )
    else:
        st.caption("No past memories on today's date yet — they'll appear here over time. 💫")

    # --- Mood chart ---
    st.markdown("#### 📈 Our moods")
    rows = couple.mood_series()
    if rows:
        df = pd.DataFrame(rows)
        pivot = (
            df.pivot_table(index="date", columns="author", values="score", aggfunc="mean")
            .sort_index()
        )
        st.line_chart(pivot)
        st.caption("Mood scale: 😢 1 → 🥰 5. Add moods to diary entries to grow this.")
    else:
        st.caption("Pick a mood when writing diary entries to see trends here.")

    # --- Daily love note ---
    st.markdown("#### 💌 Love note")
    lc1, lc2 = st.columns([1, 2])
    with lc1:
        recipient = st.selectbox("To", USERS, key="lovenote_to")
    sender = next(u for u in USERS if u != recipient)
    if st.button(f"💌 Write a note for {recipient}"):
        with st.spinner("Composing..."):
            note = couple.love_note(sender, recipient)
        st.markdown(
            f'<div class="sb-card" style="border-left-color:{author_color(sender)};">'
            f'<div class="meta">From {sender} to {recipient}</div>'
            f'<div class="body" style="font-style:italic;">“{note}”</div></div>',
            unsafe_allow_html=True,
        )

    # --- Date-idea jar ---
    st.markdown("#### 🫙 Date-idea jar")
    jar = couple.list_date_ideas()
    jc1, jc2 = st.columns(2)
    with jc1:
        if st.button("🎲 Surprise us (from our jar)"):
            if jar:
                idea = couple.pick_date_idea(random.randrange(len(jar)))
                st.success(f"🎲 {idea}")
            else:
                st.info("Your jar is empty — add ideas or generate a fresh one →")
    with jc2:
        if st.button("✨ Generate a fresh idea (AI)"):
            with st.spinner("Thinking of something fun..."):
                idea = couple.date_idea()
            st.success(f"✨ {idea}")
            st.session_state["_last_idea"] = idea

    new_idea = st.text_input(
        "Add an idea to the jar",
        value=st.session_state.get("_last_idea", ""),
        placeholder="Sunset picnic at the lake",
    )
    if st.button("➕ Add to jar") and new_idea.strip():
        couple.add_date_idea(new_idea)
        st.session_state["_last_idea"] = ""
        st.success("Added! 🫙")
        st.rerun()
    if jar:
        with st.expander(f"🫙 Our jar ({len(jar)} ideas)"):
            for i, idea in enumerate(jar, 1):
                st.markdown(f"{i}. {idea}")

    # --- Setup ---
    with st.expander("⚙️ Setup (start date & important dates)"):
        start_raw = settings.get("start_date", "")
        start_val = date.fromisoformat(start_raw) if start_raw else None
        new_start = st.date_input("Relationship start date", value=start_val)
        st.caption("Important dates (label + date). Add rows as needed.")
        existing = settings.get("important_dates", [])
        dates_df = pd.DataFrame(existing or [{"label": "", "date": ""}])
        edited = st.data_editor(
            dates_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config={
                "label": st.column_config.TextColumn("Label", help="e.g. Pooja's birthday"),
                "date": st.column_config.TextColumn("Date (MM-DD)", help="e.g. 08-14"),
            },
            key="dates_editor",
        )
        if st.button("💾 Save setup", type="primary"):
            cleaned = [
                {"label": str(r["label"]).strip(), "date": str(r["date"]).strip()}
                for r in edited.to_dict("records")
                if str(r.get("label", "")).strip() and str(r.get("date", "")).strip()
            ]
            couple.save_settings(
                {
                    "start_date": new_start.isoformat() if new_start else "",
                    "important_dates": cleaned,
                    "date_jar": settings.get("date_jar", []),
                }
            )
            st.success("Saved! 💛")
            st.rerun()


# Diary -----------------------------------------------------------------------
elif page == "📔 Diary":
    st.subheader("📔 Shared diary")
    st.caption("Write dated entries. Each one becomes a note — searchable in Ask "
               "and summarized in the Digest.")

    with st.form("diary_form", clear_on_submit=True):
        c1, c2 = st.columns([2, 1])
        with c1:
            d_author = st.radio("Who's writing?", USERS, horizontal=True)
        with c2:
            d_mood = st.selectbox("Mood (optional)", ["", *couple.MOODS])
        d_title = st.text_input("Title (optional)", placeholder="A good day")
        d_body = st.text_area("Entry", height=160, placeholder="Today we…")
        submitted = st.form_submit_button("💛 Save entry", type="primary")
        if submitted:
            try:
                path = tools.add_diary_entry(
                    d_body, author=d_author, mood=d_mood, title=d_title
                )
                st.success(f"Saved `{path}` and indexed.")
                st.balloons()
            except Exception as e:
                st.error(str(e))

    st.markdown("---")
    entries = tools.list_diary_entries()
    if not entries:
        st.info("No diary entries yet — write your first one above. 💛")
    else:
        authors = ["Everyone"] + tools.diary_authors()
        who = st.selectbox("Show entries by", authors)
        shown = entries if who == "Everyone" else [
            e for e in entries if e["author"] == who
        ]
        for e in shown:
            mood = f" · {e['mood']}" if e["mood"] else ""
            color = author_color(e["author"])
            st.markdown(
                f"""
                <div class="sb-card" style="border-left-color:{color};">
                    <div class="meta">
                        {author_chip(e['author'])} &nbsp; {e['date']}{mood}
                    </div>
                    <div class="body"><b>{e['title']}</b><br>{e['preview']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )

# Notes -----------------------------------------------------------------------
elif page == "📚 Notes":
    st.subheader("Browse notes")
    detailed = tools.list_notes_detailed()
    if not detailed:
        st.info("No notes yet. Add some on the Create or Upload tab.")
    else:
        whose = st.radio(
            "Whose notes?", ["Everyone", *USERS, "Shared"], horizontal=True
        )

        def _belongs(n: dict) -> bool:
            if whose == "Everyone":
                return True
            if whose == "Shared":
                return not n["author"]
            return n["author"] == whose

        shown = [n for n in detailed if _belongs(n)]

    if detailed and not shown:
        st.info(f"No notes for **{whose}** yet.")
    elif detailed:
        # Quick overview list with author chips (📔 marks diary entries).
        for n in shown:
            icon = "📔" if n["type"] == "diary" else "📝"
            st.markdown(
                f"{author_chip(n['author'])} &nbsp; {icon} **{n['title']}** "
                f"&nbsp;<code>{n['path']}</code>",
                unsafe_allow_html=True,
            )
        st.markdown("")

        chosen = st.selectbox("Pick a note", [n["path"] for n in shown])
        col1, col2, col3 = st.columns(3)
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
        with col3:
            if st.button("🪢 Suggest links"):
                links = tools.suggest_links(chosen)
                if not links:
                    st.info("No strongly related notes found.")
                else:
                    for s in links:
                        st.markdown(
                            f"- **[[{s['note_title']}]]** "
                            f"(`{s['source']}`, score {s['score']})"
                        )
            if st.button("🪢➕ Auto-link related"):
                try:
                    st.success(tools.auto_link(chosen))
                except Exception as e:
                    st.error(str(e))
        st.markdown("---")
        st.code(tools.read_note(chosen), language="markdown")

# Create ----------------------------------------------------------------------
elif page == "✍️ Create":
    st.subheader("Create a note")
    title = st.text_input("Title")
    c1, c2 = st.columns([1, 2])
    with c1:
        c_author = st.radio("Whose note?", [*USERS, "Shared"], horizontal=True)
    with c2:
        tags_raw = st.text_input("Tags (comma-separated)", "")
    body = st.text_area("Body", height=200)
    if st.button("Create note", type="primary"):
        if not title.strip():
            st.error("Title is required.")
        else:
            tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
            author = "" if c_author == "Shared" else c_author
            try:
                path = tools.create_note(title, body, tags, author=author)
                st.success(f"Created `{path}` and re-indexed.")
                st.balloons()
            except Exception as e:
                st.error(str(e))

# Digest ----------------------------------------------------------------------
elif page == "📰 Digest":
    st.subheader("Daily digest")
    st.caption("Summarize the notes you created or edited on a given day.")
    on = st.date_input("Day", value=None)
    if st.button("Generate digest", type="primary"):
        with st.spinner("Summarizing..."):
            digest = tools.daily_digest(on.isoformat() if on else None)
        st.markdown(f"**{digest['date']}** — {len(digest['notes'])} note(s) touched")
        if digest["notes"]:
            for n in digest["notes"]:
                st.markdown(f"- **{n['title']}** (`{n['path']}`, edited {n['modified']})")
        st.markdown("---")
        st.markdown(digest["summary"])

# Upload ----------------------------------------------------------------------
elif page == "⬆️ Upload":
    st.subheader("Upload notes")
    st.caption(
        "Upload **.md or .pdf** files into the shared vault, then they're "
        "searchable everywhere. PDF text is extracted automatically."
    )
    uploaded = st.file_uploader(
        "Choose .md or .pdf files",
        type=["md", "pdf"],
        accept_multiple_files=True,
    )
    if uploaded and st.button("Save & re-index", type="primary"):
        saved, errors = [], []
        with st.spinner("Importing & indexing..."):
            for f in uploaded:
                try:
                    saved.append(tools.import_file(f.name, f.getvalue()))
                except Exception as e:
                    errors.append(f"{f.name}: {e}")
            if saved:
                stats = ingest.build_index()
        for err in errors:
            st.error(err)
        if saved:
            st.success(
                f"Imported {len(saved)} file(s); indexed {stats['chunks']} chunks."
            )
            st.balloons()
