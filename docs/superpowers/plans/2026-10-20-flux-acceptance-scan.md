# Flux Acceptance Scan Implementation Plan

> **For agentic workers:** use executing-plans or subagent-driven-development.

**Goal:** Run and document a reproducible strict-to-loose reconstruction acceptance scan.

**Architecture:** Extend the existing native closure with whole-run acceptance;
add inference-only acceptance diagnostics and a frozen repeated-experiment driver.
Reuse existing model tuning, correlated replicas and atomic publication.

**Tech Stack:** Python, NumPy, scikit-learn, ROOT/uproot, Matplotlib, Slurm.

**Spec:** docs/superpowers/specs/2026-10-20-flux-acceptance-scan-design.md

## Global Constraints

- Preserve existing uncommitted cleanup and frozen farm results.
- At most 40 allocated cores; one CPU thread for BLAS/model fitting per process.
- Twelve excluded runs never become training, calibration or recovery targets.
- Selection uses no masked truth/asymmetry; recovery is whole-run atomic.
- No-recovery population fixed across thresholds; oracle matched to recovered population.
- Source/configuration/input identities and seeds recorded before jobs run.
- No automatic production adoption or claim of independent new-data confirmation.

## Review Focus

- Rejected masked states accidentally reenter baseline or oracle.
- Selection reads test truth, test coverage, or confirmation results.
- Invalid/missing uncertainty becomes a zero uncertainty or a free acceptance.
- Shared runs across repetitions get counted as independent experiments.
- Array jobs or nested workers allocate more than 40 cores.

### Task 1: Acceptance diagnostics and ladder

Files: create `07_flux_studies/acceptance_scan.py`, corresponding tests.
Consumes: records, prediction metadata, synchronized replica arrays.
Produces: inference-only state diagnostics and nested run-atomic decisions.

- [x] Tests: target-truth mutation cannot affect decisions; strict sets nested;
      a single failed state rejects the run; duplicate/missing inputs fail closed.
- [x] Implement fixed numerical ladder and audited per-state rejection reasons.
- [x] Run focused tests RED then GREEN.

### Task 2: Population-correct observable closure

Files: extend `flux_observable_closure.py`, add `test_acceptance_closure.py`.
Produces: optional `accepted_runs` boundary shared by all methods.

- [x] Tests: fixed no-recovery baseline; matched selected oracle; reject unknown
      accepted IDs; empty acceptance; correct replica subset.
- [x] Filter events, exposures and replacements consistently; preserve old default.
- [x] Run new and old closure tests.

### Task 3: Frozen experiment, reporting and execution

Files: new scan driver, collection/reporting entry point, farm launch script.
Consumes: tasks 1/2, full h80 count cache and production reconstructed files.

- [x] Test outer split isolation, deterministic configuration, missing-result
      reporting, no selection from confirmation, and fail-closed policy ranking.
- [x] Implement protocol/config hashes, per-trial outputs and scan plots.
- [x] Run local full suite, farm focused tests and review.
- [x] Complete isolated farm smoke trial.
- [x] Submit bounded parallel development jobs and record exact IDs/resources.
- [x] Collect completed outputs; run reserved confirmation only after freezing
      selected policy; report failures/no feasible policy honestly.

## Progress

Design accepted in conversation; numerical choices delegated to implementer.
Current branch already isolated from main; preserve working tree. No commits,
pushes or replacement of historical production outputs requested.


Execution ledger:
- Tasks 1/2 implemented with RED→GREEN regression coverage.
- Review P1 fixed: outer reservation excluded from development events and flux,
  not just from ML records (`analysis_runs`).
- Review P2 fixed: collector reads frozen protocol and checks exact schedule;
  decision identity is checked; confirmation validates selection before data.
- Full local suite: 1355 passed, one pre-existing legend warning. Farm:79 passed.
- Frozen source: results/farm-acceptance-launch-20261020/source_manifest.json.
- Main protocol prepared;239 reserved runs,1039 development runs. Smoke job5
  running on4cores. Full array submission waits for successful smoke completion.
- Launcher job6 submitted with `afterok:5`; array also waits for launcher exit
  to preserve the40-core allocation limit. Selection and conditional confirmation
  are automated. Exact current state saved in
  results/farm-acceptance-launch-20261020/launch-status.txt.
- Analyst choices: five nested ladders, ten correlated resamplings,128 replicas,
  conservative worst-point bias screen. No independent certification claimed.
- Follow-up 2026-10-20 12:01 UTC: smoke and launcher succeeded. Array7 tasks0–9
  running on40 total cores; selection8 and confirmation9 pending dependencies.
  Retrieved jobs.json locally. Scientific collection remains pending.
- Final check 2026-10-21 10:21 UTC: all10 development trials complete, no
  incomplete artifacts. No feasible policy. Conditional confirmation correctly
  skipped; no production adoption. Selection, plots and confirmation decision
  fetched locally; protocol/selection hashes verified. Report includes numeric
  results and distinguishes insufficient coverage clusters from incompatibility.
