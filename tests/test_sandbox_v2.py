"""Tests for v2 Worktree: deletion, git-stripping, and worktree prune."""

import subprocess
from pathlib import Path

import pytest
import git


def _make_repo(tmp_path: Path) -> tuple[git.Repo, str, str]:
    """Create a tiny repo with prod + test file, return (repo, parent_sha, commit_sha)."""
    repo = git.Repo.init(tmp_path)
    repo.config_writer().set_value("user", "name", "test").release()
    repo.config_writer().set_value("user", "email", "test@test.com").release()

    prod = tmp_path / "src" / "foo.py"
    prod.parent.mkdir()
    prod.write_text("def foo(): return 1\n")
    test = tmp_path / "tests" / "test_foo.py"
    test.parent.mkdir()
    test.write_text("from src.foo import foo\ndef test_foo(): assert foo() == 1\n")

    repo.index.add(["src/foo.py", "tests/test_foo.py"])
    parent = repo.index.commit("initial")

    prod.write_text("def foo(): return 2\n")
    repo.index.add(["src/foo.py"])
    commit = repo.index.commit("change foo")

    return repo, str(parent.hexsha), str(commit.hexsha)


def test_deletion_removes_test_file(tmp_path):
    from atw.harness.sandbox import Worktree
    from atw.config import RepoSpec

    repo, parent_sha, _ = _make_repo(tmp_path)
    spec = RepoSpec(name="test", url="")

    # Monkey-patch REPOS so Worktree finds our tmp repo
    import atw.harness.sandbox as sb
    orig_repos = sb.REPOS
    sb.REPOS = tmp_path.parent
    tmp_path.parent.joinpath("test").symlink_to(tmp_path)  # data/repos/test -> tmp

    try:
        wt = Worktree(parent_sha, repo=spec, delete_paths=["tests/test_foo.py"])
        with wt as w:
            assert not (w.path / "tests" / "test_foo.py").exists(), "test file should be deleted"
            assert "tests/test_foo.py" in wt.deleted_existing
            assert (w.path / "src" / "foo.py").exists(), "prod file should remain"
    finally:
        sb.REPOS = orig_repos
        link = tmp_path.parent / "test"
        if link.is_symlink():
            link.unlink()


def test_strip_git_severs_object_db(tmp_path):
    from atw.harness.sandbox import Worktree
    from atw.config import RepoSpec
    import atw.harness.sandbox as sb

    repo, parent_sha, _ = _make_repo(tmp_path)
    spec = RepoSpec(name="test2", url="")

    orig_repos = sb.REPOS
    sb.REPOS = tmp_path.parent
    tmp_path.parent.joinpath("test2").symlink_to(tmp_path)

    try:
        wt = Worktree(parent_sha, repo=spec, strip_git=True)
        with wt as w:
            assert not (w.path / ".git").exists(), ".git file should be removed"
            result = subprocess.run(
                ["git", "log", "--oneline"],
                cwd=str(w.path),
                capture_output=True, text=True,
            )
            assert result.returncode != 0, "git commands should fail after strip"
    finally:
        sb.REPOS = orig_repos
        link = tmp_path.parent / "test2"
        if link.is_symlink():
            link.unlink()


def test_nonexistent_delete_path_is_noop(tmp_path):
    from atw.harness.sandbox import Worktree
    from atw.config import RepoSpec
    import atw.harness.sandbox as sb

    repo, parent_sha, _ = _make_repo(tmp_path)
    spec = RepoSpec(name="test3", url="")

    orig_repos = sb.REPOS
    sb.REPOS = tmp_path.parent
    tmp_path.parent.joinpath("test3").symlink_to(tmp_path)

    try:
        wt = Worktree(parent_sha, repo=spec, delete_paths=["tests/does_not_exist.py"])
        with wt as w:
            assert wt.deleted_existing == [], "nonexistent file should not appear in deleted_existing"
    finally:
        sb.REPOS = orig_repos
        link = tmp_path.parent / "test3"
        if link.is_symlink():
            link.unlink()
