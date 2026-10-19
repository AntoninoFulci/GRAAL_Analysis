# Calibrated flux: neighbor interpolation and ML benchmark

## Agreed scope

Compare two-neighbor interpolation with regularized multi-output regression on
known calibrated runs, masking their flux as though it were missing. Deliver
all held-out spectrum overlays and diagnostics. No channel selection. Inclusive
h80 counts per run/state supply the normalization. User assumes stable trigger,
prescale, dead time, background and inclusive response, and **15 minutes per
run**, because acquisition timestamps do not exist even in raw files.

Use existing `flux_studies` helpers, with a separate calibrated-study entry
point: the existing raw-missing study has different targets and remains valid.
No production flux replacement, synthetic adoption or propagation into Sigma.

## Data and explicit assumptions

Two h80 files: 1998_uv and 1999_vis. Copies already in
`test_data/pre_analyzed/` have the same ROOT UUIDs and entry counts as
`trima:/data/graal/pre_analisi/`; reuse them. Calibrated/raw flux inputs are
under `data/00_external/`. Record identities and input integrity.

Count every h80 entry by RunNumber/Polarization, before channel selections.
These historical files predate the current no-tagger guard; report this
provenance, do not silently reselect events. Reject overlapping file run/state
coverage or repeated ROOT UUIDs rather than double counting. Missing/zero
counts, invalid histograms and incomplete triplets remain explicit exclusions.

Group by period, target, beam and state. Apparatus compatibility within period
is an assumption, not evidence from absent logs. Use ordinal position in the
full manifest period as acquisition-order proxy, with equal 15-minute steps;
missing histograms do not compress this ordering. Numeric run gaps are not
elapsed minutes. No UTC timestamps are invented. POL states are analyzed
separately; no state-specific acquisition duration is inferred.

## Prediction and splitting

Rebin calibrated spectra conservatively onto a fixed 128-bin energy grid,
0.5--2.0 GeV (full local calibrated range is approximately 0.64--1.72 GeV).
Reject spectra extending outside the requested grid rather than silently
truncate. No energy edges or contents from held-out targets define features.

For target B, use the nearest available training donor on each side, same
group/state. Normalize donor spectra by their own h80 count. Interpolate
these flux-per-event spectra, then multiply by B's count. Also report nearest
donor and unscaled two-neighbor interpolation as controls.

Ridge inputs: both donor flux-per-event spectra, their interpolated spectrum
(derived feature, no extra data), left/right ordinal distances in assumed
minutes and relative position. Target: calibrated spectrum per event.
StandardScaler fits only training examples; final nonnegative projection is
recorded, not hidden. Target counts only rescale the output. No target flux,
target calibration, other-state flux or calibrated target axis enters features.

Within each period assign contiguous blocks reproducibly to train/validation/
test (~60/20/20), with run-level roles shared across states. Run isolated
(block size 1) and gap (block size 3) experiments. Keep test entirely out of
feature donors, scaling, alpha selection and uncertainty estimation.
Training examples hide their whole block. Alpha is selected with three inner
blocked folds built within training: rebuild donor features in each inner
split, so inner validation truth cannot enter training features. Validation
is reserved for residual intervals; test is evaluated once after fitting.

## Uncertainty and diagnostics

Validation signed spectral residual vectors normalized by predicted integral
give exploratory per-bin 68/95% prediction bands and integral intervals. Store
residual vectors; report coverage and number of calibration examples. These
are empirical, correlated-data intervals, not guaranteed confidence regions
or independent synthetic measurements. No final test-driven model changes.

Every test target: truth/interpolation/Ridge absolute and unit-area overlays,
ratio and residual panels, with uncertainty bands where available. Full PDF
atlas plus selected PNG examples and numerical arrays. Global diagnostics:
flux vs event counts, flux/count vs run, split map, integral prediction vs
truth, relative integral error, shape L1, bias vs energy, energy/run residual
heatmaps, paired model errors, errors vs counts/gap, interval coverage,
regularization curves and train/validation/test errors. Report denominators
and excluded edge/no-bracket cases. Train error is labeled in-sample.

## Delivery and verification

Standalone CLI, tests for rebin conservation, count integrity, donor/split
leakage (including perturbing held-out truth), analytic interpolation,
block masking, serialization and plot generation. Run existing flux tests.
Execute on the two real periods, inspect plots visually, and publish a concise
report with measured results, assumptions and limitations. Input files remain
unchanged. Scientific success does not require ML to win.
