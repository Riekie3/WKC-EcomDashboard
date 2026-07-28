import io
import zipfile
from dataclasses import dataclass, field

import pandas as pd

from src.ingestion import router

REQUIRED_FIELDS = {
    "daily_sales": ["report_date"],
    "product_performance": ["item_id"],
    "ads_performance": [],
    "affiliate_marketing": ["item_id"],
    "traffic_source_performance": ["item_id"],
    "creator_performance": ["creator_username"],
}


@dataclass
class ParsedFile:
    filename: str
    raw: bytes = b""
    platform: str | None = None
    report_type: str | None = None
    df: pd.DataFrame | None = None
    error: str | None = None
    warnings: list[str] = field(default_factory=list)

    @property
    def recognized(self) -> bool:
        return self.platform is not None

    @property
    def ok(self) -> bool:
        return self.recognized and self.error is None and self.df is not None


def expand_uploads(uploaded_files: list[tuple[str, bytes]]) -> list[tuple[str, bytes]]:
    """Flatten a list of (filename, bytes). Any .zip is expanded into its member files
    (matching the exact bundle shape the user exports, e.g. marketplace export.zip)."""
    out = []
    for name, data in uploaded_files:
        if name.lower().endswith(".zip"):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for info in z.infolist():
                    if info.is_dir():
                        continue
                    member_name = info.filename.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
                    out.append((member_name, z.read(info.filename)))
        else:
            out.append((name, data))
    return out


def _validate(df: pd.DataFrame, report_type: str) -> list[str]:
    warnings = []
    if df.empty:
        warnings.append("No rows were parsed from this file.")
        return warnings
    for f in REQUIRED_FIELDS.get(report_type, []):
        if f not in df.columns:
            warnings.append(f"Expected column '{f}' is missing.")
            continue
        null_frac = df[f].isna().mean()
        if null_frac > 0.5:
            warnings.append(f"Over half of '{f}' values are missing ({null_frac:.0%}).")
    return warnings


def parse_with_mapping(filename: str, data: bytes, platform: str, report_type: str) -> ParsedFile:
    """Parse a single file against an explicit (platform, report_type) -- used both for
    filename-auto-detected files and for files the user manually assigned a mapping to."""
    parser = router.get_parser(platform, report_type)
    if parser is None:
        return ParsedFile(
            filename=filename, raw=data, platform=platform, report_type=report_type,
            error="This report type isn't supported for this platform yet.",
        )
    try:
        df = parser(io.BytesIO(data))
        warnings = _validate(df, report_type)
        return ParsedFile(filename=filename, raw=data, platform=platform, report_type=report_type, df=df, warnings=warnings)
    except Exception as e:
        return ParsedFile(
            filename=filename, raw=data, platform=platform, report_type=report_type,
            error=f"Couldn't read this file as a {platform}/{report_type} report: {e}",
        )


def parse_all(uploaded_files: list[tuple[str, bytes]]) -> list[ParsedFile]:
    results = []
    for name, data in expand_uploads(uploaded_files):
        platform, report_type = router.detect(name)
        if not platform:
            results.append(ParsedFile(filename=name, raw=data))
            continue
        results.append(parse_with_mapping(name, data, platform, report_type))
    return results
