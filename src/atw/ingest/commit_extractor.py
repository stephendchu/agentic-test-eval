"""Mine the labeled eval set from git history.

We keep commits that change BOTH production code and test code, where the test
diff *adds at least one test function* (excludes docs/format/refactor/dep-bump
churn). The human-authored test diff is the **hidden ground truth**. Only
commits after the model's training cutoff are kept (contamination control).

Authors are stored as an anonymized hash — we rank artifacts, not people.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import git

from atw.config import CFG, COMMITS, RepoSpec
from atw.ingest.clone import get_repo

TEST_DIRS = {"tests", "test"}
MAX_PATCH_CHARS = 20_000  # per-file cap to keep records sane


# --- pure classification helpers (unit-tested, no git needed) ----------------
def is_test_path(path: str) -> bool:
    p = path.replace("\\", "/")
    parts = p.split("/")
    name = parts[-1]
    if not name.endswith(".py"):
        return False
    if name == "conftest.py":
        return True
    if name.startswith("test_") or name.endswith("_test.py"):
        return True
    return any(part in TEST_DIRS for part in parts[:-1])


def is_prod_py(path: str) -> bool:
    p = path.replace("\\", "/")
    name = p.split("/")[-1]
    if not name.endswith(".py"):
        return False
    if is_test_path(p):
        return False
    if name == "setup.py":  # packaging, not behavior
        return False
    return True


def added_test_functions(test_diff: str) -> int:
    """Count test functions added (def test... on a '+' line)."""
    count = 0
    for line in test_diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            stripped = line[1:].lstrip()
            if stripped.startswith("def test") or stripped.startswith("async def test"):
                count += 1
    return count


def _anon(author: git.Actor) -> str:
    raw = (author.email or author.name or "").strip().lower().encode()
    return hashlib.sha1(raw).hexdigest()[:12]


def _patch_text(d: git.Diff) -> str:
    raw = d.diff
    if isinstance(raw, bytes):
        text = raw.decode("utf-8", "replace")
    else:
        text = raw or ""
    return text[:MAX_PATCH_CHARS]


# --- the record --------------------------------------------------------------
@dataclass
class CommitRecord:
    repo: str
    sha: str
    parent_sha: str  # pre-change snapshot to check out
    date: str
    author_hash: str
    subject: str
    prod_files: list[str]
    test_files: list[str]
    prod_diff: str  # what the change did (input to the agent)
    test_diff: str  # the maintainer's test = HIDDEN ground truth
    added_test_functions: int


def extract(
    repo_spec: RepoSpec = CFG.repo,
    after: str = CFG.post_cutoff_after,
    limit: int = CFG.n_commits_full,
    max_scan: int = 20_000,
    out: Path = COMMITS,
) -> list[CommitRecord]:
    repo = get_repo(repo_spec)
    cutoff = datetime.fromisoformat(after).replace(tzinfo=timezone.utc)
    out.mkdir(parents=True, exist_ok=True)

    records: list[CommitRecord] = []
    scanned = 0
    # `since` bounds the walk to post-cutoff commits at the git level.
    for commit in repo.iter_commits(since=after):
        if len(records) >= limit or scanned >= max_scan:
            break
        scanned += 1
        if commit.committed_datetime < cutoff:  # defensive
            continue
        if len(commit.parents) != 1:  # skip merges for clean single-parent diffs
            continue

        parent = commit.parents[0]
        prod_files: list[str] = []
        test_files: list[str] = []
        prod_chunks: list[str] = []
        test_chunks: list[str] = []
        for d in parent.diff(commit, create_patch=True):
            path = d.b_path or d.a_path
            if not path:
                continue
            if is_test_path(path):
                test_files.append(path)
                test_chunks.append(f"--- {path}\n{_patch_text(d)}")
            elif is_prod_py(path):
                prod_files.append(path)
                prod_chunks.append(f"--- {path}\n{_patch_text(d)}")

        if not prod_files or not test_files:
            continue
        test_diff = "\n".join(test_chunks)
        n_added = added_test_functions(test_diff)
        if n_added < 1:  # exclude refactor/format/dep-bump test churn
            continue

        rec = CommitRecord(
            repo=repo_spec.name,
            sha=commit.hexsha,
            parent_sha=parent.hexsha,
            date=commit.committed_datetime.isoformat(),
            author_hash=_anon(commit.author),
            subject=commit.message.splitlines()[0][:200] if commit.message else "",
            prod_files=prod_files,
            test_files=test_files,
            prod_diff="\n".join(prod_chunks),
            test_diff=test_diff,
            added_test_functions=n_added,
        )
        records.append(rec)
        (out / f"{rec.sha}.json").write_text(json.dumps(asdict(rec), indent=2))

    index = [
        {
            "sha": r.sha,
            "date": r.date,
            "author_hash": r.author_hash,
            "subject": r.subject,
            "prod_files": r.prod_files,
            "test_files": r.test_files,
            "added_test_functions": r.added_test_functions,
        }
        for r in records
    ]
    (out / "index.json").write_text(json.dumps(index, indent=2))
    return records
