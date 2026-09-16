# Data and storage

Pipeline persists files, not database records. ROOT stores event data; NPZ,
JSON, text, CSV, ROOT histograms, and PDF files store derived artifacts.

## Artifact inventory

| Artifact | Default location | Writer | Main readers |
|---|---|---|---|
| Raw detector ROOT data | `data/graal_data/` | External to repository | Pre-analysis |
| Pre-analysis ROOT files | `data/pre_analyzed/pre_*.root` | `PreAnalysis.C` | Event selector, calibration |
| Selected ROOT files | `data/selected/*.root` | `event_selector.select_events` | Beam measurement, reconstruction |
| MC ROOT files | `03_mc_simulation/data/*_mc.root` | ROOT generator macros | Feature builder, fit validation |
| Beam spectrum NPZ | `04_bdt_training/data/beam_spectrum.npz` | `bdt_training.beam_spectrum` | MC reweighting |
| Stage-1 dataset NPZ | `04_bdt_training/data/features_stage1.npz` | Feature builder | Search and training |
| Stage-1 model bundle | `04_bdt_training/artifacts/stage1/` | Search/training | BDT gate, review |
| Reconstructed ROOT files | `results/reco/` | Reconstruction entry points | Plotting |
| Plot products | `results/plots/` | Plot entry points | Analysis review |
| Run manifest | `config/run_manifest.csv` | Manifest script/manual review | Calibration workflow |
| Flux calibration bundle | `results/strip_energy_flux/` | Flux script | Physics extraction and QA |

Bulk data and rebuilt results are ignored by Git. Model artifacts required by
runtime reconstruction and selected reference reports are versioned.

## ROOT tree lineage

| Tree | Meaning |
|---|---|
| `h70` | Raw detector schema, produced outside this repository |
| `h80` | Pre-analysis event tree with reconstructed particles and run metadata |
| `h85` | h80 schema cloned after event preselection |
| `mc` | Channel-specific generated and smeared Monte Carlo event tree |
| `reco_eta_pi0_chi2` | Standard ηπ⁰ reconstruction |
| `reco_eta_pi0_bdt` | Same reconstruction after Stage-1 gate |
| `reco_2pi0` | χ²-only 2π⁰ reconstruction |

`graal_common.io.trees.resolve` handles reconstruction input tree selection.
`auto` prefers `h85` and accepts `h80` for older preselected files; an explicit
name must exist.

## h80 and h85

`h80` stores `beam` plus vectors of `gammas`, `protons`, `neutrons`, and
`deuterons`. It also carries angular, timing, energy-loss, polarization,
`RunNumber`, and `Xstrip` information required by selection, reconstruction,
and calibration.

Event selector clones h80 schema without adding or removing branches, applies:

```python
event.gammas.size() > 1 and event.fcharged_theta.size() == 1
```

and explicitly renames cloned tree to `h85`. Output filename drops `pre_`
prefix.

## Monte Carlo tree

All nine generators write `beam` and `proton`. Signal `eta_pi0` writes four
named photon branches. Other channels write `g0` through channel-dependent
last photon and record `n_true_gamma`. Signal file also stores unsmeared
`*_true` branches for kinematic-fit closure validation.

Channel branch conventions live in `graal_common.physics.channels`; readers do
not bind physics metadata by list position.

## Stage-1 NPZ contracts

Beam spectrum NPZ stores measured histogram edges and density used to reweight
each MC channel.

Feature dataset has eight required keys:

```text
X, y, w, feature_names, signal_channel, hypothesis,
signal_prior, beam_reweighted
```

`X` has 26 ordered float feature columns. `y` and `w` have one entry per event.
Loader validates dimensions, finite weights, feature count, channel, and
hypothesis before training.

## Stage-1 runtime bundle

Required runtime files:

```text
bdt_stage1.json
stage1_threshold.txt
stage1_provenance.json
```

Metrics and search/report files support review but are not needed to score an
event. Provenance has an exact schema covering signal channel, hypothesis,
signal prior, beam reweighting, phase-space sampling, tagger resolution,
detector covariance status, and feature names.

## Reconstruction trees

ηπ⁰ reconstruction writes run metadata, `chi2`, raw meson masses, beam,
target, measured proton, optional neutron, selected photons, reconstructed
mesons, and missing four-vector. With default fit enabled it also writes fitted
photons, mesons, proton, fit χ², six degrees of freedom, and convergence flag.

χ² and BDT trees share schema. They differ by events rejected by BDT gate.
Fit confidence level selects final events when fit is enabled; missing-mass
window is fallback when fit is disabled.

## Plot outputs

`plots.dalitz` writes PDF figures and `istogrammi.root` under `results/plots/`.
`plots.kinfit_resolution` writes resolution and mass-comparison PDFs.
`plots.fig7_compton_polarization` defaults to versioned PDF and ROOT artifacts
under `06_plots/artifacts/`.

## Calibration storage

Strip-energy/flux workflow atomically publishes:

```text
strip_energy_lookup.csv
flux_by_run_energy.csv
flux_by_group_energy.csv
strip_energy_flux_qa.json
```

Schemas, validation, and exit behavior are documented in
[Calibration and flux](calibration-and-flux).
