# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: AGPL-3.0

"""Database models — SQLite metadata cache for fast queries.

Content lives in git repos.  These tables cache structured metadata
so listing and search don't require walking the filesystem.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, Integer, String

from peerpedia_core.types.entities import Article, ArticleId, Review, ReviewId, Scores, User, UserId
from peerpedia_storage_gitdb.db.engine import Base, JSONType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ArticleMetaStorage(Base):
    """Metadata cache for an article — content lives in git."""

    __tablename__ = "articles"

    id: str = Column(String, primary_key=True)
    title: str = Column(String, nullable=False, default="")
    status: str = Column(String, nullable=False, default="draft", index=True)
    abstract: str | None = Column(String, nullable=True)
    keywords: list[str] | None = Column(JSONType, nullable=True)
    authors: list[str] | None = Column(JSONType, nullable=True)
    format: str | None = Column(String, nullable=True)
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)
    updated_at: datetime = Column(DateTime, nullable=False, default=_utcnow, onupdate=_utcnow)

    def to_entity(self) -> Article:
        """Convert to core :class:`Article`.

        ``content_ref`` and ``bib_data`` are not set here — they are resolved
        by ``ArticleStorage.extract()`` from the git content store.
        """
        return Article(
            id=ArticleId(id=self.id),
            title=self.title,
            status=self.status,
            authors=tuple(self.authors) if self.authors else (),
            abstract=self.abstract,
            keywords=tuple(self.keywords) if self.keywords else (),
            format=self.format,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class ReviewMetaStorage(Base):
    """Metadata cache for a peer review — review files live in git."""

    __tablename__ = "reviews"

    id: str = Column(String, primary_key=True)
    article_id: str = Column(String, nullable=False, index=True)
    reviewer_id: str = Column(String, nullable=False)
    commit_hash: str = Column(String, nullable=False, default="")
    scope: str = Column(String, nullable=False, default="")
    scores: dict[str, float] | None = Column(JSONType, nullable=True)  # type: ignore[assignment]
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)

    def to_entity(self) -> Review:
        return Review(
            id=ReviewId(id=self.id),
            article_id=ArticleId(id=self.article_id),
            reviewer_id=UserId(id=self.reviewer_id),
            scope=self.scope or "",
            scores=Scores(dimensions=dict(self.scores)) if self.scores else Scores(),
            created_at=self.created_at,
        )


class UserModel(Base):
    """Peer identity — public key and display name."""

    __tablename__ = "users"

    id: str = Column(String, primary_key=True)
    name: str = Column(String, nullable=False, default="")
    public_key: str | None = Column(String, nullable=True)
    created_at: datetime = Column(DateTime, nullable=False, default=_utcnow)

    def to_entity(self) -> User:
        return User(
            id=UserId(id=self.id),
            name=self.name,
            public_key=self.public_key,
        )
