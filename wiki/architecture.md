# Architecture and ownership

`graal_workflow` plans and executes stages, validates paths and provenance, and manages locks and publication. It performs no physics calculations. `scripts/run_pipeline.py` is its thin checkout entry point; `graal-workflow` is the installed CLI.

| Source | Import / responsibility |
| --- | --- |
| `00_common/` | `graal_common`: masses, channels, beam/energy definitions, ordered features, ROOT metadata, filesystem and parallel contracts |
| `01_pre_analysis/` | Native ROOT/C++ h70 conversion and period-dependent detector cuts |
| `02_event_selector/` | `event_selector`: h80 → selected h85 |
| `03_mc_simulation/` | `mc_simulation`: event generators and separate GEANT4 geometry work |
| `04_bdt_training/` | `bdt_training`: spectra, weighted features, search, training and bundle |
| `05_reconstruction/` | `reconstruction`: pairing, optional BDT gate, missing mass and cutflow |
| `06_calibration/` | `calibration`: run catalogs, strip-energy calibration, measured ROOT flux and QA/cache |
| `07_flux_studies/` | `flux_studies`: optional offline audits and experimental recovery studies |
| `08_observable_extraction/` | `observable_extraction`: sample loading, estimators, backgrounds, systematic components and output |
| `plots/` | Rendering and adapters for completed analysis products |

[Package mapping](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/pyproject.toml) makes numbered folders importable. [Workflow source](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/graal_workflow) separates `models`, `paths`, `planning`, `execution`, `resources`, `artifact_manifest`, and `cli`. Calibration exposes public owners for common input validation, numerical strip calibration, native ROOT production, inspection, QA, and cache. Stage 08 separates CLI dispatch, single/period workflows, extraction, background/systematic calculations, and ROOT I/O.

ROOT-free numerical cores can be tested independently; ROOT adapters enforce boundary contracts. Native resources remain in the checkout. No scheduler or generic DAG engine is required. [Workflow](workflow) describes actual order, which is not a simple ascending traversal of folder numbers.
