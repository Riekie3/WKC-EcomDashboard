import re
import pandas as pd

_NULL_TOKENS = {"", "-", "--", "/", "nan", "NaN", "None"}


def to_number(val):
    """Parse a raw report cell into a float, or None if not parseable.
    Handles thousands separators, currency prefixes (RM, MYR...), percent
    strings (returned as a fraction, e.g. "4.21%" -> 0.0421), and the
    various null placeholders ("-", "--", "/") seen across these reports.
    """
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return None if pd.isna(val) else float(val)
    s = str(val).strip()
    if s in _NULL_TOKENS:
        return None
    is_percent = s.endswith("%")
    s = re.sub(r"^[^\d\-.]+", "", s)  # strip currency prefixes like "RM"
    s = s.replace(",", "").rstrip("%").strip()
    if s in ("", "-", "."):
        return None
    try:
        f = float(s)
    except ValueError:
        return None
    return f / 100.0 if is_percent else f


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}")


def parse_date(val):
    """Parse a date cell (DD-MM-YYYY, DD/MM/YYYY, ISO, or ISO datetime) into a date, or None.
    ISO-formatted strings (YYYY-MM-DD...) are parsed without dayfirst -- pandas' dayfirst=True
    can otherwise swap month/day even on year-first strings when day <= 12 (confirmed against
    Lazada's daily export, e.g. "2026-06-01" was mis-parsed as 2026-01-06 with dayfirst=True).
    """
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if hasattr(val, "date") and not isinstance(val, str):
        return val.date()
    s = str(val).strip()
    if s in _NULL_TOKENS:
        return None
    if _ISO_DATE_RE.match(s):
        ts = pd.to_datetime(s, errors="coerce")
    else:
        ts = pd.to_datetime(s, dayfirst=True, errors="coerce")
    return None if pd.isna(ts) else ts.date()


def extras_dict(row: pd.Series, exclude: set) -> dict:
    """Turn the non-core columns of a row into a plain JSON-serializable dict for extra_metrics."""
    out = {}
    for col, val in row.items():
        if col in exclude:
            continue
        if val is None or (isinstance(val, float) and pd.isna(val)):
            continue
        s = str(val).strip()
        if s in _NULL_TOKENS:
            continue
        num = to_number(val)
        out[str(col)] = num if num is not None else s
    return out
