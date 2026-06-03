"""Central configuration. Swapping the target repo is a one-line change here."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

@dataclass(frozen=True)
class RepoSpec:
    name: str
    url: str
    language: str = "python"
    test_glob: str = "tests/**/*.py"  # where this repo keeps its tests
    src_glob: str = "**/*.py"


# --- paths -------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")  # load ANTHROPIC_API_KEY -> claude/SDK bill to API (no throttle)
DATA = ROOT / "data"
REPOS = DATA / "repos"          # git clones: data/repos/<name>
RESULTS = ROOT / "results"
REPORTS = ROOT / "reports"

# Active repo — swap here to change the whole experiment. Derived data is
# namespaced by repo name so multiple codebases coexist (data/commits/<name>,
# data/graph/<name>).
ACTIVE_REPO = RepoSpec(name="dbt-core", url="https://github.com/dbt-labs/dbt-core")
COMMITS = DATA / "commits" / ACTIVE_REPO.name
GRAPH = DATA / "graph" / ACTIVE_REPO.name


@dataclass(frozen=True)
class Config:
    repo: RepoSpec = field(default_factory=lambda: ACTIVE_REPO)

    # --- model ---------------------------------------------------------------
    model: str = "claude-opus-4-8"
    judge_model: str = "claude-opus-4-8"  # blinded judge; swap to a 2nd model for independence

    # --- contamination control ----------------------------------------------
    # Only mine commits AFTER this date (after the model's training cutoff).
    # Conservative default given a ~Jan-2026 cutoff. Configurable.
    post_cutoff_after: str = "2026-02-01"

    # --- experiment budget (kept EQUAL across both arms) ---------------------
    # Maps to --max-turns. 25 was too low: agents hit the cap before writing the
    # test (turns=26, ok=False) on harder commits. 40 gives headroom; still equal
    # across arms so the comparison stays fair.
    max_tool_calls: int = 40
    max_tokens_per_rollout: int = 200_000
    rollouts_per_commit: int = 3  # k samples for variance

    # --- dataset size --------------------------------------------------------
    n_commits_smoke: int = 10   # first defensible graph
    n_commits_full: int = 100   # full slice


CFG = Config()
