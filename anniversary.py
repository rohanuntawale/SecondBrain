"""The anniversary surprise, independent of the notes and model backends."""

from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components


def render_anniversary() -> None:
    """Render a self-contained, responsive keepsake with its own scroll area."""
    st.markdown(
        """<style>
        .stApp { background: #fbf8ed; }
        [data-testid="stHeader"] { display: none; }
        .block-container { padding: .6rem 1rem 0; max-width: 1500px; }
        iframe[title="streamlit.components.v1.html"], iframe[title="st.iframe"] {
            height: calc(100dvh - 35px); min-height: 500px;
            border: 0; border-radius: 16px;
        }
        </style>""",
        unsafe_allow_html=True,
    )
    document = (Path(__file__).parent / "assets" / "anniversary.html").read_text(
        encoding="utf-8"
    )
    # Inline the companion assets for Streamlit's srcdoc iframe. The same HTML
    # can still be opened directly from disk with its relative asset links.
    assets = Path(__file__).parent / "assets"
    document = document.replace(
        '<link rel="stylesheet" href="anniversary-extra.css">',
        "<style>" + (assets / "anniversary-extra.css").read_text(encoding="utf-8") + "</style>",
    ).replace(
        '<script src="anniversary-extra.js"></script>',
        "<script>" + (assets / "anniversary-extra.js").read_text(encoding="utf-8") + "</script>",
    )
    if hasattr(st, "iframe"):
        st.iframe(document, height=1000)
    else:
        components.html(document, height=1000, scrolling=True)
