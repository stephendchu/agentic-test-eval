# v2 Study Runbook: Test-File Deletion Protocol

This document is self-contained. A fresh Claude Code session with no prior context
can execute the full v2 study by following these steps in order.

## What v2 tests

v1 compared A1 (grep baseline) vs A3 (MCP-only, grep blocked) on dbt-core, n=7.
Result: null — grep preferred 4/7; semantic MCP 2/7.

**v2 hypothesis:** v1's null was caused by the target test file still being present
in the worktree. Grep trivially found it in one hop; the semantic tool had no edge.
The fix: delete the test file before each run. Now grep has nothing to find; the
agent must infer test location and conventions from the codebase structure.

This methodology produced dramatic improvement on the user's private work codebase.
v2 replicates it on open-source repos (dbt-core, pydantic) to test generalization.

**Arms:**
- A1 (MCP off): `Read, Grep, Glob, Bash` — full grep, no MCP
- A2 (MCP on):  `Read, Grep, Glob, Bash` + `find_related_tests` + `find_helpers`

Both arms get the same deleted worktree. A2 has the MCP mounted but is not forced
to use it — voluntary adoption when grep starves is the mechanism claim.

## Prerequisites

```bash
# Verify venv and project
cd /mnt/c/Users/Steph/agentic-test-writer
.venv/bin/python -c "import atw; print('ok')"

# Verify dbt-core graph exists
ls data/graph/dbt-core/graph.json
```

If the graph is missing, build it first:
```bash
.venv/bin/python scripts/build_graph.py
```

## ATW_REPO convention

Every command is prefixed with `ATW_REPO=<name>` to select the target repo.
Default is `dbt-core`. All derived data paths (`data/commits/<name>`,
`data/graph/<name>`, results) are namespaced by repo name.

## Phase 0 — Feasibility check (run once before starting)

```bash
# Count qualifying dbt-core commits
ATW_REPO=dbt-core .venv/bin/python - << 'EOF'
import json, re, os
idx = json.load(open("data/commits/dbt-core/index.json"))
def deletable(p):
    if not p.startswith("tests/"): return False
    b = os.path.basename(p)
    if b in ("conftest.py", "__init__.py"): return False
    return bool(re.match(r"(test_.+|.+_test)\.py$", b))
foc = [r for r in idx if len(r["prod_files"]) <= 2]
ok  = [r for r in foc if r.get("test_files") and all(deletable(p) for p in r["test_files"])]
print(f"total={len(idx)} focused={len(foc)} qualifying={len(ok)}")
EOF
```
Need qualifying ≥ 20. If short, relax by passing `--max-prod-files 3` to run_experiment.

## Phase 1 — Smoke gate (1 item, both arms, ~10 min)

Run a single item to verify the apparatus before committing to 25×2 runs.

```bash
ATW_REPO=dbt-core .venv/bin/python scripts/run_experiment.py \
  --protocol v2 --n 1 --exp-id v2-smoke-dbt --arms A1 A2
```

**After the smoke run, inspect traces manually:**

```bash
SMOKE_SHA=$(ls results/v2-smoke-dbt/ | grep -v exp_meta | head -1)
echo "Smoke SHA: $SMOKE_SHA"

# A1: confirm no deleted-file content and no successful git commands
cat results/v2-smoke-dbt/$SMOKE_SHA/A1.json | python3 -m json.tool | grep -E "ok|tool_calls|mcp"

# A2: confirm MCP was called at least once (voluntary adoption)
cat results/v2-smoke-dbt/$SMOKE_SHA/A2.json | python3 -m json.tool | grep -E "ok|mcp_tool_calls"

# A2 stream: confirm find_related_tests returned exists:false for deleted file
grep "exists" results/v2-smoke-dbt/$SMOKE_SHA/A2.stream.jsonl | head -5

# Both: confirm target file comment is present
grep "target file" results/v2-smoke-dbt/$SMOKE_SHA/A1.json
grep "target file" results/v2-smoke-dbt/$SMOKE_SHA/A2.json
```

**Smoke gate checklist (all must pass before full run):**
- [ ] Both A1.json and A2.json have `"ok": true`
- [ ] A2.json has `mcp_tool_calls >= 1` (agent reached for the tool)
- [ ] A2.stream.jsonl contains `"exists": false` (MCP served deleted path correctly, no source)
- [ ] Neither stream contains content of the deleted test file (check by grepping a test function name from the original)
- [ ] Both outputs have `# target file:` comment in test_code
- [ ] A1: no successful git log/show output in trace (git stripped)

If A2 makes 0 MCP calls: check `docs/apparatus-notes.md` for the known v1 issue
(model ignores MCP when grep is available at parent commit). With deletion, grep
should starve on the target file — if adoption is still 0, the deletion may not
have happened; inspect `deleted_existing` in A2.json.

## Phase 2 — Pydantic onboarding

```bash
# Clone and extract commits (auto-clones if not present)
ATW_REPO=pydantic .venv/bin/python scripts/extract_commits.py --limit 100

# Check qualifying count
ATW_REPO=pydantic .venv/bin/python - << 'EOF'
import json, re, os
idx = json.load(open("data/commits/pydantic/index.json"))
def deletable(p):
    if not p.startswith("tests/"): return False
    b = os.path.basename(p)
    if b in ("conftest.py", "__init__.py"): return False
    return bool(re.match(r"(test_.+|.+_test)\.py$", b))
foc = [r for r in idx if len(r["prod_files"]) <= 2]
ok  = [r for r in foc if r.get("test_files") and all(deletable(p) for p in r["test_files"])]
print(f"total={len(idx)} focused={len(foc)} qualifying={len(ok)}")
EOF

# Build graph
ATW_REPO=pydantic .venv/bin/python scripts/build_graph.py --max-history 3000

# Sanity check
ATW_REPO=pydantic .venv/bin/python - << 'EOF'
from atw.mcp.tools import Toolbox
tb = Toolbox()
print("root:", tb.root)
# Pick any pydantic prod file to verify retrieval works
result = tb.find_related_tests(["pydantic/main.py"])
print("top result:", result["results"][0]["path"] if result["results"] else "none")
EOF

# Pydantic smoke gate (same checklist as dbt-core)
ATW_REPO=pydantic .venv/bin/python scripts/run_experiment.py \
  --protocol v2 --n 1 --exp-id v2-smoke-pydantic --arms A1 A2
```

If pydantic yields < 10 qualifying commits, proceed with what exists and note it
in the results writeup. Do NOT loosen the deletable predicate.

## Phase 3 — Full runs (~8–10 h per repo, run overnight)

```bash
# dbt-core (run first; resume-safe)
ATW_REPO=dbt-core .venv/bin/python scripts/run_experiment.py \
  --protocol v2 --n 25 --exp-id v2-dbt-core --arms A1 A2

# pydantic (after dbt-core completes or in parallel in a separate terminal)
ATW_REPO=pydantic .venv/bin/python scripts/run_experiment.py \
  --protocol v2 --n 25 --exp-id v2-pydantic --arms A1 A2
```

**If rate-limited mid-run:** re-run the exact same command with the same `--exp-id`.
The harness resumes from where it stopped (settled = succeeded or 2 attempts).

**Monitor progress:**
```bash
# Count completed items
ls results/v2-dbt-core/*/A1.json 2>/dev/null | wc -l
ls results/v2-dbt-core/*/A2.json 2>/dev/null | wc -l
```

## Phase 4 — Judge + analysis

```bash
# Run behavioral judge (blinded pairwise; uses Anthropic API key)
ATW_REPO=dbt-core .venv/bin/python scripts/run_judge.py --exp-id v2-dbt-core
ATW_REPO=pydantic .venv/bin/python scripts/run_judge.py --exp-id v2-pydantic

# Score location-discovery metric
ATW_REPO=dbt-core .venv/bin/python scripts/score_location.py --exp-id v2-dbt-core
ATW_REPO=pydantic .venv/bin/python scripts/score_location.py --exp-id v2-pydantic

# Make report (alignment figures)
ATW_REPO=dbt-core .venv/bin/python scripts/make_report.py --exp-id v2-dbt-core
ATW_REPO=pydantic .venv/bin/python scripts/make_report.py --exp-id v2-pydantic

# v2-specific analysis (paired stats + mechanism table)
.venv/bin/python scripts/analyze_v2.py \
  --exp-ids v2-dbt-core v2-pydantic \
  --v1-exp-id <your-v1-exp-id-here>
```

## Phase 5 — Interpret results

**Headline question:** Did deletion flip the judge result vs v1?
- v1 baseline: A1 (grep) preferred 4/7; A3 (semantic) 2/7; win-rate 0.286, CI [0.08, 0.64]
- v2 target: A2 (MCP on) win-rate > 0.5, CI excludes 0.5

**Mechanism table to check:**
| Metric | A1 (grep, no MCP) | A2 (grep + MCP) |
|--------|-------------------|------------------|
| Judge win-rate | — | — |
| Δ alignment (A2−A1) | — | — |
| Exact location match | — | — |
| GT path surfaced in trace | — | — |
| Avg MCP calls per run | 0 | ≥? |

If A2 adoption rate ≈ 0 AND A2 ≈ A1: the deletion didn't force MCP use —
investigate whether graph.related_tests returns results for the deleted file's
prod file. Check `item_meta.json` for `existed_at_parent` and `deleted_existing`.

If A2 adoption rate > 0 BUT A2 ≈ A1: MCP is being called but not helping —
possible that the model uses the path hint but still can't locate fixtures
correctly. Look at `dir_match` vs `exact_match` for insight.

## Where results live

```
results/
  v2-dbt-core/
    exp_meta.json              # provenance
    <sha>/
      item_meta.json           # covariates (first_seen, created_post_cutoff)
      A1.json                  # result + alignment + trace
      A1.stream.jsonl          # raw stream-json
      A1.location.json         # location metric scores
      A2.json
      A2.stream.jsonl
      A2.location.json
      behavioral.json          # judge verdict (after run_judge)
```

## Novelty disclosure

The deletion-as-eval-methodology is not present in published LLM test-generation
benchmarks (TestGenEval, SWT-Bench, TestExplora as of June 2026). Those benchmarks
evaluate models on new code; this study evaluates a retrieval *tool* on existing
code with the ground-truth test deliberately withheld to create a fair comparison.
The voluntary-adoption metric (does the agent reach for the semantic tool when grep
starves?) is also novel as a mechanistic ablation in agentic tool-use evaluation.
