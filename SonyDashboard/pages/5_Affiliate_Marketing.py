import plotly.express as px
import streamlit as st

from src.dashboard.filters import sidebar_filters
from src.ingestion.router import PLATFORM_LABELS
from src.storage.db import get_session
from src.storage import repository as repo
from src.dashboard.branding import apply_logo, render_footer
from src.dashboard.auth import require_login

st.set_page_config(page_title="Affiliate & Marketing", page_icon="🤝", layout="wide")
require_login()
apply_logo()
st.title("🤝 Affiliate & Marketing")
st.caption("Commission-based / creator-driven performance -- separate from paid CPC ads. These reports don't carry a per-row date, so they show the latest uploaded snapshot per platform.")

platforms, _, _ = sidebar_filters()
session = get_session()


def _latest_batch_only(df):
    if df.empty:
        return df
    latest = df.sort_values("uploaded_at").groupby("platform")["upload_batch_id"].last()
    return df[df.apply(lambda r: r["upload_batch_id"] == latest.get(r["platform"]), axis=1)]


st.subheader("Affiliate / commission performance by product")
aff = repo.query_df(session, "affiliate_marketing", platforms=platforms)
if aff.empty:
    st.info("No affiliate marketing data yet (upload AMS_SHP.csv or AMS_TT.xlsx on the Upload Data page).")
else:
    aff = _latest_batch_only(aff)
    aff["platform_label"] = aff["platform"].map(PLATFORM_LABELS)
    for platform in aff["platform"].unique():
        sub = aff[aff["platform"] == platform]
        st.write(f"**{PLATFORM_LABELS.get(platform, platform)}**")
        top_n = sub.sort_values("commission", ascending=False).head(10)
        fig = px.bar(top_n, x="commission", y="product_name", orientation="h",
                     title="Top products by commission paid", labels={"commission": "Commission", "product_name": "Product"})
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width='stretch')
        cols = ["product_name", "item_id", "sales", "units_sold", "commission", "roi"]
        cols = [c for c in cols if c in sub.columns]
        st.dataframe(sub[cols].sort_values("sales", ascending=False), width='stretch', hide_index=True)

st.divider()
st.subheader("Shopee: traffic-source breakdown by product")
traffic = repo.query_df(session, "traffic_source_performance", platforms=[p for p in platforms if p == "shopee"])
if traffic.empty:
    st.info("No traffic-source data yet (upload sales_source_SHP.xlsx on the Upload Data page).")
else:
    traffic = _latest_batch_only(traffic)
    stage = st.selectbox("Funnel stage", options=["confirmed", "placed", "paid"], key="traffic_stage")
    stage_df = traffic[traffic["funnel_stage"] == stage]
    top_n = stage_df.sort_values("sales", ascending=False).head(10)
    fig = px.bar(top_n, x="sales", y="product_name", orientation="h",
                 title=f"Top products by sales ({stage})", labels={"sales": "Sales", "product_name": "Product"})
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, width='stretch')
    cols = ["product_name", "item_id", "sales_ratio", "sales", "impressions", "clicks", "ctr", "conversion_rate", "buyers"]
    cols = [c for c in cols if c in stage_df.columns]
    st.dataframe(stage_df[cols].sort_values("sales", ascending=False), width='stretch', hide_index=True)

st.divider()
st.subheader("TikTok Shop: creator / affiliate leaderboard")
creators = repo.query_df(session, "creator_performance", platforms=[p for p in platforms if p == "tiktok_shop"])
if creators.empty:
    st.info("No creator performance data yet (upload AMS_TT_Aff.xlsx on the Upload Data page).")
else:
    creators = _latest_batch_only(creators)
    top_n = creators.sort_values("affiliate_gmv", ascending=False).head(15)
    fig = px.bar(top_n, x="affiliate_gmv", y="creator_username", orientation="h",
                 title="Top creators by affiliate GMV", labels={"affiliate_gmv": "Affiliate GMV", "creator_username": "Creator"})
    fig.update_layout(yaxis={"categoryorder": "total ascending"})
    st.plotly_chart(fig, width='stretch')
    cols = ["creator_username", "affiliate_gmv", "commission", "orders", "followers"]
    cols = [c for c in cols if c in creators.columns]
    st.dataframe(creators[cols].sort_values("affiliate_gmv", ascending=False), width='stretch', hide_index=True)

render_footer()
