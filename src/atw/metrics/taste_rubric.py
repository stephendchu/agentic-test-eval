"""A 5-axis taste rubric for test quality.

Reference-free, per-draft, blind grading on the axes that separate good tests
from bad ones — more granular than a single pairwise "which is better?". Each
axis 0 / 0.5 / 1; per-draft total 0-5. Run per arm/condition to see WHERE each
wins (e.g. A3 may win drop_in_ready but lose helper_fit).
"""

from __future__ import annotations

from atw.metrics.behavioral import _claude_json, _extract_json

JUDGE_MODEL = "claude-sonnet-4-6"
AXES = ["helper_fit", "no_handwaving", "low_noise", "conciseness", "drop_in_ready"]

TASTE_PROMPT = """You are a senior engineer reviewing a pytest test draft written \
for the code change below. Grade ONLY the test, on five axes, each scored 0, 0.5, \
or 1. Judge blind — do not assume it is AI- or human-written.

<change>
{diff}
</change>

<test>
{test}
</test>

Axes:
- helper_fit: the fixtures/helpers it uses are real AND the right ones for THIS \
scenario (1); real but a suboptimal choice (0.5); wrong or missing (0).
- no_handwaving: no TODO/placeholder punts on the hard parts (1); minor (0.5); \
punts on the substance (0).
- low_noise: no leftover setUp/tearDown boilerplate, redundant assertions, or \
unused imports (1); some (0.5); noisy (0).
- conciseness: tight signal-to-noise, no repetition (1); acceptable (0.5); \
bloated (0).
- drop_in_ready: would run and merge essentially as-is (1); needs a minor \
reviewer pass (0.5); needs real rework (0).

Respond with ONLY JSON: {{"helper_fit":0/0.5/1, "no_handwaving":0/0.5/1, \
"low_noise":0/0.5/1, "conciseness":0/0.5/1, "drop_in_ready":0/0.5/1, "reason":"<one line>"}}"""


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
