# GRAAL Analysis

Analysis pipeline for GRAAL photoproduction data, focused on
**γp → pηπ⁰** with η → γγ and π⁰ → γγ. It compares standard photon pairing
by χ² with the same reconstruction preceded by a Stage-1 BDT background gate,
then applies a 6C kinematic fit.

## Requirements

- Python 3.10 or newer, using the interpreter compatible with PyROOT
- CERN ROOT with PyROOT
- Python dependencies from `04_bdt_training/requirements.txt`

## Setup

Load the ROOT environment first, then run repository setup from any directory:

```bash
./scripts/setup.sh --mode local
```

On the analysis farm, select the PyROOT-compatible interpreter and link the
external detector data:

```bash
./scripts/setup.sh --mode farm \
  --python /path/to/python3.10 \
  --raw-target /farm/path/graal_data \
  --pre-target /farm/path/pre_analisi
```

Setup creates or reuses `.venv` with system site packages, installs
dependencies and the editable project, prepares `data/`, and validates runtime
imports. It never replaces an existing data path or mismatched link.

## Run

```bash
graal-pipeline --help
graal-pipeline
graal-pipeline plan extract beam-asymmetry --final-state eta_pi0
graal-pipeline extract beam-asymmetry --final-state eta_pi0
```

`python -m graal_pipeline` is equivalent to the installed console command.
The orchestrator inspects existing artifacts, validates checkpoints, and runs
only the stages required by the requested result. Paths and farm overrides are
configured in `config/pipeline.toml`; relative paths are resolved from the
repository root.

See the [pipeline orchestrator guide](wiki/pipeline-orchestrator.md) for the
wizard, non-interactive policies, validation profiles, logs, and migration
status.

## Test

```bash
pytest -q
```

Architecture, data formats, configuration, component guides, and operational
details live in the [project wiki](https://github.com/AntoninoFulci/GRAAL_Analysis/wiki).
