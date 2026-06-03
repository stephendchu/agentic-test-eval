# Prior Art & Positioning

Know this cold before claiming novelty — an interviewer *will* ask "how is this
different from X?" Fill in with citations as you read.

## Adjacent work to survey

- **Meta — Automated Unit Test Improvement (TestGen-LLM, 2024):** "assured"
  offline improvement of existing tests. Position vs: we *generate* the test a
  maintainer would write for a *new change*, and study *tool design*, not just
  test improvement.
- **SWE-bench / SWE-agent:** agentic repo tasks with execution-based eval. We
  borrow the execution-grounded evaluation but target test authoring and the
  *generic-vs-semantic-tools* question.
- **Retrieval-augmented code generation / CAT-LM and similar:** retrieval helps
  codegen. We test whether *active tool use* of repo intelligence beats *passive
  retrieval* and beats *generic grep* — and we measure taste.
- **LLM-as-judge literature:** position bias, self-preference; motivates our
  blinded, human-calibrated judging.

## Our differentiated claims (to defend)

1. **Generic vs. semantic tools, controlled** — same agent/budget, only tools
   differ. (Most work compares "tools vs. none" or "model vs. model.")
2. **A validated engineering-taste metric** — taste anchored to expert human
   judgment, not just coverage. (The genuinely uncracked part.)
3. **Repo-as-historical-record** — mining engineering decisions (quality-weighted,
   anonymized) as the retrieval prior.

## The bar that proves differentiation

The literature already shows retrieval + repo context help, so beating a
**diff-only** baseline proves nothing. The headline result must be **Treatment
(A3) > standard repo-RAG (A2)** — evidence that *historical/maintainer-intent*
signal beats ordinary similarity retrieval. Notably, the RAG literature finds
*wrong* retrieval can **hurt** (≈15% degradation), which is itself an argument
for quality-ranked, intent-aware retrieval over naive similarity.
