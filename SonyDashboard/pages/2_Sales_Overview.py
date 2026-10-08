import pandas as pd
import plotly.express as px
import streamlit as st

from src.dashboard.channels import (
    OVERLAY_CHANNEL, PARTITION_CHANNELS, channel_label, channel_totals,
    latest_upload_per_day, source_breakdown,
)
from src.dashboard.filters import sidebar_filters
from src.ingestion.router import PLATFORM_LABELS
from src.storage.db import get_session
from src.storage import repository as repo
from src.dashboard.branding import apply_logo, render_footer

st.set_page_config(page_title="Sales Overview", page_icon="📊", layout="wide")
apply_logo()
st.title("📊 Sales Overview")

platforms, start_date, end_date = sidebar_filters()
session = get_session()

df = repo.query_df(session, "daily_sales", platforms=platforms, start_date=start_date, end_date=end_date)
channel_df = (
    repo.query_df(session, "channel_sales", platforms=["shopee"], start_date=start_date, end_date=end_date)
    if "shopee" in platforms else pd.DataFrame()
)
session.close()  # release this read transaction now -- on Postgres an unclosed session
                  # holds its locks until GC'd, which can block later DDL like erase_database()

if df.empty:
    st.info("No sales data for this selection yet. Upload data on the Upload Data page.")
    render_footer()
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
    st.subheader("Shopee sales by channel")
    confirmed_channels = (
        latest_upload_per_day(channel_df[channel_df["funnel_stage"] == "confirmed"])
        if not channel_df.empty else channel_df
    )
    if confirmed_channels.empty:
        st.caption(
            "No channel breakdown for this selection yet. Upload Shopee's shop-stats export "
            "(the one with the traffic-source sheets) and it fills in automatically."
        )
    else:
        st.caption(
            "Confirmed Order stage. Product Card, Seller Live, Seller Video and Affiliate split Shopee's "
            "sales exactly; Shopee Ads is measured across all of them, so it is shown on its own and "
            "never added to the total."
        )
        totals = channel_totals(confirmed_channels).set_index("channel")
        split_total = totals.reindex(PARTITION_CHANNELS)["sales"].fillna(0).sum()

        shown = [c for c in PARTITION_CHANNELS + [OVERLAY_CHANNEL] if c in totals.index]
        for col, channel in zip(st.columns(len(shown)), shown):
            sales = totals.loc[channel, "sales"]
            col.metric(channel_label(channel), f"{sales:,.0f}", help=f"{sales:,.2f}")
            if split_total:
                note = f"{sales / split_total:.1%} of sales"
                if channel == OVERLAY_CHANNEL and totals.loc[channel, "ads_expense"]:
                    note = f"{note} · ROAS {totals.loc[channel, 'ads_roas']:,.1f}"
                col.caption(note)
        if OVERLAY_CHANNEL in totals.index and totals.loc[OVERLAY_CHANNEL, "ads_expense"]:
            st.caption(f"Shopee Ads spend over this period: {totals.loc[OVERLAY_CHANNEL, 'ads_expense']:,.2f}")

        days = set(confirmed_channels["report_date"])
        shopee_confirmed = df[
            (df["platform"] == "shopee") & (df["funnel_stage"] == "confirmed") & (df["report_date"].isin(days))
        ]["revenue"].sum()
        gap = split_total - shopee_confirmed
        if abs(gap) <= 1.0:
            st.caption(f"✓ Channel sales match Shopee's confirmed daily sales ({shopee_confirmed:,.2f}) for the same days.")
        else:
            st.warning(
                f"Channel sales ({split_total:,.2f}) differ from Shopee's confirmed daily sales "
                f"({shopee_confirmed:,.2f}) for the same days by {gap:,.2f}. Check that both files cover the "
                "same dates and that neither was uploaded for a different period."
            )

        split = confirmed_channels[
            (confirmed_channels["level"] == "channel") & (confirmed_channels["channel"].isin(PARTITION_CHANNELS))
        ].copy()
        split["channel_label"] = split["channel"].map(channel_label)
        fig_split = px.bar(
            split, x="report_date", y="sales", color="channel_label",
            labels={"sales": "Sales", "report_date": "", "channel_label": "Channel"},
            category_orders={"channel_label": [channel_label(c) for c in PARTITION_CHANNELS]},
        )
        st.plotly_chart(fig_split, width='stretch')

        ads_daily = confirmed_channels[
            (confirmed_channels["channel"] == OVERLAY_CHANNEL) & (confirmed_channels["level"] == "channel")
        ]
        if not ads_daily.empty and ads_daily["ads_expense"].notna().any():
            ads_long = ads_daily.melt(
                id_vars="report_date", value_vars=["sales", "ads_expense"],
                var_name="measure", value_name="amount",
            )
            ads_long["measure"] = ads_long["measure"].map({"sales": "Ads sales", "ads_expense": "Ads spend"})
            fig_ads = px.line(ads_long, x="report_date", y="amount", color="measure", markers=True,
                              labels={"amount": "", "report_date": "", "measure": ""},
                              title="Shopee Ads: sales vs spend")
            st.plotly_chart(fig_ads, width='stretch')

        with st.expander("Where each channel's sales came from"):
            tabs = st.tabs([channel_label(c) for c in shown])
            for tab, channel in zip(tabs, shown):
                with tab:
                    detail = source_breakdown(confirmed_channels, channel)
                    if detail.empty:
                        st.caption("No sub-source breakdown for this channel.")
                        continue
                    detail["share"] = detail["share"] * 100
                    detail = detail.rename(columns={"source": "Source", "sales": "Sales", "share": "Share (%)", "orders": "Orders"})
                    st.dataframe(
                        detail, width='stretch', hide_index=True,
                        column_config={
                            "Sales": st.column_config.NumberColumn(format="%.2f"),
                            "Share (%)": st.column_config.NumberColumn(format="%.1f"),
                            "Orders": st.column_config.NumberColumn(format="%.1f"),
                        },
                    )

    with st.expander("Shopee: all funnel stages (Placed / Confirmed / Paid)"):
        shopee_df = df[df["platform"] == "shopee"]
        stage_trend = shopee_df.groupby(["report_date", "funnel_stage"], as_index=False)["orders"].sum()
        fig3 = px.line(stage_trend, x="report_date", y="orders", color="funnel_stage", markers=True)
        st.plotly_chart(fig3, width='stretch')

render_footer()
