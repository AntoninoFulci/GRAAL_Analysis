# Testing

The test suite protects numerical physics, persistent schemas, stage
boundaries, package layout, setup behavior, and documentation structure.
Passing a narrow unit test is evidence for that unit only; a completed change
also needs the affected integration tests and the full configured suite.

## Test Layout

`pyproject.toml` discovers these roots:

| Test location | Main responsibility |
|---|---|
| `tests/` | cross-stage contracts, setup, packaging, repository layout, wiki, event-selection integration |
| `00_common/tests/` | shared channel, pairing, Compton, filesystem, tree, feature, and artifact contracts |
| `03_mc_simulation/tests/` | generator inventory/physics and MC status behavior |
| `04_bdt_training/tests/` | loss, weighting, datasets, training, reporting, CLI behavior |
| `05_reconstruction/tests/` | event logic, Stage-1 gate, fits, runtime adapters, sidebands |
| `06_calibration/tests/` | manifest, strip lookup, flux integration, ROOT calibration CLI |
| `07_observable_extraction/tests/` | exposure/event adapters, estimators, background, systematics, output/plots |
| `plots/tests/` | pure kinematics, ROOT reconstruction adapter, Dalitz, Figure 7, resolution plots |

Pytest runs with `--import-mode=importlib`. The numbered parent directories
cannot become normal Python package prefixes, and their child test directories
would otherwise all collide as a package named `tests`.

Tests encode stable behavior rather than implementation text: exact array and
artifact schemas, numerical examples, output objects, failure messages at
trust boundaries, atomic replacement, and CLI defaults.

## Focused Tests

Run the smallest owning set during iteration:

```bash
pytest tests/test_event_selector.py -q
pytest 03_mc_simulation/tests -q
pytest 04_bdt_training/tests tests/test_stage1_contracts.py -q
pytest 05_reconstruction/tests -q
pytest 06_calibration/tests -q
pytest 07_observable_extraction/tests -q
pytest plots/tests -q
pytest tests/test_wiki.py -q
```

Cross-cutting environment and structure changes should include:

```bash
pytest tests/test_repository_layout.py \
  tests/test_setup_script.py \
  tests/test_packaging.py -q
```

Use a node ID for one case while developing:

```bash
pytest 07_observable_extraction/tests/test_background.py::test_signal_leakage_gate_rejects_impure_hard_sideband -q
```

Do not stop at a single passing case after a shared-contract change. Pairing,
feature order, ROOT schemas, and filesystem helpers have consumers across
multiple stages.

## ROOT-Dependent Tests

Some modules import `ROOT` at module load and require the same PyROOT-compatible
interpreter used in production. These include real event-selection, calibration
ROOT adapters, reconstruction I/O, observable ROOT serialization, Dalitz, and
Figure 7 object tests. Run them inside the configured `.venv` after loading the
ROOT environment.

Many numerical cores remain ROOT-free:

- channel/pairing and Stage-1 feature computations;
- photon-loss and weighting calculations;
- reconstruction event logic and kinematic-fit mathematics;
- ratio, likelihood, background, and systematic algorithms;
- plotting kinematics.

This split is deliberate. A ROOT-free unit test gives fast numerical feedback,
while adapter tests prove the actual tree, branch, vector, and file contract.
Do not replace adapter tests with mocks of the behavior they are meant to
verify.

Environment-related skips must remain visible in test output. A skip is not a
pass for the unavailable integration path; record it when reporting
verification on a machine without the dependency or dataset.

## Full Verification

Before commit or handoff:

```bash
pytest -q
git diff --check
git status --short
```

Read the final summary and confirm zero failures. If tests are skipped, inspect
their reasons. Review the diff for unintended generated artifacts, especially
ROOT/NPZ files and anything below `results/` or `data/`.

For Markdown wiki changes, also run `pytest tests/test_wiki.py -q`. It checks
the exact page set, sidebar coverage, internal links, placeholders, Mermaid
fences, required sections, and references to removed architecture.

For any behavior fix, the regression test must fail for the original reason
before the implementation change and pass afterward. A test added after the
code and observed only green does not prove it can detect the regression.
