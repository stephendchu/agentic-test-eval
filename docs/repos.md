# Target Repositories

Selection throughline: **recognizable brand + acknowledged engineering
excellence + mature test suite + commits after the model cutoff.** v1 also
requires Python + `pytest` (single-command harness, isolable deps) and —
importantly — **rich, idiosyncratic test infrastructure**, because that is
exactly where generic grep struggles and semantic tools should shine. A repo
with trivial tests will show no gap no matter how good the tooling.

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
