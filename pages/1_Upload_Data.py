import streamlit as st

from src.ingestion.pipeline import parse_all
from src.ingestion.router import PLATFORM_LABELS, REPORT_TYPE_LABELS
from src.storage.db import get_session
from src.storage import repository as repo

st.set_page_config(page_title="Upload Data", page_icon="📤", layout="wide")
st.title("📤 Upload Data")
st.write(
    "Drop in the export bundle your staff download from each platform -- either the whole "
    "`.zip` (e.g. `marketplace export.zip`), or individual report files. Files are matched to "
    "a platform and report type by filename automatically."
)

uploaded = st.file_uploader(
    "Upload zip or report files",
    type=["zip", "xlsx", "xls", "csv"],
    accept_multiple_files=True,
)

if uploaded:
    files = [(f.name, f.getvalue()) for f in uploaded]
    results = parse_all(files)

    recognized = [r for r in results if r.recognized]
    unrecognized = [r for r in results if not r.recognized]
    ok_results = [r for r in recognized if r.ok]

    if unrecognized:
        with st.expander(f"{len(unrecognized)} file(s) not recognized (skipped)", expanded=False):
            for r in unrecognized:
                st.write(f"- `{r.filename}` -- doesn't match a known Shopee/Lazada/TikTok Shop report filename pattern.")

    st.subheader("Preview")
    for r in recognized:
        label = f"{PLATFORM_LABELS.get(r.platform, r.platform)} — {REPORT_TYPE_LABELS.get(r.report_type, r.report_type)} ({r.filename})"
        with st.expander(label, expanded=r.error is not None):
            if r.error:
                st.error(r.error)
                continue
            if r.warnings:
                for w in r.warnings:
                    st.warning(w)
            st.caption(f"{len(r.df)} rows parsed")
            st.dataframe(r.df.head(20), width='stretch')

    if ok_results:
        st.subheader("Ready to save")
        summary = {}
        for r in ok_results:
            key = (PLATFORM_LABELS.get(r.platform, r.platform), REPORT_TYPE_LABELS.get(r.report_type, r.report_type))
            summary[key] = summary.get(key, 0) + len(r.df)
        for (platform, report_type), n in summary.items():
            st.write(f"- **{platform} — {report_type}**: {n} rows")

        if st.button("Confirm & Save to Dashboard", type="primary"):
            session = get_session()
            saved = []
            for r in ok_results:
                batch_id, n = repo.insert_batch(session, r.platform, r.report_type, r.filename, r.df)
                saved.append((r.platform, r.report_type, n))
            st.success(f"Saved {len(saved)} file(s) to the dashboard. Data is now visible on the other pages.")
            st.balloons()
    else:
        st.info("No files are ready to save yet -- fix any errors above or upload different files.")
else:
    st.caption("No files uploaded yet.")
