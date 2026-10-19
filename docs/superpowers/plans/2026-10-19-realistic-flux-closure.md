# Realistic flux closure implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans. User authorized execution in chat.

**Goal:** Exclude eight explicit runs; inventory real gaps, mimic supported gaps,
compare hybrid models and evaluate observable closure, preserving production.
**Architecture:** Extend shared quality policy and neighbor evaluator; new focused
study orchestration and closure adapter reuse existing estimators and publication.
**Spec:** ../specs/2026-10-19-realistic-flux-closure-design.md

- [x] Quality worker: extend policy validation for explicit user exclusions with
  prior benchmark evidence, update JSON, test all downstream shared boundaries.
  Own run_quality.py/config/tests only, no unrelated observable changes.
- [x] Model worker: optional validated explicit split plan in evaluate_neighbors;
  candidate predictions for targets without truth using frozen training/grid
  selections, no holdout truth; tests leakage, masks, gap and zero shape.
  Own neighbor_validation.py and dedicated tests only; coordinate API.
- [x] Closure worker: adapter from common grid to known strip axes; roundtrip
  truth control; same event/exposure universe and fixed binning; paired comparisons
  with existing extraction engine. Own new flux_observable_closure.py and tests.
- [x] Main: gap inventory and deterministic realistic split/pattern construction,
  CLI/report/plots, real execution, candidate artifacts and scientific gate.
- [x] Test new boundaries first, watch failures then implementation; focused tests
  per task, independent whole change review, full suite, verify artifact hashes
  and plots. Record blockers and supported scope; no production overwrite.

Ruling: retain current codex/dalitz-completion checkout with prior uncommitted
work; new worktree would omit active implementation. Preserve unrelated plot edits.
Ruling: no fresh independent h80 supplied; current-period outputs explicitly
remain development validation. Frozen quality decisions precede new fitting.
Interfaces: model worker supplies explicit split assignments and candidate API;
main supplies records/counts/targets; closure consumes records/predictions and
known target strip axes only after prediction. No ownership conflicts.

Execution receipt: results/realistic-flux-closure-20261019; 271 clean runs,
813 spectra; 842 global missing states, 10 with local counts and donor brackets;
55 masked test states; 6 supported candidate states in 5 runs, 18 method rows.
Closure completed for both periods with 168/30 shared estimable points (both
estimators combined). No production adoption: covariance/coverage, independent
confirmation and native missing-state strip axes unresolved. Four low-count
targets withheld from candidate artifacts, not added to quality exclusions.

Review fixes: preserve full donor-bounded windows including empty masks for
unavailable adjacent runs; validate exact left/right offsets; require complete
closure target coverage; filter unsupported candidate spectra. Regression tests
observed failing then passing. Final full suite: 1232 passed, one preexisting
empty-legend warning, 161.70s. Inputs unchanged, all eight exclusions verified,
PDFs/NPZ/indexes checked and plots inspected. Report:
docs/reports/2026-10-19-realistic-flux-closure.md.
