# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: AGPL-3.0

"""GitDBLifecycle — bridges execute() to ArticleStorage action methods.

The lifecycle is a thin mapping layer.  All storage access goes through
ArticleStorage action methods, not SQL/Git directly.
"""

from __future__ import annotations

import json

from peerpedia_core.exceptions import BadRequestError
from peerpedia_core.protocols.lifecycle import Extra, Evaluation
from peerpedia_core.types.entities import Article, Review
from peerpedia_core.types.scores import Scores
from peerpedia_core.protocols.storage import ArticleStorage

__all__ = ["GitDBLifecycle"]


class GitDBLifecycle:
    """Lifecycle bridging ``execute()`` to ``ArticleStorage`` action methods.

    Implements the 5 universal actions: create / revise / publish / delete / review.
    All storage access is delegated to the injected ``ArticleStorage``.
    """

    def __init__(self, storage: ArticleStorage):
        self.storage = storage

    @property
    def actions(self) -> frozenset[str]:
        return frozenset({"create", "revise", "publish", "delete", "review"})

    def resolve(self, action: str) -> Evaluation:
        s = self.storage
        if action == "create":
            return lambda extra, ctx: s.create_article()
        if action == "revise":
            return lambda extra, ctx: (
                s.update_article(ctx, str(extra["content"]),
                                 _require_article(extra)), ctx)[1]
        if action == "publish":
            return lambda extra, ctx: (
                s.meta.update(ctx, _require_article(extra)),
                s.reconcile_article(ctx), ctx)[2]
        if action == "delete":
            return lambda extra, ctx: (s.delete_article(ctx), ctx)[1]
        if action == "review":
            return lambda extra, ctx: (
                s.create_review(
                    ctx,
                    _require_review(extra).reviewer_id,
                    _parse_scores(extra),
                ), ctx)[1]
        raise BadRequestError(f"Unknown action: {action}")


def _require_article(extra: Extra) -> Article:
    a = extra.get("article")
    if not isinstance(a, Article):
        raise BadRequestError(
            f"Expected 'article' to be Article, got {type(a).__name__}",
            field="article", bad_value=str(type(a)),
        )
    return a


def _require_review(extra: Extra) -> Review:
    r = extra.get("review")
    if not isinstance(r, Review):
        raise BadRequestError(
            f"Expected 'review' to be Review, got {type(r).__name__}",
            field="review", bad_value=str(type(r)),
        )
    return r


def _parse_scores(extra: Extra) -> Scores:
    scores_str = str(extra.get("scores", "{}"))
    return Scores(dimensions=json.loads(scores_str))
