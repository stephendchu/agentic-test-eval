"""Resolvability — does the generated test reference REAL things in the repo?

A structural rubric: a draft is good if it
would *parse and resolve at runtime* — imports point at real modules, fixtures
map to real definitions. Reference-free and statically checkable (no maintainer
test, no execution needed). This is plausibly where semantic tools beat grep:
they surface REAL fixtures/tests, so the agent hallucinates fewer references.

Axes (dbt-core / generic pytest adaptation of the 5-axis rubric):
  - parse_ok        : the draft is even valid Python
  - imports_resolve : every repo-internal import resolves to a real module
  - fixtures_real   : every used fixture is a pytest builtin, repo-defined, or
                      locally defined (not hallucinated)
"""

from __future__ import annotations

import ast
from pathlib import Path

from atw.config import REPOS
from atw.graph.test_to_code import (
    RepoGraph,
    _modkey,
    build_import_index,
    resolve_import,
)
from atw.retrieval.helpers import fixtures_in

PYTEST_BUILTINS = {
    "self", "tmp_path", "tmpdir", "tmp_path_factory", "tmpdir_factory",
    "monkeypatch", "request", "capsys", "capfd", "capsysbinary", "capfdbinary",
    "caplog", "recwarn", "pytestconfig", "cache", "record_property",
    "record_testsuite_property", "doctest_namespace", "mocker", "freezer",
}


def _repo_top_packages(prod_files: list[str]) -> set[str]:
    """Top-level importable package names (a package dir whose parent isn't one)."""
    init_dirs = {f.rsplit("/", 1)[0] for f in prod_files if f.endswith("/__init__.py")}
    pkgs = set()
    for d in init_dirs:
        parent = d.rsplit("/", 1)[0] if "/" in d else ""
        if parent not in init_dirs:
            pkgs.add(d.split("/")[-1])
    return pkgs


def _repo_fixtures(graph: RepoGraph, root: Path) -> set[str]:
    names: set[str] = set()
    for f in graph.test_files:
        if f.split("/")[-1] == "conftest.py":
            try:
                src = (root / f).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            names.update(n for n, _ in fixtures_in(src))
    return names


def resolvability_score(code: str, graph: RepoGraph, root: Path | None = None,
                        _cache: dict | None = None) -> dict:
    root = root or (REPOS / graph.repo)
    top_pkgs = _repo_top_packages(graph.prod_files)
    repo_fix = _repo_fixtures(graph, root)
    index = build_import_index(graph.prod_files)
    pbm = {_modkey(f): f for f in graph.prod_files}

    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return {"parse_ok": False, "imports_resolve": 0.0, "fixtures_real": 0.0, "total": 0.0}

    internal_total = internal_ok = 0
    used_fixtures: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            if node.module.split(".")[0] in top_pkgs:
                internal_total += 1
                internal_ok += bool(resolve_import(node.module, index, pbm))
        elif isinstance(node, ast.Import):
            for a in node.names:
                if a.name.split(".")[0] in top_pkgs:
                    internal_total += 1
                    internal_ok += bool(resolve_import(a.name, index, pbm))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            used_fixtures += [a.arg for a in node.args.args if a.arg != "self"]

    local_fix = {n for n, _ in fixtures_in(code)}
    fx_total = fx_real = 0
    for fx in used_fixtures:
        if fx in PYTEST_BUILTINS:
            continue
        fx_total += 1
        fx_real += fx in repo_fix or fx in local_fix

    imports_resolve = 1.0 if internal_total == 0 else internal_ok / internal_total
    fixtures_real = 1.0 if fx_total == 0 else fx_real / fx_total
    total = round((imports_resolve + fixtures_real) / 2 * 100, 1)
    return {
        "parse_ok": True,
        "imports_resolve": round(imports_resolve, 3),
        "fixtures_real": round(fixtures_real, 3),
        "total": total,
        "internal_imports": internal_total,
        "used_fixtures": fx_total,
    }
