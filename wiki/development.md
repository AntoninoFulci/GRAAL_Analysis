# Development setup

## Prerequisites

- Python 3.10 or newer
- CERN ROOT with PyROOT
- compiler/runtime support required by ROOT and XGBoost

Python version must match installed PyROOT build. Project floor is Python 3.10
because analysis-farm PyROOT is built against Python 3.10.12.

## Install

Load the ROOT environment first. For a local installation, run from any
directory:

```bash
./scripts/setup.sh --mode local [--python /path/to/python]
```

For the analysis farm:

```bash
./scripts/setup.sh --mode farm \
  --python /path/to/python3.10 \
  --raw-target /farm/path/graal_data \
  --pre-target /farm/path/pre_analisi
```

Setup creates `.venv` with `--system-site-packages` so centrally installed
PyROOT remains visible. Existing valid `.venv` is reused. Farm targets must be
existing directories; setup creates absolute links at
`data/01_raw/graal_data` and `data/02_pre_analyzed/pre_analisi`. Existing
paths, broken links, or links to different targets cause a non-destructive
failure.

Activate environment and confirm imports before long jobs:

```bash
source .venv/bin/activate
python -c "import graal_common, event_selector, mc_simulation, bdt_training, reconstruction, plots"
```

`04_bdt_training/requirements.txt` pins `uproot`, `awkward`, and XGBoost and
sets minimum versions for scikit-learn, NumPy, matplotlib, tqdm, and pytest.
SciPy is used directly by fitting and training code and is also installed by
the scientific dependency stack.

## Run locally

```bash
./run_pipeline.sh --help
./run_pipeline.sh --test-data
```

For a focused iteration, use stage skip flags or run a module directly. The
pipeline preflight accepts a custom interpreter:

```bash
PYTHON=.venv/bin/python ./run_pipeline.sh --help
```

ROOT executable can be overridden similarly:

```bash
ROOT_EXEC=/path/to/root ./run_pipeline.sh --help
```

## Tests

```bash
pytest -q
pytest 05_reconstruction/tests -q
pytest tests/test_stage1_contracts.py -q
```

See [Testing](testing) for boundaries and real-data integration.

## Documentation

Edit pages under `wiki/`. They are versioned with source. To publish them to
GitHub Wiki after review:

```bash
scripts/sync-wiki.sh
```

That command performs network and remote Git writes. Analysis and tests do not
require network services or external APIs.

## Generated data

ROOT, NPZ, local detector data, test data, rebuilt results, caches, and graph
outputs are ignored. Keep durable schemas and provenance in source; do not
commit bulk runtime data.
