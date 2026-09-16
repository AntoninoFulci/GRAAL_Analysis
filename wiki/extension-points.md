# Extension points

Extensions should enter through existing registries and interfaces, then add
tests at owning boundary.

## Add a Monte Carlo channel

1. Add `MCChannel` in `graal_common.physics.channels` with production masses,
   file/branch convention, and valid weighting metadata.
2. Add matching `03_mc_simulation/generators/generate_<name>_dataset.C`.
3. Ensure tree declares `n_true_gamma` unless using named signal branches.
4. Add registry, filename, threshold, and generator-source tests.

Pipeline and MC status discover channel through `CHANNEL_NAMES`; no second
shell list should be added.

## Add a two-meson hypothesis

Add `Hypothesis` to `HYPOTHESES` with labels, masses, and pole windows. Pairing
enumeration, feature names, and χ² derive from it. Add pairing and feature tests,
then explicitly bind eligible channels or pass CLI override.

## Add detector cuts or acquisition period

Add correctly named cut macros under `01_pre_analysis/cuts/` and matching raw
run folder. `BuildCutMap` maps period to run IDs. Use `RequireCut` for mandatory
classification and encode genuinely absent detector/target case explicitly.

## Add calibration binning

Use repeatable `--binning NAME:EDGE,...` for configuration-only addition. For
new built-in preset, add `EnergyBinning` in
`graal_common.calibration.strip_energy_flux` plus boundary and serialization
tests. Preserve half-open bin convention and explicit out-of-range QA.

## Add calibration input adapter

ROOT reads belong in `scripts/build_strip_energy_flux.py`; pure lookup,
integration, aggregation, and writers stay under `graal_common.calibration`.
Adapter must feed existing dataclasses and retain atomic publication/error
contract.

## Change Stage-1 feature schema

Modify `graal_common.stage1.features`, update ordered feature names and exact
contract tests, rebuild NPZ dataset, retrain model, and publish matching
provenance. Training and gate must continue importing same function. Existing
model artifacts are incompatible when order or meaning changes.

## Add a reconstruction gate

Implement runtime `Gate` protocol:

```python
def accepts_many(photons, protons, beams) -> np.ndarray:
    ...
```

Return one boolean per event. Inject through `run_reconstruction`; do not fork
event decisions. Test batching equivalence and retained-event invariants.

## Add a reconstruction channel

Define `Channel` with hypothesis and add small entry point translating CLI into
`RecoConfig`. Reuse `run_reconstruction`. Add CLI-default, branch-label,
pairing, and event-logic tests. Add fit only when reaction model/covariance are
explicit and validated.

## Add fit reaction or resolution model

Implement `FitReactionModel` or `ResolutionModel` contract in
`reconstruction.core.kinematic_fit`. Keep solver ROOT-free. Add closure tests,
constraint/Jacobian checks, failure cases, and provenance describing
calibration status.

## Add plot product

Put reusable calculations in `plots.core`; ROOT/matplotlib orchestration stays
in entry-point module. Read reconstructed data through
`plots.core.reconstruction_data` where schema applies. Add pure calculation
tests and adapter tests before integration output.

## Change persisted schemas

Update writer, reader, validation, cross-module tests, and
[Data and storage](data-and-storage) together. Prefer explicit rejection with
migration guidance over guessing meaning of incomplete older artifact.
