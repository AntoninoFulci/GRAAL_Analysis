# 04 — Dataset and Features

The Stage-1 dataset presents every channel to the classifier through one
identical observation model and one ordered feature schema. The result is a
portable NPZ file whose arrays and physics identity are validated before
training.

## Four-Photon Event Contract

`build_channel_features` performs the same operations for signal and every
background:

1. read the channel's true generated photons, recoil proton, and tagged beam;
2. derive each photon's energy and polar angle;
3. sample independent detector loss using the shared `LossParams`;
4. retain only events with exactly four surviving photons;
5. select those four vectors and corresponding proton/beam rows;
6. randomize photon order independently within every event;
7. compute features for the selected reconstruction hypothesis;
8. compute per-event beam-spectrum weights.

The signal is not exempt from loss. Even a generated four-photon signal can
place photons outside detector acceptance; bypassing the model would make
detector visibility depend on the class label.

Photon shuffling removes generator write order. Without it, the named signal
branches place eta daughters first and a feature such as `m_gg_01` would expose
parent identity unavailable in detector data.

The input array contract after sampling is:

```text
photons: (N, 4, 4)  columns [px, py, pz, E]
proton:  (N, 4)     columns [px, py, pz, E]
beam:    (N, 4)     columns [px, py, pz, E]
```

`eta_pi0` reads the named photon branches recorded in `MCChannel`; other
generators use `g0...gN` with `n_true_gamma`. File schema, not class role,
determines decoding.

## Feature Schema

`graal_common.stage1.features.compute_stage1_features` returns `(N, 26)` with
dtype `float32`. Column order is a persisted model interface:

| Columns | Names | Definition |
|---:|---|---|
| 0–5 | `m_gg_01`, `m_gg_02`, `m_gg_03`, `m_gg_12`, `m_gg_13`, `m_gg_23` | Six two-photon invariant masses in shared `PAIR_IDX` order |
| 6 | `n_pairs_near_<light>` | Number of pair masses inside the hypothesis light-meson window |
| 7 | `n_pairs_near_<heavy>` | Number inside the heavy-meson window |
| 8 | `best_chi2_<hypothesis>` | Minimum shared pairing chi-square over the three disjoint pairings |
| 9 | `missing_mass` | Non-negative square root of clipped missing four-vector mass squared |
| 10–12 | `missing_E`, `missing_pz`, `missing_pt` | Components derived from beam + stationary proton target − recoil proton |
| 13 | `total_gamma_E` | Sum of the four photon energies |
| 14 | `beam_E` | Tagged beam energy |
| 15–17 | `max_gamma_E`, `min_gamma_E`, `gamma_E_rms` | Photon-energy extrema and RMS spread |
| 18 | `sum_opening_angles` | Sum of all six photon-pair opening angles |
| 19–20 | `min_pair_mass`, `max_pair_mass` | Extrema of the six pair masses |
| 21 | `total_pt_gamma` | Scalar sum of photon transverse momenta |
| 22–23 | `proton_p`, `proton_costheta` | Recoil-proton momentum and polar cosine; zero momentum maps to cosine zero |
| 24 | `<heavy>_E_asym` | Normalized energy asymmetry of the heavy pair from the best chi-square assignment |
| 25 | `<heavy>_<light>_angle` | Cosine of the lab angle between best-pairing meson candidates |

For the default `eta_pi0` hypothesis, the parameterized names become
`n_pairs_near_pi0`, `n_pairs_near_eta`, `best_chi2_eta_pi0`, `eta_E_asym`, and
`eta_pi0_angle`. A `2pi0` model receives names describing that hypothesis.

The chi-square and best-pair indices come from `00_common/physics/pairing.py`.
Training and reconstruction therefore do not maintain competing expressions
for the same physics quantity.

## Dataset Schema

`features_stage1.npz` contains exactly eight keys:

| Key | Shape/type | Meaning |
|---|---|---|
| `X` | `(N, 26)`, normally `float32` | Ordered feature matrix |
| `y` | `(N,)`, built as `int8` | Binary label: 1 for chosen signal, 0 for backgrounds |
| `w` | `(N,)`, built as `float32` | Physics/event weights normalized to mean one |
| `feature_names` | one-dimensional string array | Exact column names and order |
| `signal_channel` | scalar string | Registry channel assigned to class 1 |
| `hypothesis` | scalar string | Pairing/meson hypothesis used for features |
| `signal_prior` | scalar float | Deliberate training mixture choice |
| `beam_reweighted` | scalar boolean | Whether measured-beam reweighting was applied |

`Stage1Dataset` carries `X`, `y`, `w`, and a frozen
`Stage1DatasetMetadata`. Loading copies arrays out of the NPZ and validates:

- `X` is two-dimensional and has 26 columns;
- `y` and `w` are one-dimensional;
- all three arrays have equal event counts;
- exactly 26 one-dimensional feature names are present;
- every weight is numeric and finite;
- signal channel and hypothesis exist in their registries.

Identity metadata is mandatory on load. Older datasets may omit
`signal_prior` and `beam_reweighted`; those become `None` so their unknown
status remains explicit. Saving a new dataset requires both values.

## Metadata and Reproducibility

Reproducibility has several independent seeds and persisted inputs:

| Source | Control | Effect |
|---|---|---|
| Photon loss and within-event shuffle | `--loss-seed`, default 42 | Which generated photons/events survive and photon ordering |
| Search candidate order and split | `--seed`, default 42 | Random grid subset and stratified train/validation rows |
| Final fit split and XGBoost | `--seed`, default 42 | Stratified rows and model randomness |
| Beam distribution | beam-spectrum NPZ | Target density used for every channel |
| Physics identity | `signal_channel`, `hypothesis` | Labels and feature semantics |
| Mixture | `signal_prior` plus registry data | Total class/channel shares |

A seed alone is insufficient: exact reproduction also requires the same MC
ROOT files, measured beam-spectrum artifact, channel registry, loss parameters,
feature implementation, and dependency versions.

The builder records each channel's `n_gen`, survivor fraction, and beam weights
in memory through `ChannelSample`, but the final NPZ stores event arrays and
metadata rather than the per-channel intermediate objects. Preserve command
logs and source revision for a full audit.

Implementation map:

| Path | Responsibility |
|---|---|
| `04_bdt_training/dataset/mc_samples.py` | ROOT decoding, acceptance sampling, shuffling, feature calls |
| `00_common/stage1/features.py` | ordered feature names and vectorized computation |
| `04_bdt_training/dataset/stage1_dataset.py` | typed NPZ persistence and validation |
| `04_bdt_training/build_background_features.py` | channel assembly, labels, weights, and CLI |
| `tests/test_stage1_contracts.py` | stable numeric feature vector and exact NPZ schema |

See [photon pairing](photon-pairing),
[weighting and photon loss](04-weighting-and-photon-loss), and
[training artifacts](04-training-artifacts).
