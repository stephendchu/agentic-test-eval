"""5-axis taste rubric for test quality (idiomatic / completeness / clarity /
robustness / drop-in readiness), each axis 0/1/2, per-draft total 0-10.

Reference-free, per-draft, blind grading. This is the SAME instrument across
every codebase (open-source and obfuscated), so taste scores are directly
comparable on one ruler — which is what makes the cross-codebase claim valid.
"""

from __future__ import annotations

from atw.metrics.behavioral import _claude_json, _extract_json

JUDGE_MODEL = "claude-sonnet-4-6"
AXES = ["idiomatic_match", "completeness", "clarity", "robustness", "drop_in_readiness"]

TASTE_PROMPT = """You are a senior engineer reviewing a pytest test draft written \
for the code change below. Grade ONLY the test, on five axes, each scored 0, 1, \
or 2. Judge blind — do not assume it is AI- or human-written.

<change>
{diff}
</change>

<test>
{test}
</test>

Axes (0/1/2):
- idiomatic_match: uses this repo's conventions — the right helpers, fixtures, \
decorators and patterns, matching neighboring tests (2); minor variance / a \
suboptimal-but-real choice (1); wrong, non-idiomatic, or invented (0).
- completeness: verifies the change including secondary assertions and effects \
(2); skips a secondary assertion (1); misses the substance of the change (0).
- clarity: clear intent, well-structured, readable (2); acceptable (1); \
confusing or disorganized (0).
- robustness: probes the implied edge cases of the change (2); under-probes some \
(1); happy-path only (0).
- drop_in_readiness: would merge as-is, no TODOs/placeholders (2); minor TODOs or \
platform-specific values to fill in (1); needs real rework (0).

Respond with ONLY JSON: {{"idiomatic_match":0/1/2, "completeness":0/1/2, \
"clarity":0/1/2, "robustness":0/1/2, "drop_in_readiness":0/1/2, "reason":"<one line>"}}"""


def taste_score(diff: str, test: str, model: str = JUDGE_MODEL) -> dict:
    data = _claude_json(TASTE_PROMPT.format(diff=diff[:5000], test=test[:5000]), model)
    if data is None:
        return {"ok": False, "error": "no json"}
    if data.get("_timeout"):
        return {"ok": False, "rate_limited": True, "reset_hint": "timeout (likely throttled)"}
    result = data.get("result", "") or ""
    if "session limit" in result.lower() or "usage limit" in result.lower():
        return {"ok": False, "rate_limited": True, "reset_hint": result.strip()[:200]}
    ans = _extract_json(result)
    axes = {a: ans.get(a) for a in AXES}
    vals = [v for v in axes.values() if isinstance(v, (int, float))]
    return {
        "ok": True,
        "axes": axes,
        "total": round(sum(vals), 2) if len(vals) == len(AXES) else None,
        "reason": ans.get("reason", ""),
        "cost_usd_equiv": data.get("total_cost_usd"),
    }
