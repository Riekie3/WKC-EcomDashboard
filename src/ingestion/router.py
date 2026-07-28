import re

from src.ingestion.parsers import shopee, lazada, tiktok

FILENAME_PATTERNS = [
    (re.compile(r"^net_data_daily.*_shp\.", re.I), "shopee", "daily_sales"),
    (re.compile(r"^net_data_daily.*_lzd\.", re.I), "lazada", "daily_sales"),
    (re.compile(r"^net_data_daily.*_tt\.", re.I), "tiktok_shop", "daily_sales"),
    (re.compile(r"^product_performance.*_shp\.", re.I), "shopee", "product_performance"),
    (re.compile(r"^product_performance.*_lzd\.", re.I), "lazada", "product_performance"),
    (re.compile(r"^product_performance.*_tt\.", re.I), "tiktok_shop", "product_performance"),
    (re.compile(r"^ads_data.*_shp\.", re.I), "shopee", "ads_performance"),
    (re.compile(r"^ads_data.*_lzd\.", re.I), "lazada", "ads_performance"),
    (re.compile(r"^ams_shp\.", re.I), "shopee", "affiliate_marketing"),
    (re.compile(r"^sales_source.*_shp\.", re.I), "shopee", "traffic_source_performance"),
    (re.compile(r"^ams_tt_aff\.", re.I), "tiktok_shop", "creator_performance"),  # must precede AMS_TT below
    (re.compile(r"^ams_tt\.", re.I), "tiktok_shop", "affiliate_marketing"),
]

PARSERS = {
    ("shopee", "daily_sales"): shopee.parse_daily_sales,
    ("shopee", "product_performance"): shopee.parse_product_performance,
    ("shopee", "ads_performance"): shopee.parse_ads_performance,
    ("shopee", "affiliate_marketing"): shopee.parse_affiliate_marketing,
    ("shopee", "traffic_source_performance"): shopee.parse_traffic_source_performance,
    ("lazada", "daily_sales"): lazada.parse_daily_sales,
    ("lazada", "product_performance"): lazada.parse_product_performance,
    ("lazada", "ads_performance"): lazada.parse_ads_performance,
    ("tiktok_shop", "daily_sales"): tiktok.parse_daily_sales,
    ("tiktok_shop", "product_performance"): tiktok.parse_product_performance,
    ("tiktok_shop", "affiliate_marketing"): tiktok.parse_affiliate_marketing,
    ("tiktok_shop", "creator_performance"): tiktok.parse_creator_performance,
}

PLATFORM_LABELS = {"shopee": "Shopee", "lazada": "Lazada", "tiktok_shop": "TikTok Shop"}
REPORT_TYPE_LABELS = {
    "daily_sales": "Daily Sales",
    "product_performance": "Product Performance",
    "ads_performance": "Ads Performance",
    "affiliate_marketing": "Affiliate Marketing",
    "traffic_source_performance": "Traffic Source Performance",
    "creator_performance": "Creator Performance",
}


def detect(filename: str):
    """Guess (platform, report_type) from a filename using the confirmed naming convention
    (e.g. net_data_daily_SHP.xlsx, product_performance_LZD.xls, ads_data_TT... ).
    Returns (None, None) if nothing matches -- caller should fall back to manual selection."""
    base = filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    for pattern, platform, report_type in FILENAME_PATTERNS:
        if pattern.search(base):
            return platform, report_type
    return None, None


def get_parser(platform: str, report_type: str):
    return PARSERS.get((platform, report_type))
