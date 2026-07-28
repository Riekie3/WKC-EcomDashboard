"""Canonical field names for each fact table. See src/storage/models.py for the actual
SQLAlchemy columns/types -- this module exists as a single source of truth that platform
parsers (src/ingestion/parsers/*.py) target, independent of the storage layer.
"""

# Metadata columns added to every fact table by the ingestion pipeline, not by parsers.
BATCH_METADATA_FIELDS = ["platform", "upload_batch_id", "source_filename", "uploaded_at"]

DAILY_SALES_FIELDS = [
    "funnel_stage",   # 'placed' | 'confirmed' | 'paid' | 'na'
    "report_date",
    "revenue",
    "orders",
    "units_sold",
    "visitors",
    "buyers",
    "extra_metrics",
]

PRODUCT_PERFORMANCE_FIELDS = [
    "period_start",
    "period_end",
    "item_id",
    "product_name",
    "sales",
    "units_sold",
    "orders",
    "impressions",
    "clicks",
    "ctr",
    "conversion_rate",
    "extra_metrics",
]

ADS_PERFORMANCE_FIELDS = [
    "report_date",     # set for daily campaign summaries (Lazada); null for per-campaign rows
    "period_start",    # set for per-campaign rows (Shopee); null for daily summaries
    "period_end",
    "campaign_name",
    "item_id",
    "spend",
    "revenue",
    "orders",
    "roas",
    "impressions",
    "clicks",
    "ctr",
    "cpc",
    "cost_per_order",
    "extra_metrics",
]

AFFILIATE_MARKETING_FIELDS = [
    "item_id",
    "product_name",
    "sales",
    "units_sold",
    "orders",
    "clicks",
    "commission",
    "roi",
    "extra_metrics",
]

TRAFFIC_SOURCE_FIELDS = [
    "funnel_stage",
    "item_id",
    "product_name",
    "sales_ratio",
    "sales",
    "impressions",
    "clicks",
    "orders",
    "units_sold",
    "ctr",
    "conversion_rate",
    "buyers",
    "extra_metrics",
]

CREATOR_PERFORMANCE_FIELDS = [
    "creator_username",
    "affiliate_gmv",
    "commission",
    "orders",
    "impressions",
    "ctr",
    "followers",
    "extra_metrics",
]

PLATFORMS = ["shopee", "lazada", "tiktok_shop"]
REPORT_TYPES = [
    "daily_sales", "product_performance", "ads_performance",
    "affiliate_marketing", "traffic_source_performance", "creator_performance",
]
