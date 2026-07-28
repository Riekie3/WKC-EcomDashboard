import streamlit as st

from src.ingestion.pipeline import parse_all, parse_with_mapping
from src.ingestion.router import PLATFORM_LABELS, REPORT_TYPE_LABELS, platforms_with_parsers, available_report_types
from src.storage.db import get_session
from src.storage import repository as repo
from src.dashboard.branding import apply_logo, render_footer
from src.dashboard.auth import require_login

st.set_page_config(page_title="Upload Data", page_icon="📤", layout="wide")
require_login()
apply_logo()
st.title("📤 Upload Data")
st.write(
    "Drop in the export bundle your staff download from each platform -- either the whole "
    "`.zip` (e.g. `marketplace export.zip`), or individual report files. Files are matched to "
    "a platform and report type by filename automatically; anything that doesn't match can be "
    "assigned manually below."
)

_PLACEHOLDER = "-- Select --"

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
    ready_to_save = [r for r in recognized if r.ok]

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

    if unrecognized:
        st.subheader(f"{len(unrecognized)} file(s) not recognized")
        st.caption("These don't match a known filename pattern. Pick the platform and report type manually to parse them anyway.")
        platform_options = [_PLACEHOLDER] + [PLATFORM_LABELS[p] for p in platforms_with_parsers()]

        for i, r in enumerate(unrecognized):
            with st.expander(f"`{r.filename}`", expanded=True):
                col1, col2 = st.columns(2)
                platform_choice = col1.selectbox(
                    "Platform", options=platform_options, key=f"manual_platform_{i}_{r.filename}",
                )
                platform_key = next((p for p, label in PLATFORM_LABELS.items() if label == platform_choice), None)

                report_options = [_PLACEHOLDER]
                if platform_key:
                    report_options += [REPORT_TYPE_LABELS[rt] for rt in available_report_types(platform_key)]
                report_choice = col2.selectbox(
                    "Report type", options=report_options, key=f"manual_report_{i}_{r.filename}",
                )
                report_key = next((rt for rt, label in REPORT_TYPE_LABELS.items() if label == report_choice), None)

                if not platform_key or not report_key:
                    st.caption("Select both a platform and a report type to parse this file.")
                    continue

                manual = parse_with_mapping(r.filename, r.raw, platform_key, report_key)
                if manual.error:
                    st.error(manual.error)
                    continue
                if manual.warnings:
                    for w in manual.warnings:
                        st.warning(w)
                st.caption(f"{len(manual.df)} rows parsed")
                st.dataframe(manual.df.head(20), width='stretch')
                ready_to_save.append(manual)

    if ready_to_save:
        st.subheader("Ready to save")
        summary = {}
        for r in ready_to_save:
            key = (PLATFORM_LABELS.get(r.platform, r.platform), REPORT_TYPE_LABELS.get(r.report_type, r.report_type))
            summary[key] = summary.get(key, 0) + len(r.df)
        for (platform, report_type), n in summary.items():
            st.write(f"- **{platform} — {report_type}**: {n} rows")

        if st.button("Confirm & Save to Dashboard", type="primary"):
            session = get_session()
            saved = []
            for r in ready_to_save:
                batch_id, n = repo.insert_batch(session, r.platform, r.report_type, r.filename, r.df)
                saved.append((r.platform, r.report_type, n))
            st.success(f"Saved {len(saved)} file(s) to the dashboard. Data is now visible on the other pages.")
            st.balloons()
    else:
        st.info("No files are ready to save yet -- fix any errors above or upload different files.")
else:
    st.caption("No files uploaded yet.")

render_footer()
