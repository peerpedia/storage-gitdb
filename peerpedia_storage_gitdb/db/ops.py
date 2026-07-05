# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: AGPL-3.0

"""CRUD operations — typed access to the database layer.

Import from here instead of touching models or sessions directly.
"""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from peerpedia_storage_gitdb.db.models import ArticleRow, ReviewRow, UserRow


# ── Article ────────────────────────────────────────────────────────────────

def get_article(db: Session, article_id: str) -> ArticleRow | None:
    return db.get(ArticleRow, article_id)


def list_articles(db: Session, query: str | None = None) -> list[ArticleRow]:
    stmt = db.query(ArticleRow)
    if query:
        stmt = stmt.filter(
            ArticleRow.title.ilike(f"%{query}%")
            | (ArticleRow.id == query)
        )
    return stmt.order_by(ArticleRow.updated_at.desc()).limit(50).all()


def upsert_article(db: Session, article_id: str, data: dict) -> ArticleRow:
    row = db.get(ArticleRow, article_id)
    if row is None:
        row = ArticleRow(id=article_id)
        db.add(row)
    row.title = data.get("title", row.title)
    row.status = data.get("status", row.status)
    if "authors" in data:
        row.authors = json.dumps(data["authors"])
    if "abstract" in data:
        row.abstract = data["abstract"]
    if "keywords" in data:
        row.keywords = json.dumps(data["keywords"])
    if "score" in data:
        row.score = data["score"]
    db.flush()
    return row


# ── Review ─────────────────────────────────────────────────────────────────

def get_review(db: Session, article_id: str, reviewer_id: str) -> ReviewRow | None:
    return (
        db.query(ReviewRow)
        .filter(ReviewRow.article_id == article_id, ReviewRow.reviewer_id == reviewer_id)
        .first()
    )


def list_reviews(db: Session, article_id: str) -> list[ReviewRow]:
    return (
        db.query(ReviewRow)
        .filter(ReviewRow.article_id == article_id)
        .order_by(ReviewRow.created_at)
        .all()
    )


def upsert_review(
    db: Session, article_id: str, reviewer_id: str, data: dict
) -> ReviewRow:
    row = get_review(db, article_id, reviewer_id)
    if row is None:
        row = ReviewRow(article_id=article_id, reviewer_id=reviewer_id)
        db.add(row)
    if "scores" in data:
        row.scores = data["scores"]
    if "scope" in data:
        row.scope = data["scope"]
    db.flush()
    return row


# ── User ───────────────────────────────────────────────────────────────────

def get_user(db: Session, user_id: str) -> UserRow | None:
    return db.get(UserRow, user_id)


def upsert_user(db: Session, user_id: str, data: dict) -> UserRow:
    row = db.get(UserRow, user_id)
    if row is None:
        row = UserRow(id=user_id)
        db.add(row)
    row.name = data.get("name", row.name or user_id)
    if "public_key" in data:
        row.public_key = data["public_key"]
    if "reputation" in data:
        row.reputation = data["reputation"]
    db.flush()
    return row
