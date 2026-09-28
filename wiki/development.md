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
graal-pipeline --help
graal-pipeline
graal-pipeline status --final-state eta_pi0
```

For a focused iteration, prepare a dry-run plan or run a module directly:

```bash
graal-pipeline plan extract beam-asymmetry \
  --final-state eta_pi0 \
  --non-interactive \
  --old-policy reuse \
  --stale-policy rebuild \
  --untracked-policy rebuild
```

Interpreter, ROOT executable, paths, event counts, threads, and validation
policies are configured in `config/pipeline.toml` or in an alternate file:

```bash
graal-pipeline --config config/pipeline-farm.toml status \
  --final-state eta_pi0
```

Unless an alternate TOML explicitly sets `runtime.python_executable`, Python
stages inherit the exact interpreter used to launch the orchestrator. Running
`.venv/bin/python -m graal_pipeline` is therefore sufficient even when the
shell's unqualified `python` points to the system installation.

See [Pipeline orchestrator](pipeline-orchestrator) for the complete interface.

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
