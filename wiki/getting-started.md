# Getting Started

This guide takes a new analyst from a ROOT-enabled Python installation to a
verified editable checkout. It covers both local development and the analysis
farm, where raw and pre-analysis datasets remain external to the repository.

## Requirements

- Python 3.10 or newer. On the analysis farm, use the interpreter against
  which PyROOT was built.
- CERN ROOT with `import ROOT` available from the selected interpreter.
- Git and a POSIX shell for setup and development commands.
- Python packages listed in `04_bdt_training/requirements.txt`.
- External experiment data for production runs; the repository does not
  download raw, pre-analysis, or flux inputs.

The setup script creates `.venv` with `--system-site-packages` so the virtual
environment can reuse the selected interpreter's PyROOT installation. It then
installs the training requirements and the repository in editable mode.

Load the ROOT environment before running setup. If the base interpreter cannot
import ROOT, setup stops before creating a misleading environment.

## Local Setup

From any directory, invoke the repository script with an explicit mode:

```bash
./scripts/setup.sh --mode local
source .venv/bin/activate
```

Local mode creates or reuses these directories:

```text
data/00_external/
data/01_raw/
data/02_pre_analyzed/
data/03_selected/
```

It does not invent or download detector data. If
`data/00_external/flux.root` is absent, setup completes with a warning because
many development and unit-test tasks do not need the production flux file.

Use a non-default compatible interpreter when needed:

```bash
./scripts/setup.sh --mode local --python /path/to/python3.10
```

## Farm Setup

Farm mode creates the same environment and adds safe symbolic links to
external detector data:

```bash
./scripts/setup.sh --mode farm \
  --python /path/to/python3.10 \
  --raw-target /farm/path/graal_data \
  --pre-target /farm/path/pre_analisi

source .venv/bin/activate
```

The targets must already be directories. Setup creates:

- `data/01_raw/graal_data` -> the supplied raw-data target;
- `data/02_pre_analyzed/pre_analisi` -> the supplied pre-analysis target.

Rerunning the command with the same targets is safe. Setup refuses a broken
link, a link to another target, or an existing non-link path; it never replaces
data silently.

## Verify the Installation

Setup performs a final import check for ROOT and all installed project
packages. You can repeat the essential checks directly:

```bash
python -c 'import ROOT, graal_common, event_selector, mc_simulation, bdt_training, reconstruction, calibration, observable_extraction, plots'
pytest -q
```

Inspect individual entry points before supplying production inputs:

```bash
python 06_calibration/build_run_manifest.py --help
python 06_calibration/build_strip_energy_flux.py --help
python 07_observable_extraction/beam_asymmetry.py --help
python plots/dalitz.py --help
```

The project intentionally exposes stage commands rather than a central
orchestrator. Read the [workflow](workflow) before production execution and use
the [troubleshooting guide](troubleshooting) when an environment or data guard
fails.
