from datetime import datetime

import pandas as pd
from sqlalchemy import or_

from src.storage.models import FACT_TABLES, UploadBatch, DailySales, AdsPerformance


def insert_batch(session, platform: str, report_type: str, source_filename: str, df: pd.DataFrame):
    """Write a normalized DataFrame (columns matching the fact table's canonical schema)
    into the matching table, tagged under one new upload batch. Commits on success."""
    model = FACT_TABLES[report_type]
    batch = UploadBatch(platform=platform, report_type=report_type, source_filename=source_filename, row_count=len(df))
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
    return n + q2.count()


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
        "row_count": b.row_count, "status": b.status,
    } for b in rows])
