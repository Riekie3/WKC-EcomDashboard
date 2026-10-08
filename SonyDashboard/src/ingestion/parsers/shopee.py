"""Parsers for Shopee's export bundle: net_data_daily_SHP.xlsx, product_performance_SHP.xlsx,
ads_data_SHP.csv. Column names and quirks (range-summary row, banner rows) confirmed against
real sample exports -- see the plan doc for the raw structure notes.
"""
import re

import pandas as pd

from src.ingestion.transforms import (
    to_number, parse_date, extras_dict, require_columns, SchemaChangedError,
)

_DAILY_STAGE_SHEETS = {
    "Placed Order": "placed",
    "Confirmed Order": "confirmed",
    "Paid Order": "paid",
}

_DAILY_CORE = {"Date", "Sales (MYR)", "Orders", "Visitors", "# of buyers",
                "Cancelled Sales", "Returned/Refunded Sales"}
_PRODUCT_CORE = {
    "Item ID", "Product", "Sales (Confirmed Order) (MYR)", "Confirmed Order",
    "Units (Confirmed Order)", "Product Impression", "Product Clicks", "CTR",
    "Order Conversion Rate (Confirmed Order)",
}
_ADS_CORE = {
    "Ad Name", "Product ID", "Start Date", "End Date", "Impression", "Clicks",
    "GMV", "Expense", "ROAS",
}


def parse_daily_sales(path) -> pd.DataFrame:
    rows = []
    for sheet, stage in _DAILY_STAGE_SHEETS.items():
        raw = pd.read_excel(path, sheet_name=sheet, header=3)
        require_columns(raw.columns, _DAILY_CORE, f"Shopee daily sales ({sheet})")
        raw = raw[raw["Date"].astype(str).str.match(r"^\d{2}-\d{2}-\d{4}$", na=False)]
        for _, r in raw.iterrows():
            # Confirmed against staff's own dashboard: Shopee's headline revenue is the raw
            # "Sales (MYR)" figure and does NOT subtract Cancelled Sales / Returned-Refunded
            # Sales (unlike Lazada/TikTok) -- kept as gross here. Those two figures are still
            # captured (gross_revenue/refund_amount) purely for visibility on the Returns &
            # Refunds page; they intentionally do not change "revenue" itself.
            gross_revenue = to_number(r["Sales (MYR)"]) or 0.0
            cancelled = to_number(r.get("Cancelled Sales")) or 0.0
            returned = to_number(r.get("Returned/Refunded Sales")) or 0.0
            rows.append({
                "funnel_stage": stage,
                "report_date": parse_date(r["Date"]),
                "revenue": gross_revenue,
                "orders": to_number(r["Orders"]),
                "units_sold": None,
                "visitors": to_number(r["Visitors"]),
                "buyers": to_number(r["# of buyers"]),
                "gross_revenue": gross_revenue,
                "refund_amount": cancelled + returned,
                "extra_metrics": extras_dict(r, _DAILY_CORE),
            })
    return pd.DataFrame(rows)


def parse_product_performance(path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Top Performing Products", header=0)
    require_columns(raw.columns, _PRODUCT_CORE, "Shopee product performance")
    raw = raw[raw["Item ID"].notna()]
    rows = []
    for _, r in raw.iterrows():
        rows.append({
            "period_start": None,
            "period_end": None,
            "item_id": str(r["Item ID"]),
            "product_name": r.get("Product"),
            "sales": to_number(r.get("Sales (Confirmed Order) (MYR)")),
            "units_sold": to_number(r.get("Units (Confirmed Order)")),
            "orders": to_number(r.get("Confirmed Order")),
            "impressions": to_number(r.get("Product Impression")),
            "clicks": to_number(r.get("Product Clicks")),
            "ctr": to_number(r.get("CTR")),
            "conversion_rate": to_number(r.get("Order Conversion Rate (Confirmed Order)")),
            "extra_metrics": extras_dict(r, _PRODUCT_CORE),
        })
    return pd.DataFrame(rows)


_AFFILIATE_CORE = {"Item id", "Item Name", "Sales(RM)", "Item Sold", "Orders", "Clicks", "Est.Commission(RM)", "ROI"}
_TRAFFIC_SOURCE_CORE = {
    "Item ID", "Product", "Sales Ratio", "Sales (MYR)", "Product Impressions", "Product Clicks",
    "Orders", "Units", "CTR", "Order Conversion Rate", "Buyers",
}
_TRAFFIC_SOURCE_SHEETS = {
    "(placed) Product Traffic": "placed",
    "(confirmed) Product Traffic": "confirmed",
    "(paid) Product Traffic": "paid",
}


def parse_affiliate_marketing(path) -> pd.DataFrame:
    raw = pd.read_csv(path, header=0)
    require_columns(raw.columns, _AFFILIATE_CORE, "Shopee affiliate marketing")
    raw = raw[raw["Item id"].notna()]
    rows = []
    for _, r in raw.iterrows():
        rows.append({
            "item_id": str(r["Item id"]),
            "product_name": r.get("Item Name"),
            "sales": to_number(r.get("Sales(RM)")),
            "units_sold": to_number(r.get("Item Sold")),
            "orders": to_number(r.get("Orders")),
            "clicks": to_number(r.get("Clicks")),
            "commission": to_number(r.get("Est.Commission(RM)")),
            "roi": to_number(r.get("ROI")),
            "extra_metrics": extras_dict(r, _AFFILIATE_CORE),
        })
    return pd.DataFrame(rows)


def parse_traffic_source_performance(path) -> pd.DataFrame:
    rows = []
    for sheet, stage in _TRAFFIC_SOURCE_SHEETS.items():
        raw = pd.read_excel(path, sheet_name=sheet, header=0)
        require_columns(raw.columns, _TRAFFIC_SOURCE_CORE, f"Shopee traffic source ({sheet})")
        raw = raw[raw["Item ID"].notna()]
        for _, r in raw.iterrows():
            rows.append({
                "funnel_stage": stage,
                "item_id": str(r["Item ID"]),
                "product_name": r.get("Product"),
                "sales_ratio": to_number(r.get("Sales Ratio")),
                "sales": to_number(r.get("Sales (MYR)")),
                "impressions": to_number(r.get("Product Impressions")),
                "clicks": to_number(r.get("Product Clicks")),
                "orders": to_number(r.get("Orders")),
                "units_sold": to_number(r.get("Units")),
                "ctr": to_number(r.get("CTR")),
                "conversion_rate": to_number(r.get("Order Conversion Rate")),
                "buyers": to_number(r.get("Buyers")),
                "extra_metrics": extras_dict(r, _TRAFFIC_SOURCE_CORE),
            })
    return pd.DataFrame(rows)


def parse_ads_performance(path) -> pd.DataFrame:
    raw = pd.read_csv(path, header=6)
    require_columns(raw.columns, _ADS_CORE, "Shopee ads performance")
    raw = raw[raw["Ad Name"].notna()]
    rows = []
    for _, r in raw.iterrows():
        rows.append({
            "report_date": None,
            "period_start": parse_date(r.get("Start Date")),
            "period_end": None if str(r.get("End Date")).strip() == "Unlimited" else parse_date(r.get("End Date")),
            "campaign_name": r.get("Ad Name"),
            "item_id": None if str(r.get("Product ID")).strip() in ("-", "nan") else str(r.get("Product ID")),
            "spend": to_number(r.get("Expense")),
            "revenue": to_number(r.get("GMV")),
            "orders": to_number(r.get("Conversions")),
            "roas": to_number(r.get("ROAS")),
            "impressions": to_number(r.get("Impression")),
            "clicks": to_number(r.get("Clicks")),
            "ctr": to_number(r.get("CTR")),
            "cpc": None,
            "cost_per_order": to_number(r.get("Cost per Conversion")),
            "extra_metrics": extras_dict(r, _ADS_CORE),
        })
    return pd.DataFrame(rows)


# --- Channel sales: the "Source Contribution (...)" sheets of Shopee's shop-stats export ----------
#
# Each of the three stage sheets (placed / confirmed / paid) is a stack of channel blocks:
#   <channel title row>            e.g. "Seller Live"   (rest of the row blank)
#   "Traffic Source" | <metric headers...>
#   <source label> | <period total>      <- skipped, the daily rows below it add up to it
#   dd-mm-yyyy     | <that day's metrics> ...
#   <next source label> | ...
# The first source in a block carries the channel's own name and is the channel total; the
# rest are sub-sources (Search, Affiliate Live, ...). Shopee Ads has no total series of its
# own, so one is built by summing its sub-sources.

_CHANNEL_TITLES = {
    "product card": "product_card",
    "seller live": "seller_live",
    "seller video": "seller_video",
    "shopee affiliate": "affiliate",
    "shopee ads": "shopee_ads",
}
_CHANNEL_METRIC_FIELDS = {
    "Sales Ratio": "sales_ratio",
    "Sales (MYR)": "sales",
    "Product Clicks": "clicks",
    "Orders": "orders",
    "Units": "units_sold",
    "CTR": "ctr",
    "Order Conversion Rate": "conversion_rate",
    "Conversion": "conversion_rate",
    "Buyers": "buyers",
    "Ads Expense": "ads_expense",
    "Ads ROAS": "ads_roas",
}
_CHANNEL_EXPOSURE_HEADERS = {
    "Product Impressions", "Live Views", "Video Views", "Content Views", "Ads Impression",
}
_DATE_LABEL = re.compile(r"^\d{2}-\d{2}-\d{4}$")


def _channel_stage(sheet_name: str):
    n = sheet_name.lower()
    for keyword, stage in (("placed", "placed"), ("confir", "confirmed"), ("paid", "paid")):
        if keyword in n:
            return stage
    return None


def _is_blank(v) -> bool:
    return v is None or (isinstance(v, float) and pd.isna(v))


def _parse_source_contribution(raw: pd.DataFrame, stage: str, sheet_name: str) -> list[dict]:
    rows = []
    channel = channel_title = columns = source = level = None
    for _, r in raw.iterrows():
        label = r.iloc[0]
        if _is_blank(label):
            continue
        label = str(label).strip()
        rest = r.iloc[1:]

        if rest.isna().all():  # channel title row
            channel_title = label
            channel = _CHANNEL_TITLES.get(label.lower(), re.sub(r"\W+", "_", label.lower()).strip("_"))
            columns = source = level = None
            continue

        if label == "Traffic Source":  # metric header row for the block above its sources
            columns = [None if _is_blank(c) else str(c).strip() for c in rest]
            require_columns(columns, {"Sales (MYR)"}, f"Shopee channel sales ({sheet_name}, {channel_title})")
            continue

        if channel is None or columns is None:
            continue

        if _DATE_LABEL.match(label):
            if source is None:
                continue
            row = {
                "funnel_stage": stage, "report_date": parse_date(label), "channel": channel,
                "level": level, "source": source, "extra_metrics": {},
            }
            for header, value in zip(columns, rest):
                if header is None or _is_blank(value):
                    continue
                num = to_number(value)
                if header in _CHANNEL_METRIC_FIELDS:
                    row[_CHANNEL_METRIC_FIELDS[header]] = num
                elif header in _CHANNEL_EXPOSURE_HEADERS:
                    row["exposure"] = num
                elif num is not None:
                    row["extra_metrics"][header] = num
            rows.append(row)
        else:  # a source's own period-total row: start of a new source
            source = label
            level = "channel" if label.lower() == (channel_title or "").lower() else "source"
    return rows


def _add_ads_channel_totals(rows: list[dict]) -> list[dict]:
    """Shopee Ads has no total series of its own -- build one by summing its sub-sources."""
    ads = [r for r in rows if r["channel"] == "shopee_ads" and r["level"] == "source"]
    if not ads or any(r["channel"] == "shopee_ads" and r["level"] == "channel" for r in rows):
        return rows
    by_key = {}
    for r in ads:
        by_key.setdefault((r["funnel_stage"], r["report_date"]), []).append(r)
    totals = []
    for (stage, day), group in by_key.items():
        def total(field):
            vals = [g[field] for g in group if g.get(field) is not None]
            return sum(vals) if vals else None
        sales, expense = total("sales"), total("ads_expense")
        totals.append({
            "funnel_stage": stage, "report_date": day, "channel": "shopee_ads", "level": "channel",
            "source": "Shopee Ads", "sales": sales, "sales_ratio": 1.0, "exposure": total("exposure"),
            "orders": total("orders"), "ads_expense": expense,
            "ads_roas": (sales / expense) if sales is not None and expense else None,
            "extra_metrics": {},
        })
    return rows + totals


def parse_channel_sales(path) -> pd.DataFrame:
    """Sales split by channel (Product Card / Seller Live / Seller Video / Affiliate / Shopee Ads)
    from a shop-stats export. Older Shopee exports have no such sheets -- those return no rows
    rather than an error, since this is read as a companion report of the daily-sales file."""
    xl = pd.ExcelFile(path)
    sheets = [n for n in xl.sheet_names if n.lower().startswith("source contribution")]
    if not sheets:
        return pd.DataFrame([])
    rows = []
    for name in sheets:
        stage = _channel_stage(name)
        if stage is None:
            continue
        rows.extend(_parse_source_contribution(pd.read_excel(xl, sheet_name=name, header=None), stage, name))
    if not rows:
        raise SchemaChangedError(
            "Found the 'Source Contribution' sheets but couldn't read any channel rows from them -- "
            "Shopee may have changed this part of the export layout."
        )
    rows = _add_ads_channel_totals(rows)
    df = pd.DataFrame(rows)
    return df.astype(object).where(df.notna(), None)  # real NULLs, not NaN, for the database
