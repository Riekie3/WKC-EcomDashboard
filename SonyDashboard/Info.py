import os

import streamlit as st

from src.dashboard.branding import apply_logo, render_footer
from src.dashboard.auth import require_login

st.set_page_config(page_title="Sony Ecommerce Dashboard", page_icon="📊", layout="wide")
require_login()
apply_logo()

SONY_LOGO_PATH = os.path.join(os.path.dirname(__file__), "assets", "sony_logo.webp")
if os.path.exists(SONY_LOGO_PATH):
    col1, col2, col3 = st.columns([1, 1, 1])
    with col2:
        st.image(SONY_LOGO_PATH, width='stretch')

st.title("Sony Ecommerce Dashboard")
st.markdown(
    """
Consolidated performance across **Shopee**, **Lazada**, and **TikTok Shop** in one place.

### How to use this
1. Go to **Upload Data** and drop in the export bundle (the zip your staff download from each
   platform, e.g. `marketplace export.zip`) -- or individual report files.
2. Review the preview and confirm to add it to the dashboard's history.
3. Browse **Sales Overview**, **Product Performance**, and **Ads Performance** for the merged view.
4. Use **Data Management** if you ever need to remove a bad upload or a specific date range.

Data is kept indefinitely (no automatic deletion) so you can look back over the full history.
Use the pages in the sidebar to get started.
    """
)

render_footer()
