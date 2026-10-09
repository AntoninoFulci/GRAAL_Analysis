# GRAAL Analysis

Analysis pipeline for GRAAL photoproduction data, focused on
**γp → pηπ⁰** with η → γγ and π⁰ → γγ. It compares standard photon pairing
by χ² with the same reconstruction preceded by a Stage-1 BDT background gate,
then applies a 6C kinematic fit.

## Documentation

See the [GitHub Wiki](https://github.com/AntoninoFulci/GRAAL_Analysis/wiki)
for the architecture, scientific workflow, stage guides, data contracts,
commands, testing strategy, troubleshooting, and known limitations.

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
  --raw-target /farm/path/graal_data

source .venv/bin/activate
```

Setup creates or reuses `.venv` with system site packages, installs
dependencies and the editable project, prepares `data/`, and validates runtime
imports. Copy `pre_analisi_*.root` files directly into `data/02_pre_analyzed/`.
Setup never replaces an existing data path or mismatched link.

## Run

The supported full launcher begins from pre-analysis `h80` ROOT files. Test
mode uses the local UV/VIS fixtures; production uses every matching period:

```bash
python scripts/run_pipeline.py --mode test_data
python scripts/run_pipeline.py --mode production
```

Both modes accept `--phi-bins 8|12|16` (default: `12`). Each launch produces
one binning for UV/VIS ratio fits, preserving the campaign output layout.
Ratio Sigma and its error use the fixed finite-bin divisors `0.9003`,
`0.9549`, and `0.9745`, respectively; likelihood remains unscaled. See the
[scientific verification and convention](docs/research/2026-10-09-finite-phi-bin-correction.md).

Calibration runs once. Production reuses validated selection, MC, and BDT
artifacts in `data/` for up to ten days; `test_data` rebuilds its parallel
artifacts on every run. Reconstruction, asymmetry extraction, and plots live
under the named campaign in `results/`. See the
[full pipeline runbook](docs/runbooks/full-pipeline.md) for server setup,
outputs, and failure behavior.

Each numbered directory still owns one analysis step. For advanced or manual
operation, run stage entry points directly and use `--help` for inputs and
output options.

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
