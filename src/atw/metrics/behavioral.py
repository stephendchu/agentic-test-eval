"""Behavioral judge — blinded, position-randomized pairwise preference.

Given the production change and two candidate tests, an LLM judge picks which
better *verifies the behavior the change introduces* (coverage + meaningful
assertions + review-acceptability), ignoring superficial style. This is the
discriminative maintainer-intent signal the structural metric (now ceiling-bound)
can't carry alone.

Bias controls: candidate order is randomized per call (position bias); the judge
sees no arm labels (blinding). For the final run, set both_orders=True and/or a
judge model independent of the generator to bound self-preference bias.
"""

from __future__ import annotations

import json
import re

import anthropic

from atw.agent.loop import _ALL_KNOWN_TOOLS, MCP_TOOLS

# Conserve subscription quota with sonnet; use opus for the final run (stronger
# judgment + independence from a sonnet generator).
JUDGE_MODEL = "claude-sonnet-4-6"
_JUDGE_BLOCK = _ALL_KNOWN_TOOLS + MCP_TOOLS  # the judge reasons over text, no tools

JUDGE_PROMPT = """A production code change was made:

<diff>
{diff}
</diff>

Two candidate pytest tests were written for this change. Decide which candidate \
BETTER verifies the behavior the change introduces or fixes — coverage of the \
new/changed behavior, meaningful assertions, and whether a maintainer would \
accept it in review. Ignore superficial style; judge behavioral value.

<test_1>
{t1}
</test_1>

<test_2>
{t2}
</test_2>

Respond with ONLY JSON: {{"winner": 1 or 2 (or 0 for a genuine tie), "reason": "<one sentence>"}}"""


def _map_winner(pos: int, swapped: bool) -> str:
    """Map the judge's position pick back to arm A/B, undoing the random swap."""
    if pos == 1:
        return "B" if swapped else "A"
    if pos == 2:
        return "A" if swapped else "B"
    return "tie"


def _extract_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return {}
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return {}


_SDK = None


def _sdk() -> "anthropic.Anthropic":
    global _SDK
    if _SDK is None:
        _SDK = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY (loaded from .env)
    return _SDK


def _claude_json(prompt: str, model: str, timeout: int = 180) -> dict | None:
    """Single-shot text call via the Anthropic API (definitive API billing — no
    subscription throttle; `claude -p` ignores the key and uses the logged-in
    subscription). Returns a dict shaped like the old claude-p json output."""
    try:
        msg = _sdk().messages.create(
            model=model, max_tokens=8000, timeout=timeout,
            messages=[{"role": "user", "content": prompt}],
        )
    except anthropic.RateLimitError:
        return {"_timeout": True}
    except anthropic.APIError:
        return None
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    return {"result": text, "is_error": msg.stop_reason == "error", "total_cost_usd": None}


def judge_pairwise(diff: str, test_a: str, test_b: str, rng, model: str = JUDGE_MODEL,
                   max_chars: int = 4000) -> dict:
    """Compare test_a (arm A) vs test_b (arm B). Returns winner in {'A','B','tie'}."""
    swapped = rng.random() < 0.5
    t1, t2 = (test_b, test_a) if swapped else (test_a, test_b)
    prompt = JUDGE_PROMPT.format(diff=diff[:6000], t1=t1[:max_chars], t2=t2[:max_chars])
    data = _claude_json(prompt, model)
    if data is None:
        return {"ok": False, "error": "no json from judge"}
    if data.get("_timeout"):
        return {"ok": False, "rate_limited": True, "reset_hint": "timeout (likely throttled)"}
    result = data.get("result", "") or ""
    if "session limit" in result.lower() or "usage limit" in result.lower():
        return {"ok": False, "rate_limited": True, "reset_hint": result.strip()[:200]}
    ans = _extract_json(result)
    return {
        "ok": True,
        "winner": _map_winner(ans.get("winner"), swapped),
        "reason": ans.get("reason", ""),
        "swapped": swapped,
        "cost_usd_equiv": data.get("total_cost_usd"),
    }
