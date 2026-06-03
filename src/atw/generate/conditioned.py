"""Experiment B — does conditioning on real repo examples make tests more native?

Single-shot generation (no agentic loop, no tools → cheap), two conditions on the
same commit:
  V (vanilla)     : diff -> test, no examples
  C (conditioned) : diff + injected REAL repo example tests -> test
Scored afterward with the human-free indistinguishability eval. Tests the
adoption mechanism: can we *move* nativeness by handing over native examples?
"""

from __future__ import annotations

import ast

from atw.agent.loop import _extract_code
from atw.metrics.behavioral import _claude_json
from atw.mcp.tools import default_toolbox
from atw.metrics.resolvability import _repo_top_packages
from atw.retrieval.findtests import findtests

GEN_MODEL = "claude-sonnet-4-6"

_VANILLA = """Write the pytest test(s) a maintainer would add for this production \
change.

<diff>
{diff}
</diff>

Output ONLY the final test file content in a single ```python code block."""

_CONDITIONED = """Write the pytest test(s) a maintainer would add for this \
production change, matching THIS repository's conventions — naming, fixtures, \
helpers, imports, structure.

<diff>
{diff}
</diff>

Here are real, high-quality tests from this repository. Match their style and \
reuse their fixtures/helpers:

<examples>
{examples}
</examples>

Output ONLY the final test file content in a single ```python code block."""


def _examples(rec: dict, k: int = 2) -> str:
    """C condition: examples picked by OUR co-modification retrieval."""
    res = default_toolbox().find_related_tests(rec["prod_files"], k=5)["results"]
    blocks = []
    for r in res:
        if r.get("source"):
            blocks.append(f"# from {r['path']}\n{r['source']}")
        if len(blocks) >= k:
            break
    return "\n\n".join(blocks)


def _findtests_examples(rec: dict, k: int = 3) -> str:
    """F condition: examples picked by the intent-keyword findtests algorithm
    (intent = commit message)."""
    tb = default_toolbox()
    res = findtests(rec["subject"], tb.graph, k=k, root=tb.root)
    return "\n\n".join(f"# from {x['path']}\n{x['source']}" for x in res)


_CATALOG = """Write the pytest test(s) a maintainer would add for this production \
change. Use ONLY the real fixtures and symbols listed below — do NOT invent \
helpers, fixtures, or imports.

<diff>
{diff}
</diff>

<available_fixtures_and_symbols>
{catalog}
</available_fixtures_and_symbols>

Output ONLY the final test file content in a single ```python code block."""


def _file_to_module(path: str, top_pkgs: set[str]) -> str:
    parts = (path[:-3] if path.endswith(".py") else path).split("/")
    for i, p in enumerate(parts):
        if p in top_pkgs:
            return ".".join(parts[i:])
    return parts[-1]


def _helper_catalog(rec: dict) -> str:
    """H condition: a helper-catalog approach — enumerate the REAL fixtures and
    public symbols available for this change, so the agent can't fabricate."""
    tb = default_toolbox()
    top = _repo_top_packages(tb.graph.prod_files)
    fixtures = tb.find_helpers(rec["prod_files"][0], k=20)["results"] if rec["prod_files"] else []
    fx = sorted({f"{f['name']}({', '.join(f.get('params', []))})" for f in fixtures})
    syms = []
    for pf in rec["prod_files"]:
        try:
            src = (tb.root / pf).read_text(encoding="utf-8", errors="replace")
            tree = ast.parse(src)
        except (OSError, SyntaxError, ValueError):
            continue
        mod = _file_to_module(pf, top)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) \
                    and not node.name.startswith("_"):
                syms.append(f"{node.name}  (from {mod})")
    return ("Available pytest fixtures:\n" + "\n".join(f"  - {x}" for x in fx[:25])
            + "\n\nReal public symbols from the changed code (use exact names/imports):\n"
            + "\n".join(f"  - {x}" for x in syms[:40]))


def generate(rec: dict, condition: str, model: str = GEN_MODEL) -> dict:
    if condition == "V":
        prompt = _VANILLA.format(diff=rec["prod_diff"][:6000])
    elif condition == "F":
        prompt = _CONDITIONED.format(diff=rec["prod_diff"][:6000],
                                     examples=_findtests_examples(rec))
    elif condition == "H":
        prompt = _CATALOG.format(diff=rec["prod_diff"][:6000], catalog=_helper_catalog(rec))
    else:  # C
        prompt = _CONDITIONED.format(diff=rec["prod_diff"][:6000], examples=_examples(rec))
    data = _claude_json(prompt, model)
    if data is None:
        return {"ok": False, "condition": condition, "error": "no json"}
    if data.get("_timeout"):
        return {"ok": False, "condition": condition, "rate_limited": True,
                "reset_hint": "timeout (likely throttled)"}
    result = data.get("result", "") or ""
    if "session limit" in result.lower() or "usage limit" in result.lower():
        return {"ok": False, "condition": condition, "rate_limited": True,
                "reset_hint": result.strip()[:200]}
    return {"ok": True, "condition": condition, "test_code": _extract_code(result),
            "cost_usd_equiv": data.get("total_cost_usd")}
