# Beam Kinematic Features for the Pairing BDT

**Date:** 2026-06-17
**Branch:** ml-photon-pairing-bdt
**Status:** Design approved, pending implementation plan
**Builds on:** `docs/superpowers/specs/2026-06-16-photon-pairing-ml-study-design.md`

## Goal

Add beam-derived kinematic features to the existing XGBoost pairing BDT
(gamma p -> p eta pi0, choose which of 3 photon pairings is correct) and measure
whether they improve pairing accuracy over the current model (98.08%) and the
chi2 baseline (97.51%).

Scope is **pairing improvement on the existing signal MC**. Signal-vs-background
discrimination (which would need a background MC) is explicitly out of scope and
left as a future study.

## Physics rationale

The two reconstructed mesons sum to the same 4-vector regardless of pairing
(it is always the sum of all four photons), so any quantity built from the
**total** eta+pi0 system (total missing mass, W) is identical across the three
pairings and cannot discriminate the pairing.

What does depend on the pairing is the split between the eta and the pi0. Boosting
each reconstructed meson into the centre-of-mass frame (the rest frame of
beam+target) and taking its polar angle gives **cos(theta*)** — the
forward/backward direction of the individual meson — which is pairing-dependent
and physically meaningful. Its companion is the CM momentum magnitude **p***.
These are the features the user described ("at equal boost they go more forward
or backward").

## Beam data available

MC tree `mc` of `eta_pi0_mc.root`. The `beam` branch is a `TLorentzVector`
`(0, 0, E_beam, E_beam)` (smeared tagger energy, ~16 MeV). The target is a proton
at rest, `(0, 0, 0, 0.938272)`, a constant. Because the beam has momentum only
along z and the target is at rest, the CM boost is purely along z.

## Features added

Per pairing, computed in the CM frame and assigned to the lighter ("low",
pi0-like) and heavier ("high", eta-like) meson with the existing mass-ordering
mask:

- `cosstar_low`, `cosstar_high` — cos(theta*) of each meson vs the beam axis.
- `pstar_low`, `pstar_high` — CM momentum magnitude of each meson.

Per-block feature count grows from 18 to **22**.

One **global** feature per event, appended once after the three blocks:

- `beam_E` — the beam energy. Constant across the three pairings (so it does not
  discriminate between them on its own), but lets the trees condition the
  cos(theta*)/p* cuts on the kinematic scale.

Total feature vector: `3 x 22 + 1 = 67`.

## Components

### `physics.py`
Add a vectorised Lorentz boost:

- `boost(vec, beta)` — boost a 4-vector array `(..., 4)` `[E, px, py, pz]` by a
  3-velocity `beta` `(..., 3)`. General (not z-only) so it is independently
  testable, though here beta is always along z.

### `build_features.py`
- `load_beam(root_path, tree="mc", n_max=None)` -> `(N, 4)` `[E, px, py, pz]`,
  reading the `beam` branch (same uproot member access as `load_photons`:
  `fE`, `fP.fX/fY/fZ`).
- `TARGET` module constant: `np.array([0.938272, 0.0, 0.0, 0.0])` (proton at
  rest, `[E, px, py, pz]`).
- `_feature_block(P, pairing, beam)` — extended signature. Builds `W = beam +
  target`, derives the CM boost `beta_cm = W_p3 / W_E`, boosts `mesonA`/`mesonB`
  into the CM, computes `pstar` (= |CM momentum|) and `cosstar` (= CM pz / pstar,
  i.e. relative to the beam +z axis), assigns low/high via the existing `a_low`
  mask. Appends the 4 new columns to the block (order fixed in
  `_BLOCK_FEATURES`).
- `_BLOCK_FEATURES` gains `cosstar_low, cosstar_high, pstar_low, pstar_high`
  (18 -> 22). `_feature_names()` still suffixes `_block{0,1,2}`; after the 3
  blocks it appends the single global name `beam_E`.
- `build(photons, beam, seed=SEED)` — extended signature. Assembles the
  `(N, 66)` block matrix as today, then horizontally stacks `beam[:, 0]` as the
  final column -> `(N, 67)`. Returns `(X, y, masses, feature_names)` unchanged
  in meaning; `masses` stays `(N, 3, 2)`.
- CLI `main()`: load photons and beam, call `build(photons, beam, ...)`.
- `explain()` test mode: reshape the 66 block columns as `(3, 22)`, print the new
  cos(theta*)/p* rows, and print the trailing `beam_E` once per event.

### `train_bdt.py`, `evaluate_compare.py`
No logic change — both read the feature count from the data. The model simply
trains on 67 columns. Re-run after regenerating `features.npz`. `train_bdt.explain`
builds via `build(photons, beam, ...)` and stays generic.

## Data flow

`load_photons` + `load_beam` -> `build(photons, beam)` (shuffle, 3 pairings,
per-block features incl. beam, chi2 ordering, label, append `beam_E`) ->
`features.npz` (`X` now `(N, 67)`) -> `train_bdt` -> `evaluate_compare`.

## Testing (TDD)

New / updated tests:

- `physics.boost`: boosting a particle by its own velocity gives zero 3-momentum
  in its rest frame; a known back-to-back along-z case.
- `cosstar` lies in `[-1, 1]`; `pstar >= 0`.
- `build(photons, beam, ...)` returns `X.shape == (N, 67)` and
  `len(feature_names) == 67`; `feature_names[-1] == "beam_E"`.
- Update `test_feature_matrix_shape_and_names` from 54 to 67.
- `test_chi2_baseline_is_block_zero` keeps working (indexes `chi2_block{b}` by
  name, robust to block width).
- Existing no-leakage and truth-label tests are unaffected (beam features do not
  touch the label).

## Evaluation

Regenerate the full `features.npz`, retrain, and compare on the same held-out
test set:

- Pairing accuracy: new model vs current 98.08% vs chi2 97.51%.
- Updated feature-importance plot (do the beam features rank?), confusion matrix,
  and the eta/pi0 mass spectra.
- Record the numbers in `analysis/ml/plots/metrics.txt`.

## Limitation (stated up front)

The MC is signal-only and phase-space (no dynamics, no background), and chi2 is
already near-optimal, so the pairing gain from beam features may again be small.
A near-zero gain is still a valid, reportable result. The larger payoff of beam
information — rejecting physics backgrounds — requires a background MC and is a
separate future study.
