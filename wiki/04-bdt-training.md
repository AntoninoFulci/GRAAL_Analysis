# 04 — Stage-1 BDT training

Stages 4–6 build a binary XGBoost gate that separates configured signal channel
from registry-defined physical backgrounds. Gate filters events before χ²
pairing; it does not reconstruct mesons.

## Structure

- `beam_spectrum.py`: measure selected-data beam spectrum and reweight MC;
- `dataset/mc_samples.py`: decode channel photons, simulate losses, compute
  features;
- `dataset/channel_weights.py`: integrate channel cross-sections over beam
  flux and compute class shares;
- `dataset/stage1_dataset.py`: validate and persist NPZ schema;
- `build_background_features.py`: CLI orchestration and compatibility exports;
- `grid_search_stage1.py`: randomized hyperparameter search;
- `training/stage1_training.py`: pure fit/evaluation engine;
- `training/stage1_reporting.py`: metrics and figures;
- `train_bdt_stage1.py`: artifact-producing CLI facade.

## Weighting decisions

MC generator beam is flat, so every channel is reweighted onto measured
selected-data spectrum. Background mixture uses energy-dependent channel
cross-sections and generated-event counts while preserving acceptance.

Signal cross-section is intentionally absent: measuring it is analysis goal.
`--signal-prior` explicitly controls signal-versus-background training share;
backgrounds retain relative physics weights.

## Commands

```bash
python -m bdt_training.beam_spectrum \
  --selected-dir data/03_selected --tree auto \
  --output 04_bdt_training/data/beam_spectrum.npz

python -m bdt_training.build_background_features \
  --mc-dir 03_mc_simulation/data \
  --signal-channel eta_pi0 --signal-prior 0.5 \
  --beam-spectrum 04_bdt_training/data/beam_spectrum.npz \
  --output 04_bdt_training/data/features_stage1.npz

python -m bdt_training.grid_search_stage1 \
  --features 04_bdt_training/data/features_stage1.npz \
  --out-dir 04_bdt_training/artifacts/stage1 --n-iter 30

python -m bdt_training.train_bdt_stage1 \
  --features 04_bdt_training/data/features_stage1.npz \
  --out-dir 04_bdt_training/artifacts/stage1 \
  --hyperparams 04_bdt_training/artifacts/stage1/best_hyperparams.json
```

## Runtime contract

Training writes model, selected threshold, metrics, provenance, and report
plots. Gate requires model, threshold, and provenance, validates hypothesis,
then computes same shared features used for training.

See [Stage-1 features](04-bdt-training-features) and
[Data and storage](data-and-storage).
