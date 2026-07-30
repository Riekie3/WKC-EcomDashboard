import plotly.express as px
import streamlit as st

from src.dashboard.filters import sidebar_filters
from src.ingestion.router import PLATFORM_LABELS
from src.storage.db import get_session
from src.storage import repository as repo
from src.dashboard.branding import apply_logo, render_footer

st.set_page_config(page_title="Returns & Refunds", page_icon="↩️", layout="wide")
apply_logo()
st.title("↩️ Returns & Refunds")
st.caption(
    "Gross vs. net figures broken out separately here, instead of only disappearing into the "
    "revenue subtraction on the other pages. Only platforms/reports that expose a refund or "
    "cancellation figure are shown -- currently Lazada and TikTok Shop daily sales, and TikTok "
    "Shop's product, affiliate, and creator reports. Shopee's reports don't include a "
    "cancellation/refund breakdown."
)

platforms, start_date, end_date = sidebar_filters()
session = get_session()

st.subheader("Daily sales: gross vs. net")
daily = repo.query_df(session, "daily_sales", platforms=platforms, start_date=start_date, end_date=end_date)
session.close()
daily = daily[daily["gross_revenue"].notna()] if not daily.empty else daily

if daily.empty:
    st.info("No daily sales rows with a refund/cancellation breakdown for this selection.")
else:
    daily = daily.copy()
    daily["platform_label"] = daily["platform"].map(PLATFORM_LABELS)
    gross = daily["gross_revenue"].sum()
    refunded = daily["refund_amount"].sum()
    net = gross - refunded
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Gross Revenue", f"{gross:,.2f}")
    col2.metric("Refunded/Cancelled", f"{refunded:,.2f}")
    col3.metric("Net Revenue", f"{net:,.2f}")
    col4.metric("Refund Rate", f"{(refunded / gross * 100) if gross else 0:,.1f}%")

    trend = daily.groupby(["report_date", "platform_label"], as_index=False)["refund_amount"].sum()
    fig = px.line(trend, x="report_date", y="refund_amount", color="platform_label", markers=True,
                  title="Daily refunded/cancelled amount")
    st.plotly_chart(fig, width='stretch')

    cols = ["report_date", "platform_label", "gross_revenue", "refund_amount", "revenue"]
    st.dataframe(
        daily[cols].rename(columns={"revenue": "net_revenue"}).sort_values("report_date", ascending=False),
        width='stretch', hide_index=True,
    )

st.divider()
st.subheader("Product-level refunds")
session = get_session()
products = repo.query_df(session, "product_performance", platforms=platforms)
session.close()
products = products[products["refund_amount"].notna()] if not products.empty else products

if products.empty:
    st.info("No product performance rows with a refund breakdown for this selection.")
else:
    products = products.copy()
    products["platform_label"] = products["platform"].map(PLATFORM_LABELS)
    for platform in products["platform"].unique():
        sub = products[products["platform"] == platform]
        latest_batch = sub.sort_values("uploaded_at").iloc[-1]["upload_batch_id"]
        sub = sub[sub["upload_batch_id"] == latest_batch]
        st.write(f"**{PLATFORM_LABELS.get(platform, platform)}**")
        top_n = sub.sort_values("refund_amount", ascending=False).head(10)
        fig = px.bar(top_n, x="refund_amount", y="product_name", orientation="h",
                     title="Top products by refunded amount", labels={"refund_amount": "Refunded", "product_name": "Product"})
        fig.update_layout(yaxis={"categoryorder": "total ascending"})
        st.plotly_chart(fig, width='stretch')
        cols = ["product_name", "item_id", "gross_sales", "refund_amount", "sales"]
        cols = [c for c in cols if c in sub.columns]
        st.dataframe(
            sub[cols].rename(columns={"sales": "net_sales"}).sort_values("refund_amount", ascending=False),
            width='stretch', hide_index=True,
        )

st.divider()
st.subheader("Affiliate & creator refunds")
session = get_session()
aff = repo.query_df(session, "affiliate_marketing", platforms=platforms)
creators = repo.query_df(session, "creator_performance", platforms=[p for p in platforms if p == "tiktok_shop"])
session.close()
aff = aff[aff["refund_amount"].notna()] if not aff.empty else aff
creators = creators[creators["refund_amount"].notna()] if not creators.empty else creators

if aff.empty and creators.empty:
    st.info("No affiliate or creator performance rows with a refund breakdown for this selection.")
else:
    if not aff.empty:
        st.write("**Affiliate / commission performance**")
        cols = ["product_name", "item_id", "gross_sales", "refund_amount", "sales"]
        cols = [c for c in cols if c in aff.columns]
        st.dataframe(
            aff[cols].rename(columns={"sales": "net_sales"}).sort_values("refund_amount", ascending=False),
            width='stretch', hide_index=True,
        )
    if not creators.empty:
        st.write("**TikTok Shop creator leaderboard**")
        cols = ["creator_username", "gross_affiliate_gmv", "refund_amount", "affiliate_gmv"]
        cols = [c for c in cols if c in creators.columns]
        st.dataframe(
            creators[cols].rename(columns={"affiliate_gmv": "net_affiliate_gmv"}).sort_values("refund_amount", ascending=False),
            width='stretch', hide_index=True,
        )

render_footer()
