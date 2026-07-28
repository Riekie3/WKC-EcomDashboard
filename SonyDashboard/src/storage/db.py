import os
import sqlite3
import tempfile

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.storage.models import Base

REQUIRED_TABLES = {"upload_batches", "daily_sales", "product_performance", "ads_performance"}

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "app.db")


def get_engine(db_path: str = DEFAULT_DB_PATH):
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    return engine


_engine = None
_SessionLocal = None


def get_session():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = get_engine()
        _SessionLocal = sessionmaker(bind=_engine)
    return _SessionLocal()


def erase_database():
    """Wipe all data in place (drop + recreate every table on the live engine).
    Deliberately avoids deleting/replacing the .db file at the OS level -- SQLite keeps
    the file handle open even after a SQLAlchemy session commits, so a Windows file-delete
    or overwrite can hit a PermissionError; operating through the open connection instead
    sidesteps that entirely."""
    session = get_session()
    session.close()
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)


def validate_backup(backup_bytes: bytes) -> tuple[bool, str]:
    """Sanity-check an uploaded file is actually a dashboard backup before it's allowed
    to overwrite the live database. Returns (ok, message)."""
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp.write(backup_bytes)
            tmp_path = tmp.name
        conn = sqlite3.connect(tmp_path)
        try:
            rows = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        finally:
            conn.close()
        tables = {r[0] for r in rows}
        missing = REQUIRED_TABLES - tables
        if missing:
            return False, f"This doesn't look like a dashboard backup file (missing tables: {', '.join(sorted(missing))})."
        return True, ""
    except Exception as e:
        return False, f"Couldn't read this as a database file: {e}"
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


def restore_database(backup_bytes: bytes):
    """Replace the live database's contents with an uploaded backup, using SQLite's own
    backup API (source_conn.backup(target_conn)) rather than an OS-level file overwrite --
    this copies data through open connections and lets SQLite handle locking itself, instead
    of racing a Windows file lock the way a plain file replace would."""
    session = get_session()
    session.close()
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
            tmp.write(backup_bytes)
            tmp_path = tmp.name
        source = sqlite3.connect(tmp_path)
        target = sqlite3.connect(DEFAULT_DB_PATH)
        try:
            source.backup(target)
        finally:
            target.close()
            source.close()
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)
