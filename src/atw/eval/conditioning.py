"""Run experiment B (V vs C single-shot generation) over a commit slice.

Saves each condition as results/<exp>/<sha>/{V,C}.json (so the conformity eval
can score them with arms=("V","C")). Resumable; returns status for the driver.
"""

from __future__ import annotations

from datetime import datetime

from atw.config import RESULTS
from atw.eval.run_experiment import _full_record, _read, _save, _settled, select_commits
from atw.generate.conditioned import generate


def run(conditions=("V", "C"), n: int = 12, exp_id: str | None = None) -> dict:
    exp_id = exp_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = RESULTS / exp_id
    outdir.mkdir(parents=True, exist_ok=True)
    commits = select_commits(n)
    print(f"conditioning {exp_id}: {len(commits)} commits x {list(conditions)} -> {outdir}")

    for c in commits:
        sha = c["sha"]
        rec = _full_record(sha)
        for cond in conditions:
            if _settled(outdir, sha, cond):
                continue
            prev = _read(outdir, sha, cond)
            res = generate(rec, cond)
            if res.get("rate_limited"):
                print(f"  RATE LIMITED at {sha[:8]}/{cond}")
                return {"exp_id": exp_id, "rate_limited": True,
                        "reset_hint": res.get("reset_hint", ""), "complete": False}
            res["attempts"] = (prev.get("attempts", 0) if prev else 0) + 1
            _save(outdir, sha, cond, res)
            print(f"  {sha[:8]} {cond}: ok={res.get('ok')} attempt={res['attempts']} "
                  f"${res.get('cost_usd_equiv')}")
    complete = all(_settled(outdir, c["sha"], k) for c in commits for k in conditions)
    print(f"conditioning pass done (complete={complete}): {exp_id}")
    return {"exp_id": exp_id, "rate_limited": False, "complete": complete}
