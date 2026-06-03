# Experiment Design

**Positioning:** *Historical Engineering Intelligence for Repository-Aware Test
Generation* — learning maintainer intent from repository evolution. Not "better
test generation" (crowded); the novel axis is mining **historical engineering
decisions + maintainer preferences** as a first-class signal.

## Arms — the ablation ladder (same agent, task, budget; only context/tools differ)

| Arm | What it gets | Role |
|-----|--------------|------|
| **A0 Diff-only** | production diff + the changed file | floor (weak baseline) |
| **A1 Generic tools** | `grep`, `read_file`, `bash` | **strong** Claude-Code-equivalent baseline |
| **A2 Standard repo-RAG** | diff + passively-retrieved related files/tests (similarity) | the *literature competitor* |
| **A3 Treatment** | semantic MCP tools over **historical, quality-ranked** artifacts (`find_related_tests`, `find_helpers`) | repo-aware system under test |

**The thesis is proven only if A3 > A2** — beating diff-only (A0) is easy and
uninteresting; beating *standard RAG* (A2) is the real evidence of
differentiation. A1 ensures we also beat a strong agentic baseline, not a
strawman.

All arms run through one shared agentic loop (`src/atw/agent/loop.py`); the only
difference is the toolset/context in `toolsets.py`. Equal `max_tool_calls` and
token cap (see `config.py`). `k` rollouts per commit per arm for variance.

**Cost-aware sequencing.** Fail-fast = **A1 vs A3 on ~10 commits** (cheapest
meaningful signal; proves pipeline + first direction). Full demo = **A0/A1/A2/A3
on ~100 commits**. A2 (RAG) is essential to the *headline*, but for the very
first free signal we run A1 vs A3 only, then add A2.

## Execution backend & arm wiring

Arms run via **Claude Code headless** (`claude -p --output-format json`) on the
user's **subscription** (no API key). Each commit is explored in a detached **git
worktree at the parent (pre-change) commit**, so the agent never sees the
maintainer's test. Per-arm toolset via `--allowedTools`; A3 additionally mounts
our MCP server via `--mcp-config`:

- **A1** = `{Read, Grep, Glob, Bash}` (generic).
- **A3** = A1 tools **+** `mcp__atw__find_related_tests`, `mcp__atw__find_helpers`
  (measures the *marginal* value of semantic tools over generic exploration).

Same model (`claude-sonnet-4-6`) and same `--max-turns` budget for every arm.
Backend isolated in `agent/loop.py`; switching to the Anthropic API later is a
local change. Full tool-call traces will come from `--output-format stream-json`.

## Task given to the agent

> Given this production diff and the repository, write the test(s) that should
> accompany this change. (The maintainer's actual test is hidden ground truth.)

## Ablations (Phase 2+, wired but not all run in v1)

- **Quality-weighted vs. unweighted retrieval** — does ranking examples by
  anonymized artifact-quality (longevity, low-flake, regression-catch, reuse)
  beat similarity/recency ranking? (RQ4)
- **Active MCP vs. passive injection** — tools-on-demand vs. same context
  stuffed into the prompt.
- **Per-tool add/remove** — which tool carries the signal.

## Outputs logged per (commit, arm, rollout)

- generated test code
- full **tool-call trace** (which tools, args, order, count)
- tokens used, wall-clock
- all five metric scores

Stored under `results/<experiment-id>/`. Figures + traces summarized into
`reports/`.

## Statistical plan

Paired comparison on identical commits. Report mean difference ± 95% bootstrap
CI per metric. Power: pick `n` to detect a plausible effect (start with the
smoke set of ~10, scale to ~100). Per-repo results kept separate to support the
"consistent across repos" claim later.
