"""Database layer: sync SQLAlchemy 2.0 engine/session over SQLite (WAL mode).

Design decision (see plan E): sync SQLAlchemy is used instead of async to avoid
an extra aiosqlite dependency and keep the MVP robust/offline-friendly. DB-bound
REST endpoints that only read are declared as plain ``def`` so FastAPI runs them
in its threadpool; the send endpoint is ``async`` (it must await the WebSocket
broadcast) and performs a single fast local INSERT inline.
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

_settings = get_settings()


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


engine = create_engine(
    _settings.sqlalchemy_url,
    echo=False,
    future=True,
    # FastAPI may serve a request from a threadpool thread; SQLite connections
    # are guarded per-thread by default, so relax that for pooled reuse.
    connect_args={"check_same_thread": False},
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    """Enable WAL (better concurrent read/write) and enforce foreign keys."""
    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
    finally:
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db():
    """FastAPI dependency yielding a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables (idempotent). Models must be imported first."""
    from . import models  # noqa: F401  (register mappers)

    Base.metadata.create_all(bind=engine)
