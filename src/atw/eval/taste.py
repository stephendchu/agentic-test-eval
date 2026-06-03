"""Run the 5-axis taste rubric over a slice (resumable). Per-axis means per arm."""

from __future__ import annotations

import json
import statistics as st

from atw.config import RESULTS
from atw.eval.run_experiment import _full_record
from atw.metrics.taste_rubric import AXES, JUDGE_MODEL, taste_score


def run_taste(exp_id: str, arms=("A1", "A3"), model: str = JUDGE_MODEL) -> dict:
    outdir = RESULTS / exp_id
    agg = {a: {ax: [] for ax in AXES} | {"total": []} for a in arms}
    for shadir in sorted(p for p in outdir.iterdir() if p.is_dir()):
        sha = shadir.name
        rec = _full_record(sha)
        for arm in arms:
            tf = shadir / f"taste_{arm}.json"
            if tf.exists() and json.loads(tf.read_text()).get("ok"):
                r = json.loads(tf.read_text())
            else:
                af = shadir / f"{arm}.json"
                if not af.exists():
                    continue
                a = json.loads(af.read_text())
                if not (a.get("ok") and a.get("test_code")):
                    continue
                r = taste_score(rec["prod_diff"], a["test_code"], model)
                if r.get("rate_limited"):
                    print(f"  RATE LIMITED at {sha[:8]}/{arm}")
                    return {"rate_limited": True, "reset_hint": r.get("reset_hint", ""),
                            "complete": False}
                r.update({"sha": sha[:8], "arm": arm})
                tf.write_text(json.dumps(r, indent=2))
            if r.get("ok") and r.get("total") is not None:
                for ax in AXES:
                    if isinstance(r["axes"].get(ax), (int, float)):
                        agg[arm][ax].append(r["axes"][ax])
                agg[arm]["total"].append(r["total"])
                print(f"  {sha[:8]} {arm}: total={r['total']} {r['axes']}")

    print("\n=== taste rubric (per-axis mean 0-1; total 0-5) ===")
    out = {"complete": True}
    for a in arms:
        row = {ax: (round(st.mean(agg[a][ax]), 2) if agg[a][ax] else None) for ax in AXES}
        row["total"] = round(st.mean(agg[a]["total"]), 2) if agg[a]["total"] else None
        row["n"] = len(agg[a]["total"])
        out[a] = row
        print(f"  {a}: total={row['total']} (n={row['n']}) | "
              + "  ".join(f"{ax}={row[ax]}" for ax in AXES))
    return out
