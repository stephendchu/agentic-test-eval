"""Paired statistics for the A1-vs-A3 comparison.

Alignment is paired (same commit, both arms) -> paired bootstrap CI on the mean
difference. The behavioral judge is a preference proportion -> Wilson CI. Both
report whether the interval excludes the null (0 / 0.5), which is the bar for a
real effect.
"""

from __future__ import annotations

import math

import numpy as np


def paired_bootstrap(diffs, n_boot: int = 10000, ci: float = 0.95, seed: int = 0) -> dict:
    """Bootstrap CI for the mean of paired differences (e.g. A3 - A1 alignment)."""
    d = np.asarray(list(diffs), dtype=float)
    if d.size == 0:
        return {"n": 0}
    rng = np.random.default_rng(seed)
    boots = rng.choice(d, size=(n_boot, d.size), replace=True).mean(axis=1)
    lo, hi = np.percentile(boots, [(1 - ci) / 2 * 100, (1 + ci) / 2 * 100])
    return {
        "n": int(d.size),
        "mean_diff": round(float(d.mean()), 2),
        "ci_low": round(float(lo), 2),
        "ci_high": round(float(hi), 2),
        "excludes_zero": bool(lo > 0 or hi < 0),
    }


def wilson_ci(wins: int, n: int, z: float = 1.96) -> dict:
    """Wilson score interval for a win proportion (behavioral preference)."""
    if n == 0:
        return {"n": 0}
    p = wins / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    lo, hi = center - half, center + half
    return {
        "n": n,
        "win_rate": round(p, 3),
        "ci_low": round(lo, 3),
        "ci_high": round(hi, 3),
        "excludes_half": bool(lo > 0.5 or hi < 0.5),
    }
