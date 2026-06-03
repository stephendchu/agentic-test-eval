"""Aggregate a run's results into a stats summary + an alignment figure."""

from __future__ import annotations

import json
import statistics as st
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless
import matplotlib.pyplot as plt  # noqa: E402

from atw.config import REPORTS, RESULTS  # noqa: E402

_ARM_ORDER = ["A0", "A1", "A2", "A3"]


def aggregate(exp_id: str) -> tuple[dict, list[str]]:
    outdir = RESULTS / exp_id
    commits: dict[str, dict] = {}
    for shadir in sorted(p for p in outdir.iterdir() if p.is_dir()):
        sha = shadir.name[:8]
        for armf in shadir.glob("*.json"):
            r = json.loads(armf.read_text())
            if not r.get("ok") or r.get("alignment") is None:
                continue
            commits.setdefault(sha, {})[armf.stem] = {
                "alignment": r["alignment"],
                "mcp": r.get("mcp_tool_calls"),
                "n_tool_calls": r.get("n_tool_calls"),
            }
    arms = sorted(
        {a for v in commits.values() for a in v},
        key=lambda a: _ARM_ORDER.index(a) if a in _ARM_ORDER else 99,
    )
    return commits, arms


def summarize(exp_id: str) -> dict:
    commits, arms = aggregate(exp_id)
    means = {}
    for a in arms:
        vals = [c[a]["alignment"] for c in commits.values() if a in c]
        means[a] = round(st.mean(vals), 1) if vals else None
    wtl = None
    if "A1" in arms and "A3" in arms:
        w = t = l = 0
        for c in commits.values():
            if "A1" in c and "A3" in c:
                d = c["A3"]["alignment"] - c["A1"]["alignment"]
                w += d > 0.5; t += abs(d) <= 0.5; l += d < -0.5

        wtl = {"A3_wins": w, "ties": t, "A3_losses": l}
    return {"commits": commits, "arms": arms, "means": means, "wtl": wtl, "n": len(commits)}


def make_report(exp_id: str) -> Path:
    s = summarize(exp_id)
    commits, arms, means = s["commits"], s["arms"], s["means"]
    shas = list(commits.keys())
    colors = {"A0": "#9aa0a6", "A1": "#4285f4", "A2": "#fbbc04", "A3": "#34a853"}

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(12, 4.5), gridspec_kw={"width_ratios": [3, 1]})
    width = 0.8 / max(len(arms), 1)
    for i, a in enumerate(arms):
        xs = [j + i * width for j in range(len(shas))]
        ys = [commits[sh].get(a, {}).get("alignment", 0) for sh in shas]
        ax.bar(xs, ys, width, label=a, color=colors.get(a, "#777"))
    ax.set_xticks([j + width * (len(arms) - 1) / 2 for j in range(len(shas))])
    ax.set_xticklabels(shas, rotation=30, ha="right", fontsize=8)
    ax.set_ylabel("Maintainer-intent alignment (0–100)")
    ax.set_ylim(0, 105)
    ax.set_title(f"Per-commit alignment — {exp_id} (n={s['n']})")
    ax.legend()

    # means panel
    ax2.bar(list(means), [means[a] or 0 for a in means],
            color=[colors.get(a, "#777") for a in means])
    for i, a in enumerate(means):
        ax2.text(i, (means[a] or 0) + 1, str(means[a]), ha="center", fontsize=9)
    ax2.set_ylim(0, 105)
    ax2.set_title("Mean")
    sub = s["wtl"]
    if sub:
        ax2.set_xlabel(f"A3 vs A1: {sub['A3_wins']}W / {sub['ties']}T / {sub['A3_losses']}L")

    REPORTS.joinpath("figures").mkdir(parents=True, exist_ok=True)
    out = REPORTS / "figures" / f"{exp_id}_alignment.png"
    fig.tight_layout()
    fig.savefig(out, dpi=130, bbox_inches="tight")
    plt.close(fig)
    return out
