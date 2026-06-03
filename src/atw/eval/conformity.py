"""Run the indistinguishability taste eval over a slice (resumable).

Compares each arm's generated test to the maintainer's ACTUAL added test for that
change (scope-matched, from the diff). Reports per-arm distinguish-rate: how often
a blind judge correctly picks the real one. 0.5 = indistinguishable (most native).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from atw.config import COMMITS, RESULTS
from atw.metrics.conformity import JUDGE_MODEL, judge_distinguish


def _added_test_code(rec: dict) -> str:
    """The maintainer's added test lines for THIS change (scope-matched)."""
    return "\n".join(
        ln[1:] for ln in rec["test_diff"].splitlines()
        if ln.startswith("+") and not ln.startswith("+++")
    )


def run_conformity(exp_id: str, arms=("A1", "A3"), seed: int = 0,
                   model: str = JUDGE_MODEL) -> dict:
    outdir = RESULTS / exp_id
    rng = random.Random(seed)
    stats = {a: {"correct": 0, "n": 0} for a in arms}
    for shadir in sorted(p for p in outdir.iterdir() if p.is_dir()):
        sha = shadir.name
        merged = _added_test_code(json.loads((COMMITS / f"{sha}.json").read_text()))
        for arm in arms:
            cf = shadir / f"conformity_{arm}.json"
            if cf.exists() and json.loads(cf.read_text()).get("ok"):
                r = json.loads(cf.read_text())
            else:
                af = shadir / f"{arm}.json"
                if not af.exists():
                    continue
                a = json.loads(af.read_text())
                if not (a.get("ok") and a.get("test_code")):
                    continue
                r = judge_distinguish(merged, a["test_code"], rng, model)
                if r.get("rate_limited"):
                    print(f"  RATE LIMITED at {sha[:8]}/{arm}")
                    return {"rate_limited": True, "reset_hint": r.get("reset_hint", ""),
                            "complete": False}
                r.update({"sha": sha[:8], "arm": arm})
                cf.write_text(json.dumps(r, indent=2))
            if r.get("ok"):
                stats[arm]["correct"] += int(r["judge_correct"])
                stats[arm]["n"] += 1
                print(f"  {sha[:8]} {arm}: judge_correct={r['judge_correct']} "
                      f"(tell: {r.get('tell','')[:50]})")

    print("\n=== indistinguishability (distinguish-rate; 0.5 = most native) ===")
    out = {"complete": True}
    for a in arms:
        n, c = stats[a]["n"], stats[a]["correct"]
        rate = round(c / n, 3) if n else None
        out[a] = {"caught": c, "n": n, "distinguish_rate": rate}
        print(f"  {a}: judge caught {c}/{n}  ->  distinguish-rate {rate}")
    return out
