# Calibrated flux neighbor benchmark implementation

Spec: ../specs/2026-10-19-calibrated-flux-neighbors-design.md

User approved the study in chat and supplied data and timing assumptions.
Implement inline in the existing clean feature checkout, preserving inputs.

1. **Data contract** (`07_flux_studies/calibrated_data.py`):
   `rebin_counts(values, old_edges, new_edges)`,
   `count_h80(paths)`, `load_calibrated_dataset(...)`.
   Tests first: fractional-bin conservation; out-of-range rejection;
   exact run/state counts; repeated files rejected; explicit exclusions.
2. **Benchmark** (`07_flux_studies/neighbor_validation.py`):
   `split_runs(runs, block_size, seed)`, `neighbor_example(...)`,
   `evaluate_neighbors(records, block_size, seed)`.
   Reuse `fit_ridge`; inner training-only tuning, block-excluded donors,
   validation residual bands, paired final-test metrics. Tests first:
   analytic exposure scaling, unchanged predictions after changing test truth,
   no masked donor, same split per state, insufficient-data outcomes.
3. **Plots/entry point** (`07_flux_studies/neighbor_plots.py`,
   `07_flux_studies/study_calibrated_neighbors.py`):
   reuse atomic publication/JSON/CSV helpers; store NPZ spectra, PDF atlases,
   PNG summary/representative comparisons, input hashes, split and feature
   provenance, assumptions and exclusions. Integration test on small ROOT
   fixtures verifies artifacts and originals unchanged.
4. **Real pilot and review**: run two h80 inputs with calibrated local flux,
   isolated and 3-run masks; inspect images; run
   `python3 -m pytest -q 07_flux_studies/tests`; independent review; fix material
   findings; save `docs/reports/2026-10-19-calibrated-flux-neighbors.md` and
   update runbook. Report unresolved limits and measured model comparisons.

Review focus: target-axis leakage; donor truth in inner training; compressed
run order; count duplication; unsupported spectra silently clipped; intervals
calibrated on final test; metrics with unequal denominators.
