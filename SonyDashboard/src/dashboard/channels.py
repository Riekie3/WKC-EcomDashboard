"""Helpers for the Shopee "sales by channel" view (Sales Overview page)."""
import pandas as pd

CHANNEL_LABELS = {
    "product_card": "Product Card",
    "seller_live": "Seller Live",
    "seller_video": "Seller Video",
    "affiliate": "Affiliate",
    "shopee_ads": "Shopee Ads",
}
# These four split Shopee's confirmed sales exactly (they add up to the total). Shopee Ads is
# measured across them rather than alongside them, so it is never added to the others.
PARTITION_CHANNELS = ["product_card", "seller_live", "seller_video", "affiliate"]
OVERLAY_CHANNEL = "shopee_ads"

_DEDUPE_KEYS = ["funnel_stage", "channel", "level", "source", "report_date"]


def latest_upload_per_day(df: pd.DataFrame) -> pd.DataFrame:
    """Keep the most recently uploaded row for each source and day, so re-uploading an
    overlapping period (or the same file twice) never double-counts."""
    if df.empty:
        return df
    return df.sort_values("uploaded_at").drop_duplicates(_DEDUPE_KEYS, keep="last")


def channel_label(key: str) -> str:
    return CHANNEL_LABELS.get(key, key.replace("_", " ").title())


def channel_totals(df: pd.DataFrame) -> pd.DataFrame:
    """One row per channel over the whole selection: sales, orders, ads spend and ROAS."""
    own = df[df["level"] == "channel"]
    out = own.groupby("channel", as_index=False).agg(
        sales=("sales", "sum"), orders=("orders", "sum"), ads_expense=("ads_expense", "sum"),
    )
    out["ads_roas"] = out.apply(
        lambda r: r["sales"] / r["ads_expense"] if r["ads_expense"] else None, axis=1,
    )
    return out


def source_breakdown(df: pd.DataFrame, channel: str) -> pd.DataFrame:
    """Sub-sources inside one channel (Search, Affiliate Live, ...) summed over the selection."""
    sub = df[(df["channel"] == channel) & (df["level"] == "source")]
    if sub.empty:
        return pd.DataFrame(columns=["source", "sales", "share", "orders"])
    out = sub.groupby("source", as_index=False).agg(sales=("sales", "sum"), orders=("orders", "sum"))
    total = out["sales"].sum()
    out["share"] = out["sales"] / total if total else 0.0
    return out.sort_values("sales", ascending=False).reset_index(drop=True)
