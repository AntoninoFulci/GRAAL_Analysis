# Development

Development must preserve both Python package contracts and physics artifact
contracts. The repository deliberately separates ROOT-dependent adapters from
NumPy-oriented cores so most numerical behavior remains fast to test while
real file boundaries are still exercised where necessary.

## Environment

Use Python 3.10 or newer, but choose the interpreter against which the local
CERN ROOT/PyROOT installation was built. A newer unrelated Python can satisfy
the version floor and still fail `import ROOT`.

```bash
python3 -c 'import sys, ROOT; print(sys.version); print(ROOT.gROOT.GetVersion())'
./scripts/setup.sh --mode local --python /path/to/compatible/python3
source .venv/bin/activate
```

The virtual environment uses system site packages because PyROOT is normally
installed with ROOT rather than from PyPI. Python dependencies are pinned or
bounded in `04_bdt_training/requirements.txt`: uproot, awkward, XGBoost,
scikit-learn, NumPy, matplotlib, tqdm, and pytest.

Local setup creates empty data directories. Farm setup links external raw and
pre-analysis stores after validating targets and existing paths. Neither mode
downloads experiment data or fabricates `flux.root`.

## Editable Installation

Setup performs:

```bash
python -m pip install -r 04_bdt_training/requirements.txt
python -m pip install -e .
```

The editable installation is required because entry points import stable
package names such as `reconstruction` and `calibration` while source remains
in visibly ordered directories. Source edits are then immediately visible
without reinstalling.

Verify the environment after setup or dependency changes:

```bash
python -c 'import ROOT, graal_common, event_selector, mc_simulation, bdt_training, reconstruction, calibration, observable_extraction, plots'
pytest tests/test_packaging.py tests/test_repository_layout.py -q
```

## Package Imports

Python identifiers cannot begin with digits. `pyproject.toml` maps repository
directories to import packages:

| Source directory | Import package |
|---|---|
| `00_common/` | `graal_common` |
| `02_event_selector/` | `event_selector` |
| `03_mc_simulation/` | `mc_simulation` |
| `04_bdt_training/` | `bdt_training` |
| `05_reconstruction/` | `reconstruction` |
| `06_calibration/` | `calibration` |
| `07_observable_extraction/` | `observable_extraction` |
| `plots/` | `plots` |

Imports must use these package names, never numeric directory names. Shared
physics, tree, filesystem, and Stage-1 contracts belong in `graal_common`.
Stage packages own their algorithms and adapters. Plotting may consume shared
physics but must not become a second reconstruction implementation.

`01_pre_analysis/` remains C++/ROOT code rather than a Python package. Its
persisted `h80` tree is the boundary to Python stages.

## Change Workflow

1. Identify the owning layer and read its tests and public artifact contract.
2. Check working-tree status and preserve unrelated user changes.
3. For behavior changes, write a focused failing test and confirm the expected
   failure before implementation.
4. Make the smallest coherent change in the responsible package. Do not copy
   masses, feature order, pairing rules, filenames, or schemas into a new
   private definition.
5. Run the owning package tests, then affected downstream contract tests.
6. Run `pytest -q` and `git diff --check` before declaring completion.
7. Inspect the diff and stage explicit paths; do not commit generated data from
   ignored locations accidentally.

Typical focused checks:

```bash
pytest 00_common/tests/test_pairing.py tests/test_stage1_contracts.py -q
pytest 05_reconstruction/tests -q
pytest 06_calibration/tests 07_observable_extraction/tests -q
pytest plots/tests -q
```

### Contract-change checklist

- A ROOT branch/tree change requires all readers and tests to be reviewed.
- A Stage-1 feature change requires model provenance and runtime compatibility
  review; a model trained with old ordering is not interchangeable.
- A run-manifest or calibration schema change requires versioning and loader
  changes rather than permissive fallback.
- A physics constant or hypothesis change belongs in the shared registry and
  must be checked in training, reconstruction, plotting, and observables.
- A generated runtime bundle should be treated as one release; update model,
  threshold, provenance, and applicable reports together.

Do not “fix” a failing trust-boundary check by weakening validation. Determine
whether the producer is wrong, the artifact is stale, or a deliberate schema
migration is required.
