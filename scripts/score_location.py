#!/usr/bin/env python3
"""Score location-discovery metric for a v2 experiment.

Usage:
    ATW_REPO=dbt-core .venv/bin/python scripts/score_location.py --exp-id v2-smoke-dbt
"""

import argparse
import json
from pathlib import Path

from atw.config import COMMITS, RESULTS
from atw.metrics.location import score_location


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exp-id", required=True)
    args = parser.parse_args()

    outdir = RESULTS / args.exp_id
    if not outdir.exists():
        print(f"No results at {outdir}")
        return

    arm_totals: dict[str, dict] = {}

    for sha_dir in sorted(p for p in outdir.iterdir() if p.is_dir()):
        sha = sha_dir.name
        meta_path = sha_dir / "item_meta.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text())
        gt_files = meta.get("test_files", [])

        for arm_file in sha_dir.glob("*.json"):
            arm = arm_file.stem
            if arm in ("item_meta",):
                continue
            result = json.loads(arm_file.read_text())
            stream_path = sha_dir / f"{arm}.stream.jsonl"

            loc = score_location(result, stream_path if stream_path.exists() else None, gt_files)
            loc_out_path = sha_dir / f"{arm}.location.json"
            loc_out_path.write_text(json.dumps(loc, indent=2))

            if arm not in arm_totals:
                arm_totals[arm] = {"n": 0, "exact": 0, "dir": 0, "basename": 0,
                                   "surfaced": 0, "mcp_calls": 0}
            t = arm_totals[arm]
            t["n"] += 1
            t["exact"] += int(loc["exact_match"])
            t["dir"] += int(loc["dir_match"])
            t["basename"] += int(loc["basename_match"])
            t["surfaced"] += int(loc["surfaced"])
            t["mcp_calls"] += loc["mcp_tool_calls"]

    print(f"\nLocation metric — {args.exp_id}")
    print(f"{'arm':<6} {'n':>4} {'exact':>7} {'dir':>6} {'base':>6} {'surfaced':>9} {'mcp/run':>8}")
    print("-" * 50)
    for arm, t in sorted(arm_totals.items()):
        n = t["n"]
        if n == 0:
            continue
        print(f"{arm:<6} {n:>4} {t['exact']:>5}/{n} {t['dir']:>4}/{n} "
              f"{t['basename']:>4}/{n} {t['surfaced']:>7}/{n} {t['mcp_calls']/n:>7.1f}")


if __name__ == "__main__":
    main()
