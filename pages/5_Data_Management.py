import datetime
import os

import streamlit as st

from src.ingestion.router import PLATFORM_LABELS, REPORT_TYPE_LABELS
from src.storage.db import get_session, DEFAULT_DB_PATH
from src.storage import repository as repo

st.set_page_config(page_title="Data Management", page_icon="🗑️", layout="wide")
st.title("🗑️ Data Management")

session = get_session()

st.subheader("Upload history")
batches = repo.list_upload_batches(session)
if batches.empty:
    st.info("No uploads yet.")
else:
    show = batches.copy()
    show["platform"] = show["platform"].map(PLATFORM_LABELS)
    show["report_type"] = show["report_type"].map(REPORT_TYPE_LABELS)
    st.dataframe(show, use_container_width=True, hide_index=True)

    st.markdown("**Delete a single upload batch**")
    batch_options = {f"{r.uploaded_at:%Y-%m-%d %H:%M} — {PLATFORM_LABELS.get(r.platform, r.platform)} — {REPORT_TYPE_LABELS.get(r.report_type, r.report_type)} — {r.source_filename}": r.id
                      for r in batches.itertuples()}
    picked_label = st.selectbox("Batch", options=list(batch_options.keys()))
    if st.button("Delete this batch"):
        n = repo.delete_by_batch_id(session, batch_options[picked_label])
        st.success(f"Deleted {n} row(s) from batch.")
        st.rerun()

st.divider()
st.subheader("Delete by date range")
st.caption("Applies to Daily Sales and Ads Performance (Product Performance has no per-row date -- delete it via batch above).")

col1, col2 = st.columns(2)
start_date = col1.date_input("Start date", value=datetime.date.today() - datetime.timedelta(days=7))
end_date = col2.date_input("End date", value=datetime.date.today())

platform_labels = st.multiselect("Platforms (leave empty for all)", options=list(PLATFORM_LABELS.values()))
selected_platforms = [p for p, label in PLATFORM_LABELS.items() if label in platform_labels] or None

if start_date > end_date:
    st.error("Start date must be before end date.")
else:
    affected = repo.count_affected_by_date_range(session, start_date, end_date, selected_platforms)
    st.write(f"This will delete **{affected}** row(s) between **{start_date}** and **{end_date}**.")
    confirm = st.checkbox("I understand this cannot be undone.")
    if st.button("Delete rows in this range", disabled=not confirm or affected == 0, type="primary"):
        n = repo.delete_by_date_range(session, start_date, end_date, selected_platforms)
        st.success(f"Deleted {n} row(s).")
        st.rerun()

st.divider()
st.subheader("Backup")
st.caption("Download the raw database file as a safety net -- useful since data is kept indefinitely.")
if os.path.exists(DEFAULT_DB_PATH):
    with open(DEFAULT_DB_PATH, "rb") as f:
        st.download_button("Download database backup (app.db)", data=f.read(), file_name="app_backup.db")
else:
    st.caption("No data uploaded yet.")
