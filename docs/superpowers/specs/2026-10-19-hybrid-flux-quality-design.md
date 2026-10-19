# Hybrid calibrated flux, shared run exclusions and model search

User authorizes: combine ML shape with interpolated integral; exclude anomalous
runs from training AND observable extraction; compare ML algorithms and grid
search hyperparameters. Existing work and measured files must be preserved.

## Quality contract

Create one strict versioned policy in config/run_quality_exclusions.json,
owned by calibration/run_quality.py. Explicitly exclude entire runs 1322,
1482, 1970 for the diagnosed extreme flux/event ratios, preserving state,
period, reason and observed ratios. Criterion: positive finite flux per event
outside [0.01,100] times period/state median; incomplete/invalid measurements
remain separate exclusions. These three findings come from already examined
pilot data, not a blind-test selection. No automatic reassignment of POL/BREM.

Policy is consumed by calibrated-study ingestion and the common observable
exposure boundary. Verify all observable paths remove both measured events
and matching exposure contributions. Audit reasons and policy identity;
pipeline cache includes policy so old outputs cannot survive policy changes.
Keep canonical manifest and ROOT files unchanged; do not rewrite published
observable results in place. Missing/malformed default policy must fail clearly.

## Model benchmark

Reuse existing two-neighbor inputs, count normalization, 128 energy bins,
15-minute assumed ordinal spacing and contiguous-block splitting. Preserve
original splits when comparing old vs cleaned data by assigning roles before
quality exclusions; excluded runs can never be target/training/donor.

Families: Ridge, standardized RBF Kernel Ridge, Extra Trees (deterministic,
single worker). All models are multi-output. Grid training-only, three inner
folds with intact blocks interleaved over acquisition range; rebuild donors
for every inner fit. Baselines unchanged. Candidate grid: Ridge alpha expanded
through 1000; Kernel Ridge alpha/gamma; Extra Trees min_samples_leaf and
max_features with fixed 64 trees. Keep grid bounded and record every candidate,
usable denominators, fold scores, defaults and chosen parameters.

Evaluate direct per-event prediction and hybrid
I_linear * max(prediction,0) / sum(max(prediction,0)). Zero predicted integral
is not reconstructible, never silently converted to a shape. Direct and hybrid
can select different candidates, using respective training-fold relative L1.
Also record shape and integral errors for each grid candidate. Retain a default
parameter control per family to isolate tuning gains. Validation is used only
for empirical intervals; final development holdouts never enter selection.

Already examined periods remain DEVELOPMENT holdouts. Do not call reuse an
independent confirmation. Provide a freeze/apply path if practical but do not
claim independent validation without fresh periods. Actual missing calibrated
flux replacement is outside this step; exclusion integration is authorized.

## Outputs and proof

Reproduce calibrated spectra overlays with true, linear, all ML and hybrid
models. Include per-family grid surfaces/curves, default vs tuned paired errors,
shape vs integral errors, all denominators and exclusions. New result directory;
preserve first pilot. Report state/period differences, anomalies and intervals.
Test hybrid sum invariant, exclusion from donors/events/exposures, policy/cache
identity, malformed policy, inner-fold isolation, held-out truth perturbation,
and deterministic bounded grid. Run relevant calibration, flux and observable
checks; independent code review before completion.
