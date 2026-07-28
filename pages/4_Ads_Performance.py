import plotly.express as px
import streamlit as st

from src.dashboard.filters import sidebar_filters
from src.ingestion.router import PLATFORM_LABELS
from src.storage.db import get_session
from src.storage import repository as repo

st.set_page_config(page_title="Ads Performance", page_icon="📣", layout="wide")
st.title("📣 Ads Performance")

platforms, start_date, end_date = sidebar_filters()
session = get_session()

# loaded without a DB-level date filter: Shopee's campaign rows have no report_date (they're
# keyed by campaign start/end instead), so filtering at the query level would silently drop them
df = repo.query_df(session, "ads_performance", platforms=platforms)

if df.empty:
    st.info("No ads performance data for this selection yet. Upload data on the Upload Data page (or note TikTok Shop has no CPC ads report in the current export bundle).")
    st.stop()

df["platform_label"] = df["platform"].map(PLATFORM_LABELS)

daily = df[df["report_date"].notna()].copy()
daily = daily[(daily["report_date"] >= start_date) & (daily["report_date"] <= end_date)]

campaigns = df[df["report_date"].isna()].copy()

if not daily.empty:
    st.subheader("Daily ad spend & ROAS (platforms reporting daily campaign totals)")
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Spend", f"{daily['spend'].sum():,.2f}")
    col2.metric("Total Revenue", f"{daily['revenue'].sum():,.2f}")
    spend_sum = daily["spend"].sum()
    blended_roas = daily["revenue"].sum() / spend_sum if spend_sum else 0
    col3.metric("Blended ROAS", f"{blended_roas:,.2f}")

    trend = daily.groupby(["report_date", "platform_label"], as_index=False)[["spend", "revenue"]].sum()
    fig = px.line(trend, x="report_date", y="spend", color="platform_label", markers=True, title="Daily spend")
    st.plotly_chart(fig, width='stretch')

if not campaigns.empty:
    st.subheader("Campaign / product-level ads (platforms reporting per-campaign totals)")
    for platform in campaigns["platform"].unique():
        sub = campaigns[campaigns["platform"] == platform]
        st.write(f"**{PLATFORM_LABELS.get(platform, platform)}**")
        cols = ["campaign_name", "item_id", "spend", "revenue", "roas", "impressions", "clicks", "ctr", "cost_per_order"]
        cols = [c for c in cols if c in sub.columns]
        st.dataframe(
            sub[cols].sort_values("spend", ascending=False),
            width='stretch', hide_index=True,
        )
