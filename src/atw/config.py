"""Central configuration. Swapping the target repo is a one-line change here."""

from __future__ import annotations

import os
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

# Known repos — add here to onboard a new codebase. Switch via ATW_REPO env var.
# Every v2 command: ATW_REPO=<name> .venv/bin/python scripts/...
KNOWN_REPOS: dict[str, RepoSpec] = {
    "dbt-core": RepoSpec(name="dbt-core", url="https://github.com/dbt-labs/dbt-core"),
    "pydantic": RepoSpec(name="pydantic", url="https://github.com/pydantic/pydantic"),
    "sqlalchemy": RepoSpec(name="sqlalchemy", url="https://github.com/sqlalchemy/sqlalchemy"),
}

ACTIVE_REPO = KNOWN_REPOS[os.environ.get("ATW_REPO", "dbt-core")]
COMMITS = DATA / "commits" / ACTIVE_REPO.name
GRAPH = DATA / "graph" / ACTIVE_REPO.name


@dataclass(frozen=True)
class Config:
    repo: RepoSpec = field(default_factory=lambda: ACTIVE_REPO)

    # --- model ---------------------------------------------------------------
    model: str = "claude-sonnet-4-6"        # model under test, held constant across both arms
    judge_model: str = "claude-sonnet-4-6"  # same family as the generator; the headline AST-alignment metric is model-independent. Swap to a different family to harden judge independence.

    # --- contamination control ----------------------------------------------
    # Only mine commits AFTER this date (after the model's training cutoff).
    # Conservative default given a ~Jan-2026 cutoff. Configurable.
    post_cutoff_after: str = "2026-02-01"

    # --- experiment budget (kept EQUAL across both arms) ---------------------
    # Maps to --max-turns. 25 was too low: agents hit the cap before writing the
    # test (turns=26, ok=False) on harder commits. 40 gives headroom; still equal
    # across arms so the comparison stays fair.
    max_tool_calls: int = 60
    max_tokens_per_rollout: int = 200_000
    rollouts_per_commit: int = 3  # k samples for variance

    # --- dataset size --------------------------------------------------------
    n_commits_smoke: int = 10   # first defensible graph
    n_commits_full: int = 100   # full slice


CFG = Config()
