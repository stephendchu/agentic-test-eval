"""Autonomously grind a slice to completion across subscription reset windows.

Loop: resume experiment -> on rate-limit, parse the reset time and sleep until
then -> repeat until all commits done -> run the behavioral judge the same way ->
build the report. Designed to run as a background job; it emits a heartbeat log
and exits (notifying the parent) when the whole slice is finished.

    .venv/bin/python scripts/auto_resume.py --exp-id failfast3-A1A3 --n 8
"""

from __future__ import annotations

import argparse
import re
import time
import zoneinfo
from datetime import datetime, timedelta

from atw.eval.judge import run_judge
from atw.eval.report import make_report
from atw.eval.run_experiment import run

TZ = zoneinfo.ZoneInfo("America/Chicago")


def parse_reset_seconds(hint: str, default: int = 1500) -> int:
    """Seconds until the reset time named in a limit message; clamped [60, 6h]."""
    m = re.search(r"resets?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)", hint or "", re.I)
    if not m:
        return default
    hour = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "pm" else 0)
    minute = int(m.group(2) or 0)
    now = datetime.now(TZ)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        # named reset time already passed -> window likely fresh; retry shortly
        return 300
    return max(60, min(int((target - now).total_seconds()) + 60, 6 * 3600))


def _grind(step, label: str, max_cycles: int = 40, max_stall: int = 3) -> bool:
    stall = 0
    for cycle in range(max_cycles):
        st = step()
        if st.get("complete"):
            print(f"[auto] {label} COMPLETE", flush=True)
            return True
        if st.get("rate_limited"):
            stall = 0
            secs = parse_reset_seconds(st.get("reset_hint", ""))
            wake = (datetime.now(TZ) + timedelta(seconds=secs)).strftime("%H:%M %Z")
            print(f"[auto] {label}: rate-limited; sleeping {secs//60} min until ~{wake} "
                  f"(cycle {cycle+1})", flush=True)
            time.sleep(secs)
        else:
            # Incomplete but NOT rate-limited = some agent runs failed (e.g. hit the
            # turn cap). Those saved as ok=False and will re-run next pass. Retry a
            # few times, then proceed with partial data rather than block forever.
            stall += 1
            if stall >= max_stall:
                print(f"[auto] {label}: {stall} passes w/o completion (persistent agent "
                      f"failures); proceeding with partial data", flush=True)
                return False
            print(f"[auto] {label}: incomplete (agent failures), retry {stall}/{max_stall}",
                  flush=True)
            time.sleep(120)
    print(f"[auto] {label}: hit max_cycles", flush=True)
    return False


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exp-id", required=True)
    ap.add_argument("--n", type=int, default=8)
    ap.add_argument("--arms", nargs="+", default=["A1", "A3"])
    args = ap.parse_args()
    arms = tuple(args.arms)

    print(f"[auto] start {args.exp_id}: experiment then judge then report", flush=True)
    if _grind(lambda: run(arms, args.n, args.exp_id), "experiment"):
        _grind(lambda: run_judge(args.exp_id, arms[0], arms[1]), "judge")
    out = make_report(args.exp_id)
    print(f"[auto] report -> {out}\n[auto] DONE", flush=True)


if __name__ == "__main__":
    main()
