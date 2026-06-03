"""Build the alignment figure + stats summary for an experiment.

Usage:
    .venv/bin/python scripts/make_report.py --exp-id failfast2-A1A3
"""

from __future__ import annotations

import argparse

from atw.eval.report import make_report, summarize


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exp-id", required=True)
    args = ap.parse_args()

    s = summarize(args.exp_id)
    print(f"n={s['n']}  means={s['means']}  A3-vs-A1={s['wtl']}")
    out = make_report(args.exp_id)
    print(f"figure -> {out}")


if __name__ == "__main__":
    main()
