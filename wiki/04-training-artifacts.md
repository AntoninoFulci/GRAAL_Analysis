# 04 — Training Artifacts

Stage-1 search and final training share a validated dataset but produce two
different artifact classes: analyst-facing search/reporting evidence and the
three-file bundle required by reconstruction.

## Hyperparameter Search

`grid_search_stage1.py` loads `features_stage1.npz`, casts `X`, `y`, and `w` to
`float32`, and makes a stratified train/validation split using
`val_fraction=0.20` and seed 42 by default. Both training and validation receive
their event weights.

The current grid is:

| Parameter | Values |
|---|---|
| `max_depth` | 3, 4, 5, 6 |
| `learning_rate` | 0.05, 0.10, 0.15, 0.20 |
| `subsample` | 0.7, 0.8, 1.0 |
| `colsample_bytree` | 0.7, 0.8, 1.0 |
| `min_child_weight` | 1, 5, 20 |
| `gamma` | 0.0, 0.1, 0.3 |

Random search shuffles all 1,296 combinations with Python's seeded RNG and
takes the first `n_iter`; full-grid mode evaluates all of them. Every candidate
uses histogram trees, at most 400 estimators, AUC evaluation, and 20-round early
stopping. Ranking uses weighted validation ROC AUC. `best_iteration + 1`
becomes the proposed `n_estimators` for final fitting.

Outputs:

- `grid_search_results.csv`: successful rows sorted by descending AUC, including
  fitted estimator count and elapsed seconds;
- `best_hyperparams.json`: the best complete result row.

A candidate failure is printed and skipped. Search artifacts are training
inputs/evidence; reconstruction never reads them.

## Model Training

`training.stage1_training.fit_stage1` is the side-effect-free fit/evaluation
core. `train_bdt_stage1.train` owns filesystem publication and reporting.

The final fit:

1. validates and loads the dataset;
2. performs a seeded, stratified train/validation split;
3. passes `w_train` to `sample_weight` and `w_val` to
   `sample_weight_eval_set`;
4. fits `XGBClassifier` with `tree_method="hist"` and `eval_metric="auc"`;
5. computes weighted validation AUC;
6. scans 200 inclusive candidate thresholds from 0.01 to 0.99;
7. chooses the threshold maximizing weighted binary F1;
8. computes weighted precision, recall, and F1 at that threshold;
9. writes the bundle and reports.

Verbose training attaches `TqdmCallback`, which shows one update per tree and
the first validation AUC it finds in XGBoost's evaluation log. The callback
does not alter stopping or model decisions.

`stage1_metrics.txt` records signal channel, hypothesis, training prior, beam
reweighting flag, AUC, threshold, precision, recall, F1, and split sizes.
When Matplotlib is installed, training also produces:

- `stage1_roc.png` — weighted validation ROC;
- `stage1_feature_importance.png` — top 20 XGBoost feature importances;
- `stage1_score_dist.png` — class score distributions and chosen threshold.

## Runtime Bundle

Reconstruction requires these files from one consistent training run:

| Filename | Runtime required | Owner and purpose |
|---|---:|---|
| `bdt_stage1.json` | yes | XGBoost classifier serialized by `save_model` |
| `stage1_threshold.txt` | yes | scalar decision boundary; score equal to threshold is accepted |
| `stage1_provenance.json` | yes | hypothesis, signal identity, feature order, and training assumptions |
| `stage1_metrics.txt` | no | human-readable validation summary |
| `stage1_roc.png` | no | discrimination diagnostic |
| `stage1_feature_importance.png` | no | model-inspection diagnostic |
| `stage1_score_dist.png` | no | operating-point diagnostic |
| `best_hyperparams.json` | no | optional final-training input and search record |
| `grid_search_results.csv` | no | search audit table |

All are currently versioned under `04_bdt_training/artifacts/stage1/`. The
checked-in snapshot reports signal `eta_pi0`, hypothesis `eta_pi0`, prior 0.5,
beam reweighting enabled, validation AUC about 0.9991, and threshold 0.275930.
Those numbers describe the versioned model; retraining may legitimately change
them.

`Stage1ArtifactPaths` centralizes runtime filenames so trainer and gate do not
duplicate string conventions.

## Provenance Validation

`stage1_provenance.json` has an exact, closed schema:

| Key | Meaning |
|---|---|
| `signal_channel` | registry channel assigned to class 1 |
| `hypothesis` | feature/pairing hypothesis |
| `signal_prior` | explicit class-mixture choice or null for a legacy dataset |
| `beam_reweighted` | boolean or null when legacy status is unknown |
| `phase_space_sampling` | generator sampling convention; currently `accept-reject-unweighted` |
| `tagger_resolution_fwhm_gev` | configured 0.016 GeV FWHM |
| `tagger_resolution_sigma_gev` | FWHM converted to Gaussian sigma |
| `detector_covariance_status` | current calibration status string |
| `feature_names` | exact ordered model input names |

The dependency-free parser rejects missing keys, unexpected keys, wrong types,
non-finite numeric values, and non-string feature arrays. This makes schema
drift explicit before XGBoost scoring.

At load time, `Stage1Gate` additionally requires model, threshold, and
provenance files; resolves the provenance hypothesis through the shared
registry; and exposes `check_hypothesis`. Reconstruction must call that check
before gating. The gate then imports the same feature implementation used by
training and accepts batch rows whose signal score is greater than or equal to
the stored threshold.

Current validation does not cryptographically bind the three runtime files or
compare provenance feature names against the XGBoost model's internal feature
metadata. Treat the directory as one indivisible release and replace all three
runtime files together.

Verification commands:

```bash
pytest 00_common/tests/test_stage1_artifacts.py \
  04_bdt_training/tests/test_stage1_training.py \
  04_bdt_training/tests/test_stage1_reporting.py \
  tests/test_stage1_contracts.py -q
```

Related pages: [Stage-1 training](04-bdt-training),
[Stage-1 gate](05-stage1-gate), and [data and artifacts](data-and-artifacts).

## Full Feature Distributions (ROOT and PDF)

Export an existing validated dataset without training or changing the model:

```bash
python3 -m bdt_training.plot_training_features \
  --features test_data/vis/bdt/features_stage1.npz \
  --out-dir results/training-features-20261013/vis
```

Supply both UV and VIS NPZs after `--features` to compare them with identical
bin edges while keeping separate profile directories. At most one dataset per
profile is accepted; mixed hypotheses are rejected. An absent profile stays
`unknown`, regardless of the filename. An absent input is an error, not an
invitation to simulate training data. The output directory must not already
contain any of the three report files.

The reusable exporter lives in `training/feature_reporting.py`. Training can
request it explicitly with `--feature-diagnostics-dir <new-directory>` (or the
`feature_diagnostics_dir` argument to `train`). It runs before fitting and does
not change the split, model, feature values or threshold. Existing training
commands keep their dependency requirements: PyROOT and Matplotlib are needed
only when this diagnostic export is requested. Diagnostic files are separate
from the runtime model bundle.

Outputs:

- `training_features.root`: all 26 feature distributions, signal/background,
  weighted/unweighted yield and separately normalized shape;
- `training_features.pdf`: provenance cover and one page per feature/profile,
  four panels for weighted/unweighted yield/shape, with flow and NaN totals;
- `training_features.json`: the same dictionary and audit metadata embedded in
  ROOT as the JSON title of `TNamed("training_features_metadata", ...)`.

ROOT paths are
`<profile>/all/<signal|background>/<feature>/<weighted|unweighted>_<yield|shape>`.
Yields retain `sum(w)`, errors `sqrt(sum(w^2))`, and under/overflow bins. ROOT
entries count finite feature values, including flows and events with zero
weight. NaN values are omitted from TH1 and separately counted with their
`sum(w)` and `sum(w^2)`; infinities and fractional discrete counts fail validation.
Feature names and order must match the shared hypothesis contract exactly.

Shape copies divide by the total finite weight **including both flow bins**;
`Integral(0, nbins + 1)` is therefore one. They represent fraction per bin,
not density per unit x (chi-square has nonuniform bins). Shapes with a
non-positive total weight are explicitly undefined and are not written.
Shape errors use a fixed normalization; they do not estimate covariance from
the shared normalization. Signed weights remain in the yield histograms.

`graal_common.stage1.feature_descriptions` documents formula, physical domain,
unit, discrete/continuous kind, family and fixed plotting window for every
column, deriving names from `features.feature_names(hypothesis)`. Counts have
integer-centered bins. All windows are fixed independently of the data; values
outside them remain in ROOT flows and PDF audit totals. No data are cut to
improve plots. Units use c=1; counters, cosines and energy asymmetry are not
labelled GeV. `eta_pi0_angle` is a **cosine**, while `sum_opening_angles` is in
radians. Feature `missing_mass` uses `beam + target - proton`, unlike the recoil
mass used by reconstruction.

Current NPZs do not persist training split indices, per-event MC channel IDs,
photon-loss settings or the historical feature-code version. The exporter
reports only recoverable categories; it never regenerates a random split or
infers event channels. The seed is recorded only when called by the trainer.
Hashes bind the report to the NPZ and current source files, not retrospectively
to a historical model. Hypothesis masses describe the current shared feature
contract; missing historical provenance stays explicit.

Verification:

```bash
python3 -m pytest -q 04_bdt_training/tests/test_training_feature_root.py \
  04_bdt_training/tests/test_stage1_reporting.py \
  04_bdt_training/tests/test_stage1_dataset.py tests/test_stage1_contracts.py
```
