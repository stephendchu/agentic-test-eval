"""Reusable autonomous-grind loop: run a step, sleep through reset windows on
rate-limit, retry on transient failures, stop when complete."""

from __future__ import annotations

import re
import time
import zoneinfo
from datetime import datetime, timedelta

TZ = zoneinfo.ZoneInfo("America/Chicago")


def parse_reset_seconds(hint: str, default: int = 1500) -> int:
    """Seconds until the reset named in a limit message; clamped [60, 6h].
    If the named time already passed, retry shortly (window likely fresh)."""
    m = re.search(r"resets?\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)", hint or "", re.I)
    if not m:
        return default
    hour = int(m.group(1)) % 12 + (12 if m.group(3).lower() == "pm" else 0)
    minute = int(m.group(2) or 0)
    now = datetime.now(TZ)
    target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if target <= now:
        return 300
    return max(60, min(int((target - now).total_seconds()) + 60, 6 * 3600))


def grind(step, label: str, max_cycles: int = 40, max_stall: int = 3) -> bool:
    """Call step() until it reports complete. step() returns a dict with keys
    `complete` / `rate_limited` / `reset_hint`."""
    stall = 0
    for cycle in range(max_cycles):
        st = step()
        if st.get("complete"):
            print(f"[grind] {label} COMPLETE", flush=True)
            return True
        if st.get("rate_limited"):
            stall = 0
            secs = parse_reset_seconds(st.get("reset_hint", ""))
            wake = (datetime.now(TZ) + timedelta(seconds=secs)).strftime("%H:%M %Z")
            print(f"[grind] {label}: rate-limited; sleeping {secs // 60} min until ~{wake} "
                  f"(cycle {cycle + 1})", flush=True)
            time.sleep(secs)
        else:
            stall += 1
            if stall >= max_stall:
                print(f"[grind] {label}: {stall} passes w/o completion; proceeding partial",
                      flush=True)
                return False
            print(f"[grind] {label}: incomplete, retry {stall}/{max_stall}", flush=True)
            time.sleep(120)
    return False
