# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: AGPL-3.0

"""Database layer — SQLAlchemy engine, models, and CRUD operations."""

from peerpedia_storage_gitdb.db.engine import get_engine, get_session
from peerpedia_storage_gitdb.db.models import ArticleRow, ReviewRow, UserRow
from peerpedia_storage_gitdb.db.ops import (
    get_article, list_articles, upsert_article,
    get_review, list_reviews, upsert_review,
    get_user, upsert_user,
)

__all__ = [
    "get_engine", "get_session",
    "ArticleRow", "ReviewRow", "UserRow",
    "get_article", "list_articles", "upsert_article",
    "get_review", "list_reviews", "upsert_review",
    "get_user", "upsert_user",
]
