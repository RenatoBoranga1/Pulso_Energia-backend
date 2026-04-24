from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings


def _build_engine_kwargs() -> dict[str, object]:
    settings = get_settings()
    engine_kwargs: dict[str, object] = {
        "pool_pre_ping": True,
        "future": True,
    }
    if settings.is_sqlite:
        engine_kwargs["connect_args"] = {"check_same_thread": False}
        if ":memory:" in settings.database_url:
            engine_kwargs["poolclass"] = StaticPool
    else:
        engine_kwargs.update(
            {
                "pool_size": settings.db_pool_size,
                "max_overflow": settings.db_max_overflow,
                "pool_timeout": settings.db_pool_timeout_seconds,
                "pool_recycle": settings.db_pool_recycle_seconds,
            }
        )
    return engine_kwargs


@lru_cache
def get_engine() -> Engine:
    settings = get_settings()
    return create_engine(settings.database_url, **_build_engine_kwargs())


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    return sessionmaker(
        bind=get_engine(),
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
        class_=Session,
    )


def get_db_session() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def dispose_engine() -> None:
    if "get_engine" in globals():
        try:
            get_engine().dispose()
        except Exception:
            pass
    get_session_factory.cache_clear()
    get_engine.cache_clear()
