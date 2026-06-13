# Target Repositories

Selection throughline: **recognizable brand + acknowledged engineering
excellence + mature test suite + commits after the model cutoff.** v1 also
requires Python + `pytest` (single-command harness, isolable deps) and —
importantly — **rich, idiosyncratic test infrastructure**, because that is
exactly where generic grep struggles and semantic tools should shine. A repo
with trivial tests will show no gap no matter how good the tooling.

## Test-infrastructure depth (the independent variable)

Test-file discoverability is the variable the gradient is built on, so it is
worth stating concretely. "Root" is the repo's test directory (`tests/` for
pydantic and dbt-core, `test/` for SQLAlchemy). "Depth" counts directory levels
*below* that root, so depth 0 means a test file lives directly in the root.

| Repo | Test root | Dirs under root | Max test-file depth | Test files | Depth distribution |
|------|-----------|----------------|---------------------|-----------|--------------------|
| **pydantic** | `tests/` | 18 (17 subdirs) | 1 | 90 | depth 0: 71 · depth 1: 19 |
| **dbt-core** | `tests/` | 105 † | — † | — † | — † |
| **SQLAlchemy** | `test/` | 34 (33 subdirs) | 2 | 225 | depth 1: 152 · depth 2: 73 |

Reading the rows:

- **pydantic** — shallow *and* narrow. 79% of test files sit directly in
  `tests/`; nothing is more than one level down. An agent can infer where a test
  belongs from sibling files alone, which is exactly why grep is sufficient and
  findtest goes unused (0% adoption).
- **SQLAlchemy** — moderately deep and, tellingly, **no test files at the root
  at all**: every test is pushed at least one level down (depth 1–2), behind the
  custom `sqlalchemy.testing` plugin (`@testing.combinations`, `assert_compile`).
  Depth + framework idiosyncrasy is what breaks grep here.
- **dbt-core** — the breadth case: standard pytest, but the tests fan out across
  105 directories. Sheer directory count, not depth, is enough to make the right
  location hard to grep for.

† **dbt-core is not re-measurable at HEAD.** The "105 test directories" figure is
what was recorded during the study. Since then dbt-core's `main` has been
rewritten in Rust (`crates/`, `lib/`) — no Python `tests/` tree remains — and
`src/atw/config.py` clones HEAD rather than pinning a commit SHA, and the study's
`data/` (including `data/commits/dbt-core/`) is git-ignored and not retained. The
depth/file figures therefore can't be reconstructed without the study-era SHA.
This is a reproducibility gap, disclosed rather than papered over; pinning a SHA
per repo in `config.py` is the fix for any re-run.

*Measured at current HEAD for pydantic and SQLAlchemy via
`find <root> -type f -name 'test_*.py' -o -name '*_test.py'`, bucketed by path
depth below the root.*

## v1 default (set in `config.py`)

- **dbt-core** (dbt Labs) — company-backed, serious pytest culture, complex
  fixtures/custom test infra, heavy review.

Fallback if deps are painful: **Pydantic** (immaculate tests, trivial deps).
Other strong Python/pytest options, swap via one config line: Sentry backend
(Sentry), scikit-learn (NumFOCUS), FastAPI/Starlette (Encode).

## Phase-2 diversity portfolio (one marquee repo per language)

Supports the strongest claim — "consistent across repos and languages." Each
non-Python repo needs its own runner adapter.

| Language | Repo | Org |
|----------|------|-----|
| Python | scikit-learn / Sentry | NumFOCUS / Sentry |
| TypeScript/JS | TypeScript / React+Jest | Microsoft / Meta |
| Go | Terraform or Vault | HashiCorp |
| Java | Guava or Elasticsearch | Google / Elastic |
| Rust | Polars or ripgrep | Polars / BurntSushi |

All have prod+test co-change commits after the cutoff, so contamination control
holds.

## Runner notes

- **Python/pytest:** `pytest <path>` in a dependency-pinned venv/Docker per
  commit snapshot. (v1)
- Non-Python: per-language runner adapter — Phase 2.
