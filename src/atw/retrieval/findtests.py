"""Intent-keyword test retrieval — `findtests`.

Intent-keyword scoring (not co-modification): tokenize the intent, score every
test by keyword overlap with method name / token-bag / helper names, return the
top-k as "close working examples to adapt". This is the domain-agnostic core of
the algorithm — exactly the part that lets us test "is it the retrieval
algorithm or the domain that beats grep?".

Scoring:
  +3 if an intent token appears in the test method name
  +2 if it appears in the token bag (helper names + docstring)
  +2 if it appears in any helper name
Then drop score==0, sort by (-score, path), take top-k.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from atw.config import REPOS
from atw.graph.test_to_code import RepoGraph

_CAMEL = re.compile(r"[A-Z]?[a-z]+|[A-Z]+(?![a-z])|\d+")


def tokenize(text: str) -> set[str]:
    """camelCase + snake_case + words -> lowercase token set (matches prod)."""
    toks: set[str] = set()
    for chunk in re.split(r"[^A-Za-z0-9]+", text or ""):
        toks.update(m.group(0).lower() for m in _CAMEL.finditer(chunk))
    return {t for t in toks if len(t) > 1}


def _extract_tests(src: str) -> list[dict]:
    """Per test function: name, docstring, helper-ish calls, source slice."""
    out = []
    try:
        tree = ast.parse(src)
    except (SyntaxError, ValueError):
        return out
    lines = src.splitlines()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test"):
            doc = ast.get_docstring(node) or ""
            helpers = []
            for n in ast.walk(node):
                if isinstance(n, ast.Call):
                    f = n.func
                    if isinstance(f, ast.Attribute):
                        helpers.append(f.attr)
                    elif isinstance(f, ast.Name):
                        helpers.append(f.id)
            end = getattr(node, "end_lineno", node.lineno)
            out.append({
                "name": node.name,
                "doc": doc,
                "helpers": helpers,
                "source": "\n".join(lines[node.lineno - 1:end]),
            })
    return out


def _score(intent_tokens: set[str], t: dict) -> int:
    name_toks = tokenize(t["name"])
    bag = tokenize(" ".join(t["helpers"]) + " " + t["doc"])
    helper_toks = tokenize(" ".join(t["helpers"]))
    s = 0
    for tok in intent_tokens:
        if tok in name_toks:
            s += 3
        if tok in bag:
            s += 2
        if tok in helper_toks:
            s += 2
    return s


def findtests(intent: str, graph: RepoGraph, k: int = 3, root: Path | None = None,
              source_max_chars: int = 3500) -> list[dict]:
    """Top-k 'close working examples' for an intent string (e.g. commit message)."""
    root = root or (REPOS / graph.repo)
    itoks = tokenize(intent)
    scored = []
    for tf in graph.test_files:
        try:
            src = (root / tf).read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for t in _extract_tests(src):
            s = _score(itoks, t)
            if s > 0:
                scored.append((s, tf, t))
    scored.sort(key=lambda x: (-x[0], x[1], x[2]["name"]))
    return [
        {"path": tf, "score": s, "test": t["name"],
         "source": t["source"][:source_max_chars]}
        for s, tf, t in scored[:k]
    ]
