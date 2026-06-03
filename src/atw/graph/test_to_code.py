"""Test-to-code mapping, derived entirely from the repo itself.

Two repo-native signals (nothing hardcoded to any repo):
  1. **imports** — which production modules a test file imports (AST).
  2. **co-modification** — which (prod, test) files maintainers change together
     in the same commit (the historical engineering-intent signal).

Both are combined later (retrieval/) and weighted by artifact quality.
"""

from __future__ import annotations

import ast
import json
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from atw.ingest.commit_extractor import is_prod_py, is_test_path


def _modkey(path: str) -> str:
    """posix path minus .py, e.g. core/dbt/parser/manifest.py -> core/dbt/parser/manifest"""
    p = path.replace("\\", "/")
    return p[:-3] if p.endswith(".py") else p


def parse_imports(source: str) -> list[str]:
    """Return dotted module names imported by a source file (absolute imports)."""
    out: list[str] = []
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")  # repo files may have invalid escapes
            tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return out
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.level == 0:  # absolute only (relative is repo-internal noise)
                out.append(node.module)
    return out


@dataclass
class RepoGraph:
    repo: str
    prod_files: list[str] = field(default_factory=list)
    test_files: list[str] = field(default_factory=list)
    # prod_file -> [test_files that import it]
    imports_inverse: dict[str, list[str]] = field(default_factory=dict)
    # prod_file -> {test_file: co-change count}
    comod: dict[str, dict[str, int]] = field(default_factory=dict)
    # file -> {"count": int, "first": iso, "last": iso}
    file_stats: dict[str, dict] = field(default_factory=dict)

    # --- queries -------------------------------------------------------------
    def related_tests(self, prod_file: str) -> dict[str, float]:
        """Candidate tests for a prod file -> raw association strength."""
        scores: dict[str, float] = {}
        for t in self.imports_inverse.get(prod_file, []):
            scores[t] = scores.get(t, 0.0) + 2.0  # import = strong, direct signal
        for t, c in self.comod.get(prod_file, {}).items():
            scores[t] = scores.get(t, 0.0) + float(c)  # historical co-change
        return scores

    # --- persistence ---------------------------------------------------------
    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.__dict__, indent=2))

    @classmethod
    def load(cls, path: Path) -> "RepoGraph":
        return cls(**json.loads(Path(path).read_text()))


def build_import_index(prod_files: list[str]) -> dict[str, list[str]]:
    """last-path-segment -> [prod modkeys] for fast suffix resolution."""
    index: dict[str, list[str]] = {}
    for f in prod_files:
        key = _modkey(f)
        last = key.split("/")[-1]
        index.setdefault(last, []).append(key)
    return index


def resolve_import(dotted: str, index: dict[str, list[str]], prod_by_modkey: dict[str, str]) -> list[str]:
    """Map an imported dotted module to repo prod file(s) by path-suffix match."""
    needle = dotted.replace(".", "/")
    last = needle.split("/")[-1]
    out: list[str] = []
    for modkey in index.get(last, []):
        if modkey == needle or modkey.endswith("/" + needle):
            out.append(prod_by_modkey[modkey])
    return out
