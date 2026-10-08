import datetime

import streamlit as st

from src.ingestion.router import PLATFORM_LABELS
from src.storage import repository as repo
from src.storage.db import get_session

_ALL_PLATFORMS = list(PLATFORM_LABELS.keys())


def _default_date_range():
    """90 days ending on the latest day that has data -- not on today, which may be weeks
    past the last upload and would leave the picker sitting on days with nothing in them."""
    session = get_session()
    try:
        latest = repo.latest_report_date(session)
    finally:
        session.close()
    end = latest or datetime.date.today()
    return (end - datetime.timedelta(days=90), end)


def sidebar_filters():
    """Shared date-range + platform filter, persisted across pages via st.session_state
    (widget `key=` makes Streamlit remember the selection as the user navigates pages)."""
    st.sidebar.header("Filters")

    labels = [PLATFORM_LABELS[p] for p in _ALL_PLATFORMS]
    selected_labels = st.sidebar.multiselect(
        "Platforms", options=labels, default=labels, key="filter_platform_labels",
    )
    selected_platforms = [p for p in _ALL_PLATFORMS if PLATFORM_LABELS[p] in selected_labels] or _ALL_PLATFORMS

    default_range = _default_date_range()
    picked = st.sidebar.date_input("Date range", value=default_range, key="filter_date_range")

    if isinstance(picked, tuple) and len(picked) == 2:
        start_date, end_date = picked
    else:
        start_date, end_date = default_range

    return selected_platforms, start_date, end_date
