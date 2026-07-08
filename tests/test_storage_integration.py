"""Integration tests — uses real SQLite + Git backends."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from peerpedia_core.exceptions import NotFoundError
from peerpedia_core.protocols.lifecycle import Extra, execute
from peerpedia_core.types import (
    Article, ArticleId, Review, ReviewId, Scores, User, UserId, Version,
)
from peerpedia_core.types.queries import ArticleQuery

from peerpedia_storage_gitdb.factory import build_storage, build_user_storage
from peerpedia_storage_gitdb.lifecycle import GitDBLifecycle
from peerpedia_storage_gitdb.db.engine import dispose_engine


@pytest.fixture
def db_url():
    return "sqlite:///:memory:"


@pytest.fixture
def articles_dir(tmp_path):
    return str(tmp_path / "articles")


@pytest.fixture
def storage(articles_dir, db_url):
    s = build_storage(articles_dir, db_url)
    yield s
    dispose_engine(db_url)


@pytest.fixture
def lifecycle(storage):
    return GitDBLifecycle(storage)


@pytest.fixture
def user_storage(db_url):
    us = build_user_storage(db_url)
    yield us
    dispose_engine(db_url)


# ═══════════════════════════════════════════════════════════════════════════
# Article lifecycle
# ═══════════════════════════════════════════════════════════════════════════


def test_create_article(storage, lifecycle):
    """create → revise → publish → review → delete via real backends."""
    aid = execute("create", {}, None, lifecycle)
    article = Article(id=aid, title="Test Paper", status="draft", authors=("Alice",))
    execute("revise", {"content": "# Hello World", "article": article}, aid, lifecycle)

    meta = storage.meta.read(aid)
    assert meta.title == "Test Paper"
    assert meta.status == "draft"

    # Verify git — read body from content storage
    cref = storage.content.read(aid)
    body = storage.content.read_body(cref)
    assert "Hello World" in body

    # Publish
    pub_meta = Article(id=aid, title="Test Paper", status="published", authors=("Alice",))
    execute("publish", {"article": pub_meta}, aid, lifecycle)
    assert storage.meta.read(aid).status == "published"

    # Delete
    storage.delete_article(aid)
    with pytest.raises(NotFoundError):
        storage.meta.read(aid)


def test_review_lifecycle(storage, lifecycle):
    """Full review: create → revise → review."""
    aid = execute("create", {}, None, lifecycle)
    article = Article(id=aid, title="Review Test", status="draft", authors=("Bob",))
    execute("revise", {"content": "# My Paper", "article": article}, aid, lifecycle)

    # Publish first (needed for review in the lifecycle)
    pub_meta = Article(id=aid, title="Review Test", status="published", authors=("Bob",))
    execute("publish", {"article": pub_meta}, aid, lifecycle)

    # Review
    uid = UserId(id="reviewer-1")
    review = Review(
        id=ReviewId(id="r1"), article_id=aid, reviewer_id=uid,
        scores=Scores(dimensions={"clarity": 4.5, "rigor": 3.5}),
    )
    execute("review", {
        "review": review,
        "scores": json.dumps({"clarity": 4.5, "rigor": 3.5}),
    }, aid, lifecycle)

    # Read back from meta
    reviews = storage.review_meta.list(aid)
    assert len(reviews) == 1
    assert reviews[0].reviewer_id.id == "reviewer-1"

    # Read back from content
    rcontent = storage.review_content
    scores = rcontent.read(aid, uid)
    assert scores is not None
    assert json.loads(scores)["clarity"] == 4.5


# ═══════════════════════════════════════════════════════════════════════════
# Article query
# ═══════════════════════════════════════════════════════════════════════════


def test_article_query(storage, lifecycle):
    aids = []
    for i, title in enumerate(["Alpha", "Beta", "Gamma"]):
        aid = execute("create", {}, None, lifecycle)
        article = Article(id=aid, title=title, status="draft")
        execute("revise", {"content": f"# {title}", "article": article}, aid, lifecycle)
        aids.append(aid)

    all_articles = storage.meta.query()
    assert len(all_articles) == 3

    # Search
    result = storage.meta.query(ArticleQuery(search="Alpha"))
    assert len(result) == 1
    assert result[0].title == "Alpha"

    # Limit
    result = storage.meta.query(ArticleQuery(limit=2))
    assert len(result) == 2

    # Status filter
    result = storage.meta.query(ArticleQuery(statuses=frozenset({"draft"})))
    assert len(result) == 3

    result = storage.meta.query(ArticleQuery(statuses=frozenset({"published"})))
    assert len(result) == 0


# ═══════════════════════════════════════════════════════════════════════════
# User CRUD
# ═══════════════════════════════════════════════════════════════════════════


def test_user_crud(user_storage):
    uid = user_storage.create()
    assert isinstance(uid, UserId)

    user_storage.update(uid, User(id=uid, name="Alice", public_key="ab" * 32))
    user = user_storage.read(uid)
    assert user.name == "Alice"
    assert user.public_key == "ab" * 32

    # Search
    assert len(user_storage.search("Ali")) == 1
    assert len(user_storage.search("Bob")) == 0

    # Delete
    user_storage.delete(uid)
    with pytest.raises(NotFoundError):
        user_storage.read(uid)


# ═══════════════════════════════════════════════════════════════════════════
# Review content storage (scores + threads in git)
# ═══════════════════════════════════════════════════════════════════════════


def test_review_content_crud(articles_dir, db_url):
    """Direct tests on GitReviewContentStorage."""
    storage = build_storage(articles_dir, db_url)
    rcontent = storage.review_content
    aid = ArticleId(id="art-review-content")
    uid = UserId(id="bob")

    # Must init article repo first
    storage.content.create(aid, "markdown")

    # Write review
    rcontent.write_review(aid, type("Write", (), {
        "reviewer_id": uid, "content": "Great paper!",
        "scores": Scores(dimensions={"clarity": 5.0}),
        "commit": None, "scope": "",
    })())  # type: ignore

    assert rcontent.read(aid, uid) is not None
    thread = rcontent.read_thread(aid, uid)
    assert len(thread) >= 1

    # Append reply
    rcontent.append_thread_entry(aid, uid, "Thanks!", "[reply]")
    thread = rcontent.read_thread(aid, uid)
    assert len(thread) >= 2

    # list reviewers
    reviewers = rcontent.list_reviewers(aid)
    assert uid.id in [r.id for r in reviewers]

    dispose_engine(db_url)


# ═══════════════════════════════════════════════════════════════════════════
# Article encode/decode round-trip
# ═══════════════════════════════════════════════════════════════════════════


def test_article_encode_decode():
    a = Article(
        id=ArticleId(id="a1"), title="Test", status="draft",
        authors=("Alice",), abstract="An abstract.",
    )
    b = Article.decode(a.encode())
    assert b.title == a.title
    assert b.authors == a.authors
    assert b.abstract == a.abstract


# ═══════════════════════════════════════════════════════════════════════════
# Content storage direct (history, diff, bundle)
# ═══════════════════════════════════════════════════════════════════════════


def test_content_history_and_diff(articles_dir, db_url):
    storage = build_storage(articles_dir, db_url)
    content = storage.content
    aid = ArticleId(id="art-hist")

    v1 = content.create(aid, "markdown")
    v2 = content.update(aid, "# Version 2")

    history = content.history(aid)
    assert len(history) >= 1

    diff = content.diff(aid, v1, v2)
    assert diff.version_a.id == v1.id
    assert diff.version_b.id == v2.id

    dispose_engine(db_url)


def test_content_bundle_sync(articles_dir, db_url):
    storage = build_storage(articles_dir, db_url)
    content = storage.content
    aid = ArticleId(id="art-bundle")

    content.create(aid, "markdown")
    content.update(aid, "# Sync Test")

    bundle = content.create_bundle(aid)
    assert len(bundle) > 0

    # Ingest into same repo (simulates pull)
    v = content.ingest_bundle(aid, bundle)
    assert v.id is not None

    dispose_engine(db_url)
