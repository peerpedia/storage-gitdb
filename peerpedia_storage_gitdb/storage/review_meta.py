"""SQLite ReviewMetaStorage — indexed review cache."""
from __future__ import annotations

import time
import uuid

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.types.entities import ArticleId, Review, ReviewId, Scores, UserId, Version
from sqlalchemy import Engine

from peerpedia_storage_gitdb.db.engine import get_session
from peerpedia_storage_gitdb.db.models import ReviewMetaStorage


class SqlReviewMetaStorage:
    """Implements peerpedia_core.protocols.storage.ReviewMetaStorage."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def create(self, article_id: ArticleId, reviewer_id: UserId) -> Review:
        with get_session(self._engine) as session:
            row = ReviewMetaStorage(
                id=str(uuid.uuid4()),
                article_id=article_id.id,
                reviewer_id=reviewer_id.id,
            )
            session.add(row)
            session.flush()
            return self._row_to_review(row)

    def read(self, article_id: ArticleId, reviewer_id: UserId) -> Review:
        with get_session(self._engine) as session:
            return self._row_to_review(self._require_review(session, article_id.id, reviewer_id.id))

    def update(
        self, article_id: ArticleId, reviewer_id: UserId, review: Review,
    ) -> Version:
        with get_session(self._engine) as session:
            row = self._require_review(session, article_id.id, reviewer_id.id)
            row.scope = review.scope
            row.scores = dict(review.scores.dimensions) if review.scores.dimensions else None
            return Version(id=f"v-{time.monotonic_ns()}")

    def delete(self, article_id: ArticleId, reviewer_id: UserId) -> Version:
        with get_session(self._engine) as session:
            row = self._require_review(session, article_id.id, reviewer_id.id)
            session.delete(row)
            return Version(id=f"v-{time.monotonic_ns()}")

    def list(self, article_id: ArticleId) -> list[Review]:
        with get_session(self._engine) as session:
            rows = session.query(ReviewMetaStorage).filter_by(article_id=article_id.id).all()
            return [self._row_to_review(r) for r in rows]

    def _require_review(self, session, article_id: str, reviewer_id: str) -> ReviewMetaStorage:
        row = session.query(ReviewMetaStorage).filter_by(
            article_id=article_id, reviewer_id=reviewer_id,
        ).first()
        if row is None:
            raise NotFoundError(
                resource_type="review",
                resource_id=f"{article_id}/{reviewer_id}",
            )
        return row

    def _row_to_review(self, row: ReviewMetaStorage) -> Review:
        return Review(
            id=ReviewId(id=row.id),
            article_id=ArticleId(id=row.article_id),
            reviewer_id=UserId(id=row.reviewer_id),
            scope=row.scope or "",
            scores=Scores(dimensions=row.scores) if row.scores else Scores(),
            created_at=row.created_at,
        )
