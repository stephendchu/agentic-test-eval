"""Human-free taste eval: indistinguishability from the maintainer's real test.

    .venv/bin/python scripts/run_conformity.py --exp-id failfast4-A1A3
"""

from __future__ import annotations

import argparse

from atw.eval.conformity import run_conformity
from atw.metrics.conformity import JUDGE_MODEL


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exp-id", required=True)
    ap.add_argument("--arms", nargs="+", default=["A1", "A3"])
    ap.add_argument("--model", default=JUDGE_MODEL)
    args = ap.parse_args()
    run_conformity(args.exp_id, tuple(args.arms), model=args.model)


if __name__ == "__main__":
    main()
