# Roadmap & Status

Strategic plan (full rationale): `~/.claude/plans/deep-conjuring-pnueli.md`.

| Phase | What | Status |
|-------|------|--------|
| 0 | Foundation: skeleton, config, docs, deps, smoke test | ✅ done |
| 1 | Commit extraction (post-cutoff, filtered) → labeled dataset (89 dbt-core commits) | ✅ done |
| 2 | Test-to-code graph → retrieval core → quality scoring → MCP server | ✅ done, validated on real commits |
| 3 | Agentic loop; arms A1 (generic) vs A3 (semantic MCP); traces | 🔄 in progress |
| 4 | Sandbox runner → metrics (regression→behavioral→style→efficiency) → stats | todo |
| 5 | Run experiment over slice → graphs + traces → writeup | todo |
| 6 | Taste validation tool (expert-rated) → validate judge | todo |

## Execution backend (decided 2026-05-31)

**Free first, bank later.** The agent arms run through **Claude Code headless
(`claude -p`) on the user's subscription** — no API key, no per-token billing.
Verified working with `--mcp-config` (mounts our tool server = A3) and
`--allowedTools` (per-arm toolset). The model backend is isolated in
`agent/loop.py` so flipping to the Anthropic API later (for throughput/scale) is
a local change.

Cost of free: **speed and scale, not validity.** Same model held constant across
arms ⇒ the comparison stays scientifically valid; we just run serially under
subscription rate limits, so free realistically covers the ~10-commit fail-fast,
not the full 100-commit powered run.

## Sequencing (frugal fail-fast)

1. **A1 vs A3 on ~10 focused commits, free.** Does semantic tooling beat generic
   grep at all? (No PyTorch, no API yet.)
2. If A3 shows an edge → add **A2 (strong RAG, sentence-transformers/PyTorch)** as
   the real bar, scale toward ~100 commits, and *then* weigh the API for throughput.

## Apparatus bug found & fixed (2026-05-31) — prior numbers VOID

First "result" (A3 76.4 vs A1 71.3) was **invalid** and has been deleted.
Tool-call traces revealed **A3 never called the MCP tools** — `bypassPermissions`
auto-approved *all* default tools, so A1 and A3 were the *same* all-tools agent,
and a spawned subagent (`Task`) escaped restriction entirely. Caught for a few
dollars of quota; this is why traces + a controlled apparatus come before scale.

**Fix (validated):** `--permission-mode default` + explicit `--disallowedTools`
(block grep/bash/glob/subagent/ToolSearch per arm). A3 now does
`find_related_tests → find_helpers → Read → write` — the intended semantic flow;
generic discovery tools are blocked. A1 = generic only, MCP blocked.

**Open apparatus item:** `--max-turns` is a soft cap (saw 30 vs 25) — log actual
turns/tool-calls per run and keep the flag equal across arms; revisit if budgets
diverge materially.

**First VALID slice (n=3, arms confirmed differentiated):** A1 mean 77.4 vs A3
85.0 (+7.6); A3 won 1 / tied 1 / **lost 1**. Traces confirm A1 used grep/bash
(0 MCP) and A3 used `find_related_tests`+`find_helpers` (0 grep). Real signal,
n=3 — not yet evidence.

**Metric-bias finding (from the A3 loss):** the whole 5-pt loss was the `imports`
component — A1 spuriously imported `jinja2`/`msgpack` that the maintainer's *whole
file* imports (for other tests), while A3 wrote clean minimal imports. Comparing a
*focused* generated test to a *whole multi-test file* rewards bloated imports.
**Fix (next):** ground truth = maintainer's added test fn(s) + the file's import
block, OR score imports by precision (no penalty for omitting irrelevant
file-level imports). Document the change as a pre-declared correction, not
post-hoc tuning to favor A3.

**Apparatus leak #2 fixed:** `Skill`/`ToolSearch` also slipped past
`--permission-mode default` (it doesn't deny unlisted tools). Now deny-by-default:
block every known tool not explicitly allowed by the arm.

**Metric correction applied (imports/fixtures → precision).** Re-scored n=3: the
spurious A3 loss (61378e93) became a tie (both 93.3); means A1 91.2 / A3 97.8;
A3 now 1W/2T/0L. BUT precision is lenient → scores now **cluster 91–100 (ceiling
effect)**, so the structural metric is losing discriminative power. Implication:
the **LLM-judge behavioral metric + objective regression metric must carry the
headline**; structural alignment becomes a supporting signal. Remaining
whole-file bias in the `structure` component is a known TODO (fix via
added-function-level ground truth).

**Still required before any claim:** real n (~30+); the metric-bias fix above;
objective control (does the test run/pass) for "aligned *without* losing
correctness".

**Framing decision:** headline = **Maintainer-Intent Alignment** (novel, less
crowded), but the objective metric stays as the *control*, not dropped — even the
alignment thesis needs "pass rate unchanged" to be credible, which requires the
execution harness.

## RESULT — first complete slice (failfast3, n=7) — thesis NOT supported

Behavioral judge (discriminative): **A1 grep preferred 4/7, A3 semantic 2/7, 1
tie** — A3 win-rate 0.286, Wilson CI [0.08, 0.64]. Structural alignment: mean
Δ(A3−A1) = **−8.8**, CI [−28.6, +5.3]. A3 also had 1 total failure (a5b77258) and
over-explores (36–41 turns, up to $1.40/run). Nothing significant (n=7), but both
point estimates favor **A1**, and there is **no evidence** for the thesis.

**Likely mechanism (the real finding):** the model ignores semantic tools when
grep is available (0 MCP calls), and when forced onto them (grep removed) it does
*worse* — current frontier models' native grep beats "find related tests"
pointers. Bar for a useful coding-agent tool is higher than surfacing files.

**Fork:** (1) report as rigorous negative result (Anthropic-relevant tool-design
finding); (2) iterate tools to return quality-ranked example test *code* + intent
history (value grep can't give) and test as *augmentation*; (3) more n (likely
confirms null). Decision pending with user.

## The verdict depends on the metric (key finding, 2026-06-01)

Re-scored A1(grep) vs A3(semantic) on three metrics over existing results:
- **Style-mimicry alignment:** A3 ≤ A1 (Δ −8.8). Against thesis.
- **Pairwise behavioral judge:** A1 preferred 4/7, A3 2/7. Against thesis.
- **Resolvability** (Stephen's `sthmcp`-style: does the test reference REAL repo
  things): A3 > A1, **+9.2 after de-biasing** (CI [−0.44, 26.3], includes 0 at
  n=9). *Only* metric favoring A3. Mechanism: A3's `find_helpers` surfaces real
  fixtures so it hallucinates fewer; A1 grep invents fixtures (`expected`,
  `version`). Caveat found & fixed: naive fixtures_real penalized dbt's valid
  external `project` fixture — corrected by checking repo-wide `def name(`.

**Contradiction to resolve:** A3 is *more structurally real* yet *less preferred*
by the holistic judge. Stephen's production **taste rubric** (helper-fit, TODOs,
noise, conciseness, drop-in readiness) should break this down — likely A3 wins
"drop-in readiness" (fewer hallucinations) but loses "helper-fit-for-scenario".
Adopt that rubric next. Proper fixture/helper realness ultimately needs the real
test env (Stephen's sthmcp has it; we approximate).

**Validated by Stephen's production stack:** structural-not-behavioral focus
(skip execution harness); judge-based grading; findtests returns "working
examples to adapt" (matches our enriched tool); k=3 sampling (we use k=1).

## Conformity / taste result (2026-06-01) — A3 not more native either

Human-free indistinguishability eval (judge tells generated from real merged
test; lower distinguish-rate = more native): **A1 0.375, A3 0.667.** A1 (grep) is
MORE native; the taste/adoption metric *also* favors grep. A1 below 0.5 (below
chance) hints Claude+grep tests are near-indistinguishable from real — but
confounded (compared vs maintainer diff *fragment* vs AI *complete* test; relative
result robust, absolute needs full-test comparison).

**Convergent conclusion across 4 metrics:** semantic tools (A3) are never the
clear winner — A1 wins style/preference/taste, A3 only +9.2 n.s. on resolvability.
Stop hunting a 5th metric (= p-hacking). The honest deliverable is a **rigorous
multi-metric NEGATIVE result on custom retrieval tools + a human-free taste-eval
methodology** (revealed preference from git merges). Consolidate into the writeup.

## Guiding constraints

- **Time-to-first-result:** get one defensible result on a ~10-commit slice
  before building the full matrix.
- **Strong baseline first:** A1 (and later A2 RAG) must be genuinely good — the
  headline bar is **A3 > A2**, never A3 > a strawman.
- **Win-or-draw framing:** beat on quality, or match at lower cost (efficiency),
  or deliver the validated taste metric — any of these is a result.

---

## v2 — Deletion protocol (2026-06-11)

### Why v1 was null: the test file was present

v1's worktree contained the stale version of the target test file (the eval
commit *modified* it; the parent still had yesterday's copy). Grep located it in
one hop. Both arms copied its location, imports, and fixture style trivially. The
structural alignment metric hit a 91–100 ceiling. The semantic tool had no headroom
to win — the question it answers ("where do tests for this code live?") was already
answered by the filesystem.

The same deletion methodology was applied on the user's private work codebase and
produced dramatic improvement. v2 tests whether the methodology difference explains
the internal-positive / open-source-null discrepancy.

### Three latent validity bugs found and fixed

**Bug A (ground-truth source leakage to A3, v1 retroactive caveat):**
`src/atw/mcp/tools.py` set `Toolbox.root` to the canonical clone at HEAD, not the
worktree. `find_related_tests` could therefore serve the maintainer's *post-change*
test source for top-ranked entries that landed in `source_k=2`. v1's A3 alignment
numbers may have been inflated by this. Fix: `ATW_TOOL_ROOT` env var repoints the
MCP subprocess to the worktree; `find_related_tests` now returns `exists: false`
with no `source` for deleted/missing files, promoting to the next existing exemplar.

**Bug B (git resurrection for A1):** git worktrees link back to the shared object
DB via a `.git` file. `git show <sha>:<path>` inside the worktree could resurrect
any deleted file, including the eval commit's test. Fix: `.git` is unlinked after
`worktree add`. Both arms get the stripped worktree identically.

**Bug C (is_test_path misclassification):** `is_test_path` classified
`core/dbt/artifacts/resources/v1/singular_test.py` and `core/dbt/tests/util.py`
as test files (verified in `data/commits/dbt-core/index.json`, sha 317b050f).
Deleting these would delete production code. Fix: `deletable_test_file` predicate
requires `tests/` prefix AND `test_*.py`/`*_test.py` naming, excluding conftest.py
and `__init__.py`.

### v2 experimental design

| Parameter | Value |
|-----------|-------|
| Arms | A1 (Read/Grep/Glob/Bash) vs **A2** (same + MCP mounted) |
| Why A2 not A3 | Mirrors work-codebase study: MCP on/off toggle, both arms have grep |
| Protocol | Delete all maintainer-touched test files from worktree; strip `.git` |
| Repos | dbt-core (37 qualifying commits → n=25) + pydantic (13 qualifying → n=13) |
| Selection | `select_commits_v2`: all test files must be safely deletable |
| Post-cutoff | 2026-02-01 (unchanged from v1) |
| Runs | 1 per (commit, arm); resume-safe via `--exp-id` |
| New metric | Location-discovery: `# target file:` declared path + GT path surfaced in trace |
| Voluntary adoption | Count A2 MCP calls from traces — key mechanism metric |

### Smoke gate results (2026-06-11)

**dbt-core smoke (n=1, sha 6f89ae63):**
- Deletion confirmed: `tests/unit/test_events.py` deleted from both worktrees
- A2 made 1 voluntary MCP call to `find_related_tests`
- MCP returned `exists: false` for deleted file with no source leakage; promoted to
  next existing exemplar (`tests/functional/deprecations/test_deprecations.py`)
- Both arms produced `# target file:` comment; both declared `tests/unit/task/test_printer.py`
- A1: 0 MCP calls; no successful git commands observed (git stripped)
- Apparatus confirmed clean: all smoke-gate checks pass ✅

**pydantic smoke (n=1, sha 4ec2d8e3):**
- Deletion confirmed: `tests/test_aliases.py` deleted
- A2 made 0 MCP calls — pydantic's flat `tests/` with standard pytest conventions
  gives grep enough signal from sibling files; findtest not needed to navigate
- Note: max_turns=70 required for pydantic (test files 3–4× larger than dbt-core)
- Both arms declared correct `# target file: tests/test_aliases.py`

**Pydantic 0-adoption pre-finding:** pydantic's test structure is navigable by
directory convention alone; dbt-core's custom fixture ecosystem is where findtest
has theoretical edge. This codebase-dependence of adoption rate may be a core
contribution: findtest adds value when fixture/convention complexity exceeds what
grep + directory inference can surface.

### Run commands

```bash
# Full runs (run overnight, resume-safe)
ATW_REPO=dbt-core .venv/bin/python scripts/run_experiment.py \
  --protocol v2 --n 25 --exp-id v2-dbt-core --arms A1 A2

ATW_REPO=pydantic .venv/bin/python scripts/run_experiment.py \
  --protocol v2 --n 13 --exp-id v2-pydantic --arms A1 A2 --max-turns 70

# Post-run analysis
ATW_REPO=<repo> .venv/bin/python scripts/run_judge.py --exp-id v2-<repo>
ATW_REPO=<repo> .venv/bin/python scripts/score_location.py --exp-id v2-<repo>
.venv/bin/python scripts/analyze_v2.py --exp-ids v2-dbt-core v2-pydantic
```

See `docs/v2-runbook.md` for the complete self-contained execution guide.
