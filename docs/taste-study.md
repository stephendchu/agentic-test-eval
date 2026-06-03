# Engineering Taste: Validation Study

Measuring "writes tests like this repo's best engineers" is the uncracked
problem and our most differentiated contribution. The goal here is a **taste
metric validated against human judgment**, which stands on its own even if the
tool comparison ties.

## Two complementary sources of taste signal

- **Git history = expert-authored ground truth** — "what the maintainer wrote."
- **Taste page = expert preference data** — "which of two tests experts prefer."
  Git history can't give you this directly; it's what anchors the judge.

## Protocol

1. **Pairs:** show two tests for the same change (e.g. human vs. generated, or
   Control vs. Treatment), source-blinded, position-randomized.
2. **Questions:** Which would you accept in review? Which is more maintainable?
   Which tests behavior rather than implementation?
3. **Raters — the make-or-break:** must be *engineers*. Options, most→least
   rigorous: (a) small recruited panel of 5-10 engineers; (b) open page gated by
   a calibration screen (seeded known-answer pairs; weight raters by agreement);
   (c) open/unqualified — only for coarse engagement signal, NOT ground truth.
4. **Validate the judge:** compute agreement between the LLM-judge and humans
   (Cohen's κ / accuracy). Only report the Taste Score once the judge tracks
   humans well enough.

## Sequencing

- **v1:** minimal internal rating tool + a handful of expert raters, *after* the
  first regression-detection graph exists. Just enough to validate the judge.
- **Phase 3:** grow into the polished "taste CAPTCHA" — low-friction, calibrated,
  potential community/benchmark/SaaS artifact.

Storage: ratings in a small local DB (`taste-ratings.db`, gitignored); the app
lives in `src/atw/taste/`, served via `scripts/serve_taste_page.py`.
