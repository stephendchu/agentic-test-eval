"""Materialize the repo at a specific commit via a detached git worktree.

Each arm explores the **pre-change** snapshot (the commit's parent), so it never
sees the maintainer's test (ground truth) or the post-change production code.
Worktrees keep HEAD (and our prebuilt graph) undisturbed.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import git

from atw.config import CFG, REPOS, RepoSpec


class Worktree:
    def __init__(self, sha: str, repo: RepoSpec = CFG.repo):
        self.repo_path = REPOS / repo.name
        self.sha = sha
        self.path: Path | None = None

    def __enter__(self) -> Path:
        self.path = Path(tempfile.mkdtemp(prefix=f"atw-wt-{self.sha[:8]}-"))
        git.Repo(self.repo_path).git.worktree("add", "--detach", str(self.path), self.sha)
        return self.path

    def __exit__(self, *exc) -> None:
        try:
            git.Repo(self.repo_path).git.worktree("remove", "--force", str(self.path))
        except git.GitCommandError:
            if self.path:
                shutil.rmtree(self.path, ignore_errors=True)
