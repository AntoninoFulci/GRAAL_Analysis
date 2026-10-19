# Native flux recovery implementation plan

> **For agentic workers:** Use superpowers:subagent-driven-development or superpowers:executing-plans task by task.

**Goal:** Validate native-strip neural reconstruction and whether recovered runs improve total measurement precision.

**Architecture:** Extend ingestion and estimator factory; reuse isolated neighbor validation and existing observable extraction. New uncertainty module owns synchronized replicas; new study entry point coordinates existing components.

**Tech Stack:** NumPy, PyTorch, sklearn baselines, uproot, existing ROOT-compatible extraction.

**Spec:** docs/superpowers/specs/2026-10-19-native-flux-recovery-design.md

## Global constraints

Local only; preserve production sources and all unrelated working changes. No commits requested. Existing checkout contains required uncommitted prior stages. Exact budgets and exclusions are defined in the spec. Never tune on test truth.

## Review focus

Target truth/axes leaking into features; bootstrap states desynchronized; failed replica fits silently discarded; unsupported missing calibrations; apparent precision gain ignoring reconstruction uncertainty.

### Task 1: Native strip representation

- [x] Extend calibrated_data.py with representation='native_strip' while retaining legacy default; validate axes and preserve independent axis metadata.
- [x] Add strip audit and native identity/leakage tests; inspect actual source mappings.

### Task 2: PyTorch shape estimators

- [x] Add neural_models.py and factory/grid integration in neighbor_models.py, training-only preprocessing, CPU deterministic seeds, multiple initializations.
- [x] Test positivity, shape, reproducibility, input validation and unchanged hybrid integral.

### Task 3: Observable recovery comparison

- [x] Extend flux_observable_closure.py for native_strip representation and synchronized flux replicas.
- [x] Compare without_recovery/native_truth/model extractions, preserve denominators, export covariance and per-point total uncertainty/gates.
- [x] Test event/exposure removal together, native identity, replica failures and total-precision accounting.

### Task 4: Uncertainty and integration

- [x] Add block bootstrap/refitting and validation-only correlated residual replicas in flux_uncertainty.py; test isolation and synchronization.
- [x] Add study_native_recovery.py, execute local real-data comparison and diagnostic plots in a new output directory.
- [x] Review changes, run relevant tests, inspect artifacts and write Italian report with terminology definitions and limitations.

## Progress

Implementation, local runs, review and report completed. Review fixed stale original-donor clustering in bootstrap, vacuous NaN-only tests, JSON list candidate groups, and ambiguous total-error wording. Complete suite: 1265 passed, one pre-existing legend warning; subsequent coverage-diagnostic tests and 15 closure tests passed. Realistic native grid and 64-replica propagation published in results/native-flux-recovery-20261019; complementary 3-run benchmark published in results/native-flux-three-block-20261019 (159 spectra). Input hashes unchanged in both studies. Diagnostic PDFs inspected; Italian report: docs/reports/2026-10-19-native-flux-recovery.md. Native representation shift zero; conditional median precision gain 9–11%. Ratio-fit outlier traced to existing p=.01 model-selection discontinuity, without changing the estimator. Production adoption remains unvalidated pending independent bias/coverage, normalization discontinuity checks, candidate uncertainty and independent missing-state energy calibration.
