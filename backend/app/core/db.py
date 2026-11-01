"""SQLAlchemy engine and session factory (sync, psycopg 3).

Sync SQLAlchemy is shared by the API (FastAPI runs sync dependencies in a threadpool), Celery
workers and scripts, so there is exactly one data-access style in the codebase.
"""

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


@lru_cache
def get_engine() -> Engine:
    s = get_settings()
    return create_engine(
        str(s.database_url),
        pool_size=s.db_pool_size,
        max_overflow=s.db_max_overflow,
        pool_timeout=s.db_pool_timeout_s,
        pool_pre_ping=True,
        connect_args={
            "connect_timeout": 5,
            "options": f"-c statement_timeout={s.db_statement_timeout_ms} -c timezone=UTC",
        },
    )


@lru_cache
def get_sessionmaker() -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: one session per request; services own commit boundaries."""
    db = get_sessionmaker()()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def ping_db() -> None:
    with get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
