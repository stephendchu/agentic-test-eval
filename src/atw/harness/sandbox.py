"""Materialize the repo at a specific commit via a detached git worktree.

Each arm explores the **pre-change** snapshot (the commit's parent), so it never
sees the maintainer's test (ground truth) or the post-change production code.
Worktrees keep HEAD (and our prebuilt graph) undisturbed.

v2 protocol additions:
- delete_paths: test files deleted from the worktree before the agent runs,
  making test-location/convention/fixture discovery a real retrieval problem.
- strip_git: unlinks the .git pointer file, fully severing the shared object DB
  so the agent cannot git-show the deleted content back (Bug B fix).
Both options are applied identically to both arms.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import git

from atw.config import CFG, REPOS, RepoSpec


class Worktree:
    def __init__(
        self,
        sha: str,
        repo: RepoSpec = CFG.repo,
        delete_paths: list[str] | None = None,
        strip_git: bool = False,
    ):
        self.repo_path = REPOS / repo.name
        self.sha = sha
        self.delete_paths = delete_paths or []
        self.strip_git = strip_git
        self.path: Path | None = None
        self.deleted_existing: list[str] = []  # subset of delete_paths that existed at parent

    def __enter__(self) -> "Worktree":
        self.path = Path(tempfile.mkdtemp(prefix=f"atw-wt-{self.sha[:8]}-"))
        git.Repo(self.repo_path).git.worktree("add", "--detach", str(self.path), self.sha)

        for rel in self.delete_paths:
            target = self.path / rel
            if target.exists():
                target.unlink()
                self.deleted_existing.append(rel)

        if self.strip_git:
            git_ptr = self.path / ".git"
            if git_ptr.exists():
                git_ptr.unlink()

        return self

    def __exit__(self, *exc) -> None:
        repo = git.Repo(self.repo_path)
        try:
            repo.git.worktree("remove", "--force", str(self.path))
        except git.GitCommandError:
            if self.path:
                shutil.rmtree(self.path, ignore_errors=True)
        try:
            repo.git.worktree("prune")
        except git.GitCommandError:
            pass
