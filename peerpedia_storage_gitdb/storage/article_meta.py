"""SQLite ArticleMetaStorage — indexed metadata cache."""
from __future__ import annotations

import time
import uuid

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.types.entities import Article, ArticleId, Version
from peerpedia_core.types.queries import ArticleQuery
from sqlalchemy import Engine

from peerpedia_storage_gitdb.db.engine import get_session
from peerpedia_storage_gitdb.db.models import ArticleMetaStorage


class SqlArticleMetaStorage:
    """Implements peerpedia_core.protocols.storage.ArticleMetaStorage."""

    def __init__(self, engine: Engine):
        self._engine = engine

    def create(self) -> ArticleId:
        with get_session(self._engine) as session:
            row = ArticleMetaStorage(id=str(uuid.uuid4()), title="", status="draft")
            session.add(row)
            session.flush()
            return ArticleId(id=row.id)

    def read(self, key: ArticleId) -> Article:
        with get_session(self._engine) as session:
            return self._require_article(session, key.id).to_entity()

    def update(self, key: ArticleId, meta: Article) -> Version:
        with get_session(self._engine) as session:
            row = self._require_article(session, key.id)
            row.title = meta.title
            row.status = meta.status
            row.abstract = meta.abstract
            row.authors = list(meta.authors) if meta.authors else None
            row.keywords = list(meta.keywords) if meta.keywords else None
            row.format = meta.format
            return Version(id=f"v-{time.monotonic_ns()}")

    def delete(self, key: ArticleId) -> Version:
        with get_session(self._engine) as session:
            row = self._require_article(session, key.id)
            session.delete(row)
            return Version(id=f"v-{time.monotonic_ns()}")

    def query(self, q: ArticleQuery | None = None) -> list[Article]:
        with get_session(self._engine) as session:
            query = session.query(ArticleMetaStorage)

            if q is not None:
                if q.statuses is not None:
                    query = query.filter(ArticleMetaStorage.status.in_(q.statuses))
                if q.search is not None:
                    p = f"%{q.search}%"
                    query = query.filter(
                        ArticleMetaStorage.title.ilike(p)
                        | ArticleMetaStorage.abstract.ilike(p)
                    )
                if q.id_prefix is not None:
                    query = query.filter(ArticleMetaStorage.id.startswith(q.id_prefix))

            query = query.order_by(ArticleMetaStorage.updated_at.desc())

            if q is not None:
                if q.limit is not None:
                    query = query.limit(q.limit)
                if q.offset:
                    query = query.offset(q.offset)

            return [row.to_entity() for row in query.all()]

    def _require_article(self, session, article_id: str) -> ArticleMetaStorage:
        row = session.query(ArticleMetaStorage).filter_by(id=article_id).first()
        if row is None:
            raise NotFoundError(resource_type="article", resource_id=article_id)
        return row
