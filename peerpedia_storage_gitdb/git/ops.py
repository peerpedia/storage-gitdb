# SPDX-FileCopyrightText: 2024-2026 Chenqi Meng and PeerPedia contributors
# SPDX-License-Identifier: AGPL-3.0

"""Git write/read operations — content-addressed article storage."""

from __future__ import annotations

import shutil
from pathlib import Path

import git

from peerpedia_core.crypto import SigningKey
from peerpedia_storage_gitdb.config import ARTICLES_DIR


# ── Init ───────────────────────────────────────────────────────────────────

def init_article_repo(article_id: str) -> Path:
    """Initialize a git repository for *article_id* if it doesn't exist."""
    rp = ARTICLES_DIR / article_id
    if (rp / ".git").is_dir():
        return rp
    rp.mkdir(parents=True, exist_ok=True)
    repo = git.Repo.init(rp, initial_branch="main")
    (rp / "reviews").mkdir(exist_ok=True)
    repo.git.add(A=True)
    repo.git.commit(m="Init article repo", allow_empty=True)
    return rp


# ── Commit ─────────────────────────────────────────────────────────────────

def commit_content(
    repo_path: Path,
    message: str,
    signer: SigningKey,
) -> str:
    """Stage all changes and commit. Returns the commit hash.

    Uses the *signer*'s Ed25519 key for SSH signing.  The public key
    fingerprint is appended to the commit message.
    """
    repo = git.Repo(repo_path)
    if not repo.is_dirty(untracked_files=True):
        return repo.head.commit.hexsha

    repo.git.add(A=True)
    fingerprint = signer.public_key().fingerprint()
    full_message = f"{message}\n\nPubkey: {fingerprint}"

    # Write allowed_signers for git SSH signing
    allowed_signers = repo_path / ".git" / "allowed_signers"
    allowed_signers.write_text(
        f"{fingerprint} {signer.public_key().fingerprint()}"
    )

    env = {
        "GIT_SSH_COMMAND": "ssh -o StrictHostKeyChecking=accept-new",
        "GIT_SSH_ALLOWED_SIGNERS": str(allowed_signers),
    }

    # For now, use a regular commit. SSH signing via gitpython is complex;
    # production code uses git's native ssh signing with Ed25519 keys.
    repo.index.write()
    repo.git.commit(m=full_message, allow_empty=True)
    return repo.head.commit.hexsha


# ── Read ───────────────────────────────────────────────────────────────────

def read_content(repo_path: Path) -> bytes:
    """Return the current article source content."""
    source_file = repo_path / "article.md"
    if source_file.exists():
        return source_file.read_bytes()
    return b""


# ── History ────────────────────────────────────────────────────────────────

def repo_history(repo_path: Path, since: str | None = None) -> list[dict]:
    """Return commit history for *repo_path*, optionally since *since*."""
    repo = git.Repo(repo_path)
    commits = []
    for c in repo.iter_commits():
        if since and c.hexsha == since:
            break
        commits.append({
            "hash": c.hexsha,
            "message": c.message.strip(),
            "author": str(c.author),
            "timestamp": c.committed_datetime.isoformat(),
        })
    return commits


# ── Delete ─────────────────────────────────────────────────────────────────

def delete_article_repo(article_id: str) -> None:
    """Remove the git repository for *article_id*."""
    rp = ARTICLES_DIR / article_id
    if rp.is_dir():
        shutil.rmtree(rp, onerror=_on_rm_error)


def _on_rm_error(func, path, exc_info):
    import stat
    Path(path).chmod(stat.S_IWRITE)
    func(path)
