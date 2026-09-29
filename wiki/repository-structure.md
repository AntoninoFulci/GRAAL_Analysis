# Repository Structure

Physical directories are numbered so processing order is visible in a file
listing. `pyproject.toml` maps those directories to importable package names
because Python package identifiers cannot begin with digits.

## Top-Level Layout

| Path | Ownership |
|---|---|
| `00_common/` | Shared physics registries, numerical contracts, ROOT-array adapters, filesystem utilities, and Stage-1 schemas |
| `01_pre_analysis/` | ROOT selector and detector/run-period cut implementations |
| `02_event_selector/` | `h80` to `h85` event preselection |
| `03_mc_simulation/` | Channel generators, smearing helper, and file-status reporting |
| `04_bdt_training/` | Beam spectrum, dataset, weighting, search, training, reporting, and Stage-1 artifacts |
| `05_reconstruction/` | ROOT-free event/fit core, runtime adapters, and reconstruction entry points |
| `06_calibration/` | Run-manifest and strip-energy/flux calibration |
| `07_observable_extraction/` | Estimators, corrections, covariance, I/O, diagnostics, and public observable products |
| `plots/` | Reconstruction and beam diagnostic consumers |
| `config/` | Versioned analysis configuration such as `run_manifest.csv` |
| `data/` | Local external/raw/intermediate data layout; large scientific inputs are not repository source |
| `scripts/` | Environment setup and explicit wiki publication tools |
| `tests/` | Cross-package, packaging, setup, layout, and integration contracts |
| `test_data/` | Small integration fixtures when present locally |
| `docs/superpowers/` | Reviewed design specifications and implementation plans |
| `wiki/` | Versioned Markdown source published to the GitHub Wiki |

`00_common/` is numbered only so it sorts before all consumers. It is not an
executable pipeline stage. `plots/` is intentionally unnumbered because it
consumes completed results rather than producing an input required by the next
scientific stage.

## Package Name Mapping

Editable installation uses these mappings from `pyproject.toml`:

| Physical directory | Import package |
|---|---|
| `00_common/` | `graal_common` |
| `02_event_selector/` | `event_selector` |
| `03_mc_simulation/` | `mc_simulation` |
| `04_bdt_training/` | `bdt_training` |
| `05_reconstruction/` | `reconstruction` |
| `06_calibration/` | `calibration` |
| `07_observable_extraction/` | `observable_extraction` |
| `plots/` | `plots` |

Subpackages are listed explicitly so editable installation exposes numerical
cores, runtime adapters, calibration adapters, plotting helpers, and tests
without renaming the on-disk stage layout. Stage 01 remains ROOT C++ source and
is not installed as a Python package.

Pytest uses `--import-mode=importlib`. This prevents separate stage-local
`tests/` directories from colliding under the single top-level name `tests`.

## Generated and External Data

Setup prepares four local data tiers:

| Path | Meaning |
|---|---|
| `data/00_external/` | External reference inputs, including optional `flux.root` |
| `data/01_raw/` | Raw detector input or a farm link |
| `data/02_pre_analyzed/` | Pre-analysis files or a farm link |
| `data/03_selected/` | Event-selection output |

Monte Carlo, training datasets, reconstruction files, calibration outputs, and
figures can be large and are generally generated locally. Production plots and
analysis products belong under ignored `results/` paths unless a small file is
deliberately versioned as a stable contract or reference artifact.

The versioned Stage-1 bundle under `04_bdt_training/artifacts/stage1/` is an
intentional exception: runtime reconstruction tests and default model loading
depend on its model, threshold, and provenance. See [Data and artifacts](data-and-artifacts)
for the complete ownership matrix.
