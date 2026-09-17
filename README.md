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
./run_pipeline.sh --help
./run_pipeline.sh
./run_pipeline.sh --raw-dir /farm/raw/graal_data \
  --pre-dir /farm/pre/pre_analisi --selected-dir data/03_selected
```

`run_pipeline.sh` orchestrates eight stages: detector pre-analysis, event
selection, Monte Carlo generation, feature construction, hyperparameter
search, BDT training, reconstruction, and plotting.

## Test

```bash
pytest -q
```

Architecture, data formats, configuration, component guides, and operational
details live in the [project wiki](https://github.com/AntoninoFulci/GRAAL_Analysis/wiki).
