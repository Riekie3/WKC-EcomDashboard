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


class SchemaChangedError(ValueError):
    """Raised when a report file is missing column(s) a parser depends on -- almost always
    means the platform changed its export format (renamed/removed/reordered a column) since
    this parser was written against a real sample file. Deliberately a distinct, clearly-named
    exception (not a bare KeyError) so pipeline.py can show an actionable message instead of a
    raw Python trace, and so a silently-wrong read never gets a chance to reach the database."""


def require_columns(columns, required: set, context: str):
    """Check that every column a parser is about to access by name is actually present,
    and fail loudly and immediately if not -- rather than letting pandas raise a much less
    clear KeyError partway through row processing, or (worse) silently producing all-null
    output for a renamed column that a parser accesses via `.get()`."""
    missing = required - set(columns)
    if missing:
        raise SchemaChangedError(
            f"Expected column(s) not found in this {context} file: {', '.join(sorted(str(m) for m in missing))}. "
            f"The platform's export format may have changed since this was last checked -- "
            f"columns actually found: {', '.join(str(c) for c in columns)}"
        )


def require_header_positions(header_row, expected: dict, context: str):
    """For parsers that read columns by POSITION rather than name (needed when a report has
    no usable header row, e.g. TikTok's multi-segment product performance file) -- verify the
    header text at each position we're about to read from still matches what we expect.
    Positional access can't raise a KeyError on its own if the platform reorders columns, so
    without this check a shifted layout would silently read the wrong data into the wrong
    field instead of failing at all.
    `expected` is {column_index: expected_header_text}.
    """
    mismatches = []
    for idx, expected_text in expected.items():
        actual = header_row[idx] if idx < len(header_row) else None
        if str(actual).strip() != expected_text:
            mismatches.append(f"column {idx} expected {expected_text!r}, found {actual!r}")
    if mismatches:
        raise SchemaChangedError(
            f"This {context} file's column layout doesn't match what's expected -- "
            f"the platform may have reordered or renamed columns: {'; '.join(mismatches)}"
        )


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
