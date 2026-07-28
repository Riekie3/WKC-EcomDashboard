import datetime

import streamlit as st

from src.ingestion.router import PLATFORM_LABELS, REPORT_TYPE_LABELS
from src.storage.db import get_session, erase_database
from src.storage.backup import export_backup, validate_backup, restore_backup
from src.storage import repository as repo
from src.dashboard.branding import apply_logo, render_footer

st.set_page_config(page_title="Data Management", page_icon="🗑️", layout="wide")
apply_logo()
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
    st.dataframe(show, width='stretch', hide_index=True)

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
st.caption("Download a full export of every table as a safety net -- useful since data is kept indefinitely.")
if st.button("Prepare backup"):
    st.session_state["backup_bytes"] = export_backup(session)
if "backup_bytes" in st.session_state:
    st.download_button(
        "Download backup (.zip)", data=st.session_state["backup_bytes"],
        file_name=f"wkc_dashboard_backup_{datetime.date.today():%Y%m%d}.zip",
    )

st.divider()
st.subheader("Restore from backup")
st.caption("Upload a previously downloaded backup .zip. This replaces the entire current database -- everything currently in the dashboard that isn't in the backup will be lost.")
backup_file = st.file_uploader("Backup file (.zip)", type=["zip"], key="restore_upload")
if backup_file is not None:
    ok, msg = validate_backup(backup_file.getvalue())
    if not ok:
        st.error(msg)
    else:
        st.warning("This will completely replace the current database with the uploaded backup. This cannot be undone.")
        confirm_restore = st.checkbox("I understand this replaces all current data.", key="confirm_restore")
        if st.button("Restore this backup", disabled=not confirm_restore, type="primary"):
            restore_backup(session, backup_file.getvalue())
            st.success("Database restored from backup.")
            st.rerun()

st.divider()
st.subheader("⚠️ Danger zone")
with st.expander("Erase everything"):
    st.error("This permanently deletes ALL data in the dashboard (every platform, every report type, every batch). There is no undo -- download a backup first if you're not sure.")
    typed = st.text_input('Type "ERASE" to confirm', key="erase_confirm_text")
    if st.button("Erase all data", disabled=typed != "ERASE", type="primary"):
        erase_database()
        st.success("All data erased.")
        st.rerun()

render_footer()
