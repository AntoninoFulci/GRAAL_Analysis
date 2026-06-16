# Photon-Pairing ML Study (XGBoost BDT vs chi2)

**Date:** 2026-06-16
**Channel:** gamma p -> p eta pi0, with eta -> gamma gamma and pi0 -> gamma gamma (4 photons)
**Status:** Design approved, pending implementation plan

## Goal

Demonstrate, on Monte Carlo, whether a learned photon-pairing classifier beats
the current chi2 minimisation at assigning 4 photons to the correct eta + pi0
candidates. This is a **study**: prove (or disprove) that ML beats the baseline
before any integration into the real-data reconstruction. No real-data
application and no modification of `reconstruct_eta_pi0.py` in this scope.

Success criterion: the BDT pairing accuracy on a held-out MC test set is higher
than the chi2 method's accuracy on the same set, with comparable or narrower
reconstructed meson mass peaks.

## Background

- `simulation/generate_eta_pi0_dataset.C` already produces a labelled MC dataset
  (`eta_pi0_mc.root`, tree `mc`): truth + Gaussian-smeared 4-vectors for the four
  decay photons (`eta_gamma1/2`, `pi0_gamma1/2`), the two mesons, beam, target,
  proton. The four photons are always present (no acceptance losses, no
  splitoffs).
- `analysis/reconstruct_eta_pi0.py` is the current baseline: for each event it
  builds the 3 photon pairings, picks the one minimising
  `chi2 = ((m12 - m_pi0)/(0.08 m_pi0))^2 + ((m34 - m_eta)/(0.08 m_eta))^2`,
  applies `chi2 < 10`.
- The four photons admit exactly 3 disjoint pairings:
  `(12)(34)`, `(13)(24)`, `(14)(23)`. Exactly one is correct, and in MC the
  correct one is known from truth.

## Library choice

XGBoost (gradient-boosted decision trees). Best fit for this tabular, small
feature-set, fixed 3-candidate problem; the HEP standard for combinatorial
pairing, and it beats neural nets on tabular data of this size. Supporting
libraries:

- `xgboost` — the BDT model (`XGBClassifier`).
- `uproot` + `awkward` — read `eta_pi0_mc.root` without a ROOT dependency on the
  ML side (lighter than pyROOT; the C++/ROOT pipeline is unchanged).
- `numpy`, `scikit-learn` — train/test split, metrics. No feature scaling needed
  (trees are scale-invariant).
- `matplotlib` — diagnostic and comparison plots.

## Architecture

New directory `analysis/ml/` with three scripts plus outputs:

| File | Responsibility |
|------|----------------|
| `build_features.py` | MC root -> feature matrix `X` + truth labels `y`, saved to disk (`.npz`). Pure data prep, no model. |
| `train_bdt.py` | Load features, split, train the BDT, save model + training diagnostics. |
| `evaluate_compare.py` | Apply BDT and chi2 to the held-out test set, produce the BDT-vs-chi2 comparison plots and metrics. |

Outputs:

- `analysis/ml/data/features.npz` — `X`, `y`, and a `chi2_order` index map.
- `analysis/ml/model/bdt.json` (saved XGBoost model).
- `analysis/ml/plots/*.png`, plus a metrics summary printed to stdout / written
  to `analysis/ml/plots/metrics.txt`.

## Data flow

1. **Read MC** (`build_features.py`): load tree `mc` via uproot, extract the four
   smeared photon 4-vectors per event.
2. **Shuffle** the 4 photons into a random order (fixed seed) so the model cannot
   exploit input position — truth ordering must not leak.
3. **Build 3 pairings**. Truth label = the pairing that groups the two
   eta-photons together and the two pi0-photons together.
4. **Order the 3 pairings by their chi2** (ascending). This gives a stable,
   physically meaningful block order. The label becomes the *position of the
   truth pairing within the chi2-sorted order*, directly framing the task as
   "does the model agree with chi2's best choice, or override it".
5. **Feature engineering** (full set, see below): one feature block per pairing,
   3 blocks concatenated into a single row per event.
6. Save `X` (events x features), `y` (class in {0,1,2}).

## Features

Per pairing, the two pairs are internally sorted by mass (`m_low`, `m_high`) and
the two photons within each pair sorted by energy, to remove permutation
ambiguity. All quantities derive from the same smeared 4-vectors (no inconsistent
mixing). Per-pairing block:

- `m_low`, `m_high` — invariant masses of the two pairs.
- `|m_low - m_pi0|`, `|m_high - m_eta|` — distance from nominal masses
  (m_pi0 = 0.134977, m_eta = 0.547862).
- `A_low`, `A_high` — energy asymmetry `|E1 - E2| / (E1 + E2)` per pair.
- `theta_open_low`, `theta_open_high` — opening angle between the two photons of
  each pair.
- `E1, E2, E3, E4` — the four photon energies, sorted descending (shared across
  the 3 blocks, but recomputed per row for self-containment).
- `cos_angle_mesons` — cosine of the angle between the two reconstructed meson
  momenta.
- `pT_low`, `pT_high` — transverse momenta of the two meson candidates.
- `beta_low`, `beta_high` — boost (|p|/E) of the two meson candidates.
- `chi2` — the engineered chi2 value for this pairing (the baseline quantity,
  used as a feature).

~17 features per pairing x 3 pairings concatenated per event.

## Model

`XGBClassifier`, multiclass (`multi:softprob`) over the 3 pairing classes:

- Input: raw feature vector (no scaling; trees are scale-invariant).
- Starting hyperparameters: `n_estimators ~200`, `max_depth ~5`,
  `learning_rate ~0.05`, `subsample 0.8`, `colsample_bytree 0.8`,
  `eval_metric "mlogloss"`. Tune with early stopping on a validation split.
- Output: 3 class probabilities; argmax selects the pairing.
- Fixed `random_state` for reproducibility.

## Evaluation (the deliverable)

On a held-out MC test set (truth known), compare BDT vs chi2:

- **Pairing accuracy** — fraction of events where the chosen pairing equals the
  truth pairing. BDT vs chi2, headline number.
- **Confusion matrix** for the BDT (which wrong pairing it picks).
- **Reconstructed mass spectra** — eta and pi0 invariant-mass peaks built from
  truth / chi2-chosen / BDT-chosen pairings; report peak width and combinatorial
  background under the peak (purity).
- **Feature importance** — native XGBoost gain-based importance, to see which
  features drive the decision.
- **Training diagnostics** — train/val mlogloss curves.

All plots saved to `analysis/ml/plots/`; headline metrics to `metrics.txt`.

## Edge cases

- Smeared 4-vectors can give a slightly negative `E^2 - p^2`: guard with
  `sqrt(max(., 0))` when computing masses.
- MC always has exactly 4 photons -> no missing-photon / variable-multiplicity
  handling needed.
- Fixed random seeds for photon shuffle and train/test split for reproducibility.

## Testing

- Feature-builder sanity test: for a handful of events, the truth pairing's
  `m_low`/`m_high` reproduce the nominal pi0/eta masses within smearing.
- No-leakage check: truth pairing position is uniformly distributed across the
  3 shuffled classes (i.e. shuffling actually randomises position).
- Success gate: BDT test-set pairing accuracy > chi2 accuracy on the same set.

## Out of scope (stated limitation)

This is a pure 4-photon idealisation. Real `h80` data has variable photon
multiplicity, calorimeter splitoffs, and acceptance losses. Integrating the
trained model into `reconstruct_eta_pi0.py` for real data is a separate, later
project, contingent on this study showing a real gain.
