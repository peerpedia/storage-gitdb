# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: AGPL-3.0

"""SQLAlchemy engine and session management."""

from __future__ import annotations

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from peerpedia_storage_gitdb.config import DB_URL
from peerpedia_storage_gitdb.db.models import Base

_engine: Engine | None = None
_Session: sessionmaker | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_engine(DB_URL, echo=False)
        Base.metadata.create_all(_engine)
    return _engine


def get_session() -> Session:
    global _Session
    if _Session is None:
        _Session = sessionmaker(bind=get_engine())
    return _Session()
