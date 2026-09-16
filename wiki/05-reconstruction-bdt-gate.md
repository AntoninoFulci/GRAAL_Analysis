# BDT gate

`reconstruction.runtime.stage1_gate.Stage1Gate` filters background-like
events before χ² pairing.

## Loading

`Stage1Gate.load(model_dir)` requires:

- `bdt_stage1.json`;
- `stage1_threshold.txt`;
- `stage1_provenance.json`.

Provenance identifies signal channel, two-meson hypothesis, and exact feature
schema. ηπ⁰ entry point refuses a model trained for incompatible hypothesis.

## Scoring

`accepts_many` computes shared 26-feature vectors, evaluates XGBoost signal
probability column, and keeps scores at or above stored threshold. Score is
classifier output; code does not claim calibration as detector-data
probability.

ROOT runtime buffers up to 20,000 eligible events for vectorized scoring.
Input guards run before buffering, so standard and gated reconstruction start
from same event population. Accepted events continue through identical χ²,
energy, and fit decisions.

Training and inference import same `compute_stage1_features`; cross-module
tests enforce feature and artifact compatibility.
