"""Behavioral pairwise judge over a slice (A1 vs A3). Resumable.

Usage:
    .venv/bin/python scripts/run_judge.py --exp-id failfast3-A1A3
"""

from __future__ import annotations

import argparse

from atw.eval.judge import run_judge
from atw.metrics.behavioral import JUDGE_MODEL


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exp-id", required=True)
    ap.add_argument("--arm-a", default="A1")
    ap.add_argument("--arm-b", default="A3")
    ap.add_argument("--model", default=JUDGE_MODEL, help="judge model (opus for the final run)")
    args = ap.parse_args()
    run_judge(args.exp_id, args.arm_a, args.arm_b, model=args.model)


if __name__ == "__main__":
    main()
