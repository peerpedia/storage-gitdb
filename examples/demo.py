#!/usr/bin/env python3
"""PeerPedia end-to-end demo -- real SQLite + git backends.

Usage:
    pip install peerpedia-storage-gitdb
    python examples/demo.py

This script creates temporary directories, exercises the full article lifecycle,
inspects git and SQLite to prove data integrity, and demonstrates bundle sync.
"""
from __future__ import annotations

import json
import shutil
import sqlite3
import subprocess
import tempfile
from pathlib import Path

from peerpedia_core import Peerpedia
from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.types import Article, Review, ReviewId, Scores, User, UserId
from peerpedia_storage_gitdb import build_storage, build_user_storage, GitDBLifecycle


def main():
    workdir = Path(tempfile.mkdtemp(prefix="peerpedia-demo-"))
    articles_dir = workdir / "articles"
    db_path = workdir / "peerpedia.db"
    db_url = f"sqlite:///{db_path}"
    _git_setup()

    print("=" * 60)
    print("PeerPedia end-to-end demo")
    print("=" * 60)
    print(f"Workdir: {workdir}\n")

    # -- 1. Set up --------------------------------------------------------
    print("[1] Building storage...")
    storage = build_storage(str(articles_dir), db_url)
    users = build_user_storage(db_url)
    lifecycle = GitDBLifecycle(storage)
    pp = Peerpedia(storage=storage, lifecycle=lifecycle, user_storage=users)

    # -- 2. Create a user -------------------------------------------------
    print("[2] Creating user...")
    uid = users.create()
    users.update(uid, User(id=uid, name="Alice", public_key="ab" * 32))
    print(f"    User ID: {uid.id}, name: Alice\n")

    # -- 3. Create an article ---------------------------------------------
    print("[3] Creating article...")
    aid = pp.create()
    print(f"    Article ID: {aid.id}, status: draft\n")

    # -- 4. Revise --------------------------------------------------------
    print("[4] Revising article...")
    article = Article(
        id=aid, title="The Future of P2P Review", status="draft",
        authors=("Alice",), abstract="We propose a decentralized review model.",
    )
    pp.revise(aid, content="# Introduction\n\nThis paper explores...", article=article)
    print(f"    Title: {article.title}")
    print(f"    Authors: {article.authors}\n")

    # -- 5. Read back from meta cache -------------------------------------
    print("[5] Reading back from meta cache...")
    meta = pp.read_meta(aid)
    assert meta.title == "The Future of P2P Review"
    assert "Alice" in meta.authors
    assert meta.status == "draft"
    print(f"    Title: {meta.title}")
    print(f"    Authors: {meta.authors}")
    print(f"    Status: {meta.status}\n")

    # -- 6. Publish -------------------------------------------------------
    print("[6] Publishing article...")
    pub_article = Article(
        id=aid, title=meta.title, status="published",
        authors=meta.authors, abstract=meta.abstract,
    )
    pp.publish(aid, article=pub_article)
    assert pp.read_meta(aid).status == "published"
    print("    Status: published\n")

    # -- 7. Review --------------------------------------------------------
    print("[7] Submitting review...")
    review = Review(
        id=ReviewId(id="r1"), article_id=aid, reviewer_id=uid,
        scores=Scores(dimensions={"originality": 4.5, "rigor": 4.0, "impact": 3.5}),
    )
    scores_json = json.dumps({"originality": 4.5, "rigor": 4.0, "impact": 3.5})
    pp.review(aid, review=review, scores_json=scores_json)
    reviews = storage.review_meta.list(aid)
    print(f"    Reviews: {len(reviews)}")
    print(f"    Reviewer: {reviews[0].reviewer_id.id}")
    print(f"    Scores: {dict(reviews[0].scores.dimensions)}\n")

    # -- 8. Inspect git repo ----------------------------------------------
    print("[8] Inspecting git repo...")
    repo_path = articles_dir / aid.id
    git_log = subprocess.run(
        ["git", "-C", str(repo_path), "log", "--oneline"],
        capture_output=True, text=True,
    ).stdout.strip()
    print(f"    Commits:\n{_indent(git_log, 8)}")

    source_path = repo_path / "article.md"
    source_text = source_path.read_text()
    print(f"    Source file ({source_path.name}):")
    for line in source_text.split("\n")[:10]:
        print(f"        {line}")
    print(f"        ...\n")

    # Check review scores in git
    reviews_dir = repo_path / "reviews" / uid.id
    scores_path = reviews_dir / "scores.json"
    if scores_path.exists():
        scores_git = json.loads(scores_path.read_text())
        print(f"    Git scores.json: {scores_git}\n")

    # -- 9. Inspect SQLite ------------------------------------------------
    print("[9] Inspecting SQLite cache...")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT id, title, status, format, authors FROM articles"
    ).fetchone()
    assert row["id"] == aid.id
    authors = json.loads(row["authors"])
    print(f"    articles: id={row['id']}, title={row['title']}, "
          f"status={row['status']}, authors={authors}")
    review_row = conn.execute(
        "SELECT id, article_id, reviewer_id, scores FROM reviews"
    ).fetchone()
    print(f"    reviews:  article={review_row['article_id']}, "
          f"reviewer={review_row['reviewer_id']}, "
          f"scores={review_row['scores']}")
    conn.close()
    print()

    # -- 10. Bundle sync --------------------------------------------------
    print("[10] Demonstrating P2P bundle sync...")
    bundle = storage.content.create_bundle(aid)
    print(f"    Bundle size: {len(bundle)} bytes")

    # Create second article and pull the first one's bundle into it
    aid2 = pp.create()
    storage.content.create(aid2, "markdown")
    v = storage.content.ingest_bundle(aid2, bundle)
    print(f"    Ingested into {aid2.id}: HEAD={v.id[:8]}\n")

    # -- 11. History and diff ---------------------------------------------
    print("[11] History and diff...")
    history = storage.content.history(aid)
    print(f"    History entries: {len(history)}")
    print(f"    Latest commit: {history[0].message.split(chr(10))[0]}")
    print(f"    Author: {history[0].user.name}\n")

    # -- 12. Delete -------------------------------------------------------
    print("[12] Deleting article...")
    pp.delete(aid)
    try:
        pp.read_meta(aid)
        print("    ERROR: article still exists!")
        sys.exit(1)
    except NotFoundError:
        print("    Article deleted: meta cache confirms removal\n")

    # -- Done -------------------------------------------------------------
    print("[13] Cleaning up...")
    dispose_engine(db_url)
    shutil.rmtree(workdir)
    print("    Temp directory removed")
    print("\n=== All checks passed ===")


def _git_setup():
    """Ensure git identity is configured for CI runners."""
    import os
    os.environ.setdefault("GIT_AUTHOR_NAME", "PeerPedia")
    os.environ.setdefault("GIT_AUTHOR_EMAIL", "noreply@peerpedia")
    os.environ.setdefault("GIT_COMMITTER_NAME", "PeerPedia")
    os.environ.setdefault("GIT_COMMITTER_EMAIL", "noreply@peerpedia")


def dispose_engine(db_url: str):
    """Dispose engine to release SQLite WAL lock."""
    try:
        from peerpedia_storage_gitdb.db.engine import dispose_engine as _dispose
        _dispose(db_url)
    except Exception:
        pass


def _indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(f"{prefix}{line}" for line in text.split("\n"))


if __name__ == "__main__":
    import sys
    main()
