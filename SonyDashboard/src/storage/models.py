import uuid
from datetime import datetime, date

from sqlalchemy import String, Float, Integer, Date, DateTime, JSON, ForeignKey
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return uuid.uuid4().hex


class UploadBatch(Base):
    __tablename__ = "upload_batches"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=_uuid)
    platform: Mapped[str] = mapped_column(String, index=True)
    report_type: Mapped[str] = mapped_column(String, index=True)
    source_filename: Mapped[str] = mapped_column(String)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, index=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="committed")


class _BatchMixin:
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    platform: Mapped[str] = mapped_column(String, index=True)
    upload_batch_id: Mapped[str] = mapped_column(String, ForeignKey("upload_batches.id"), index=True)
    source_filename: Mapped[str] = mapped_column(String)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class DailySales(Base, _BatchMixin):
    __tablename__ = "daily_sales"

    funnel_stage: Mapped[str] = mapped_column(String, default="na")
    report_date: Mapped[date] = mapped_column(Date, index=True)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    orders: Mapped[float | None] = mapped_column(Float, nullable=True)
    units_sold: Mapped[float | None] = mapped_column(Float, nullable=True)
    visitors: Mapped[float | None] = mapped_column(Float, nullable=True)
    buyers: Mapped[float | None] = mapped_column(Float, nullable=True)
    # revenue above is already net (gross_revenue - refund_amount); these two are kept
    # alongside it so refunds/cancellations have their own visible breakdown instead of
    # silently vanishing into the subtraction. Null where a platform's report has no
    # separate refund/cancellation figure to break out (e.g. Shopee).
    gross_revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    refund_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class ProductPerformance(Base, _BatchMixin):
    __tablename__ = "product_performance"

    period_start: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    item_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    product_name: Mapped[str | None] = mapped_column(String, nullable=True)
    sales: Mapped[float | None] = mapped_column(Float, nullable=True)
    units_sold: Mapped[float | None] = mapped_column(Float, nullable=True)
    orders: Mapped[float | None] = mapped_column(Float, nullable=True)
    impressions: Mapped[float | None] = mapped_column(Float, nullable=True)
    clicks: Mapped[float | None] = mapped_column(Float, nullable=True)
    ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    conversion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    # sales above is already net; see the comment on DailySales.gross_revenue
    gross_sales: Mapped[float | None] = mapped_column(Float, nullable=True)
    refund_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AdsPerformance(Base, _BatchMixin):
    __tablename__ = "ads_performance"

    report_date: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    campaign_name: Mapped[str | None] = mapped_column(String, nullable=True)
    item_id: Mapped[str | None] = mapped_column(String, nullable=True)
    spend: Mapped[float | None] = mapped_column(Float, nullable=True)
    revenue: Mapped[float | None] = mapped_column(Float, nullable=True)
    orders: Mapped[float | None] = mapped_column(Float, nullable=True)
    roas: Mapped[float | None] = mapped_column(Float, nullable=True)
    impressions: Mapped[float | None] = mapped_column(Float, nullable=True)
    clicks: Mapped[float | None] = mapped_column(Float, nullable=True)
    ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    cpc: Mapped[float | None] = mapped_column(Float, nullable=True)
    cost_per_order: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class AffiliateMarketing(Base, _BatchMixin):
    __tablename__ = "affiliate_marketing"

    item_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    product_name: Mapped[str | None] = mapped_column(String, nullable=True)
    sales: Mapped[float | None] = mapped_column(Float, nullable=True)
    units_sold: Mapped[float | None] = mapped_column(Float, nullable=True)
    orders: Mapped[float | None] = mapped_column(Float, nullable=True)
    clicks: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission: Mapped[float | None] = mapped_column(Float, nullable=True)
    roi: Mapped[float | None] = mapped_column(Float, nullable=True)
    # sales above is already net; see the comment on DailySales.gross_revenue
    gross_sales: Mapped[float | None] = mapped_column(Float, nullable=True)
    refund_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class TrafficSourcePerformance(Base, _BatchMixin):
    __tablename__ = "traffic_source_performance"

    funnel_stage: Mapped[str] = mapped_column(String, default="na")
    item_id: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    product_name: Mapped[str | None] = mapped_column(String, nullable=True)
    sales_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    sales: Mapped[float | None] = mapped_column(Float, nullable=True)
    impressions: Mapped[float | None] = mapped_column(Float, nullable=True)
    clicks: Mapped[float | None] = mapped_column(Float, nullable=True)
    orders: Mapped[float | None] = mapped_column(Float, nullable=True)
    units_sold: Mapped[float | None] = mapped_column(Float, nullable=True)
    ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    conversion_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    buyers: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class CreatorPerformance(Base, _BatchMixin):
    __tablename__ = "creator_performance"

    creator_username: Mapped[str | None] = mapped_column(String, nullable=True, index=True)
    affiliate_gmv: Mapped[float | None] = mapped_column(Float, nullable=True)
    commission: Mapped[float | None] = mapped_column(Float, nullable=True)
    orders: Mapped[float | None] = mapped_column(Float, nullable=True)
    impressions: Mapped[float | None] = mapped_column(Float, nullable=True)
    ctr: Mapped[float | None] = mapped_column(Float, nullable=True)
    followers: Mapped[float | None] = mapped_column(Float, nullable=True)
    # affiliate_gmv above is already net; see the comment on DailySales.gross_revenue
    gross_affiliate_gmv: Mapped[float | None] = mapped_column(Float, nullable=True)
    refund_amount: Mapped[float | None] = mapped_column(Float, nullable=True)
    extra_metrics: Mapped[dict | None] = mapped_column(JSON, nullable=True)


FACT_TABLES = {
    "daily_sales": DailySales,
    "product_performance": ProductPerformance,
    "ads_performance": AdsPerformance,
    "affiliate_marketing": AffiliateMarketing,
    "traffic_source_performance": TrafficSourcePerformance,
    "creator_performance": CreatorPerformance,
}
