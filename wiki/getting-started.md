# Getting started

Use Python ≥3.10 compatible with the installed CERN ROOT/PyROOT, and load the ROOT environment before setup. Run commands from the repository root unless an explicit checkout path is supplied. The pinned Python dependencies are in [pyproject.toml](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/pyproject.toml).

```bash
./scripts/setup.sh --mode local
source .venv/bin/activate
python scripts/run_pipeline.py --help
```

For a farm installation, choose the interpreter and external raw-data location:

```bash
./scripts/setup.sh --mode farm --python /path/to/pyroot-compatible-python --raw-target /farm/path/graal_data
```

Setup defaults to a venv with system site packages. The optional `--install user` uses the selected base Python and leaves an existing venv alone; it requires an enabled user site and a Python installation that permits user installs. Setup refuses mismatched data links. Run `./scripts/setup.sh --help` for supported options.

Production h80 files belong under `data/02_pre_analyzed/`; external raw flux is `data/00_external/flux.root`. The common manifest [config/common_inputs.json](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/config/common_inputs.json) authenticates the curated run catalog, quality policy, and raw flux. Missing files or digest mismatches must be resolved before a campaign.

The reduced UV+VIS cohort in `data_test/sample/` is immutable diagnostic input. It is not a production normalization sample. The cohort was deleted during the 24 October 2026 cleanup; a separately requested rebuild and manifest validation are required first (see [local availability](data-and-artifacts#local-availability-after-cleanup)). Once available, start its campaign with:

```bash
python scripts/run_pipeline.py --mode test_data
```

The launcher displays validated configuration and asks before starting. This is a scientific computation, not an installation smoke test. Use `--help` for a non-computing check. Wheel installations of `graal-workflow` need `--repo-root /path/to/GRAAL_Analysis` to locate native checkout resources; editable installations can resolve their source checkout.

The former theory package is retired. No theory installation or calculation is part of setup; see the [restart boundary](09-theory).

See [commands](commands-and-configuration) for production and manual extraction, and [maintenance](maintenance) for isolated tests.
