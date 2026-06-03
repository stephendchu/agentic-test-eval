"""Run the behavioral pairwise judge over a finished slice (resumable)."""

from __future__ import annotations

import json
import random
from pathlib import Path

from atw.config import COMMITS, RESULTS
from atw.metrics.behavioral import JUDGE_MODEL, judge_pairwise


def _load(outdir: Path, sha: str, arm: str) -> dict | None:
    f = outdir / sha / f"{arm}.json"
    return json.loads(f.read_text()) if f.exists() else None


def run_judge(exp_id: str, arm_a: str = "A1", arm_b: str = "A3",
              seed: int = 0, model: str = JUDGE_MODEL) -> dict:
    outdir = RESULTS / exp_id
    rng = random.Random(seed)
    rows = []
    for shadir in sorted(p for p in outdir.iterdir() if p.is_dir()):
        sha = shadir.name
        jf = shadir / "behavioral.json"
        if jf.exists() and json.loads(jf.read_text()).get("ok"):
            rows.append(json.loads(jf.read_text()))
            continue  # resume: already judged
        a, b = _load(outdir, sha, arm_a), _load(outdir, sha, arm_b)
        if not (a and a.get("ok") and b and b.get("ok")):
            continue
        rec = json.loads((COMMITS / f"{sha}.json").read_text())
        res = judge_pairwise(rec["prod_diff"], a["test_code"], b["test_code"], rng, model)
        res.update({"sha": sha[:8], "arm_a": arm_a, "arm_b": arm_b})
        if res.get("rate_limited"):
            print(f"  RATE LIMITED judging {sha[:8]}")
            return {"rate_limited": True, "reset_hint": res.get("reset_hint", ""),
                    "complete": False}
        jf.write_text(json.dumps(res, indent=2))
        rows.append(res)
        print(f"  {sha[:8]}: prefer={res.get('winner')}  ({res.get('reason','')[:64]})")

    ok = [r for r in rows if r.get("ok")]
    b_wins = sum(r["winner"] == "B" for r in ok)
    a_wins = sum(r["winner"] == "A" for r in ok)
    ties = sum(r["winner"] == "tie" for r in ok)
    n = len(ok)
    # complete = every commit with both arms present has been judged
    eligible = [p.name for p in outdir.iterdir() if p.is_dir()
                and _load(outdir, p.name, arm_a) and _load(outdir, p.name, arm_b)
                and _load(outdir, p.name, arm_a).get("ok") and _load(outdir, p.name, arm_b).get("ok")]
    complete = all((outdir / sha / "behavioral.json").exists() for sha in eligible)
    print(f"\n{arm_b} preferred {b_wins}/{n} | {arm_a} {a_wins} | ties {ties}  "
          f"({arm_b} win-rate {round(b_wins / n, 3) if n else None})")
    return {"rate_limited": False, "reset_hint": "", "complete": complete,
            "n": n, f"{arm_b}_preferred": b_wins, f"{arm_a}_preferred": a_wins, "ties": ties}
