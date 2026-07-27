import io
import zipfile
from dataclasses import dataclass

import pandas as pd

from src.ingestion import router

REQUIRED_FIELDS = {
    "daily_sales": ["report_date"],
    "product_performance": ["item_id"],
    "ads_performance": [],
}


@dataclass
class ParsedFile:
    filename: str
    platform: str | None = None
    report_type: str | None = None
    df: pd.DataFrame | None = None
    error: str | None = None
    warnings: list[str] | None = None

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
    for field in REQUIRED_FIELDS.get(report_type, []):
        if field not in df.columns:
            warnings.append(f"Expected column '{field}' is missing.")
            continue
        null_frac = df[field].isna().mean()
        if null_frac > 0.5:
            warnings.append(f"Over half of '{field}' values are missing ({null_frac:.0%}).")
    return warnings


def parse_all(uploaded_files: list[tuple[str, bytes]]) -> list[ParsedFile]:
    results = []
    for name, data in expand_uploads(uploaded_files):
        platform, report_type = router.detect(name)
        if not platform:
            results.append(ParsedFile(filename=name))
            continue
        parser = router.get_parser(platform, report_type)
        if parser is None:
            results.append(ParsedFile(
                filename=name, platform=platform, report_type=report_type,
                error="This report type is recognized but not yet supported for ingestion.",
            ))
            continue
        try:
            df = parser(io.BytesIO(data))
            warnings = _validate(df, report_type)
            results.append(ParsedFile(
                filename=name, platform=platform, report_type=report_type,
                df=df, warnings=warnings,
            ))
        except Exception as e:
            results.append(ParsedFile(
                filename=name, platform=platform, report_type=report_type,
                error=f"Couldn't read this file as a {platform}/{report_type} report: {e}",
            ))
    return results
