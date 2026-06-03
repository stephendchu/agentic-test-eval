"""Clone / open the target repository. One full clone (we need history)."""

from __future__ import annotations

from pathlib import Path

import git

from atw.config import CFG, REPOS, RepoSpec


def ensure_clone(repo: RepoSpec = CFG.repo, dest_root: Path = REPOS) -> Path:
    """Clone the repo if not already present; return its working-tree path."""
    dest = dest_root / repo.name
    dest_root.mkdir(parents=True, exist_ok=True)
    if (dest / ".git").exists():
        return dest
    print(f"Cloning {repo.url} -> {dest} (full history; this can take a minute)...")
    git.Repo.clone_from(repo.url, dest)
    return dest


def get_repo(repo: RepoSpec = CFG.repo, dest_root: Path = REPOS) -> git.Repo:
    return git.Repo(ensure_clone(repo, dest_root))
