"""
SQLAlchemy engine/session management for the Aurora PostgreSQL metadata
repository and target data warehouse (same cluster, different schemas).
"""
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from etl_platform.config import DB


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(DB.sqlalchemy_url, pool_pre_ping=True, pool_size=5, max_overflow=10)


@lru_cache(maxsize=1)
def get_session_factory():
    return sessionmaker(bind=get_engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Session:
    """Provide a transactional scope around a series of operations."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
