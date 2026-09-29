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

source .venv/bin/activate
```

Setup creates or reuses `.venv` with system site packages, installs
dependencies and the editable project, prepares `data/`, and validates runtime
imports. It never replaces an existing data path or mismatched link.

## Run

Each numbered directory owns one analysis step. Run stage entry points directly;
use `--help` for required inputs and output options.

```bash
python 06_calibration/build_run_manifest.py --help
python 06_calibration/build_strip_energy_flux.py --help
python 07_observable_extraction/beam_asymmetry.py --help
python plots/dalitz.py --help
```

Calibration is step 06. Observable extraction follows as step 07. Plotting is
an unnumbered consumer of completed analysis outputs and writes generated files
under ignored `results/` paths.

## Test

```bash
pytest -q
```
