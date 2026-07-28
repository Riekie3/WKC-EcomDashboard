import plotly.express as px
import streamlit as st

from src.dashboard.filters import sidebar_filters
from src.ingestion.router import PLATFORM_LABELS
from src.storage.db import get_session
from src.storage import repository as repo

st.set_page_config(page_title="Product Performance", page_icon="🏆", layout="wide")
st.title("🏆 Product Performance")

platforms, _, _ = sidebar_filters()
st.caption("Product performance reports don't carry a per-row date, so the date filter doesn't apply here -- this shows the latest uploaded snapshot per platform.")
session = get_session()

df = repo.query_df(session, "product_performance", platforms=platforms)

if df.empty:
    st.info("No product performance data for this selection yet. Upload data on the Upload Data page.")
    st.stop()

df["platform_label"] = df["platform"].map(PLATFORM_LABELS)

for platform in platforms:
    label = PLATFORM_LABELS.get(platform, platform)
    sub = df[df["platform"] == platform]
    with st.container(border=True):
        st.subheader(label)
        if sub.empty:
            st.write("No product performance data for this platform yet.")
            continue
        # keep only the most recent upload batch for this platform so re-uploads don't double-count
        latest_batch = sub.sort_values("uploaded_at").iloc[-1]["upload_batch_id"]
        sub = sub[sub["upload_batch_id"] == latest_batch]

        top_n = sub.sort_values("sales", ascending=False).head(10)
        fig = px.bar(top_n, x="sales", y="product_name", orientation="h",
                     title="Top sellers by revenue", labels={"sales": "Revenue", "product_name": "Product"})
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width='stretch')

        cols = ["product_name", "item_id", "sales", "units_sold", "orders", "impressions", "clicks", "ctr"]
        cols = [c for c in cols if c in sub.columns]
        st.dataframe(sub[cols].sort_values("sales", ascending=False), width='stretch', hide_index=True)
