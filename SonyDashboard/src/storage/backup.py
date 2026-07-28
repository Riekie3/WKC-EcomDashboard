"""Database-agnostic backup/restore: exports every row of every table as JSON, zipped
together. Replaces the earlier SQLite-only approach (raw .db file download + sqlite3
.backup()), which only made sense for a SQLite backend -- this works identically whether
the live database is local SQLite or a hosted Postgres.
"""
import datetime
import io
import json
import zipfile

from sqlalchemy import Date, DateTime
from sqlalchemy.orm import sessionmaker

from src.storage.models import Base, FACT_TABLES, UploadBatch

ALL_TABLES = {"upload_batches": UploadBatch, **FACT_TABLES}
BACKUP_FORMAT = "wkc-dashboard-backup"


def _serialize_value(v):
    if isinstance(v, (datetime.datetime, datetime.date)):
        return v.isoformat()
    return v


def _deserialize_row(row: dict, model) -> dict:
    out = {}
    for col in model.__table__.columns:
        if col.name not in row:
            continue
        val = row[col.name]
        if val is None:
            out[col.name] = None
        elif isinstance(col.type, DateTime) and isinstance(val, str):
            out[col.name] = datetime.datetime.fromisoformat(val)
        elif isinstance(col.type, Date) and isinstance(val, str):
            out[col.name] = datetime.date.fromisoformat(val)
        else:
            out[col.name] = val
    return out


def export_backup(session) -> bytes:
    """Export every row of every table as JSON, zipped together."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = {"format": BACKUP_FORMAT, "version": 1, "tables": list(ALL_TABLES.keys())}
        zf.writestr("manifest.json", json.dumps(manifest))
        for table_name, model in ALL_TABLES.items():
            rows = session.query(model).all()
            data = [
                {c.name: _serialize_value(getattr(r, c.name)) for c in model.__table__.columns}
                for r in rows
            ]
            zf.writestr(f"{table_name}.json", json.dumps(data))
    return buf.getvalue()


def validate_backup(backup_bytes: bytes) -> tuple[bool, str]:
    """Sanity-check an uploaded file is actually a dashboard backup before it's allowed
    to overwrite the live database. Returns (ok, message)."""
    try:
        with zipfile.ZipFile(io.BytesIO(backup_bytes)) as zf:
            names = set(zf.namelist())
            if "manifest.json" not in names:
                return False, "This doesn't look like a dashboard backup file (missing manifest)."
            manifest = json.loads(zf.read("manifest.json"))
            if manifest.get("format") != BACKUP_FORMAT:
                return False, "This doesn't look like a dashboard backup file (unrecognized format)."
            missing = [t for t in ALL_TABLES if f"{t}.json" not in names]
            if missing:
                return False, f"Backup is missing data for: {', '.join(missing)}."
        return True, ""
    except zipfile.BadZipFile:
        return False, "Couldn't read this as a backup file (not a valid zip)."
    except Exception as e:
        return False, f"Couldn't read this as a backup file: {e}"


def restore_backup(session, backup_bytes: bytes):
    """Replace all current data with the contents of the backup archive."""
    engine = session.get_bind()

    with zipfile.ZipFile(io.BytesIO(backup_bytes)) as zf:
        table_data = {}
        for table_name, model in ALL_TABLES.items():
            raw = json.loads(zf.read(f"{table_name}.json"))
            table_data[table_name] = [_deserialize_row(row, model) for row in raw]

    session.close()
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)

    new_session = sessionmaker(bind=engine)()
    try:
        # upload_batches first: fact tables have a foreign key into it.
        ordered = ["upload_batches"] + [t for t in ALL_TABLES if t != "upload_batches"]
        for table_name in ordered:
            model = ALL_TABLES[table_name]
            rows = table_data.get(table_name, [])
            if rows:
                new_session.bulk_insert_mappings(model, rows)
        new_session.commit()
    finally:
        new_session.close()
