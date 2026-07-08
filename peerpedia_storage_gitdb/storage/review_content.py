"""Git-based ReviewContentStorage — review files in article git repos."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import git

from peerpedia_core.types.entities import ArticleId, UserId, Version
from peerpedia_core.types.writes import ReviewWrite


class GitReviewContentStorage:
    """Implements peerpedia_core.protocols.storage.ReviewContentStorage."""

    def __init__(self, articles_dir: Path):
        self._articles_dir = Path(articles_dir)

    def _review_dir(self, article_id: ArticleId, reviewer_id: UserId) -> Path:
        return self._articles_dir / article_id.id / "reviews" / reviewer_id.id

    def _stage_and_commit(self, article_id: ArticleId, message: str) -> Version:
        """git add -A && git commit, return HEAD hash."""
        rp = self._articles_dir / article_id.id
        repo = git.Repo(rp)
        repo.git.add(A=True)
        repo.index.commit(message)
        return Version(id=repo.head.commit.hexsha)

    def create(self, article_id: ArticleId, reviewer_id: UserId) -> Version:
        rd = self._review_dir(article_id, reviewer_id)
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "scores.json").write_text("{}")
        (rd / "threads").mkdir(exist_ok=True)
        return self._stage_and_commit(article_id, f"[review-init] {reviewer_id.id}")

    def write_review(self, article_id: ArticleId, write: ReviewWrite) -> Version:
        rd = self._review_dir(article_id, write.reviewer_id)
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "scores.json").write_text(
            json.dumps(dict(write.scores.dimensions), ensure_ascii=False),
        )
        if write.content:
            (rd / "threads").mkdir(exist_ok=True)
            n = len(list((rd / "threads").glob("*.md"))) + 1
            (rd / "threads" / f"{n:03d}.md").write_text(write.content)
        marker = write.commit.message if write.commit else "[review]"
        return self._stage_and_commit(article_id, f"{marker} {write.reviewer_id.id}")

    def read(self, article_id: ArticleId, reviewer_id: UserId) -> str | None:
        sj = self._review_dir(article_id, reviewer_id) / "scores.json"
        return sj.read_text() if sj.is_file() else None

    def update(self, article_id: ArticleId, reviewer_id: UserId, scores: str) -> Version:
        rd = self._review_dir(article_id, reviewer_id)
        rd.mkdir(parents=True, exist_ok=True)
        (rd / "scores.json").write_text(scores)
        return self._stage_and_commit(article_id, f"[review-update] {reviewer_id.id}")

    def delete(self, article_id: ArticleId, reviewer_id: UserId) -> Version:
        rd = self._review_dir(article_id, reviewer_id)
        if rd.exists():
            shutil.rmtree(rd)
        return self._stage_and_commit(article_id, f"[review-delete] {reviewer_id.id}")

    def append_thread_entry(
        self, article_id: ArticleId, reviewer_id: UserId,
        content: str, marker: str,
    ) -> Version:
        rd = self._review_dir(article_id, reviewer_id)
        (rd / "threads").mkdir(parents=True, exist_ok=True)
        n = len(list((rd / "threads").glob("*.md"))) + 1
        (rd / "threads" / f"{n:03d}.md").write_text(content)
        return self._stage_and_commit(article_id, f"{marker} {reviewer_id.id}")

    def read_thread(self, article_id: ArticleId, reviewer_id: UserId) -> list[str]:
        td = self._review_dir(article_id, reviewer_id) / "threads"
        if not td.is_dir():
            return []
        return [f.read_text() for f in sorted(td.glob("*.md"), key=lambda p: p.stem)]

    def list_reviewers(self, article_id: ArticleId) -> list[UserId]:
        rd = self._articles_dir / article_id.id / "reviews"
        if not rd.is_dir():
            return []
        return [UserId(id=d.name) for d in rd.iterdir() if d.is_dir()]
