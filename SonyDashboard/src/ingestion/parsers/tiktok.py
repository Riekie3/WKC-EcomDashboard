"""Parsers for TikTok Shop's export bundle: net_data_daily_TT.xlsx, product_performance_TT.xlsx.

TikTok's net_data_daily report varies by the date range selected at export time: a range export
has a "Daily data" section (one row per day); a same-day export instead has a "Today's data"
section (one row per hour, no "Daily data" block at all) -- both are handled here, the hourly
case is aggregated into a single daily row.

TikTok's product_performance report has ~176 columns with a two-level header (a segment label
like "All" or "Seller Product card" above each metric name). Per the approved plan, v1 only
ingests the core "All"-segment metrics; the long tail is intentionally not captured yet.

TikTok has no ads_data_TT file in the sample bundle (no CPC ads report was exported), so there
is no parse_ads_performance here -- the filename router simply has nothing to map to it.
"""
import pandas as pd

from src.ingestion.transforms import to_number, parse_date, extras_dict

_DAILY_CORE = {"GMV", "Orders", "Customers", "Items sold"}

# column positions (0-indexed) of the core "All"-segment metrics in product_performance_TT.xlsx
_PRODUCT_CORE_IDX = {
    "product_name": 0,
    "product_id": 1,
    "gmv": 4,
    "orders": 19,
    "items_sold": 21,
    "impressions": 24,
    "clicks": 25,
    "ctr": 26,
}


def _find_section_row(col0: pd.Series, label: str):
    matches = col0[col0.str.strip().str.lower() == label.lower()].index
    return matches[0] if len(matches) else None


def _extract_block(raw_all: pd.DataFrame, header_row: int) -> pd.DataFrame:
    header = raw_all.iloc[header_row].tolist()
    if pd.isna(header[0]):
        header[0] = "_date_col"  # the date column's header cell is blank in these reports
    data = raw_all.iloc[header_row + 1:]
    blank_mask = data.isna().all(axis=1)
    if blank_mask.any():
        end = blank_mask.idxmax()
        data = data.loc[:end - 1]
    data = data.dropna(how="all")
    data = data.copy()
    data.columns = header
    return data


def parse_daily_sales(path) -> pd.DataFrame:
    raw_all = pd.read_excel(path, sheet_name=0, header=None)
    col0 = raw_all[0].astype(str)
    daily_row = _find_section_row(col0, "Daily data")
    today_row = _find_section_row(col0, "Today's data")

    if daily_row is not None:
        data = _extract_block(raw_all, daily_row + 1)
        rows = []
        for _, r in data.iterrows():
            d = parse_date(r.iloc[0])
            if d is None:
                continue
            rows.append({
                "funnel_stage": "na",
                "report_date": d,
                "revenue": to_number(r.get("GMV")),
                "orders": to_number(r.get("Orders")),
                "units_sold": to_number(r.get("Items sold")),
                "visitors": None,
                "buyers": to_number(r.get("Customers")),
                "extra_metrics": extras_dict(r, _DAILY_CORE | {r.index[0]}),
            })
        return pd.DataFrame(rows)

    if today_row is not None:
        data = _extract_block(raw_all, today_row + 1)
        if data.empty:
            return pd.DataFrame([])
        dates = data.iloc[:, 0].apply(parse_date)
        d = next((x for x in dates if x is not None), None)
        if d is None:
            return pd.DataFrame([])
        numeric_cols = [c for c in data.columns if c != data.columns[0]]
        agg = {c: data[c].apply(to_number).sum(min_count=1) for c in numeric_cols}
        row = {
            "funnel_stage": "na",
            "report_date": d,
            "revenue": agg.get("GMV"),
            "orders": agg.get("Orders"),
            "units_sold": agg.get("Items sold"),
            "visitors": None,
            "buyers": agg.get("Customers"),
            "extra_metrics": {k: v for k, v in agg.items() if k not in _DAILY_CORE and pd.notna(v)},
        }
        return pd.DataFrame([row])

    raise ValueError("Could not find a 'Daily data' or \"Today's data\" section in this TikTok Shop file")


_AFFILIATE_CORE = {"Product ID", "Product name", "GMV", "Items sold", "Est. commission"}
_CREATOR_CORE = {"Creator username", "Affiliate GMV", "Est. commission", "Affiliate orders",
                  "Product impressions", "CTR", "Affiliate followers"}


def parse_affiliate_marketing(path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Sheet 1", header=0)
    raw = raw[raw["Product ID"].notna()]
    rows = []
    for _, r in raw.iterrows():
        rows.append({
            "item_id": str(r["Product ID"]),
            "product_name": r.get("Product name"),
            "sales": to_number(r.get("GMV")),
            "units_sold": to_number(r.get("Items sold")),
            "orders": None,
            "clicks": None,
            "commission": to_number(r.get("Est. commission")),
            "roi": None,
            "extra_metrics": extras_dict(r, _AFFILIATE_CORE),
        })
    return pd.DataFrame(rows)


def parse_creator_performance(path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Sheet 1", header=0)
    raw = raw[raw["Creator username"].notna()]
    rows = []
    for _, r in raw.iterrows():
        rows.append({
            "creator_username": r.get("Creator username"),
            "affiliate_gmv": to_number(r.get("Affiliate GMV")),
            "commission": to_number(r.get("Est. commission")),
            "orders": to_number(r.get("Affiliate orders")),
            "impressions": to_number(r.get("Product impressions")),
            "ctr": to_number(r.get("CTR")),
            "followers": to_number(r.get("Affiliate followers")),
            "extra_metrics": extras_dict(r, _CREATOR_CORE),
        })
    return pd.DataFrame(rows)


def parse_product_performance(path) -> pd.DataFrame:
    raw = pd.read_excel(path, sheet_name="Sheet1", header=None)
    data = raw.iloc[4:]
    data = data[data[_PRODUCT_CORE_IDX["product_id"]].notna()]
    rows = []
    for _, r in data.iterrows():
        rows.append({
            "period_start": None,
            "period_end": None,
            "item_id": str(r[_PRODUCT_CORE_IDX["product_id"]]),
            "product_name": r[_PRODUCT_CORE_IDX["product_name"]],
            "sales": to_number(r[_PRODUCT_CORE_IDX["gmv"]]),
            "units_sold": to_number(r[_PRODUCT_CORE_IDX["items_sold"]]),
            "orders": to_number(r[_PRODUCT_CORE_IDX["orders"]]),
            "impressions": to_number(r[_PRODUCT_CORE_IDX["impressions"]]),
            "clicks": to_number(r[_PRODUCT_CORE_IDX["clicks"]]),
            "ctr": to_number(r[_PRODUCT_CORE_IDX["ctr"]]),
            "conversion_rate": None,
            # v1 scope: core "All"-segment metrics only (approved plan decision) -- the ~166
            # remaining LIVE/video/affiliate segment columns are not captured here yet.
            "extra_metrics": {},
        })
    return pd.DataFrame(rows)
