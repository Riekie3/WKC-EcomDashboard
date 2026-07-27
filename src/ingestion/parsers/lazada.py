"""Parsers for Lazada's export bundle: net_data_daily_LZD.xls, product_performance_LZD.xls,
ads_data_LZD.xlsx. Legacy .xls files require the `xlrd` engine (handled transparently by pandas
once xlrd is installed).
"""
import pandas as pd

from src.ingestion.transforms import to_number, parse_date, extras_dict

_DAILY_CORE = {"Date", "Revenue", "Orders", "Visitors", "Buyers"}
_PRODUCT_CORE = {"Product ID", "Product Name", "Revenue", "Orders", "Units Sold",
                  "Product Visitors", "Product Pageviews", "Conversion Rate"}
_ADS_CORE = {"Date", "Spend", "Revenue", "Orders", "ROAS", "Impression", "Clicks", "CPC", "Cost Per Order"}


def parse_daily_sales(path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Key Metrics", header=5)
    raw = raw[raw["Date"].astype(str).str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)]
    rows = []
    for _, r in raw.iterrows():
        rows.append({
            "funnel_stage": "na",
            "report_date": parse_date(r["Date"]),
            "revenue": to_number(r["Revenue"]),
            "orders": to_number(r["Orders"]),
            "units_sold": to_number(r.get("Units Sold")),
            "visitors": to_number(r["Visitors"]),
            "buyers": to_number(r["Buyers"]),
            "extra_metrics": extras_dict(r, _DAILY_CORE),
        })
    return pd.DataFrame(rows)


def parse_product_performance(path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Product", header=5)
    raw = raw[raw["Product ID"].notna()]
    # keep only the product-level rollup rows (SKU ID == '-'), not the per-SKU-variant breakdown rows,
    # to match one-row-per-product granularity used by Shopee/TikTok's core product performance table
    raw = raw[raw["SKU ID"].astype(str).str.strip() == "-"]
    rows = []
    for _, r in raw.iterrows():
        rows.append({
            "period_start": None,
            "period_end": None,
            "item_id": str(r["Product ID"]),
            "product_name": r.get("Product Name"),
            "sales": to_number(r.get("Revenue")),
            "units_sold": to_number(r.get("Units Sold")),
            "orders": to_number(r.get("Orders")),
            "impressions": to_number(r.get("Product Pageviews")),
            "clicks": None,
            "ctr": None,
            "conversion_rate": to_number(r.get("Conversion Rate")),
            "extra_metrics": extras_dict(r, _PRODUCT_CORE),
        })
    return pd.DataFrame(rows)


def parse_ads_performance(path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Sheet0", header=0)
    raw = raw[raw["Date"].notna()]
    rows = []
    for _, r in raw.iterrows():
        rows.append({
            "report_date": parse_date(r["Date"]),
            "period_start": None,
            "period_end": None,
            "campaign_name": None,
            "item_id": None,
            "spend": to_number(r.get("Spend")),
            "revenue": to_number(r.get("Revenue")),
            "orders": to_number(r.get("Orders")),
            "roas": to_number(r.get("ROAS")),
            "impressions": to_number(r.get("Impression")),
            "clicks": to_number(r.get("Clicks")),
            "ctr": to_number(r.get("CTR")),
            "cpc": to_number(r.get("CPC")),
            "cost_per_order": to_number(r.get("Cost Per Order")),
            "extra_metrics": extras_dict(r, _ADS_CORE),
        })
    return pd.DataFrame(rows)
