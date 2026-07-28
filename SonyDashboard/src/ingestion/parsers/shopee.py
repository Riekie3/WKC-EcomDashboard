"""Parsers for Shopee's export bundle: net_data_daily_SHP.xlsx, product_performance_SHP.xlsx,
ads_data_SHP.csv. Column names and quirks (range-summary row, banner rows) confirmed against
real sample exports -- see the plan doc for the raw structure notes.
"""
import pandas as pd

from src.ingestion.transforms import to_number, parse_date, extras_dict

_DAILY_STAGE_SHEETS = {
    "Placed Order": "placed",
    "Confirmed Order": "confirmed",
    "Paid Order": "paid",
}

_DAILY_CORE = {"Date", "Sales (MYR)", "Orders", "Visitors", "# of buyers"}
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
        raw = raw[raw["Date"].astype(str).str.match(r"^\d{2}-\d{2}-\d{4}$", na=False)]
        for _, r in raw.iterrows():
            rows.append({
                "funnel_stage": stage,
                "report_date": parse_date(r["Date"]),
                "revenue": to_number(r["Sales (MYR)"]),
                "orders": to_number(r["Orders"]),
                "units_sold": None,
                "visitors": to_number(r["Visitors"]),
                "buyers": to_number(r["# of buyers"]),
                "extra_metrics": extras_dict(r, _DAILY_CORE),
            })
    return pd.DataFrame(rows)


def parse_product_performance(path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Top Performing Products", header=0)
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
