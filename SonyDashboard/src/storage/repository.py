from datetime import datetime

import pandas as pd
from sqlalchemy import or_

from src.storage.models import FACT_TABLES, UploadBatch, DailySales, AdsPerformance, ChannelSales


def insert_batch(session, platform: str, report_type: str, source_filename: str, df: pd.DataFrame, period=None):
    """Write a normalized DataFrame (columns matching the fact table's canonical schema)
    into the matching table, tagged under one new upload batch. Commits on success.
    `period` is the (start, end) dates the file covers, when known."""
    model = FACT_TABLES[report_type]
    period_start, period_end = period if period else (None, None)
    batch = UploadBatch(
        platform=platform, report_type=report_type, source_filename=source_filename,
        row_count=len(df), period_start=period_start, period_end=period_end,
    )
    session.add(batch)
    session.flush()
    now = datetime.utcnow()
    records = []
    for _, row in df.iterrows():
        data = row.to_dict()
        data.update(platform=platform, upload_batch_id=batch.id, source_filename=source_filename, uploaded_at=now)
        records.append(model(**data))
    session.add_all(records)
    session.commit()
    return batch.id, len(records)


def delete_by_date_range(session, start_date, end_date, platforms=None) -> int:
    """Delete rows whose date falls in [start_date, end_date] from daily_sales and
    ads_performance. product_performance rows carry no per-row date in the current
    report set, so they are only removable via delete_by_batch_id."""
    total = 0

    q = session.query(DailySales).filter(DailySales.report_date.between(start_date, end_date))
    if platforms:
        q = q.filter(DailySales.platform.in_(platforms))
    total += q.delete(synchronize_session=False)

    q2 = session.query(AdsPerformance).filter(
        or_(
            AdsPerformance.report_date.between(start_date, end_date),
            AdsPerformance.period_start.between(start_date, end_date),
        )
    )
    if platforms:
        q2 = q2.filter(AdsPerformance.platform.in_(platforms))
    total += q2.delete(synchronize_session=False)

    q3 = session.query(ChannelSales).filter(ChannelSales.report_date.between(start_date, end_date))
    if platforms:
        q3 = q3.filter(ChannelSales.platform.in_(platforms))
    total += q3.delete(synchronize_session=False)

    session.commit()
    return total


def delete_by_batch_id(session, batch_id: str) -> int:
    batch = session.get(UploadBatch, batch_id)
    if batch is None:
        return 0
    model = FACT_TABLES[batch.report_type]
    count = session.query(model).filter(model.upload_batch_id == batch_id).delete(synchronize_session=False)
    session.delete(batch)
    session.commit()
    return count


def count_affected_by_date_range(session, start_date, end_date, platforms=None) -> int:
    q = session.query(DailySales).filter(DailySales.report_date.between(start_date, end_date))
    if platforms:
        q = q.filter(DailySales.platform.in_(platforms))
    n = q.count()
    q2 = session.query(AdsPerformance).filter(
        or_(
            AdsPerformance.report_date.between(start_date, end_date),
            AdsPerformance.period_start.between(start_date, end_date),
        )
    )
    if platforms:
        q2 = q2.filter(AdsPerformance.platform.in_(platforms))
    q3 = session.query(ChannelSales).filter(ChannelSales.report_date.between(start_date, end_date))
    if platforms:
        q3 = q3.filter(ChannelSales.platform.in_(platforms))
    return n + q2.count() + q3.count()


def latest_report_date(session):
    """Most recent day that has dated data (daily sales / channel sales), or None if empty."""
    from sqlalchemy import func
    days = [
        session.query(func.max(model.report_date)).scalar()
        for model in (DailySales, ChannelSales)
    ]
    days = [d for d in days if d is not None]
    return max(days) if days else None


def query_df(session, report_type: str, platforms=None, start_date=None, end_date=None) -> pd.DataFrame:
    """Load a fact table (optionally filtered) into a DataFrame for dashboard use."""
    model = FACT_TABLES[report_type]
    q = session.query(model)
    if platforms:
        q = q.filter(model.platform.in_(platforms))
    date_col = getattr(model, "report_date", None)
    if date_col is not None and (start_date or end_date):
        if start_date:
            q = q.filter(date_col >= start_date)
        if end_date:
            q = q.filter(date_col <= end_date)
    rows = q.all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([{c.name: getattr(r, c.name) for c in model.__table__.columns} for r in rows])


def list_upload_batches(session) -> pd.DataFrame:
    rows = session.query(UploadBatch).order_by(UploadBatch.uploaded_at.desc()).all()
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame([{
        "id": b.id, "platform": b.platform, "report_type": b.report_type,
        "source_filename": b.source_filename, "uploaded_at": b.uploaded_at,
        "row_count": b.row_count, "period_start": b.period_start, "period_end": b.period_end,
        "status": b.status,
    } for b in rows])


def set_batch_period(session, batch_id: str, period_start, period_end) -> bool:
    """Record the dates an already-uploaded file covers (for files saved before periods were
    tracked, or whose period couldn't be detected)."""
    batch = session.get(UploadBatch, batch_id)
    if batch is None:
        return False
    batch.period_start, batch.period_end = period_start, period_end
    session.commit()
    return True


def backfill_batch_periods(session, companion_window_minutes: int = 30):
    """Fill in the period of batches saved before periods were tracked, in three steps:
    1. a batch of dated rows (daily sales, channel sales, daily ads) -> the first to last day of its rows;
    2. a file whose name carries the dates -> those dates;
    3. any other file -> the period of a dated file from the same platform uploaded within
       `companion_window_minutes` of it (a month's reports are uploaded together).
    Returns [(batch, period, how)] for what it set; anything it can't tell is left alone."""
    from datetime import timedelta
    from sqlalchemy import func
    from src.ingestion.periods import period_from_filename

    changes = []
    batches = session.query(UploadBatch).order_by(UploadBatch.uploaded_at).all()

    def record(batch, period, how):
        batch.period_start, batch.period_end = period
        changes.append((batch, period, how))

    for b in batches:
        if b.period_start is None:
            model = FACT_TABLES.get(b.report_type)
            date_col = getattr(model, "report_date", None) if model else None
            if date_col is not None:
                lo, hi = session.query(func.min(date_col), func.max(date_col)).filter(model.upload_batch_id == b.id).one()
                if lo and hi:
                    record(b, (lo, hi), "from its dated rows")
    for b in batches:
        if b.period_start is None:
            found = period_from_filename(b.source_filename)
            if found:
                record(b, found, "from the dates in its filename")
    window = timedelta(minutes=companion_window_minutes)
    for b in batches:
        if b.period_start is not None:
            continue
        near = [
            o for o in batches
            if o.period_start is not None and o.platform == b.platform and abs(o.uploaded_at - b.uploaded_at) <= window
        ]
        if near:
            closest = min(near, key=lambda o: abs(o.uploaded_at - b.uploaded_at))
            record(b, (closest.period_start, closest.period_end), f"same upload as {closest.source_filename}")
    session.commit()
    return changes


def attach_batch_periods(session, df: pd.DataFrame) -> pd.DataFrame:
    """Add batch_period_start / batch_period_end (the dates each row's upload covers) to a
    fact-table frame. Named apart from the fact tables' own period_start/period_end columns,
    which mean something else on some tables (e.g. a Shopee ad's own start date)."""
    if df.empty:
        return df
    periods = {
        b.id: (b.period_start, b.period_end)
        for b in session.query(UploadBatch).filter(UploadBatch.id.in_(df["upload_batch_id"].unique().tolist())).all()
    }
    out = df.copy()
    out["batch_period_start"] = out["upload_batch_id"].map(lambda i: periods.get(i, (None, None))[0])
    out["batch_period_end"] = out["upload_batch_id"].map(lambda i: periods.get(i, (None, None))[1])
    return out
