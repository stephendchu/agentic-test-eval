"""Run the A1-vs-A3 fail-fast slice (resumable after rate limits).

Usage:
    .venv/bin/python scripts/run_experiment.py --n 8 --arms A1 A3
    # resume a rate-limited run:
    .venv/bin/python scripts/run_experiment.py --exp-id 20260531-031500
"""

from __future__ import annotations

import argparse

from atw.eval.run_experiment import run


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=8, help="number of focused commits")
    ap.add_argument("--arms", nargs="+", default=["A1", "A3"])
    ap.add_argument("--exp-id", default=None, help="reuse to resume a prior run")
    args = ap.parse_args()
    run(arms=tuple(args.arms), n=args.n, exp_id=args.exp_id)


if __name__ == "__main__":
    main()
