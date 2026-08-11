"""
SQLAlchemy engine + session management.

`pool_pre_ping=True` is important here specifically because Supabase's
pooled connections can go stale/be recycled server-side; pre-ping avoids
surfacing that as a random 500 mid-request.
"""
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""
    pass


def get_db() -> Session:
    """
    FastAPI dependency that yields a request-scoped DB session and
    guarantees it is closed afterward, even on exceptions.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@contextmanager
def get_task_db_session() -> Iterator[Session]:
    """
    Session helper for Celery tasks, which have no FastAPI request to be
    scoped to. Use as:

        with get_task_db_session() as db:
            ...

    Commits are still the task's responsibility (same as request-scoped
    usage) — this only guarantees the session is closed on exit.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
