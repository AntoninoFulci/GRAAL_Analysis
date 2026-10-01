# Local VIS analysis runbook

Run every command from repository root. For routine full campaigns use
`python scripts/run_pipeline.py --mode test_data`; commands below remain a
manual VIS diagnostic workflow.

Analysis interval is exact: `0.9313 <= E_gamma <= 1.10 GeV`. A calibrated run
is accepted only when `POL1`, `POL2`, and `BREM` are all present. Missing any
one component skips whole run.

## 1. Prepare directories and select VIS data

```bash
mkdir -p test_data/vis/mc test_data/vis/bdt

python -m event_selector.select_events \
  --input-dir test_data/pre_analyzed \
  --output-dir test_data/vis/selected \
  --pattern pre_analisi_1999_vis.root
```

Checkpoint: confirm only `test_data/vis/selected/analisi_1999_vis.root` was
created and record `h85` entry count:

```bash
python -c 'import ROOT; p="test_data/vis/selected/analisi_1999_vis.root"; f=ROOT.TFile.Open(p); print(f.Get("h85").GetEntries()); f.Close()'
```

## 2. Generate six VIS Monte Carlo channels

```bash
root -l -b -q '03_mc_simulation/generators/generate_eta_pi0_dataset.C(1000000,0.9313,1.10,"test_data/vis/mc/eta_pi0_mc.root")'
root -l -b -q '03_mc_simulation/generators/generate_pi0pi0_dataset.C(1000000,0.9313,1.10,"test_data/vis/mc/pi0pi0_mc.root")'
root -l -b -q '03_mc_simulation/generators/generate_3pi0_dataset.C(1000000,0.9313,1.10,"test_data/vis/mc/3pi0_mc.root")'
root -l -b -q '03_mc_simulation/generators/generate_eta_via_3pi0_dataset.C(1000000,0.9313,1.10,"test_data/vis/mc/eta_via_3pi0_mc.root")'
root -l -b -q '03_mc_simulation/generators/generate_4pi0_dataset.C(1000000,0.9313,1.10,"test_data/vis/mc/4pi0_mc.root")'
root -l -b -q '03_mc_simulation/generators/generate_eta_pi0_via_3pi0_dataset.C(1000000,0.9313,1.10,"test_data/vis/mc/eta_pi0_via_3pi0_mc.root")'

python -m mc_simulation.mc_status \
  --data-dir test_data/vis/mc \
  --channels eta_pi0 pi0pi0 3pi0 eta_via_3pi0 4pi0 eta_pi0_via_3pi0
```

Checkpoint: status must report `6/6`. Inspect `beam_true` and confirm every
generated truth energy is inside channel threshold-adjusted VIS window, never
above `1.10 GeV`.

`eta_2pi0`, `omega_pi0`, and `etaprime` are deliberately absent: production
thresholds lie above VIS endpoint. Do not replace missing required VIS files
with legacy broad-range MC.

## 3. Measure VIS spectrum and build Stage-1 dataset

```bash
python -m bdt_training.beam_spectrum \
  --selected-dir test_data/vis/selected \
  --profile vis \
  --output test_data/vis/bdt/beam_spectrum.npz

python -m bdt_training.build_background_features \
  --mc-dir test_data/vis/mc \
  --signal-channel eta_pi0 \
  --background-channels pi0pi0 3pi0 eta_via_3pi0 4pi0 eta_pi0_via_3pi0 \
  --beam-spectrum test_data/vis/bdt/beam_spectrum.npz \
  --profile vis \
  --output test_data/vis/bdt/features_stage1.npz
```

Checkpoint: record per-channel survival, zero-weight count, and Kish effective
sample size. Confirm profile metadata, feature shape, and finite weights:

```bash
python -c 'import numpy as np; p="test_data/vis/bdt/features_stage1.npz"; d=np.load(p); print(d["beam_profile"].item(), d["energy_min_gev"].item(), d["energy_max_gev"].item(), d["X"].shape, np.isfinite(d["w"]).all())'
```

Expected prefix: `vis 0.9313 1.1`; feature matrix is two-dimensional and all
weights are finite.

## 4. Train VIS BDT

```bash
python -m bdt_training.train_bdt_stage1 \
  --features test_data/vis/bdt/features_stage1.npz \
  --hyperparams 04_bdt_training/artifacts/stage1/best_hyperparams.json \
  --out-dir test_data/vis/bdt/artifacts/stage1
```

Checkpoint: artifact directory contains model, threshold, provenance, metrics,
ROC, score distribution, and feature importance. Record AUC and operating
threshold together with survival, zero weights, and ESS. These are diagnostics,
not new feasibility cuts.

## 5. Reconstruct VIS data

```bash
python -m reconstruction.reconstruct_eta_pi0_bdt \
  --input-dir test_data/vis/selected \
  --output-file test_data/vis/reco/reco_eta_pi0_bdt.root \
  --model-dir test_data/vis/bdt/artifacts/stage1 \
  --profile vis
```

Checkpoint: record input, outside-profile, BDT-rejected, physics-cut, and
written counts. Inspect output tree and assert all stored beam energies satisfy
`0.9313 <= E_gamma <= 1.10 GeV`, including exact endpoints.

## 6. Extract VIS asymmetries

```bash
python 07_observable_extraction/beam_asymmetry.py \
  --raw-bdt test_data/vis/reco/reco_eta_pi0_bdt.root \
  --profile vis \
  --flux-file results/campaign/common/flux_calibrated.root \
  --run-manifest config/run_manifest.csv \
  --output-dir test_data/vis/beam_asymmetry \
  --estimator both \
  --bootstrap-replicas 0
```

Checkpoint: confirm run 2071 is skipped because BREM is missing. Record any
events dropped for missing valid exposure and populated physical bins. ROOT
energy edges must be exactly `[0.9313, 1.10]`; every emitted fit must contain
at least 20 selected `POL1 + POL2` events.

## 7. Combine VIS and UV figures

```bash
python -m observable_extraction.combine_profiles \
  --uv-root results/campaign/uv/beam_asymmetry/beam_asymmetry.root \
  --vis-root results/campaign/vis/beam_asymmetry/beam_asymmetry.root \
  --published-csv 07_observable_extraction/references/ajaka2008_figure4_digitized.csv \
  --output-dir results/campaign/combined
```

Checkpoint: inspect all four PDFs:

- `figure4_experimental.pdf`: VIS row first, followed by four UV rows;
- `figure4_comparison_ajaka2008.pdf`: Ajaka points only in UV rows;
- `comparison_estimators.pdf`: ratio and likelihood in same physical panels;
- `fit_diagnostics.pdf`: ratio-only p-value and `chi2/ndf` diagnostics.
