# Full-statistics farm flux recovery implementation plan

> Execute inline with superpowers:executing-plans; one final independent review.

**Goal:** Launch the existing native comparison on all proton periods in the farm's complete campaign and reconstruct factor-100 anomalous runs as missing.

**Architecture:** Reuse the existing native driver, models, uncertainty and extraction. Add a preparation entry point that counts the campaign h80 files, freezes a campaign-specific quality policy, and builds missing-state geometry. Pass that policy explicitly into study ingestion and closure. Extend inventory with an explicit set of excluded runs to reconstruct in all states. Production defaults stay unchanged.

**Tech Stack:** Existing Python, ROOT/uproot, PyTorch, sklearn and Slurm on trimax.

**Spec:** User authorization of 19 October: full-statistics farm study, retain model comparison, treat factor-100 anomalous runs as missing. Existing native design and numerical budgets remain applicable.

## Constraints and rulings

- Preserve existing local and farm work; no commits or pushes. Use an isolated source snapshot and new farm output paths.
- Full statistics means the 13 proton periods of production_full_proton_20261016T092133Z, with its own h80, calibrated flux and UV/VIS reconstructed events.
- Do not mix historical h80 counts with the current production h80 convention (events without tagger removed).
- Apply inclusive ratio bounds [0.01, 100] per period/state. A violation excludes all states of the run from truth, training, donors and closure. Preserve all eight prior exclusions.
- Recover the three previously diagnosed factor-100 runs plus newly diagnosed factor-100 runs, in all states. The five user-excluded benchmark failures remain excluded separately, not reclassified as factor-100 cases.
- No anomalous measured flux used as truth or model input; axes retained only as separate calibration metadata if present. No automatic adoption or model selection from farm test results.
- Repeat realistic-gap validation and the three-run-block benchmark, with the same model grids, 64 replicas, seed definitions and diagnostic outputs. Publish unsupported candidates with reasons rather than silently extrapolating.
- Farm jobs may be long-running; report exact submission IDs, durable logs and verified progress. Do not call a running campaign complete.

## Review focus

Policy propagation into both exposure and event selection; whole-run donor exclusion; stale local counts/geometry reused on farm; unsupported target prediction loss; actual data paths and source identity.

## Tasks

- [x] Add tests for diagnostic records including incomplete/excluded runs, explicit campaign policy, and anomalous whole-run candidate inventory; observe failures.
- [x] Extend calibrated_data and realistic_gaps with backward-compatible arguments. Add prepare_native_recovery to count, freeze policy, audit and save cache/design/inventory.
- [x] Extend native driver and closure for campaign policy and transparent candidate support diagnostics. Keep defaults unchanged. Test isolation and policy enforcement.
- [x] Run focused tests; independent review; resolve material issues and run full suite.
- [x] Transfer isolated source snapshot, create isolated neural environment, verify ROOT and packages; submit preparation plus dependent study/stress jobs to Slurm, with resource limits and exit logs.
- [x] Verify live execution, record counts/anomalies when available, update runbook/report and exact monitoring instructions.

## Progress

Farm accessible via SSH. Full campaign contains 13 h80 files (199 GiB), UV/VIS reconstructions and calibrated flux. Scheduler LocalQ available. Existing farm checkout has unrelated plotting edits and will not be overwritten.

Implementation and launch completed. Local full suite: 1271 passed with one preexisting warning; two subsequently added tests passed. Farm: 25 targeted tests passed. Review found unavailable neural fit diagnostics could crash plotting; regression reproduced and fixed. Stress benchmark now emits independent axes needed by postprocessing.

Snapshot: 383 files, SHA-256 verified on farm; isolated ROOT-compatible Python/PyTorch CPU environment. Farm directory: /data/graal/GRAAL_Analysis/results/flux-recovery-full-20261019. Slurm preparation job 2 running; realistic job 3 and block3 job 4 depend on its success. At 14:38 UTC preparation was hashing the full inputs, process active; counts and new anomaly totals not yet available. Durable report: docs/reports/2026-10-19-farm-flux-recovery.md. Local launch record: results/farm-flux-launch-20261019. Scientific campaign is running, not completed; model selection remains deferred.
