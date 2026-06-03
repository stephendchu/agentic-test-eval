"""Artifact-quality scoring — the 'historical engineering intelligence' prior.

Ranks *artifacts, not people* (authors never enter the score). v1 uses signals
available from git alone:
  - **longevity** — how long the test file has survived (dominant signal).
  - **maintenance/reuse** — commit touches (log-damped).
Flake rate and regression-catch rate need CI data -> Phase 2 (documented gap).
Scores are min-max normalized across the repo's own test corpus, so the metric
is repo-relative by construction (plug-and-play).
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from atw.graph.test_to_code import RepoGraph


def _parse(dt: str) -> datetime:
    return datetime.fromisoformat(dt)


class QualityScorer:
    def __init__(self, graph: RepoGraph, now: datetime | None = None):
        self.now = now or datetime.now(timezone.utc)
        self.stats = graph.file_stats
        ages, churns = [], []
        for t in graph.test_files:
            s = self.stats.get(t)
            if not s:
                continue
            ages.append(self._age_days(s))
            churns.append(s["count"])
        self._amin, self._amax = (min(ages), max(ages)) if ages else (0.0, 1.0)
        self._cmin, self._cmax = (min(churns), max(churns)) if churns else (0, 1)

    def _age_days(self, s: dict) -> float:
        return max(0.0, (self.now - _parse(s["first"])).total_seconds() / 86400.0)

    @staticmethod
    def _norm(v: float, lo: float, hi: float) -> float:
        return 0.5 if hi <= lo else max(0.0, min(1.0, (v - lo) / (hi - lo)))

    def score(self, test_file: str) -> float:
        """0..1; higher = a more durable, well-maintained example to learn from."""
        s = self.stats.get(test_file)
        if not s:
            return 0.3  # unknown history -> below-average prior
        age = self._norm(self._age_days(s), self._amin, self._amax)
        reuse = self._norm(
            math.log1p(s["count"]), math.log1p(self._cmin), math.log1p(self._cmax)
        )
        return round(0.7 * age + 0.3 * reuse, 4)
