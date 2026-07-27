import streamlit as st

st.set_page_config(page_title="Sony Ecommerce Dashboard", page_icon="📊", layout="wide")

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
