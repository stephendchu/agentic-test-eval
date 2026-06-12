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

---

## v2 Protocol: Test-File Deletion

### Motivation

v1 left the maintainer's prior test file in the worktree. Grep trivially located
it; both arms copied its style. Structural alignment hit a 91–100 ceiling and no
meaningful contrast was measurable. The **deletion protocol** removes the target
test file(s) before each agent run, making the retrieval question real: the agent
must infer where tests belong, what fixtures are in scope, and what conventions
apply — from the codebase structure alone, not from a ready-made file.

### Deletion procedure

For each eval item:
1. Identify the set of test files modified by the maintainer's commit
   (records in `data/commits/<repo>/<sha>.json → test_files`).
2. Apply `deletable_test_file` predicate: path must start with `tests/`, basename
   must match `test_*.py` / `*_test.py`, must not be `conftest.py` or `__init__.py`.
   Commits with any non-deletable test file are excluded from `select_commits_v2`.
3. After `git worktree add` at the parent SHA, delete each qualifying test file
   (`Path.unlink()`). Record which files actually existed at parent in
   `deleted_existing` (files added by the eval commit won't be present at parent;
   this is the harder test case and is a covariate).
4. Unlink the worktree's `.git` pointer file to sever the shared git object DB.
   This prevents any arm from using `git show` to retrieve deleted content.
5. Both arms receive an identical deleted worktree. The deletion is not a
   treatment — it is a precondition applied to both arms equally.

### Arms for v2

| Arm | Tools | MCP |
|-----|-------|-----|
| A1 (control) | Read, Grep, Glob, Bash | not mounted |
| A2 (treatment) | Read, Grep, Glob, Bash | mounted (voluntary use) |

A2 mirrors the work-codebase study's on/off toggle. Both arms have full grep;
A2 additionally has the semantic tools available but is not forced to use them.
**Voluntary adoption rate** (fraction of A2 runs with ≥1 MCP call) is a
first-class mechanism metric: if deletion starves grep and A2 adopts the MCP,
that directly confirms the hypothesized mechanism.

### Disclosed design decisions

**Graph built once at HEAD, not per-item:** The RepoGraph encodes co-modification
history through all commits, including post-eval ones. This means `find_related_tests`
has a small amount of future information in its *ranking* — it knows that the
deleted test file co-changed with the target production file in the future. This is
acceptable because: (a) returning the deleted file's *path* is the tool's stated
thesis (historical knowledge); (b) its *content* is blocked (the worktree has no
source, and `ATW_TOOL_ROOT` repoints the server to the worktree so the file is
genuinely absent); (c) per-item graph rebuilds would be prohibitively expensive
(~3000-commit scan × 50 items) and would break paired comparability. This is
disclosed, not hidden.

**Path-fair, content-blocked rule:** `find_related_tests` may return the deleted
file's path with `"exists": false` and a note explaining its absence. Source code
is never served for non-existent files. The tool's value claim is precisely that
it surfaces relevant paths from history — returning the path even when the file is
absent is the thesis in action.

**Prompt delta (v1 → v2):** `TASK_V2` adds two sentences: (a) "Version-control
history is not available in this working directory" — prevents asymmetric turn
waste when the agent tries git commands that now fail silently; (b) first line of
the code block must be `# target file: <path>` — enables the location-discovery
metric. The task instruction ("study how this repository tests similar code")
is unchanged. This prompt is held constant across both arms within v2.

### New metric: location discovery

Because arms have no Write tool, the agent cannot create a file; it only outputs
a code block. The `# target file:` first-line comment is the only record of the
agent's test-location decision. Scoring:
- `exact_match`: declared path equals any ground-truth test file (normalized)
- `dir_match`: declared path is in the correct directory
- `basename_match`: declared filename matches any ground-truth test basename
- `surfaced`: any ground-truth path string appears anywhere in the trace (tool
  inputs or results), indicating the agent encountered it via retrieval

This metric answers the mechanism question: did findtest actually guide the agent
to the right location, or did both arms succeed/fail equally?
