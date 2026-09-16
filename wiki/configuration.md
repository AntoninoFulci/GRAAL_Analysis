# Configuration

Configuration is distributed by responsibility. No central settings file
overrides every stage.

## Pipeline configuration

`run_pipeline.sh` owns stage paths, stage ordering, reuse policy, and public
pipeline flags. `PYTHON` and `ROOT_EXEC` select executables without changing
source.

See [Pipeline and entry points](pipeline) for complete defaults.

## Run manifest

`config/run_manifest.csv` is versioned configuration for calibration. Each row
contains:

```text
run_number,source_period,target,beam_type,group,classification_source,source_file
```

`graal_common.calibration.run_manifest` accepts targets `P`, `D`, or
`UNKNOWN`; beam types `UV`, `VIS`, or `UNKNOWN`; and groups `P_UV`, `P_VIS`,
`D_UV`, `D_VIS`, or `UNASSIGNED`. Classification source records whether a row
was automatic, manual, or unresolved.

Generate or validate it with:

```bash
python scripts/build_run_manifest.py --input-dir DATA_ROOT --output config/run_manifest.csv
python scripts/build_run_manifest.py --validate config/run_manifest.csv
```

## Physics registry

`graal_common.physics.channels` is authoritative for:

- particle masses and tagger resolution;
- two-meson `Hypothesis` objects;
- nine `MCChannel` records;
- MC filenames, photon branch conventions, production thresholds, reference
  cross-sections, and signal branching-ratio linkage.

Signal channel and two-meson hypothesis are separate concepts. A channel that
does not determine a complete four-photon hypothesis requires explicit
`--hypothesis` configuration during feature construction.

## Stage-1 configuration

Feature construction accepts MC directory, signal channel, optional background
subset, optional hypothesis, signal prior, beam spectrum, random seed, and
photon-loss parameters. Output NPZ embeds signal channel, hypothesis, signal
prior, beam-reweighting state, and ordered feature names.

Training defaults live in `bdt_training.training.stage1_training.TrainingConfig`.
Optional grid-search output can override classifier parameters. Training writes
`stage1_provenance.json`; reconstruction validates its hypothesis before using
model scores.

## Reconstruction configuration

Common CLI options translate into `reconstruction.runtime.reco_core.RecoConfig`:

| Field | Default |
|---|---:|
| input tree | `auto` |
| χ² cut | `10.0` |
| partner | proton |
| missing-mass half-width | `0.06 GeV` |
| kinematic fit | enabled for ηπ⁰ entry points |
| minimum fit confidence level | `0.01` |

With fit enabled, fit confidence level replaces missing-mass selection. The
2π⁰ entry point does not expose fit flags and uses non-fit defaults.

## Calibration configuration

`graal_common.calibration.strip_energy_flux` defines built-in energy binnings
`ajaka_cross_section` and `ajaka_sigma`. `scripts/build_strip_energy_flux.py`
accepts repeatable custom `NAME:EDGE,EDGE,...` binnings plus thresholds for
minimum strip statistics, maximum MAD, and monotonic tolerance.

## Versioned artifacts as configuration

`04_bdt_training/artifacts/stage1/` is runtime configuration plus model state:

- `bdt_stage1.json`
- `stage1_threshold.txt`
- `stage1_provenance.json`
- `stage1_metrics.txt`
- optional search/report artifacts

Runtime gate loading requires model, threshold, and provenance. Missing or
incompatible files fail before event scoring.
