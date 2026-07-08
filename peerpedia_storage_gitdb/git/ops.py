# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: AGPL-3.0

"""Git operations — read and write.

Read: source, history, diff.  Write: init, commit, delete.
Write calls are used by lifecycle actions, not called directly.
"""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path

import git

from peerpedia_core.crypto import SigningKey
from peerpedia_core.types.entities import HistoryEntry, User, Version

ARTICLE_EXTENSIONS = ("md", "typ")
_EXT_TO_FORMAT = {"md": "markdown", "typ": "typst"}
_FORMAT_TO_EXT = {"markdown": "md", "typst": "typ"}

_ARTICLE_GITIGNORE = "__pycache__/\n*.pyc\n.DS_Store\n*.tmp\n*.swp\n"


def article_format_to_ext(fmt: str) -> str:
    return _FORMAT_TO_EXT.get(fmt, "md")

def article_ext_to_format(ext: str) -> str:
    return _EXT_TO_FORMAT.get(ext, "markdown")

def article_filename(ext: str) -> str:
    return f"article.{ext}"


# ── Init / Delete ──────────────────────────────────────────────────────────

def init_article_repo(repo_path: Path) -> None:
    repo_path.mkdir(parents=True, exist_ok=True)
    repo = git.Repo.init(repo_path, initial_branch="main")
    (repo_path / "reviews").mkdir(exist_ok=True)
    (repo_path / ".gitignore").write_text(_ARTICLE_GITIGNORE)
    if not repo.head.is_valid():
        repo.git.add(A=True)
        repo.git.commit(m="Init article repo", author="PeerPedia <noreply@peerpedia>", allow_empty=True)

def delete_article_repo(repo_path: Path) -> None:
    if repo_path.exists():
        rmtree_force(repo_path)

def rmtree_force(path: Path) -> None:
    """Remove *path* with retries for transient OS errors (Windows)."""
    import gc, time
    def _onerror(func, p, exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    for i in range(3):
        try:
            shutil.rmtree(str(path), onerror=_onerror)
            return
        except (OSError, PermissionError):
            if i < 2:
                time.sleep(0.05 * (i + 1))
    gc.collect()
    shutil.rmtree(str(path), onerror=_onerror)


# ── Commit ─────────────────────────────────────────────────────────────────

def require_on_main(repo: git.Repo) -> None:
    """Raise RuntimeError if HEAD is detached or not on refs/heads/main.

    Article repos use a single-mainline model — every git operation
    expects HEAD to point to ``refs/heads/main``.
    """
    if not repo.head.is_valid():
        return
    if repo.head.is_detached:
        raise RuntimeError(
            "HEAD is detached — expected refs/heads/main; "
            "article repos use a single-mainline model"
        )
    if repo.head.reference.path != "refs/heads/main":
        raise RuntimeError(
            f"HEAD is on {repo.head.reference.path}, expected refs/heads/main — "
            "article repos use a single-mainline model"
        )


def commit_article(
    repo_path: Path, message: str, author_name: str,
    author_email: str = "noreply@peerpedia",
    signer: SigningKey | None = None,
    allow_empty: bool = False,
) -> str:
    repo = git.Repo(repo_path)
    require_on_main(repo)
    repo.git.add(A=True)

    if signer is not None:
        signature = signer.sign(
            f"commit:{repo.head.commit.hexsha if repo.head.is_valid() else 'init'}:{message}".encode())
        pubkey = signer.public_key()
        author = f"{author_name} <{pubkey.fingerprint()}@peerpedia>"
        full_message = f"{message}\n\nPubkey: {pubkey.fingerprint()}\nSignature: {signature.hex()}"
    else:
        author = f"{author_name} <{author_email}>"
        full_message = message

    repo.index.write()
    repo.git.commit(m=full_message, author=author, allow_empty=allow_empty)
    return repo.head.commit.hexsha


# ── Read source ───────────────────────────────────────────────────────────


def resolve_article_format(repo_path: Path) -> str:
    for ext in ARTICLE_EXTENSIONS:
        if (repo_path / article_filename(ext)).is_file():
            return article_ext_to_format(ext)
    return "markdown"


def read_article_source(repo_path: Path) -> tuple[str, str] | None:
    """Return ``(content, format)`` or None."""
    if not repo_path.is_dir():
        return None
    fmt = resolve_article_format(repo_path)
    f = repo_path / article_filename(article_format_to_ext(fmt))
    if f.is_file():
        return f.read_text(), fmt
    return None


# ── History ───────────────────────────────────────────────────────────────


def get_commit_history(
    repo_path: Path,
    max_count: int = 50,
    since_hash: str | None = None,
) -> list[HistoryEntry]:
    """Return commit history as typed entries.  Raises ValueError if no repo/commits."""
    try:
        repo = git.Repo(repo_path)
    except git.exc.NoSuchPathError:
        raise ValueError("REPO_NOT_FOUND") from None
    require_on_main(repo)
    if not repo.head.is_valid():
        raise ValueError("REPO_NO_COMMITS")

    rev = f"{since_hash}..HEAD" if since_hash else None
    return [
        HistoryEntry(
            version=Version(id=c.hexsha),
            message=c.message.strip(),
            user=User(
                id=(c.author.email or "").strip().split("@")[0] if c.author and c.author.email else "",
                name=str(c.author) if c.author else "",
            ),
            timestamp=c.committed_datetime,
        )
        for c in repo.iter_commits(rev=rev, max_count=max_count)
    ]


def get_head_hash(repo_path: Path) -> str:
    commits = get_commit_history(repo_path, max_count=1)
    return commits[0].version.id


# ── Diff ──────────────────────────────────────────────────────────────────


def get_diff_between(repo_path: Path, hash_a: str, hash_b: str) -> str:
    """Return unified diff text between two commits."""
    repo = git.Repo(repo_path)
    c_a = repo.commit(hash_a)
    c_b = repo.commit(hash_b)
    parts: list[str] = []
    for d in c_a.diff(c_b, create_patch=True):
        patch = d.diff
        if patch is None:
            continue
        parts.append(patch.decode("utf-8", errors="replace") if isinstance(patch, bytes) else str(patch))
    return "\n".join(parts)
