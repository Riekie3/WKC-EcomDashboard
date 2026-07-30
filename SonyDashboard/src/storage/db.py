import os

import streamlit as st
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker

from src.storage.models import Base

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data", "app.db")


def get_database_url() -> str:
    """Postgres connection string when deployed (set DATABASE_URL in
    .streamlit/secrets.toml, e.g. a Supabase/Neon connection string), falling back to a
    local SQLite file for local development -- so nothing has to change to run locally."""
    try:
        url = st.secrets.get("DATABASE_URL")
    except Exception:
        url = None
    if not url:
        url = os.environ.get("DATABASE_URL")
    if url:
        return url
    return f"sqlite:///{DEFAULT_DB_PATH}"


def _add_missing_columns(engine):
    """Add any model columns that don't exist yet on an already-deployed table.
    Base.metadata.create_all() only creates missing TABLES -- it does nothing for a table
    that already exists but is missing a column added to the model later (e.g. the
    gross_revenue/refund_amount columns), so new nullable columns need this instead."""
    inspector = inspect(engine)
    existing_tables = set(inspector.get_table_names())
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if table.name not in existing_tables:
                continue
            existing_cols = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing_cols:
                    continue
                col_type = col.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" {col_type}'))


def get_engine(database_url: str | None = None):
    database_url = database_url or get_database_url()
    if database_url.startswith("sqlite"):
        os.makedirs(os.path.dirname(DEFAULT_DB_PATH), exist_ok=True)
        connect_args = {"check_same_thread": False}
    else:
        # Supabase's connection-pooler URL runs PgBouncer in transaction-pooling mode,
        # which reassigns the underlying Postgres connection between transactions --
        # psycopg's server-side prepared statements are cached per that underlying
        # connection, so a prepared-statement name can collide with a different query
        # already prepared under it on whichever connection the pooler hands back
        # (psycopg.errors.DuplicatePreparedStatement). Disabling server-side prepare
        # avoids this; it's unrelated to any schema/data issue.
        connect_args = {"prepare_threshold": None}
    engine = create_engine(database_url, connect_args=connect_args)
    Base.metadata.create_all(engine)
    _add_missing_columns(engine)
    return engine


_engine = None
_SessionLocal = None


def get_session():
    global _engine, _SessionLocal
    if _engine is None:
        _engine = get_engine()
        _SessionLocal = sessionmaker(bind=_engine)
    return _SessionLocal()


def is_sqlite() -> bool:
    return get_database_url().startswith("sqlite")


def backend_label() -> str:
    """Human-readable, secret-safe description of which database is currently in use --
    useful for confirming a DATABASE_URL secret is actually being picked up once deployed
    (a typo'd secret key silently falls back to local SQLite rather than erroring)."""
    url = get_database_url()
    if url.startswith("sqlite"):
        return f"Local SQLite ({url.replace('sqlite:///', '')})"
    try:
        from sqlalchemy.engine import make_url
        return f"Postgres ({make_url(url).host})"
    except Exception:
        return "Postgres (connection string set)"


def erase_database():
    """Wipe all data in place (drop + recreate every table on the live engine).
    Works the same way regardless of backend (SQLite locally, Postgres when deployed) --
    SQLAlchemy's drop_all/create_all is backend-agnostic."""
    session = get_session()
    session.close()
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)
