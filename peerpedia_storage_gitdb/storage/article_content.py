"""Git-based ArticleContentStorage — versioned source of truth."""
from __future__ import annotations

import json
from pathlib import Path

import git

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.types.entities import (
    Article, ArticleDiff, ArticleId, ContentRef, HistoryEntry, Version,
)
from peerpedia_core.types.writes import ArticleWrite

from peerpedia_storage_gitdb.git.guards import require_article_repo
from peerpedia_storage_gitdb.git.ops import (
    commit_article,
    delete_article_repo,
    get_commit_history,
    get_diff_between,
    get_head_hash,
    init_article_repo,
    read_article_source,
)


class GitArticleContentStorage:
    """Implements peerpedia_core.protocols.storage.ArticleContentStorage."""

    def __init__(self, articles_dir: Path):
        self._articles_dir = Path(articles_dir)
        self._fmt_to_ext = {"markdown": "md", "typst": "typ"}

    def repo_path(self, key: ArticleId) -> Path:
        return self._articles_dir / key.id

    # ── Creation ──

    def create(self, key: ArticleId, fmt: str) -> Version:
        rp = self.repo_path(key)
        init_article_repo(rp)
        return Version(id=get_head_hash(rp))

    # ── Read ──

    def read(self, key: ArticleId) -> ContentRef:
        rp = require_article_repo(self._articles_dir, key.id)
        return ContentRef(ref=str(rp))

    def read_body(self, ref: ContentRef) -> str:
        rp = Path(ref.ref)
        source = read_article_source(rp)
        if source is None:
            raise NotFoundError(
                "Article source not found",
                resource_type="article_source", resource_id=ref.ref,
            )
        content, _fmt = source
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                return parts[2].lstrip("\n")
        return content

    # ── Write ──

    def write_article(self, key: ArticleId, write: ArticleWrite) -> Version:
        rp = self.repo_path(key)
        require_article_repo(self._articles_dir, key.id)
        ext = self._fmt_to_ext.get(write.article.format or "markdown", "md")
        fm = _build_frontmatter(write.article)
        source_path = rp / f"article.{ext}"
        source_path.write_text(fm + write.content)
        msg = write.commit.message if write.commit else "update"
        author = write.commit.user.name if write.commit else "PeerPedia"
        email = write.commit.user.id.id + "@peerpedia" if write.commit else "noreply@peerpedia"
        signer = write.commit.signer if write.commit else None
        return Version(id=commit_article(
            rp, message=msg, author_name=author, author_email=email, signer=signer,
        ))

    def update(self, key: ArticleId, content: str) -> Version:
        """Body-only write — preserve existing frontmatter, replace body."""
        rp = self.repo_path(key)
        require_article_repo(self._articles_dir, key.id)
        ext = self._fmt_to_ext.get("markdown", "md")
        source_path = rp / f"article.{ext}"

        # Preserve frontmatter if present
        existing = source_path.read_text() if source_path.is_file() else ""
        if existing.startswith("---"):
            parts = existing.split("---", 2)
            if len(parts) >= 3:
                body = f"---{parts[1]}---\n{content}"
                source_path.write_text(body)
                return Version(id=commit_article(rp, message="update", author_name="PeerPedia"))

        source_path.write_text(content)
        return Version(id=commit_article(rp, message="update", author_name="PeerPedia"))

    def delete(self, key: ArticleId) -> Version:
        rp = self.repo_path(key)
        head = get_head_hash(rp)
        delete_article_repo(rp)
        return Version(id=head)

    # ── Bundle (P2P sync) ──

    def create_bundle(self, key: ArticleId, since: Version | None = None) -> bytes:
        rp = self.repo_path(key)
        require_article_repo(self._articles_dir, key.id)
        repo = git.Repo(rp)
        rev_range = f"{since.id}..HEAD" if since else "HEAD"
        proc = repo.git.bundle("create", "-", rev_range, as_process=True)
        stdout, _stderr = proc.communicate()
        return stdout

    def ingest_bundle(self, key: ArticleId, data: bytes) -> Version:
        rp = self.repo_path(key)
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".bundle", delete=False) as f:
            f.write(data)
            f.flush()
            f.close()
            try:
                repo = git.Repo(rp)
                try:
                    repo.git.bundle("verify", f.name)
                except git.GitCommandError as e:
                    raise ValueError(f"Invalid bundle: {e}") from e
                repo.git.fetch(str(f.name))
                return Version(id=get_head_hash(rp))
            finally:
                repo.close()
                self._unlink_temp(f.name)

    def _unlink_temp(self, path: str) -> None:
        try:
            Path(path).unlink(missing_ok=True)
        except (OSError, PermissionError):
            pass

    # ── History & Diff ──

    def history(self, key: ArticleId, since: Version | None = None) -> list[HistoryEntry]:
        rp = self.repo_path(key)
        return get_commit_history(rp, since_hash=since.id if since else None)

    def diff(self, key: ArticleId, a: Version, b: Version) -> ArticleDiff:
        rp = self.repo_path(key)
        return ArticleDiff(version_a=a, version_b=b, content_diff=get_diff_between(rp, a.id, b.id))


def _build_frontmatter(article: Article) -> str:
    """Build JSON-compatible frontmatter from an Article entity.

    Uses ``json.dumps`` so values round-trip cleanly through
    ``_merge_frontmatter`` without fragile ``repr()`` hacks.
    """
    lines = ["---"]
    lines.append(f"title: {json.dumps(article.title, ensure_ascii=False)}")
    lines.append(f"status: {json.dumps(article.status, ensure_ascii=False)}")
    if article.authors:
        lines.append(f"authors: {json.dumps(list(article.authors), ensure_ascii=False)}")
    if article.abstract:
        lines.append(f"abstract: {json.dumps(article.abstract, ensure_ascii=False)}")
    if article.keywords:
        lines.append(f"keywords: {json.dumps(list(article.keywords), ensure_ascii=False)}")
    lines.append("---\n")
    return "\n".join(lines)
