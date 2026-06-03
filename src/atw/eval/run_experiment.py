"""Run arms over a commit slice, persist results, resume after rate limits.

Each (commit, arm) result is one JSON under results/<exp_id>/<sha>/<arm>.json so a
rate-limited run can be re-invoked with the same --exp-id to pick up where it
stopped. Free structural alignment is computed inline; execution-based
regression detection is added by the harness later.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from atw.config import COMMITS, RESULTS
from atw.agent.loop import run_arm
from atw.ingest.clone import get_repo
from atw.metrics.style import alignment_score


def select_commits(n: int, max_prod_files: int = 2) -> list[dict]:
    """Focused commits (small change footprint) give clean per-commit attribution."""
    idx = json.loads((COMMITS / "index.json").read_text())
    focused = [r for r in idx if len(r["prod_files"]) <= max_prod_files]
    focused.sort(key=lambda r: r["added_test_functions"])
    return focused[:n]


def _full_record(sha: str) -> dict:
    return json.loads((COMMITS / f"{sha}.json").read_text())


def ground_truth_code(record: dict) -> str:
    """The maintainer's FULL test file(s) at the commit (complete, with imports).

    Falls back to diff-added lines only if a file can't be read.
    """
    repo = get_repo()
    parts = []
    for path in record["test_files"]:
        try:
            parts.append(repo.git.show(f"{record['sha']}:{path}"))
        except Exception:
            pass
    if parts:
        return "\n\n".join(parts)
    return "\n".join(
        ln[1:] for ln in record["test_diff"].splitlines()
        if ln.startswith("+") and not ln.startswith("+++")
    )


def rescore(exp_id: str) -> list[dict]:
    """Recompute alignment for a finished/partial run against full ground truth."""
    outdir = RESULTS / exp_id
    rows = []
    for shadir in sorted(p for p in outdir.iterdir() if p.is_dir()):
        rec = _full_record(shadir.name)
        truth = ground_truth_code(rec)
        row = {"sha": shadir.name[:8]}
        for armf in shadir.glob("*.json"):
            res = json.loads(armf.read_text())
            if res.get("ok") and res.get("test_code"):
                score, comps = alignment_score(res["test_code"], truth)
                res["alignment"], res["alignment_components"] = score, comps
                armf.write_text(json.dumps(res, indent=2))
                row[armf.stem] = score
        rows.append(row)
    return rows


def _save(outdir: Path, sha: str, arm: str, payload: dict) -> None:
    d = outdir / sha
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{arm}.json").write_text(json.dumps(payload, indent=2))


MAX_ATTEMPTS = 2  # a commit that fails this many times is left as a permanent failure


def _read(outdir: Path, sha: str, arm: str) -> dict | None:
    f = outdir / sha / f"{arm}.json"
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text())
    except json.JSONDecodeError:
        return None


def _settled(outdir: Path, sha: str, arm: str) -> bool:
    """Done = succeeded, or failed MAX_ATTEMPTS times (stop retrying)."""
    r = _read(outdir, sha, arm)
    return bool(r and (r.get("ok") or r.get("attempts", 1) >= MAX_ATTEMPTS))


def run(arms=("A1", "A3"), n: int = 8, exp_id: str | None = None) -> dict:
    exp_id = exp_id or datetime.now().strftime("%Y%m%d-%H%M%S")
    outdir = RESULTS / exp_id
    outdir.mkdir(parents=True, exist_ok=True)
    commits = select_commits(n)
    print(f"experiment {exp_id}: {len(commits)} commits x arms {list(arms)} -> {outdir}")

    for c in commits:
        sha = c["sha"]
        rec = _full_record(sha)
        truth = ground_truth_code(rec)
        for arm in arms:
            if _settled(outdir, sha, arm):
                continue
            prev = _read(outdir, sha, arm)
            res = run_arm(rec, arm)
            if res.get("rate_limited"):
                print(f"  RATE LIMITED at {sha[:8]}/{arm}: {res.get('error')}")
                return {"exp_id": exp_id, "rate_limited": True,
                        "reset_hint": res.get("error", ""), "complete": False}
            res["attempts"] = (prev.get("attempts", 0) if prev else 0) + 1
            if res.get("ok"):
                score, comps = alignment_score(res.get("test_code", ""), truth)
                res["alignment"] = score
                res["alignment_components"] = comps
            _save(outdir, sha, arm, res)
            print(f"  {sha[:8]} {arm}: ok={res.get('ok')} turns={res.get('num_turns')} "
                  f"align={res.get('alignment')} attempt={res['attempts']} ${res.get('cost_usd_equiv')}")
    complete = all(_settled(outdir, c["sha"], a) for c in commits for a in arms)
    print(f"experiment pass done (complete={complete}): {exp_id}")
    return {"exp_id": exp_id, "rate_limited": False, "reset_hint": "", "complete": complete}
