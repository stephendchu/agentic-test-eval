# Methodology

**Positioning:** *Historical Engineering Intelligence for Repository-Aware Test
Generation* — learning maintainer intent from repository evolution. The
differentiator vs. the literature (TestGen-LLM, SWE-agent, repo-RAG) is mining
**historical engineering decisions + maintainer preferences** as a first-class
signal, and measuring **taste**, not just coverage/correctness.

## Question

Does giving Claude **custom, repo-aware MCP tools** produce better, more
repo-native tests than the **same agent with generic file tools** (grep, read,
bash)? "Better" = correctness, repo-style alignment, and engineering taste —
measured, not asserted.

## Hypothesis

Repo-aware semantic tooling outperforms generic exploration on style/taste, and
matches-or-beats it on correctness — and/or reaches comparable quality with
**fewer tool calls / tokens** (efficiency).

## Research questions

- **RQ1** Does semantic repo tooling improve test quality vs. generic tools?
- **RQ2** Does historical-example retrieval improve behavioral coverage?
- **RQ3** Can engineering taste be measured from historical artifacts + human
  judgment (validated taste metric)?
- **RQ4** Which artifacts/tools drive the gains (ablation)?

## The labeled eval set (the spine)

Git history is a free, labeled, held-out set. For a real historical commit we
already know the test the maintainer wrote. Procedure per commit: take the
pre-commit snapshot + production diff, **hide** the human test, have each arm
generate a test, then score against ground truth + objective execution checks.

## Metrics

| # | Metric | Type | Notes |
|---|--------|------|-------|
| 1 | **Regression detection** | objective | fail-before-fix / pass-after-fix. **Headline.** No judge. |
| 2 | Behavioral similarity | LLM judge | vs. ground-truth test; blinded |
| 3 | Style alignment | hybrid | naming/fixtures/assertions/mocking conventions |
| 4 | **Engineering taste** | judge + human | validated against expert raters (see taste-study.md) |
| 5 | Efficiency | objective | tool-calls + tokens to reach the test |

## Controls (non-negotiable — this is the credibility)

1. **Strong baseline.** Control is Claude with *real* generic tools and a good
   prompt — a Claude-Code-equivalent, not a strawman.
2. **Tool-access confound.** Both arms have tools; only *which* tools differ.
   Isolates semantic vs. generic, not tools vs. no-tools.
3. **Equal budget.** Same max tool-calls and token cap per arm.
4. **Contamination.** Post-cutoff commits only + memorization baseline (can the
   model reproduce the test with no diff? if so, drop the commit).
5. **Judge independence.** Blinded, position-randomized; calibrate against a
   human-rated set; optionally a second judge model.
6. **Stats.** Paired (same commits across arms), mean ± bootstrap CI, per-repo
   reported, n powered up front.

## Success framing

Optimize for an **honest, well-controlled finding**, not a headline number.
"Custom tools help on taste/structure and/or reach quality more efficiently,
here's exactly when and why" is a win even if correctness ties.
