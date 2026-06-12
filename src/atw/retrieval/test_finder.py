"""find_related_tests — the core Treatment query.

Given the production files a change touches, return the existing tests most
worth learning from: ranked by (historical association strength) x (artifact
quality). This is what makes A3 different from naive similarity RAG (A2).
"""

from __future__ import annotations

import ast
from pathlib import Path

from atw.config import REPOS
from atw.graph.test_to_code import RepoGraph
from atw.retrieval.quality import QualityScorer


def prod_files_from_diff(prod_diff: str) -> list[str]:
    """Our stored prod_diff prefixes each file patch with '--- <path>'."""
    return [ln[4:].strip() for ln in prod_diff.splitlines() if ln.startswith("--- ")]


def test_function_names(src: str, limit: int = 12) -> list[str]:
    names: list[str] = []
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return names
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            names.append(node.name)
            if len(names) >= limit:
                break
    return names


def find_related_tests(
    changed_files: list[str],
    graph: RepoGraph,
    scorer: QualityScorer,
    k: int = 5,
    root: Path | None = None,
    source_k: int = 2,
    source_max_chars: int = 4500,
) -> list[dict]:
    """Ranked related tests. For the top `source_k`, hand back the actual test
    SOURCE (quality-ranked, ready-to-adapt) — value the agent's own grep can't
    cheaply produce — not just pointers."""
    root = root or (REPOS / graph.repo)
    agg: dict[str, float] = {}
    for prod in changed_files:
        for t, assoc in graph.related_tests(prod).items():
            agg[t] = agg.get(t, 0.0) + assoc

    ranked = []
    for t, assoc in agg.items():
        q = scorer.score(t)
        final = assoc * (0.5 + q)  # quality reweights association
        ranked.append((t, final, assoc, q))
    ranked.sort(key=lambda x: x[1], reverse=True)

    results = []
    sources_emitted = 0
    for t, final, assoc, q in ranked[:k]:
        file_path = root / t
        exists = file_path.exists()
        try:
            src = file_path.read_text(encoding="utf-8", errors="replace") if exists else ""
        except OSError:
            src = ""
            exists = False

        entry: dict = {
            "path": t,
            "score": round(final, 4),
            "quality": q,
            "exists": exists,
            "test_functions": test_function_names(src),
        }
        if not exists:
            # Returning the path is fair (historical knowledge is the tool's thesis);
            # content must not flow — that would be ground-truth leakage in v2.
            entry["note"] = "file not present in this working tree (known from repository history)"
        elif sources_emitted < source_k:
            entry["source"] = src[:source_max_chars]
            sources_emitted += 1

        results.append(entry)
    return results
