# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: AGPL-3.0

"""SQLAlchemy ORM models — database representation of core entities.

These rows mirror ``peerpedia_core.types.entities`` but add storage-layer
concerns (columns, indexes, foreign keys).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.dialects.sqlite import JSON as JSONType
from sqlalchemy.orm import declarative_base

Base = declarative_base()


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ArticleRow(Base):
    __tablename__ = "articles"

    id: str = Column(String, primary_key=True, default=_new_id)
    title: str = Column(String, nullable=False)
    status: str = Column(String, nullable=False, default="draft", index=True)
    authors: str = Column(String, nullable=False, default="")      # JSON-encoded tuple
    abstract: str | None = Column(String, nullable=True)
    keywords: str | None = Column(String, nullable=True)            # JSON-encoded list
    score: dict | None = Column(JSONType, nullable=True)
    forked_from: str | None = Column(String, nullable=True, index=True)
    fork_count: int = Column(Integer, nullable=False, default=0)
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)
    updated_at: datetime = Column(DateTime, nullable=False, default=_utcnow)


class ReviewRow(Base):
    __tablename__ = "reviews"

    id: str = Column(String, primary_key=True, default=_new_id)
    article_id: str = Column(String, ForeignKey("articles.id"), nullable=False, index=True)
    reviewer_id: str = Column(String, ForeignKey("users.id"), nullable=False)
    scope: str = Column(String, nullable=False, default="sedimentation")
    scores: dict = Column(JSONType, nullable=False, default=dict)
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)


class UserRow(Base):
    __tablename__ = "users"

    id: str = Column(String, primary_key=True)
    name: str = Column(String, nullable=False)
    public_key: str | None = Column(String, nullable=True)
    reputation: dict | None = Column(JSONType, nullable=True)
