"""find_helpers — surface the pytest fixtures/helpers available near a change.

Derived from the repo's own conftest.py files (and their fixtures), ranked by
directory proximity to the target. Repo-agnostic: it reads whatever fixtures the
repo actually defines.
"""

from __future__ import annotations

import ast
from pathlib import Path

from atw.config import REPOS
from atw.graph.test_to_code import RepoGraph
from atw.ingest.commit_extractor import is_prod_py


def _decorator_name(dec: ast.expr) -> str | None:
    if isinstance(dec, ast.Call):
        dec = dec.func
    if isinstance(dec, ast.Attribute):
        return dec.attr
    if isinstance(dec, ast.Name):
        return dec.id
    return None


def fixtures_in(src: str) -> list[tuple[str, list[str]]]:
    out: list[tuple[str, list[str]]] = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return out
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if any(_decorator_name(d) == "fixture" for d in node.decorator_list):
                out.append((node.name, [a.arg for a in node.args.args]))
    return out


def find_helpers(
    reference_path: str,
    graph: RepoGraph,
    k: int = 10,
    root: Path | None = None,
) -> list[dict]:
    root = root or (REPOS / graph.repo)
    conftests = [f for f in graph.test_files if f.split("/")[-1] == "conftest.py"]

    # Anchor proximity on the *test-side* location. If given a production file,
    # map it to its related test files first (a prod path shares no leading
    # components with any tests/ conftest, so anchoring on it is meaningless).
    if is_prod_py(reference_path):
        related = sorted(graph.related_tests(reference_path).items(), key=lambda x: -x[1])
        anchors = [t for t, _ in related[:5]] or [reference_path]
    else:
        anchors = [reference_path]

    # pytest applies a conftest.py only to tests UNDER its directory. So a
    # conftest is relevant iff its dir is an ancestor of an anchor test path.
    # Rank relevant conftests deepest-first (most specific fixtures win); fall
    # back to the shallowest conftests (e.g. tests/conftest.py) if none match.
    def conftest_dir(cf: str) -> str:
        return cf.rsplit("/", 1)[0] if "/" in cf else ""

    def is_ancestor(d: str) -> bool:
        return any(a == d or a.startswith(d + "/") for a in anchors)

    relevant = sorted(
        (cf for cf in conftests if is_ancestor(conftest_dir(cf))),
        key=lambda cf: conftest_dir(cf).count("/"),
        reverse=True,
    )
    # Fallback only to repo-global conftests (depth <= 1, e.g. tests/conftest.py)
    # — never deep, non-applicable ones like tests/functional/auth/conftest.py.
    fallback = sorted(
        (cf for cf in conftests if conftest_dir(cf).count("/") <= 1),
        key=lambda cf: conftest_dir(cf).count("/"),
    )
    ordered = relevant + [cf for cf in fallback if cf not in relevant]

    results: list[dict] = []
    for cf in ordered:
        try:
            src = (root / cf).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name, params in fixtures_in(src):
            results.append({"name": name, "kind": "fixture", "file": cf, "params": params})
            if len(results) >= k:
                return results
    return results
