"""5-axis taste rubric over a slice (resumable).

    .venv/bin/python scripts/run_taste.py --exp-id failfast3-A1A3
"""

from __future__ import annotations

import argparse

from atw.eval.taste import run_taste
from atw.metrics.taste_rubric import JUDGE_MODEL


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exp-id", required=True)
    ap.add_argument("--arms", nargs="+", default=["A1", "A3"])
    ap.add_argument("--model", default=JUDGE_MODEL)
    args = ap.parse_args()
    run_taste(args.exp_id, tuple(args.arms), model=args.model)


if __name__ == "__main__":
    main()
