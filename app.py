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

from core import config, couple, ingest, photos, rag, store, tools  # noqa: E402

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


_HEART_EMOJIS = ["❤️", "💕", "💖", "💗", "💛", "🌹", "💞", "💘"]


def hearts_html(n: int = 16) -> str:
    """Build floating-heart particles for the romantic banner (varied + lively)."""
    spans = []
    for i in range(n):
        left = round(3 + (94 * i / n) + random.uniform(-3, 3), 1)
        size = random.randint(13, 27)
        delay = round(random.uniform(0, 6), 2)
        dur = round(random.uniform(4.5, 8), 2)
        emo = _HEART_EMOJIS[i % len(_HEART_EMOJIS)]
        spans.append(
            f'<span class="heart" style="left:{left}%;font-size:{size}px;'
            f'animation-delay:{delay}s;animation-duration:{dur}s;">{emo}</span>'
        )
    return "".join(spans)

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

    /* ---- Romance (Us page): hearts, heartbeat, polaroids ---- */
    @keyframes floatUp {{
        0%   {{ transform: translateY(0) scale(.5); opacity: 0; }}
        12%  {{ opacity: .95; }}
        100% {{ transform: translateY(-165px) scale(1.15); opacity: 0; }}
    }}
    @keyframes heartbeat {{
        0%,30%,100% {{ transform: scale(1); }}
        8%  {{ transform: scale(1.13); }}
        16% {{ transform: scale(1); }}
        24% {{ transform: scale(1.08); }}
    }}
    @keyframes sparkle {{
        0%,100% {{ opacity:.35; transform: scale(.8) rotate(0); }}
        50%     {{ opacity:1; transform: scale(1.25) rotate(18deg); }}
    }}
    .us-banner {{
        position: relative; overflow: hidden; text-align: center;
        background: linear-gradient(120deg,#FFE0EC 0%, #FBF1D6 45%, #FFD9E8 100%);
        background-size: 200% 200%;
        animation: sbGradient 10s ease infinite;
        border: 1px solid #F2C9D8; border-radius: 18px;
        padding: 1.7rem 1rem 1.5rem; margin-bottom: 1rem;
        box-shadow: 0 8px 26px rgba(214,51,108,.16);
    }}
    .us-banner .names {{
        font-size: 2rem; font-weight: 700; color: #9B2D52;
        position: relative; z-index: 1; display: inline-block;
        animation: heartbeat 2.6s ease-in-out infinite;
    }}
    .us-banner .tag {{ color:#7A5C12; margin-top:.2rem; font-size:1rem; position:relative; z-index:1; }}
    .us-banner .heart {{
        position: absolute; bottom: -14px;
        animation: floatUp 6s linear infinite; pointer-events: none;
    }}
    .us-banner .spark {{ position:absolute; top:12px; animation: sparkle 2.4s ease-in-out infinite; }}

    .polaroid-row {{ display:flex; flex-wrap:wrap; gap:.7rem; justify-content:center; margin:.3rem 0 .5rem; }}
    .polaroid {{
        background:#fff; border:1px solid #F0D6DF; border-radius:10px;
        padding:.55rem .55rem .4rem; width:104px; text-align:center;
        box-shadow:0 4px 12px rgba(155,45,82,.12);
        animation: sbFadeUp .6s ease both;
        transition: transform .2s ease, box-shadow .2s ease;
    }}
    .polaroid:nth-child(odd)  {{ transform: rotate(-3deg); }}
    .polaroid:nth-child(even) {{ transform: rotate(3deg); }}
    .polaroid:hover {{ transform: rotate(0) translateY(-5px) scale(1.06); box-shadow:0 10px 22px rgba(155,45,82,.22); }}
    .polaroid .pic {{ font-size:2.4rem; background:linear-gradient(135deg,#FFE6F0,#FFF6E6); border-radius:7px; padding:.45rem 0; }}
    .polaroid .cap {{ font-size:.78rem; color:#9B2D52; margin-top:.35rem; font-style:italic; }}

    .love-counter {{ animation: heartbeat 2.6s ease-in-out infinite; display:inline-block; }}

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
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');

    html, body, [class*="css"], .stApp, .stMarkdown, input, textarea, button, select {
        font-family: 'Poppins', sans-serif !important;
    }

    /* Soft animated ambient background with drifting glow blobs */
    .stApp {
        background:
            radial-gradient(1000px circle at 0% -10%, rgba(231,201,91,.20), transparent 42%),
            radial-gradient(900px circle at 100% 0%, rgba(214,51,108,.13), transparent 42%),
            radial-gradient(1000px circle at 50% 120%, rgba(231,201,91,.12), transparent 45%),
            #FFFDFA !important;
        background-attachment: fixed !important;
    }
    .stApp::before, .stApp::after {
        content:""; position:fixed; border-radius:50%; z-index:0;
        pointer-events:none; filter: blur(26px);
    }
    .stApp::before {
        width:340px; height:340px; top:-90px; left:-70px;
        background: radial-gradient(circle, rgba(231,201,91,.30), transparent 70%);
        animation: floatBlob 17s ease-in-out infinite alternate;
    }
    .stApp::after {
        width:300px; height:300px; bottom:-80px; right:-60px;
        background: radial-gradient(circle, rgba(214,51,108,.22), transparent 70%);
        animation: floatBlob2 21s ease-in-out infinite alternate;
    }
    @keyframes floatBlob  { from{transform:translate(0,0)} to{transform:translate(70px,50px)} }
    @keyframes floatBlob2 { from{transform:translate(0,0)} to{transform:translate(-60px,-40px)} }

    /* Keep content above the blobs + a gentle entrance */
    [data-testid="stMain"] .block-container {
        position: relative; z-index: 1;
        animation: sbFadeUp .55s ease both;
    }

    /* Warm, bold section headings with a gradient accent underline */
    [data-testid="stMarkdownContainer"] h2,
    [data-testid="stMarkdownContainer"] h3,
    [data-testid="stMarkdownContainer"] h4,
    [data-testid="stMarkdownContainer"] h5 {
        color: #9C6B16 !important; font-weight: 700 !important; letter-spacing:.2px;
    }
    [data-testid="stMarkdownContainer"] h3::after {
        content:""; display:block; width:54px; height:3px; margin-top:7px;
        background: linear-gradient(90deg,#C8A227,#D6336C); border-radius:3px;
    }

    /* Glassy cards */
    .sb-card {
        background: rgba(255,255,255,.72) !important;
        backdrop-filter: blur(9px); -webkit-backdrop-filter: blur(9px);
    }

    /* Buttons: rounded, with a shine sweep on hover */
    .stButton > button {
        position: relative; overflow: hidden;
        border-radius: 12px !important; font-weight: 600 !important;
    }
    .stButton > button::after {
        content:""; position:absolute; top:0; left:-130%; width:55%; height:100%;
        background: linear-gradient(100deg, transparent, rgba(255,255,255,.55), transparent);
        transform: skewX(-18deg); transition: left .55s ease;
    }
    .stButton > button:hover::after { left: 150%; }

    /* Inputs: rounded + gold focus glow */
    .stTextInput input, .stTextArea textarea, .stNumberInput input,
    [data-baseweb="input"], [data-baseweb="select"] > div, [data-baseweb="textarea"] {
        border-radius: 11px !important;
    }
    .stTextInput input:focus, .stTextArea textarea:focus {
        border-color: #C8A227 !important;
        box-shadow: 0 0 0 3px rgba(200,162,39,.18) !important;
    }

    /* Radio "pills" — nav bar + mode/author pickers */
    div[role="radiogroup"] > label {
        background: rgba(255,255,255,.7);
        border: 1px solid #EAD9A0; border-radius: 999px;
        padding: .32rem .9rem !important; margin: 0 !important;
        transition: transform .16s ease, box-shadow .16s ease, background .2s ease;
        backdrop-filter: blur(6px);
    }
    div[role="radiogroup"] > label:hover {
        transform: translateY(-2px); box-shadow: 0 5px 14px rgba(200,162,39,.22);
    }
    div[role="radiogroup"] > label:has(input:checked) {
        background: linear-gradient(135deg,#E7C95B,#C8A227);
        border-color: #A67C00; box-shadow: 0 5px 16px rgba(200,162,39,.34);
    }

    /* Expanders + uploader polish */
    [data-testid="stExpander"] {
        border: 1px solid #EAD9A0 !important; border-radius: 13px !important;
        background: rgba(255,255,255,.6); overflow: hidden;
    }
    [data-testid="stFileUploaderDropzone"] {
        border-radius: 13px !important; border: 1.5px dashed #E0B94B !important;
        background: rgba(251,246,233,.6) !important; transition: all .2s ease;
    }
    [data-testid="stFileUploaderDropzone"]:hover { background: rgba(247,230,184,.7) !important; }

    /* Images: rounded + lift on hover */
    [data-testid="stImage"] img {
        border-radius: 12px; transition: transform .2s ease, box-shadow .2s ease;
        box-shadow: 0 4px 14px rgba(0,0,0,.08);
    }
    [data-testid="stImage"]:hover img {
        transform: scale(1.02); box-shadow: 0 10px 24px rgba(214,51,108,.18);
    }

    /* Gold scrollbar + rounded alerts */
    ::-webkit-scrollbar { width: 10px; height: 10px; }
    ::-webkit-scrollbar-thumb { background: linear-gradient(#E7C95B,#C8A227); border-radius: 10px; }
    ::-webkit-scrollbar-track { background: #FBF6E9; }
    [data-testid="stAlert"] { border-radius: 12px; }
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
    "💬 Ask", "💞 Us", "📸 Photos", "📔 Diary", "📚 Notes",
    "✍️ Create", "📰 Digest", "⬆️ Upload",
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
    settings = couple.load_settings()

    # --- Romantic animated banner (floating hearts + heartbeat) ---
    st.markdown(
        f'<div class="us-banner">{hearts_html()}'
        f'<span class="spark" style="left:11%">✨</span>'
        f'<span class="spark" style="right:11%;top:18px">✨</span>'
        f'<div class="names">{USERS[0]}&nbsp;💞&nbsp;{USERS[1]}</div>'
        f'<div class="tag">together &amp; growing 🌹</div></div>',
        unsafe_allow_html=True,
    )

    # --- Recent shared photos (real ones if added, else cute stand-ins) ---
    recent_photos = photos.list_photos(limit=6)
    if recent_photos:
        st.markdown("##### 📸 Recent memories")
        rcols = st.columns(min(len(recent_photos), 3))
        for i, ph in enumerate(recent_photos):
            with rcols[i % len(rcols)]:
                st.image(ph["data"], caption=(ph["caption"] or ph["by"]),
                         use_container_width=True)
        st.caption("See them all on the 📸 Photos page.")
    else:
        pics = [
            ("💑", "us"), ("🌹", "for you"), ("💌", "love notes"),
            ("🌅", "our sunsets"), ("🥂", "celebrations"), ("🧸", "cuddles"),
        ]
        cards = "".join(
            f'<div class="polaroid"><div class="pic">{e}</div>'
            f'<div class="cap">{c}</div></div>'
            for e, c in pics
        )
        st.markdown(f'<div class="polaroid-row">{cards}</div>', unsafe_allow_html=True)
        st.caption("💡 Add your own pictures on the 📸 Photos page — they'll appear here.")

    # --- Two counters: official + unofficial ---
    def _counter_card(col, bd, title, emoji, color):
        with col:
            if bd:
                st.markdown(
                    f'<div class="sb-card" style="border-left-color:{color};text-align:center;">'
                    f'<div class="meta">{title} · since {bd["start"]}</div>'
                    f'<div class="body"><span class="love-counter" style="font-size:1.7rem;">'
                    f'{emoji} <b>{bd["days"]}</b> days</span></div>'
                    f'<div class="meta">{bd["years"]}y {bd["months"]}m {bd["rem_days"]}d</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.info("Set this date in ⚙️ Setup below.")

    cc1, cc2 = st.columns(2)
    _counter_card(cc1, couple.days_together(), "Official 💍", "💖", AUTHOR_COLORS["Pooja"])
    _counter_card(cc2, couple.days_unofficial(), "Unofficial 💞", "💛", GOLD)

    # --- Upcoming anniversaries / birthdays ---
    ups = couple.upcoming_dates()
    if ups:
        lines = "".join(
            f"<div class='body'>🎉 <b>{u['label']}</b> in "
            f"<b>{u['days_until']}</b> day(s) <span style='color:#888'>"
            f"({u['next']})</span></div>"
            for u in ups[:4]
        )
        st.markdown(
            f'<div class="sb-card" style="border-left-color:{GOLD_DARK};">'
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

    # --- For You: write & receive romantic notes ---
    st.markdown("#### 💌 For You")
    # Clear the editor on the run after a send (must happen before the widget).
    if st.session_state.pop("_love_clear", False):
        st.session_state["love_msg_area"] = ""

    fc1, fc2 = st.columns([1, 1])
    with fc1:
        love_from = st.radio("From", USERS, horizontal=True, key="love_from")
    love_to = next(u for u in USERS if u != love_from)
    with fc2:
        st.markdown(
            f"<div style='padding-top:1.9rem;'>To "
            f"<b style='color:{author_color(love_to)}'>{love_to}</b> 💞</div>",
            unsafe_allow_html=True,
        )

    if st.button("✨ Help me write (AI)"):
        with st.spinner("Finding the words..."):
            st.session_state["love_msg_area"] = couple.love_note(love_from, love_to)
        st.rerun()

    love_msg = st.text_area(
        f"Your note for {love_to}",
        key="love_msg_area",
        placeholder="Write something sweet…",
        height=110,
    )
    if st.button(f"💝 Send to {love_to}", type="primary"):
        if love_msg.strip():
            couple.add_love_message(love_from, love_to, love_msg)
            st.session_state["_love_clear"] = True
            st.success(f"Sent to {love_to} 💞")
            st.balloons()
            st.rerun()
        else:
            st.warning("Write something sweet first 💕")

    # Inbox — notes addressed to a person
    st.markdown("##### 💞 Notes received")
    inbox_who = st.selectbox("Show notes for", USERS, key="love_inbox_who")
    msgs = couple.list_love_messages(inbox_who)
    if not msgs:
        st.caption(f"No notes for {inbox_who} yet — write the first one above 💕")
    else:
        for m in msgs:
            st.markdown(
                f'<div class="sb-card" style="border-left-color:{author_color(m["from"])};">'
                f'<div class="meta">💌 From {m["from"]} · {m["date"]}</div>'
                f'<div class="body" style="font-style:italic;">“{m["message"]}”</div>'
                f"</div>",
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
    with st.expander("⚙️ Setup (dates & anniversaries)"):
        start_raw = settings.get("start_date", "")
        start_val = date.fromisoformat(start_raw) if start_raw else None
        uno_raw = settings.get("unofficial_date", "")
        uno_val = date.fromisoformat(uno_raw) if uno_raw else None
        sc1, sc2 = st.columns(2)
        with sc1:
            new_start = st.date_input(
                "Official start date 💍", value=start_val,
                min_value=date(2000, 1, 1),
            )
        with sc2:
            new_uno = st.date_input(
                "Unofficial start date 💞", value=uno_val,
                min_value=date(2000, 1, 1),
            )
        st.caption("Important dates (label + date as MM-DD). Add rows as needed.")
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
                    "unofficial_date": new_uno.isoformat() if new_uno else "",
                    "important_dates": cleaned,
                    "date_jar": settings.get("date_jar", []),
                }
            )
            st.success("Saved! 💛")
            st.rerun()


# Photos (shared gallery) -----------------------------------------------------
elif page == "📸 Photos":
    st.subheader("📸 Our photos")
    st.caption(
        "Upload pictures of each other — you both see every photo (shared vault). "
        "Images are auto-compressed so they stay light."
    )

    up = st.file_uploader(
        "Add photos",
        type=["png", "jpg", "jpeg", "webp", "bmp"],
        accept_multiple_files=True,
        key="photo_uploader",
    )
    pc1, pc2 = st.columns([1, 2])
    with pc1:
        ph_by = st.radio("Added by", USERS, horizontal=True, key="photo_by")
    with pc2:
        ph_cap = st.text_input("Caption (optional)", key="photo_caption")
    if up and st.button("⬆️ Add to gallery", type="primary"):
        ok = 0
        with st.spinner("Saving photos..."):
            for f in up:
                try:
                    photos.add_photo(f.getvalue(), by=ph_by, caption=ph_cap)
                    ok += 1
                except Exception as e:
                    st.error(f"{f.name}: {e}")
        if ok:
            st.success(f"Added {ok} photo(s) 📸")
            st.balloons()
            st.rerun()

    st.markdown("---")
    gallery = photos.list_photos()
    if not gallery:
        st.info("No photos yet — add your first memory above. 💞")
    else:
        st.caption(f"{len(gallery)} photo(s)")
        gcols = st.columns(3)
        for i, ph in enumerate(gallery):
            with gcols[i % 3]:
                cap = ph["caption"] or "—"
                st.image(ph["data"], use_container_width=True)
                st.markdown(
                    f"{author_chip(ph['by'])} &nbsp; *{cap}*",
                    unsafe_allow_html=True,
                )
                if st.button("🗑️ Remove", key=f"delphoto_{ph['path']}"):
                    photos.delete_photo(ph["path"])
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
