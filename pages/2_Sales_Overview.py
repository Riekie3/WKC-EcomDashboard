import plotly.express as px
import streamlit as st

from src.dashboard.filters import sidebar_filters
from src.ingestion.router import PLATFORM_LABELS
from src.storage.db import get_session
from src.storage import repository as repo

st.set_page_config(page_title="Sales Overview", page_icon="📊", layout="wide")
st.title("📊 Sales Overview")

platforms, start_date, end_date = sidebar_filters()
session = get_session()

df = repo.query_df(session, "daily_sales", platforms=platforms, start_date=start_date, end_date=end_date)

if df.empty:
    st.info("No sales data for this selection yet. Upload data on the Upload Data page.")
    st.stop()

# Shopee reports three funnel stages per day; the headline KPI uses Confirmed Order
# (approved plan decision) so Shopee isn't triple-counted against Lazada/TikTok's single stage.
headline_df = df[(df["platform"] != "shopee") | (df["funnel_stage"] == "confirmed")]

df["platform_label"] = df["platform"].map(PLATFORM_LABELS)
headline_df = headline_df.copy()
headline_df["platform_label"] = headline_df["platform"].map(PLATFORM_LABELS)

col1, col2, col3 = st.columns(3)
col1.metric("Total Revenue", f"{headline_df['revenue'].sum():,.2f}")
col2.metric("Total Orders", f"{headline_df['orders'].sum():,.0f}")
col3.metric("Total Buyers", f"{headline_df['buyers'].sum():,.0f}")
st.caption("Shopee figures above use the Confirmed Order funnel stage.")

st.subheader("Revenue trend")
trend = headline_df.groupby(["report_date", "platform_label"], as_index=False)["revenue"].sum()
fig = px.line(trend, x="report_date", y="revenue", color="platform_label", markers=True)
st.plotly_chart(fig, width='stretch')

st.subheader("Platform comparison")
cmp = headline_df.groupby("platform_label", as_index=False)["revenue"].sum()
fig2 = px.bar(cmp, x="platform_label", y="revenue")
st.plotly_chart(fig2, width='stretch')

if "shopee" in platforms:
    with st.expander("Shopee: all funnel stages (Placed / Confirmed / Paid)"):
        shopee_df = df[df["platform"] == "shopee"]
        stage_trend = shopee_df.groupby(["report_date", "funnel_stage"], as_index=False)["orders"].sum()
        fig3 = px.line(stage_trend, x="report_date", y="orders", color="funnel_stage", markers=True)
        st.plotly_chart(fig3, width='stretch')
