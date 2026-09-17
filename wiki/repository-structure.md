# Repository structure

## Top-level layout

| Path | Responsibility |
|---|---|
| `00_common/` | Shared physics, ROOT I/O, calibration, and Stage-1 contracts |
| `01_pre_analysis/` | ROOT pre-analysis macro, detector cut manager, cut files |
| `02_event_selector/` | h80-to-h85 event preselection |
| `03_mc_simulation/` | MC status command, ROOT generators, smearing, tests |
| `04_bdt_training/` | Beam reweighting, datasets, feature build, search, training, versioned model artifacts |
| `05_reconstruction/` | ROOT-free reconstruction core, runtime adapters, channel entry points, validation |
| `06_plots/` | Plot entry points, reusable kinematics/data adapters, versioned reference artifact |
| `config/` | Versioned run manifest |
| `scripts/` | Repository setup, manifest, strip-energy/flux, and wiki synchronization commands |
| `tests/` | Cross-package packaging, layout, pipeline, calibration, and Stage-1 contract tests |
| `wiki/` | Source of GitHub Wiki pages |
| `run_pipeline.sh` | Eight-stage pipeline orchestrator |
| `pyproject.toml` | Package mapping, Python floor, pytest discovery |

Runtime contents under `data/`, plus `results/`, `test_data/`, and
`graphify-out/`, are ignored local analysis areas. Small versioned exception:
`data/00_external/flux.root`. Executable defaults remain authoritative; see
[Pipeline](pipeline) and [Data and storage](data-and-storage).

## Shared package

| Package | Contents |
|---|---|
| `graal_common.physics` | Masses, hypotheses, MC channels, cross-sections, pairing |
| `graal_common.io` | Preselection tree resolution and four-vector conversion |
| `graal_common.calibration` | Run manifest and strip-energy/flux contracts |
| `graal_common.stage1` | Shared 26-feature computation and model artifact schemas |

These modules are shared because training, inference, reconstruction, and
calibration must use identical definitions.

## Responsibility-oriented subpackages

- `bdt_training.dataset`: MC decoding, photon-loss sampling, channel weights,
  and typed NPZ storage.
- `bdt_training.training`: pure model fitting, callbacks, and reports.
- `reconstruction.core`: event decisions, two-meson definitions, and 6C fit.
- `reconstruction.runtime`: CLI configuration, ROOT event loop, and BDT gate.
- `plots.core`: reconstruction-tree adapter and ROOT-independent kinematics.

## Package-name mapping

Python identifiers cannot begin with digits. `pyproject.toml` maps physical
directories to importable packages:

| Directory | Python package |
|---|---|
| `00_common/` | `graal_common` |
| `02_event_selector/` | `event_selector` |
| `03_mc_simulation/` | `mc_simulation` |
| `04_bdt_training/` | `bdt_training` |
| `05_reconstruction/` | `reconstruction` |
| `06_plots/` | `plots` |

`01_pre_analysis/` contains ROOT C++ macros and is not a Python package.

## Versioned and generated artifacts

`04_bdt_training/artifacts/stage1/` contains model bundle consumed by runtime
reconstruction, including model, threshold, metrics, provenance, and search
reports. `04_bdt_training/artifacts/legacy_feature_reports/` preserves older
report images but is not runtime input. `06_plots/artifacts/` contains a
versioned Compton-polarization reference PDF.

Bulk ROOT/NPZ data and rebuilt results are ignored. See
[Data and storage](data-and-storage) for ownership and lifecycle.

## Planned layout changes

Not implemented yet:

- move plotting out of numbered analysis stages by renaming `06_plots/` to an
  unnumbered plotting directory;
- create `06_observable_extraction/` for yield, flux-normalization, and
  observable-extraction workflows;
- move `scripts/build_strip_energy_flux.py` into that stage, potentially under
  a dedicated calibration subdirectory;
- update package mappings, imports, tests, pipeline commands, and wiki links in
  the same refactor.

## Wiki publication

`wiki/` is canonical documentation source in this repository.
`scripts/sync-wiki.sh` clones GitHub Wiki, replaces its Markdown pages,
commits, and pushes them. Run it only when remote publication is intended.
