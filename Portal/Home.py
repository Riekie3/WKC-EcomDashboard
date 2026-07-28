import base64
import os

import streamlit as st

from brands import BRANDS

st.set_page_config(page_title="Ecommerce Dashboard Portal", page_icon="🏠", layout="wide")


def resolve_url(brand: dict) -> str | None:
    """Pick url_local or url_public depending on how *this* Portal page was reached,
    so a tile clicked from localhost stays on localhost instead of round-tripping
    through Tailscale, while the public URL still works for everyone else."""
    try:
        current_url = st.context.url or ""
    except Exception:
        current_url = ""
    is_local = "localhost" in current_url or "127.0.0.1" in current_url
    return brand.get("url_local") if is_local else brand.get("url_public")

st.markdown(
    """
    <style>
    .brand-tile {
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        height: 180px;
        margin-bottom: 24px;
        border-radius: 12px;
        text-decoration: none;
        transition: transform 0.15s ease, box-shadow 0.15s ease;
    }
    .brand-tile.live {
        background: #0a0a0a;
        border: 1px solid #333;
        cursor: pointer;
    }
    .brand-tile.live:hover {
        transform: translateY(-4px);
        box-shadow: 0 8px 20px rgba(0,0,0,0.35);
    }
    .brand-tile.live img {
        max-width: 80%;
        max-height: 70%;
        object-fit: contain;
    }
    .brand-tile.soon {
        background: transparent;
        border: 2px dashed #555;
        color: #888;
    }
    .brand-tile.soon .brand-name {
        font-size: 1.2em;
        font-weight: 600;
        color: #888;
    }
    .brand-tile.soon .brand-badge {
        margin-top: 0.4em;
        font-size: 0.8em;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        color: #666;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Ecommerce Dashboard Portal")
st.write("Select a brand to open its dashboard.")

cols_per_row = 4
rows = [BRANDS[i:i + cols_per_row] for i in range(0, len(BRANDS), cols_per_row)]

for row in rows:
    cols = st.columns(cols_per_row)
    for col, brand in zip(cols, row):
        with col:
            url = resolve_url(brand)
            if brand["status"] == "live" and brand["logo"] and url and os.path.exists(brand["logo"]):
                with open(brand["logo"], "rb") as f:
                    b64 = base64.b64encode(f.read()).decode()
                ext = os.path.splitext(brand["logo"])[1].lstrip(".")
                st.markdown(
                    f"""
                    <a class="brand-tile live" href="{url}" target="_blank" title="Open {brand['name']} dashboard">
                        <img src="data:image/{ext};base64,{b64}" alt="{brand['name']}">
                    </a>
                    """,
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f"""
                    <div class="brand-tile soon">
                        <div class="brand-name">{brand['name']}</div>
                        <div class="brand-badge">Coming soon</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

st.markdown(
    "<div style='text-align: center; color: gray; font-size: 0.8em; margin-top: 3em;'>@rie</div>",
    unsafe_allow_html=True,
)
