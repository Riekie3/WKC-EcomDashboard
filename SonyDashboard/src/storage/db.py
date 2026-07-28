import os

import streamlit as st
from sqlalchemy import create_engine
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


def get_engine(database_url: str | None = None):
    database_url = database_url or get_database_url()
    connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
    if database_url.startswith("sqlite"):
        os.makedirs(os.path.dirname(DEFAULT_DB_PATH), exist_ok=True)
    engine = create_engine(database_url, connect_args=connect_args)
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


def is_sqlite() -> bool:
    return get_database_url().startswith("sqlite")


def erase_database():
    """Wipe all data in place (drop + recreate every table on the live engine).
    Works the same way regardless of backend (SQLite locally, Postgres when deployed) --
    SQLAlchemy's drop_all/create_all is backend-agnostic."""
    session = get_session()
    session.close()
    Base.metadata.drop_all(_engine)
    Base.metadata.create_all(_engine)
