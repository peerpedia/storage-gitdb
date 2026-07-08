# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: AGPL-3.0

"""Wiring helpers — build fully wired storage from config strings."""
from __future__ import annotations

from pathlib import Path

from peerpedia_core.protocols.storage import ArticleStorage

from peerpedia_storage_gitdb.db.engine import get_engine, init_db
from peerpedia_storage_gitdb.storage.article import GitDBArticleStorage
from peerpedia_storage_gitdb.storage.article_content import GitArticleContentStorage
from peerpedia_storage_gitdb.storage.article_meta import SqlArticleMetaStorage
from peerpedia_storage_gitdb.storage.review_content import GitReviewContentStorage
from peerpedia_storage_gitdb.storage.review_meta import SqlReviewMetaStorage
from peerpedia_storage_gitdb.storage.user import SqlUserStorage


def build_storage(articles_dir: str, database_url: str) -> ArticleStorage:
    """Build a fully wired ArticleStorage from config strings.

    Usage::

        storage = build_storage("/data/articles", "sqlite:///peerpedia.db")
    """
    engine = get_engine(database_url)
    init_db(engine)
    return GitDBArticleStorage(
        meta=SqlArticleMetaStorage(engine),
        content=GitArticleContentStorage(Path(articles_dir)),
        review_meta=SqlReviewMetaStorage(engine),
        review_content=GitReviewContentStorage(Path(articles_dir)),
    )


def build_user_storage(database_url: str) -> SqlUserStorage:
    """Build a UserStorage from a database URL.

    May share an engine with ``build_storage()`` or use a separate DB.
    """
    engine = get_engine(database_url)
    init_db(engine)
    return SqlUserStorage(engine)
