import os

import streamlit as st

LOGO_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "assets", "logo.png")


def apply_logo():
    """Shows the company logo above the sidebar page navigation. Call once near the top of
    every page script (st.logo must be called on each page/rerun, not just once globally)."""
    if os.path.exists(LOGO_PATH):
        st.logo(LOGO_PATH, size="large")


def render_footer():
    """Small credit line pinned to the bottom of the page content."""
    st.markdown(
        "<div style='text-align: center; color: gray; font-size: 0.8em; margin-top: 3em;'>@rie</div>",
        unsafe_allow_html=True,
    )
