"""GitDBArticleStorage — ArticleStorage subclass with git-aware extract()."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from peerpedia_core.protocols.storage import ArticleStorage
from peerpedia_core.types.entities import Article, ArticleId, Review, ReviewId, Scores

from peerpedia_storage_gitdb.git.guards import require_article_repo
from peerpedia_storage_gitdb.git.ops import read_article_source


class GitDBArticleStorage(ArticleStorage):
    """ArticleStorage with git-aware extract() that parses frontmatter.

    Sub-storages are injected.  ``extract()`` reads the raw git body,
    parses the YAML-like frontmatter, and merges it into the cached
    metadata so ``reconcile_article()`` populates title/authors/abstract
    from the git source of truth.
    """

    def extract(self, key: ArticleId) -> Article:
        """Reconstruct metadata from git content + meta cache."""
        article = self.meta.read(key)
        try:
            cref = self.content.read(key)
        except Exception:
            return article

        path = require_article_repo(Path(cref.ref).parent, key.id)
        source = read_article_source(path)
        if source is None:
            return article

        full_text, fmt = source
        return _merge_frontmatter(article, full_text, fmt)

    def extract_reviews(self, key: ArticleId) -> list[Review]:
        """Read reviews from git content, rebuild Review objects."""
        rcontent = self.review_content
        reviews: list[Review] = []
        for reviewer_id in rcontent.list_reviewers(key):
            scores_json = rcontent.read(key, reviewer_id)
            scores = Scores(dimensions=json.loads(scores_json)) if scores_json else Scores()
            reviews.append(Review(
                id=ReviewId(id=f"rev-{key.id}-{reviewer_id.id}"),
                article_id=key,
                reviewer_id=reviewer_id,
                scores=scores,
            ))
        return reviews


def _merge_frontmatter(article: Article, full_text: str, fmt: str | None) -> Article:
    """Parse YAML-like frontmatter from *full_text* and merge into *article*.

    Fields already set in *article* (from the meta cache) take precedence —
    frontmatter only fills in *missing* values.
    """
    if not full_text.startswith("---"):
        return replace(article, format=fmt or article.format or "markdown")

    parts = full_text.split("---", 2)
    if len(parts) < 3:
        return replace(article, format=fmt or article.format or "markdown")

    fm_text = parts[1].strip()
    updates: dict[str, object] = {}
    for line in fm_text.split("\n"):
        line = line.strip()
        if not line or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()

        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            continue

        if not getattr(article, key, None):
            if isinstance(parsed, str) and key in ("title", "status", "abstract"):
                updates[key] = parsed
            elif isinstance(parsed, list) and key in ("authors", "keywords"):
                updates[key] = tuple(parsed)

    updates.setdefault("format", fmt or article.format or "markdown")
    return replace(article, **updates)
