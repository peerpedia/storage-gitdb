# peerpedia-storage-gitdb

[![PyPI](https://img.shields.io/pypi/v/peerpedia-storage-gitdb)](https://pypi.org/project/peerpedia-storage-gitdb/)
[![Python](https://img.shields.io/pypi/pyversions/peerpedia-storage-gitdb)](https://pypi.org/project/peerpedia-storage-gitdb/)

Git + SQLite implementation of [peerpedia-core](https://pypi.org/project/peerpedia-core/) storage protocols.

## What this is

Concrete backends that implement the seven storage protocols defined in
`peerpedia-core`.  Content lives in bare git repos (GitPython); metadata
lives in a SQLite cache (SQLAlchemy).  The cache is rebuilt from git
history via `reconcile_article()` — git is the source of truth.

## Quick start

```python
from peerpedia_core import Peerpedia
from peerpedia_storage_gitdb import build_storage, build_user_storage, GitDBLifecycle

storage = build_storage("/data/articles", "sqlite:///peerpedia.db")
users = build_user_storage("sqlite:///peerpedia.db")
lifecycle = GitDBLifecycle(storage)

pp = Peerpedia(storage=storage, lifecycle=lifecycle, user_storage=users)
aid = pp.create()
```

## Architecture

```
storage/
├── article_meta.py    ← SqlArticleMetaStorage    (ArticleMetaStorage)
├── article_content.py ← GitArticleContentStorage (ArticleContentStorage)
├── review_meta.py     ← SqlReviewMetaStorage     (ReviewMetaStorage)
├── review_content.py  ← GitReviewContentStorage  (ReviewContentStorage)
├── user.py            ← SqlUserStorage           (UserStorage)
└── article.py         ← GitDBArticleStorage      (ArticleStorage subclass)

db/
├── engine.py          ← SQLAlchemy engine + JSONType
└── models.py          ← ORM models (articles, reviews, users)

git/
├── ops.py             ← git init, commit, history, diff, bundle
└── guards.py          ← require_article_repo
```

## Requirements

- Python ≥ 3.11
- [peerpedia-core](https://pypi.org/project/peerpedia-core/) ≥ 0.2.0
- sqlalchemy ≥ 2.0
- gitpython ≥ 3.1

## License

AGPL-3.0 — see [LICENSE](LICENSE).
