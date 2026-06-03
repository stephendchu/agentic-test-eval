"""Repo-style alignment — the automated proxy for Maintainer-Intent Alignment.

Compares a generated test to the maintainer's actual test on structural,
judge-free features (imports, fixtures, naming, structure, assertion style).
This is the cheap structural component; the human-validated alignment study
(docs/taste-study.md) is the gold standard it will be calibrated against.
"""

from __future__ import annotations

import ast


def _features(code: str) -> dict:
    f = {
        "imports": set(), "test_names": [], "fixtures": set(),
        "parametrize": False, "raises": False, "class_based": False,
        "plain_asserts": 0, "self_asserts": 0,
    }
    try:
        tree = ast.parse(code)
    except (SyntaxError, ValueError):
        return f
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            f["imports"].update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                f["imports"].add(node.module.split(".")[0])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test"):
                f["test_names"].append(node.name)
                f["fixtures"].update(a.arg for a in node.args.args if a.arg != "self")
            for dec in node.decorator_list:
                if "parametrize" in ast.unparse(dec):
                    f["parametrize"] = True
        elif isinstance(node, ast.ClassDef) and node.name.startswith("Test"):
            f["class_based"] = True
        elif isinstance(node, ast.Assert):
            f["plain_asserts"] += 1
        elif isinstance(node, ast.Attribute) and node.attr.startswith("assert"):
            f["self_asserts"] += 1
        elif isinstance(node, ast.Call) and "raises" in ast.unparse(node.func):
            f["raises"] = True
    return f


def _jaccard(a, b) -> float:
    a, b = set(a), set(b)
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b) if (a | b) else 0.0


def _precision(gen, truth) -> float:
    """Of what the generated test uses, how much is consistent with the maintainer?

    Ground truth is the maintainer's WHOLE test file (many tests). A focused
    generated test legitimately omits imports/fixtures other tests in the file
    need, so Jaccard (which penalizes those omissions) is biased against focus.
    Precision asks only "are the generated test's choices correct?" — not "did it
    reproduce the whole file?". Documented metric correction (2026-05-31).
    """
    gen, truth = set(gen), set(truth)
    if not gen:
        return 1.0 if not truth else 0.0
    return len(gen & truth) / len(gen)


def _dominant_assert(f: dict) -> str:
    return "self" if f["self_asserts"] > f["plain_asserts"] else "plain"


WEIGHTS = {"imports": 0.25, "fixtures": 0.20, "name_style": 0.15,
           "structure": 0.20, "assert_style": 0.20}


def alignment_score(generated: str, ground_truth: str) -> tuple[float, dict]:
    """0..100 structural alignment of a generated test to the maintainer's test."""
    g, t = _features(generated), _features(ground_truth)
    comps = {
        # precision, not Jaccard: don't penalize a focused test for omitting
        # whole-file imports/fixtures it doesn't need (see _precision).
        "imports": _precision(g["imports"], t["imports"]),
        "fixtures": _precision(g["fixtures"], t["fixtures"]),
        "name_style": (
            sum(n.startswith("test_") for n in g["test_names"]) / len(g["test_names"])
            if g["test_names"] else 0.0
        ),
        "structure": sum(
            g[b] == t[b] for b in ("parametrize", "raises", "class_based")
        ) / 3,
        "assert_style": 1.0 if _dominant_assert(g) == _dominant_assert(t) else 0.0,
    }
    score = sum(comps[k] * WEIGHTS[k] for k in WEIGHTS) * 100
    return round(score, 1), {k: round(v, 3) for k, v in comps.items()}
