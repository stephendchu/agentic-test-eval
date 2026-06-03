"""Build (and persist) the RepoGraph from a cloned repo.

One pass over the working tree for imports, one bounded pass over history for
co-modification + per-file lifetime stats. Repo-agnostic.
"""

from __future__ import annotations

from pathlib import Path

import git

from atw.config import CFG, GRAPH, REPOS, RepoSpec
from atw.graph.test_to_code import (
    RepoGraph,
    build_import_index,
    parse_imports,
    resolve_import,
    _modkey,
)
from atw.ingest.clone import get_repo
from atw.ingest.commit_extractor import is_prod_py, is_test_path


def _tracked_files(repo: git.Repo) -> list[str]:
    return repo.git.ls_files().splitlines()


def _iter_history(repo: git.Repo, max_history: int):
    """Yield (iso_date, [changed_paths]) per commit via a single fast git-log call.

    Far faster than per-commit gitpython diffs. \\x01 marks each commit header;
    \\x00 separates hash from committer-date so file paths can't be confused with
    headers.
    """
    raw = repo.git.log(
        "--no-merges",
        "--name-only",
        f"--max-count={max_history}",
        "--format=%x01%H%x00%cI",
    )
    date: str | None = None
    files: list[str] = []
    for line in raw.splitlines():
        if line.startswith("\x01"):
            if date is not None:
                yield date, files
            _, date = line[1:].split("\x00", 1)
            files = []
        elif line.strip():
            files.append(line)
    if date is not None:
        yield date, files


def build_graph(
    repo_spec: RepoSpec = CFG.repo,
    max_history: int = 3000,
    out: Path = GRAPH,
) -> RepoGraph:
    repo = get_repo(repo_spec)
    root = REPOS / repo_spec.name
    files = _tracked_files(repo)
    prod_files = [f for f in files if is_prod_py(f)]
    test_files = [f for f in files if is_test_path(f)]

    g = RepoGraph(repo=repo_spec.name, prod_files=prod_files, test_files=test_files)

    # --- imports: test_file imports -> prod_file (inverted to prod -> tests) --
    index = build_import_index(prod_files)
    prod_by_modkey = {_modkey(f): f for f in prod_files}
    inverse: dict[str, set[str]] = {}
    for tf in test_files:
        try:
            src = (root / tf).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for dotted in parse_imports(src):
            for prod in resolve_import(dotted, index, prod_by_modkey):
                inverse.setdefault(prod, set()).add(tf)
    g.imports_inverse = {p: sorted(ts) for p, ts in inverse.items()}

    # --- one history pass: co-modification + per-file lifetime stats ----------
    comod: dict[str, dict[str, int]] = {}
    stats: dict[str, dict] = {}
    for date, changed in _iter_history(repo, max_history):
        if not changed:
            continue
        for p in changed:
            s = stats.setdefault(p, {"count": 0, "first": date, "last": date})
            s["count"] += 1
            if date < s["first"]:
                s["first"] = date
            if date > s["last"]:
                s["last"] = date
        prods = [p for p in changed if is_prod_py(p)]
        tests = [p for p in changed if is_test_path(p)]
        for p in prods:
            bucket = comod.setdefault(p, {})
            for t in tests:
                bucket[t] = bucket.get(t, 0) + 1
    g.comod = comod
    g.file_stats = stats

    g.save(out / "graph.json")
    return g


def load_graph(out: Path = GRAPH) -> RepoGraph:
    return RepoGraph.load(out / "graph.json")
