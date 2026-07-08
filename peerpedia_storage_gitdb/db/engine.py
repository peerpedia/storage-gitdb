# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: AGPL-3.0

"""Database engine, session factory, and utility types.

Provides:
- JSONType type decorator for SQLite (stores list/dict as JSON text)
- Engine creation with WAL mode + foreign keys
- Session factory
- Declarative Base
"""

from __future__ import annotations

import json
import logging
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.types import Text, TypeDecorator

_log = logging.getLogger(__name__)


# ── JSON column type ────────────────────────────────────────────────────────


class JSONType(TypeDecorator):
    """Store Python list or dict as JSON string in SQLite."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return json.loads(value)


# ── Base + Engine ───────────────────────────────────────────────────────────


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_engine_cache: dict[str, Engine] = {}


def get_engine(database_url: str) -> Engine:
    """Return a cached SQLAlchemy engine, creating one on first call per URL.

    SQLAlchemy Engine is thread-safe and designed to be a process singleton.
    """
    if database_url in _engine_cache:
        return _engine_cache[database_url]

    connect_args = {}
    if "sqlite" in database_url:
        connect_args["check_same_thread"] = False

    engine = create_engine(database_url, connect_args=connect_args, echo=False)

    if "sqlite" in database_url:

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    _engine_cache[database_url] = engine
    return engine


def init_db(engine: Engine) -> None:
    """Create all tables if they don't exist."""
    Base.metadata.create_all(engine)


def dispose_engine(database_url: str) -> None:
    """Dispose and evict a cached engine.

    Removes the engine from the cache and closes all pooled connections.
    This triggers SQLite WAL checkpoint so the next process sees committed data.
    """
    engine = _engine_cache.pop(database_url, None)
    if engine is not None:
        engine.dispose()
    _factory_cache.pop(database_url, None)


_factory_cache: dict[str, sessionmaker] = {}


def get_session_factory(engine: Engine) -> sessionmaker:
    """Return a cached sessionmaker for *engine*."""
    key = str(engine.url)
    if key not in _factory_cache:
        _factory_cache[key] = sessionmaker(bind=engine, expire_on_commit=False)
    return _factory_cache[key]


def get_session(engine: Engine) -> Generator[Session, None, None]:
    """Context manager that yields a session with auto commit/rollback/close.

    Usage::

        with get_session(engine) as session:
            row = session.query(...).first()
        # session is committed and closed on exit
    """

    @contextmanager
    def _session_scope() -> Generator[Session, None, None]:
        factory = get_session_factory(engine)
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return _session_scope()
