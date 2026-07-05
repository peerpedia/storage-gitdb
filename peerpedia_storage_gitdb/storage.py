# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: AGPL-3.0

"""GitDBStorage — git + SQLite implementation of ArticleStorage.

Key scheme::

    "articles/<id>"           → Article metadata + source in git
    "reviews/<article_id>/<reviewer_id>" → Review data
    "users/<id>"              → User metadata

Read pipeline::

    storage.read("articles/abc")    → {"title": ..., "status": ..., ...}
    storage.list("author:alice")    → ["articles/abc", "articles/def"]

Write pipeline (called by lifecycle action)::

    storage.write("articles/abc", {...}, signer, "publish article")
"""

from __future__ import annotations

import json
from typing import Any

from peerpedia_core.crypto import SigningKey
from peerpedia_core.protocols.storage import ArticleStorage

from peerpedia_storage_gitdb.db import (
    get_article, get_review, get_session, get_user,
    list_articles, list_reviews,
    upsert_article, upsert_review, upsert_user,
)
from peerpedia_storage_gitdb.db.models import ArticleRow, ReviewRow, UserRow
from peerpedia_storage_gitdb.git import (
    commit_content, init_article_repo, read_content, repo_history,
)


class GitDBStorage:
    """Implements ``ArticleStorage`` with git repos + SQLite."""

    def __init__(self) -> None:
        self._session = get_session()

    # ── Read ────────────────────────────────────────────────────────────

    def read(self, key: str) -> dict[str, Any]:
        """Return data at *key* as a dict."""
        parts = key.split("/")
        db = self._session

        if parts[0] == "articles" and len(parts) == 2:
            return _article_to_dict(get_article(db, parts[1]))
        if parts[0] == "reviews" and len(parts) == 3:
            r = get_review(db, parts[1], parts[2])
            if r is None:
                from peerpedia_core.exceptions import NotFoundError
                raise NotFoundError(
                    resource_type="review",
                    resource_id=f"{parts[1]}/{parts[2]}",
                )
            return _review_to_dict(r)
        if parts[0] == "users" and len(parts) == 2:
            return _user_to_dict(get_user(db, parts[1]))
        from peerpedia_core.exceptions import BadRequestError
        raise BadRequestError(f"Unknown key format: {key}")

    def list(self, query: str | None = None) -> list[str]:
        """Return keys matching *query*."""
        db = self._session
        rows = list_articles(db, query)
        return [f"articles/{r.id}" for r in rows]

    def diff(
        self, article_id: str, from_version: str, to_version: str
    ) -> str:
        """Return unified diff between two versions."""
        import git
        rp = init_article_repo(article_id)
        repo = git.Repo(rp)
        return repo.git.diff(from_version, to_version)

    # ── Write ───────────────────────────────────────────────────────────

    def write(
        self,
        key: str,
        data: dict[str, Any],
        signer: SigningKey,
        message: str,
    ) -> str:
        """Persist *data* at *key*, return version identifier."""
        parts = key.split("/")
        db = self._session

        if parts[0] == "articles" and len(parts) == 2:
            return self._write_article(parts[1], data, signer, message)
        if parts[0] == "reviews" and len(parts) == 3:
            return self._write_review(parts[1], parts[2], data, signer, message)
        if parts[0] == "users" and len(parts) == 2:
            return self._write_user(parts[1], data, signer, message)
        from peerpedia_core.exceptions import BadRequestError
        raise BadRequestError(f"Unknown key format: {key}")

    # ── History ─────────────────────────────────────────────────────────

    def history(
        self, key: str, since: str | None = None
    ) -> list[dict]:
        """Return change history for *key*."""
        parts = key.split("/")
        if parts[0] == "articles" and len(parts) == 2:
            rp = init_article_repo(parts[1])
            return repo_history(rp, since)
        return []

    # ── Internal ────────────────────────────────────────────────────────

    def _write_article(
        self, article_id: str, data: dict, signer: SigningKey, message: str
    ) -> str:
        db = self._session
        rp = init_article_repo(article_id)

        # Write source if provided
        if "content" in data:
            (rp / "article.md").write_text(data["content"])

        # Git commit
        commit_hash = commit_content(rp, message, signer)

        # DB metadata
        upsert_article(db, article_id, data)
        db.commit()

        return commit_hash

    def _write_review(
        self, article_id: str, reviewer_id: str, data: dict,
        signer: SigningKey, message: str,
    ) -> str:
        db = self._session
        rp = init_article_repo(article_id)

        # Write review to git
        review_dir = rp / "reviews" / reviewer_id
        review_dir.mkdir(parents=True, exist_ok=True)
        (review_dir / "review.md").write_text(data.get("comment", ""))

        commit_hash = commit_content(rp, message, signer)

        # DB metadata
        upsert_review(db, article_id, reviewer_id, data)
        db.commit()

        return commit_hash

    def _write_user(
        self, user_id: str, data: dict, signer: SigningKey, message: str
    ) -> str:
        db = self._session
        upsert_user(db, user_id, data)
        db.commit()
        # Users don't have git repos; return a database version marker
        return f"db:{user_id}"


# ── Row → dict helpers ──────────────────────────────────────────────────────

def _article_to_dict(row: ArticleRow | None) -> dict:
    if row is None:
        from peerpedia_core.exceptions import NotFoundError
        raise NotFoundError(resource_type="article")
    return {
        "id": row.id,
        "title": row.title,
        "status": row.status,
        "authors": tuple(json.loads(row.authors)) if row.authors else (),
        "abstract": row.abstract,
        "keywords": tuple(json.loads(row.keywords)) if row.keywords else (),
        "score": row.score,
        "forked_from": row.forked_from,
        "fork_count": row.fork_count,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _review_to_dict(row: ReviewRow) -> dict:
    return {
        "id": row.id,
        "article_id": row.article_id,
        "reviewer_id": row.reviewer_id,
        "scope": row.scope,
        "scores": row.scores or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _user_to_dict(row: UserRow | None) -> dict:
    if row is None:
        from peerpedia_core.exceptions import NotFoundError
        raise NotFoundError(resource_type="user")
    return {
        "id": row.id,
        "name": row.name,
        "public_key": row.public_key,
        "reputation": row.reputation,
    }
