"""Autonomously run experiment B across reset windows: generate V/C conditions,
then score nativeness with the human-free indistinguishability eval.

    .venv/bin/python scripts/auto_conditioning.py --exp-id condB-dbtcore --n 12
"""

from __future__ import annotations

import argparse

from atw.eval.conditioning import run as run_conditioning
from atw.eval.conformity import run_conformity
from atw.grind import grind


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exp-id", required=True)
    ap.add_argument("--n", type=int, default=12)
    args = ap.parse_args()

    print(f"[auto-B] start {args.exp_id}: conditioning (V vs C) then conformity", flush=True)
    if grind(lambda: run_conditioning(("V", "C"), args.n, args.exp_id), "conditioning"):
        grind(lambda: run_conformity(args.exp_id, ("V", "C")), "conformity")
    print("[auto-B] DONE", flush=True)


if __name__ == "__main__":
    main()
