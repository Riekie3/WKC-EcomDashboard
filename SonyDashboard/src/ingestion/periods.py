"""Work out which dates a report file covers.

Reports without a date on each row (product performance, affiliate, traffic source, creator,
Shopee ad campaigns) are snapshots of a period. Knowing that period lets the dashboard show
only the snapshot that matches the dates being viewed, instead of the latest file no matter
what month it is from.
"""
import datetime
import io
import re

import pandas as pd

# Report types that are a snapshot of a period rather than one row per day.
SNAPSHOT_REPORT_TYPES = {
    "product_performance", "affiliate_marketing", "traffic_source_performance",
    "creator_performance", "ads_performance",
}

# "01/06/2026~30/06/2026", "01-06-2026 - 30-06-2026", "01/06/2026 to 30/06/2026"
_TEXT_RANGE = re.compile(
    r"(\d{2})[/-](\d{2})[/-](\d{4})\s*(?:~|-|–|to)\s*(\d{2})[/-](\d{2})[/-](\d{4})"
)
# "20260701_20260731", "20260701-20260722"
_FILENAME_YMD = re.compile(r"(?<!\d)(\d{4})(\d{2})(\d{2})[_-](\d{4})(\d{2})(\d{2})(?!\d)")
# "01_07_2026-31_07_2026"
_FILENAME_DMY = re.compile(r"(?<!\d)(\d{2})_(\d{2})_(\d{4})-(\d{2})_(\d{2})_(\d{4})(?!\d)")


# "2026-06-01_2026-06-30" (Lazada's "Date Range :" banner), also "~" or "to" between the two
_ISO_RANGE = re.compile(r"(\d{4})-(\d{2})-(\d{2})\s*(?:_|~|–|to)\s*(\d{4})-(\d{2})-(\d{2})")


def _date(y, m, d):
    try:
        return datetime.date(int(y), int(m), int(d))
    except ValueError:
        return None


def _ordered(start, end):
    if start is None or end is None:
        return None
    return (start, end) if start <= end else None


def _from_text(text: str):
    text = text or ""
    m = _TEXT_RANGE.search(text)
    if m:
        d1, m1, y1, d2, m2, y2 = m.groups()
        return _ordered(_date(y1, m1, d1), _date(y2, m2, d2))
    m = _ISO_RANGE.search(text)
    if m:
        y1, m1, d1, y2, m2, d2 = m.groups()
        return _ordered(_date(y1, m1, d1), _date(y2, m2, d2))
    return None


def _from_filename(filename: str):
    m = _FILENAME_YMD.search(filename)
    if m:
        y1, m1, d1, y2, m2, d2 = m.groups()
        found = _ordered(_date(y1, m1, d1), _date(y2, m2, d2))
        if found:
            return found
    m = _FILENAME_DMY.search(filename)
    if m:
        d1, m1, y1, d2, m2, y2 = m.groups()
        return _ordered(_date(y1, m1, d1), _date(y2, m2, d2))
    return None


def period_from_filename(filename: str):
    """Dates written in a file's name, e.g. parentskudetail.20260701_20260731.xlsx."""
    return _from_filename(filename or "")


def _from_content(filename: str, data: bytes):
    """Banner text near the top of a file ("Analysis date: ...", "Date Range :...",
    "Date Period,..."). Only the first rows are looked at."""
    name = filename.lower()
    if name.endswith(".csv"):
        head = data[:4000].decode("utf-8-sig", errors="replace")
        return _from_text(head)
    if name.endswith((".xlsx", ".xls")):
        top = pd.read_excel(io.BytesIO(data), sheet_name=0, header=None, nrows=8)
        text = " ".join(str(v) for v in top.to_numpy().ravel().tolist() if not pd.isna(v))
        return _from_text(text)
    return None


def period_from_dates(df: pd.DataFrame):
    """Min/max of a report's own dated rows, when it has them."""
    if df is None or df.empty or "report_date" not in df.columns:
        return None
    days = [d for d in df["report_date"].tolist() if isinstance(d, datetime.date)]
    return (min(days), max(days)) if days else None


def detect_period(filename: str, data: bytes, df: pd.DataFrame | None = None):
    """(start, end) the file covers, or None when it can't be told. Dated rows win, then the
    file's own banner text, then dates written in the filename."""
    found = period_from_dates(df)
    if found:
        return found
    try:
        found = _from_content(filename, data)
    except Exception:
        found = None
    return found or _from_filename(filename)
