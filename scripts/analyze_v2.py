#!/usr/bin/env python3
"""Statistical analysis for v2 experiments.

Computes paired alignment CI, Wilson CI on judge win-rate, location/adoption
rates, and stratification by file-creation covariate. Prints a results table
and optionally compares to v1 baseline numbers.

Usage:
    .venv/bin/python scripts/analyze_v2.py --exp-ids v2-dbt-core v2-pydantic
    .venv/bin/python scripts/analyze_v2.py --exp-ids v2-dbt-core --v1-win-rate 0.286 --v1-n 7
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np

from atw.config import RESULTS

# v1 baseline (A3 win-rate on dbt-core, n=7, Wilson CI [0.08, 0.64])
V1_WIN_RATE = 0.286
V1_N = 7


# ---------------------------------------------------------------------------
# Stats helpers
# ---------------------------------------------------------------------------

def wilson_ci(successes: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score confidence interval for a proportion."""
    if n == 0:
        return (0.0, 0.0)
    p = successes / n
    denom = 1 + z**2 / n
    center = (p + z**2 / (2 * n)) / denom
    margin = (z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))) / denom
    return (max(0.0, center - margin), min(1.0, center + margin))


def bootstrap_mean_diff(a_scores: list[float], b_scores: list[float],
                        n_boot: int = 10_000, seed: int = 42) -> tuple[float, float, float]:
    """Bootstrap CI for mean(B) - mean(A) on paired data.

    Returns (point_estimate, ci_lower, ci_upper).
    """
    rng = np.random.default_rng(seed)
    diffs = np.array(b_scores) - np.array(a_scores)
    point = float(np.mean(diffs))
    boots = [float(np.mean(rng.choice(diffs, size=len(diffs), replace=True)))
             for _ in range(n_boot)]
    lo, hi = np.percentile(boots, [2.5, 97.5])
    return point, float(lo), float(hi)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_exp(exp_id: str) -> tuple[list[dict], list[dict]]:
    """Load all paired (A1, A2) result dicts for an experiment."""
    outdir = RESULTS / exp_id
    a1_results, a2_results = [], []
    for sha_dir in sorted(p for p in outdir.iterdir() if p.is_dir()):
        a1_path = sha_dir / "A1.json"
        a2_path = sha_dir / "A2.json"
        beh_path = sha_dir / "behavioral.json"
        loc_a1 = sha_dir / "A1.location.json"
        loc_a2 = sha_dir / "A2.location.json"
        meta_path = sha_dir / "item_meta.json"

        if not (a1_path.exists() and a2_path.exists()):
            continue

        a1 = json.loads(a1_path.read_text())
        a2 = json.loads(a2_path.read_text())

        # Attach behavioral judge verdict if available.
        # behavioral.json stores winner as "A"/"B"/"tie" with a swapped flag;
        # resolve to arm names (A1/A2) before storing.
        if beh_path.exists():
            beh = json.loads(beh_path.read_text())
            raw_winner = beh.get("winner")  # "A", "B", or "tie"
            swapped = beh.get("swapped", False)
            arm_a = beh.get("arm_a", "A1")
            arm_b = beh.get("arm_b", "A2")
            if raw_winner == "tie":
                resolved = "tie"
            elif raw_winner == "A":
                resolved = arm_b if swapped else arm_a
            elif raw_winner == "B":
                resolved = arm_a if swapped else arm_b
            else:
                resolved = None
            a1["judge_winner"] = resolved
            a2["judge_winner"] = resolved

        # Attach location scores if available
        if loc_a1.exists():
            a1["location"] = json.loads(loc_a1.read_text())
        if loc_a2.exists():
            a2["location"] = json.loads(loc_a2.read_text())

        # Attach item covariates
        if meta_path.exists():
            meta = json.loads(meta_path.read_text())
            for r in (a1, a2):
                r["item_meta"] = meta

        a1["sha"] = sha_dir.name
        a2["sha"] = sha_dir.name
        a1_results.append(a1)
        a2_results.append(a2)

    return a1_results, a2_results


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------

def analyze(exp_ids: list[str], v1_win_rate: float | None = None, v1_n: int | None = None) -> None:
    all_a1, all_a2 = [], []
    repo_results: dict[str, tuple[list, list]] = {}

    for exp_id in exp_ids:
        outdir = RESULTS / exp_id
        if not outdir.exists():
            print(f"WARNING: {exp_id} not found, skipping")
            continue
        a1, a2 = _load_exp(exp_id)
        repo_name = exp_id.replace("v2-", "")
        repo_results[repo_name] = (a1, a2)
        all_a1.extend(a1)
        all_a2.extend(a2)

    if not all_a1:
        print("No results found.")
        return

    def _report_section(label: str, a1_list: list[dict], a2_list: list[dict]) -> None:
        n = len(a1_list)
        print(f"\n{'='*60}")
        print(f"  {label}  (n={n} items)")
        print(f"{'='*60}")

        # --- Alignment ---
        a1_align = [r["alignment"] for r in a1_list if r.get("ok") and r.get("alignment") is not None]
        a2_align = [r["alignment"] for r in a2_list if r.get("ok") and r.get("alignment") is not None]
        paired = [(r1["alignment"], r2["alignment"])
                  for r1, r2 in zip(a1_list, a2_list)
                  if r1.get("ok") and r2.get("ok")
                  and r1.get("alignment") is not None and r2.get("alignment") is not None]

        print(f"\nAlignment (0–100, structural AST match to ground truth):")
        print(f"  A1 mean: {sum(a for a,_ in paired)/len(paired):.1f}" if paired else "  A1: no data")
        print(f"  A2 mean: {sum(b for _,b in paired)/len(paired):.1f}" if paired else "  A2: no data")
        if len(paired) >= 2:
            point, lo, hi = bootstrap_mean_diff(
                [a for a, _ in paired], [b for _, b in paired]
            )
            sign = "+" if point >= 0 else ""
            print(f"  Δ(A2−A1): {sign}{point:.1f}  95% CI [{lo:.1f}, {hi:.1f}]")
            if lo > 0:
                print(f"  → CI excludes zero: A2 significantly better on alignment")
            elif hi < 0:
                print(f"  → CI excludes zero: A1 significantly better on alignment")
            else:
                print(f"  → CI includes zero: no significant alignment difference")

        # --- Judge ---
        judged = [r for r in a1_list if r.get("judge_winner") in ("A1", "A2", "tie")]
        if judged:
            a2_wins = sum(1 for r in judged if r["judge_winner"] == "A2")
            a1_wins = sum(1 for r in judged if r["judge_winner"] == "A1")
            ties = sum(1 for r in judged if r["judge_winner"] == "tie")
            n_decided = a2_wins + a1_wins  # exclude ties for Wilson
            wr = a2_wins / n_decided if n_decided > 0 else 0
            lo_w, hi_w = wilson_ci(a2_wins, n_decided) if n_decided > 0 else (0, 0)
            print(f"\nBehavioral judge (pairwise, blinded):")
            print(f"  A2 wins: {a2_wins}/{len(judged)}  A1 wins: {a1_wins}/{len(judged)}  ties: {ties}")
            print(f"  A2 win-rate (excl. ties): {wr:.3f}  95% Wilson CI [{lo_w:.2f}, {hi_w:.2f}]")
            if v1_win_rate is not None and label.startswith("ALL") or "dbt" in label.lower():
                v1_str = f"v1 baseline: {v1_win_rate:.3f} (n={v1_n})" if v1_n else f"v1 baseline: {v1_win_rate:.3f}"
                print(f"  {v1_str}  →  v2 Δ: {wr - v1_win_rate:+.3f}")
            if lo_w > 0.5:
                print(f"  → A2 significantly preferred")
            elif hi_w < 0.5:
                print(f"  → A1 significantly preferred")
            else:
                print(f"  → No significant preference")

        # --- Success rate ---
        a1_ok = sum(1 for r in a1_list if r.get("ok"))
        a2_ok = sum(1 for r in a2_list if r.get("ok"))
        print(f"\nSuccess rate:  A1 {a1_ok}/{n}  A2 {a2_ok}/{n}")

        # --- MCP adoption (A2) ---
        a2_mcp_counts = [r.get("mcp_tool_calls", 0) for r in a2_list if r.get("ok")]
        if a2_mcp_counts:
            adopted = sum(1 for c in a2_mcp_counts if c > 0)
            print(f"\nMCP adoption (A2 only):")
            print(f"  Runs with ≥1 MCP call: {adopted}/{len(a2_mcp_counts)}  "
                  f"({100*adopted/len(a2_mcp_counts):.0f}%)")
            print(f"  Mean MCP calls/run: {sum(a2_mcp_counts)/len(a2_mcp_counts):.2f}")
            print(f"  Distribution: {sorted(set(a2_mcp_counts))} "
                  f"(counts: {[a2_mcp_counts.count(v) for v in sorted(set(a2_mcp_counts))]})")

        # --- Location metric ---
        loc_pairs = [(r1.get("location"), r2.get("location"))
                     for r1, r2 in zip(a1_list, a2_list)
                     if r1.get("location") and r2.get("location")]
        if loc_pairs:
            def rate(key: str, arm_idx: int) -> str:
                vals = [p[arm_idx] for p in loc_pairs if p[arm_idx]]
                hits = sum(1 for v in vals if v.get(key))
                return f"{hits}/{len(vals)}"

            print(f"\nLocation discovery:")
            print(f"  {'metric':<20} {'A1':>8} {'A2':>8}")
            print(f"  {'-'*36}")
            for key, label_k in [
                ("exact_match",    "exact path match"),
                ("dir_match",      "correct directory"),
                ("basename_match", "correct filename"),
                ("surfaced",       "GT path in trace"),
            ]:
                print(f"  {label_k:<20} {rate(key, 0):>8} {rate(key, 1):>8}")

        # --- Covariates stratification ---
        cov_items = [(r1, r2) for r1, r2 in zip(a1_list, a2_list)
                     if r1.get("item_meta")]
        post_cutoff = [(r1, r2) for r1, r2 in cov_items
                       if any(fc.get("created_post_cutoff")
                              for fc in r1["item_meta"].get("file_covariates", []))]
        pre_cutoff = [(r1, r2) for r1, r2 in cov_items if (r1, r2) not in post_cutoff]
        if post_cutoff or pre_cutoff:
            print(f"\nStratification by test file creation date:")
            print(f"  Post-cutoff test files: {len(post_cutoff)} items")
            print(f"  Pre-cutoff test files:  {len(pre_cutoff)} items")
            for stratum_label, stratum in [
                ("post-cutoff", post_cutoff), ("pre-cutoff", pre_cutoff)
            ]:
                if not stratum:
                    continue
                s_pairs = [(r1.get("alignment"), r2.get("alignment"))
                           for r1, r2 in stratum
                           if r1.get("ok") and r2.get("ok")
                           and r1.get("alignment") is not None]
                if s_pairs:
                    d = sum(b - a for a, b in s_pairs) / len(s_pairs)
                    print(f"    {stratum_label}: Δ align = {d:+.1f}  (n={len(s_pairs)})")

        # --- Efficiency ---
        a1_turns = [r.get("num_turns", 0) or 0 for r in a1_list if r.get("ok")]
        a2_turns = [r.get("num_turns", 0) or 0 for r in a2_list if r.get("ok")]
        if a1_turns and a2_turns:
            print(f"\nEfficiency (successful runs only):")
            print(f"  Avg turns:  A1 {sum(a1_turns)/len(a1_turns):.1f}  "
                  f"A2 {sum(a2_turns)/len(a2_turns):.1f}")

    # Per-repo sections
    for repo_name, (a1, a2) in repo_results.items():
        _report_section(repo_name, a1, a2)

    # Pooled
    if len(repo_results) > 1:
        _report_section("ALL REPOS POOLED", all_a1, all_a2)

    # Headline summary
    print(f"\n{'='*60}")
    print("  HEADLINE: Did deletion flip the result vs v1?")
    print(f"{'='*60}")
    if v1_win_rate is not None:
        judged_all = [r for r in all_a1 if r.get("judge_winner") in ("A1", "A2", "tie")]
        if judged_all:
            a2w = sum(1 for r in judged_all if r["judge_winner"] == "A2")
            a1w = sum(1 for r in judged_all if r["judge_winner"] == "A1")
            nd = a2w + a1w
            wr = a2w / nd if nd else 0
            lo_w, hi_w = wilson_ci(a2w, nd) if nd else (0, 0)
            print(f"  v1 A3 win-rate:   {v1_win_rate:.3f}  (n={v1_n}, CI [0.08, 0.64])")
            print(f"  v2 A2 win-rate:   {wr:.3f}  (n={nd}, CI [{lo_w:.2f}, {hi_w:.2f}])")
            flipped = lo_w > 0.5
            inconclusive = lo_w <= 0.5 <= hi_w
            print(f"  Result: {'FLIPPED ✓ — deletion changed the finding' if flipped else 'INCONCLUSIVE — CI still includes 0.5' if inconclusive else 'NULL — A2 not preferred'}")
        else:
            print("  Judge results not yet available — run run_judge.py first")
    else:
        print("  Pass --v1-win-rate 0.286 --v1-n 7 to compare against v1 baseline")
    print()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--exp-ids", nargs="+", required=True,
                    help="experiment IDs to analyze (e.g. v2-dbt-core v2-pydantic)")
    ap.add_argument("--v1-win-rate", type=float, default=V1_WIN_RATE,
                    help=f"v1 A3 win-rate for headline comparison (default {V1_WIN_RATE})")
    ap.add_argument("--v1-n", type=int, default=V1_N,
                    help=f"v1 sample size (default {V1_N})")
    args = ap.parse_args()
    analyze(args.exp_ids, args.v1_win_rate, args.v1_n)


if __name__ == "__main__":
    main()
