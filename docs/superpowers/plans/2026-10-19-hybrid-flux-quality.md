# Hybrid flux and quality implementation

Spec: ../specs/2026-10-19-hybrid-flux-quality-design.md
User already authorized implementation in chat. Existing working-tree edits
belong to preceding pilot and are preserved. Work in current feature checkout.

1. Quality worker owns calibration/run_quality.py, config policy, calibrated
   ingestion, observable exclusion integration, pipeline cache dependencies,
   focused regression tests. First prove failures then implement shared policy.
2. Model worker owns neighbor_validation.py, new neighbor_models.py and model
   tests. Preserve prediction/fit structure; extend with model families, hybrid
   invariant, training-only grid and default controls. No plot/CLI edits.
3. Main owns study CLI/summary, neighbor_plots.py, documentation and real runs.
   Integrate interfaces, preserve pre-exclusion split assignment, hash policy,
   label development reuse, compare common targets, render all model overlays.
4. Run real pilot on two available h80 files, all valid calibrated periods,
   report quality exclusions, default/tuned performance and hybrid result.
   Run relevant tests, independent review, resolve material findings, verify
   artifacts visually and numerically. Do not update production ROOT/results.

Completed 19 October 2026. Real benchmark: 276 runs, 828 spectra;
156/162 development targets for block 1/3; all three model families and fixed
controls; 318 overlay pages. Input hashes unchanged. Shared exclusions applied
to future observable extraction; previous outputs preserved. Full suite:
1189 passed, one empty-legend warning. Independent review: no Critical/Important
findings. Report: docs/reports/2026-10-19-hybrid-flux-model-search.md.
