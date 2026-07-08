# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: AGPL-3.0

"""Git-layer guard functions — repo/file existence checks."""

from __future__ import annotations

from pathlib import Path

from peerpedia_core.exceptions import NotFoundError


def require_article_repo(articles_dir: Path, article_id: str) -> Path:
    """Return the article repo path or raise NotFoundError."""
    rp = articles_dir / article_id
    if not (rp / ".git").is_dir():
        raise NotFoundError(
            code="ARTICLE_REPO_NOT_FOUND",
            resource_type="article_repo",
            resource_id=article_id,
        )
    return rp
