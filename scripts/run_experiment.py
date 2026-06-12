"""Run an experiment slice (resumable after rate limits).

Usage:
    # v2 (deletion protocol, A1 vs A2):
    ATW_REPO=dbt-core .venv/bin/python scripts/run_experiment.py --protocol v2 --n 25 --arms A1 A2 --exp-id v2-dbt-core
    # v1 (legacy, A1 vs A3):
    .venv/bin/python scripts/run_experiment.py --n 8 --arms A1 A3
    # resume a rate-limited run (same exp-id):
    ATW_REPO=dbt-core .venv/bin/python scripts/run_experiment.py --protocol v2 --exp-id v2-dbt-core
"""

from __future__ import annotations

import argparse

from atw.eval.run_experiment import run


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=8, help="number of focused commits")
    ap.add_argument("--arms", nargs="+", default=["A1", "A3"])
    ap.add_argument("--exp-id", default=None, help="reuse to resume a prior run")
    ap.add_argument("--protocol", default="v1", choices=["v1", "v2"],
                    help="v2 enables test-file deletion + git-stripping")
    ap.add_argument("--max-turns", type=int, default=None,
                    help="override CFG.max_tool_calls per run (useful for repos with large test files)")
    args = ap.parse_args()
    run(arms=tuple(args.arms), n=args.n, exp_id=args.exp_id, protocol=args.protocol,
        max_turns=args.max_turns)


if __name__ == "__main__":
    main()
