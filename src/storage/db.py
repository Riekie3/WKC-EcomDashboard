import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.storage.models import Base

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
