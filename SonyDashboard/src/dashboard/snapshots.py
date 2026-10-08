"""Pick which uploaded snapshot to show for the dates being viewed.

Product performance, affiliate, traffic-source, creator and Shopee ad-campaign reports have no
date on each row -- each upload is a snapshot of a period. Showing "the latest upload" no matter
which dates are selected made a month with no upload (say July) display June's file. Here each
platform's snapshot is chosen by whether its period overlaps the selected dates.
"""
import datetime

import pandas as pd
import streamlit as st

from src.ingestion.router import PLATFORM_LABELS


def _is_date(v) -> bool:
    return isinstance(v, datetime.date) and not pd.isna(v)


def _fmt(d) -> str:
    return d.strftime("%d %b %Y")


def pick_snapshots(df: pd.DataFrame, start, end):
    """For each platform in `df` (which must carry batch_period_start / batch_period_end, see
    repository.attach_batch_periods), keep the most recently uploaded file whose period overlaps
    [start, end]. A file with no recorded period is used only when no dated file matches, and is
    flagged. Returns (rows to show, {platform: note}), where a note has a status of "match",
    "unknown" or "none" plus the period and filename involved."""
    notes, kept = {}, []
    for platform, rows in df.groupby("platform"):
        batches = []
        for _, g in rows.groupby("upload_batch_id"):
            first = g.iloc[0]
            batches.append({
                "id": first["upload_batch_id"], "uploaded_at": g["uploaded_at"].max(),
                "start": first["batch_period_start"], "end": first["batch_period_end"],
                "filename": first.get("source_filename"),
            })
        dated = [b for b in batches if _is_date(b["start"]) and _is_date(b["end"])]
        dated_ids = {b["id"] for b in dated}
        undated = [b for b in batches if b["id"] not in dated_ids]
        matching = [b for b in dated if b["end"] >= start and b["start"] <= end]

        if matching:
            chosen, status = max(matching, key=lambda b: b["uploaded_at"]), "match"
        elif undated:
            chosen, status = max(undated, key=lambda b: b["uploaded_at"]), "unknown"
        else:
            latest = max(dated, key=lambda b: b["end"]) if dated else None
            notes[platform] = {"status": "none", "start": latest and latest["start"],
                               "end": latest and latest["end"], "filename": latest and latest["filename"]}
            continue
        kept.append(rows[rows["upload_batch_id"] == chosen["id"]])
        notes[platform] = {"status": status, "start": chosen["start"], "end": chosen["end"],
                           "filename": chosen["filename"]}
    frame = pd.concat(kept) if kept else df.iloc[0:0]
    return frame, notes


def render_snapshot_notes(notes: dict):
    """One line per platform saying which file is shown, or why nothing is."""
    for platform, note in notes.items():
        label = PLATFORM_LABELS.get(platform, platform)
        if note["status"] == "match":
            st.caption(f"{label}: showing the file covering {_fmt(note['start'])} – {_fmt(note['end'])}.")
        elif note["status"] == "unknown":
            st.warning(
                f"{label}: the latest file has no recorded period, so it may not be from the dates "
                "selected. Set its period under Data Management so it can be matched properly."
            )
        elif note["start"]:
            st.info(
                f"{label}: no file covers these dates. The file on record covers "
                f"{_fmt(note['start'])} – {_fmt(note['end'])}."
            )
