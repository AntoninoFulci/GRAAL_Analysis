# Testing

Repository has unit, contract, adapter, and real-data integration layers.

## Full suite

```bash
pytest -q
```

`pyproject.toml` discovers tests in:

```text
tests/
00_common/tests/
03_mc_simulation/tests/
04_bdt_training/tests/
05_reconstruction/tests/
06_plots/tests/
06_observable_extraction/tests/
```

`--import-mode=importlib` prevents each numbered directory's `tests` package
from colliding with others.

## Test boundaries

| Area | Coverage |
|---|---|
| `tests/` | Packaging, repository ownership, shell pipeline contract, calibration CLI, cross-module Stage-1 schemas |
| `00_common/tests/` | Channel registry, cross-sections, pairing, manifest, artifact schemas, strip-energy/flux calculations |
| `03_mc_simulation/tests/` | Generator source contracts and MC status behavior |
| `04_bdt_training/tests/` | Beam reweighting, photon loss, MC decoding, weights, NPZ storage, fitting, reporting, CLI facade |
| `05_reconstruction/tests/` | CLI translation, event decisions, pairing physics, kinematic fit, ROOT runtime adapter, BDT gate |
| `06_plots/tests/` | Kinematics, reconstruction data adapter, Dalitz orchestration, resolution helpers, Compton plot calculations |
| `06_observable_extraction/tests/` | Flux joins, pair projections, both Sigma estimators, sidebands, bootstrap/systematics, ROOT/PDF products, synthetic end-to-end recovery |

Most physics and schema tests are ROOT-free. ROOT-facing tests use small test
doubles where they verify adapter behavior without detector files. Generator
tests inspect source contracts rather than running million-event macros.

## Stable cross-module contracts

Root-level tests protect boundaries most likely to drift during refactoring:

- numbered directory to Python package mapping;
- eight-stage shell interface and public flags;
- shared ordered 26-feature vector;
- exact Stage-1 NPZ keys and metadata;
- exact runtime model bundle and provenance keys;
- default model location used by reconstruction.

## Real-data integration

`--test-data` redirects detector and result paths to `test_data/` while keeping
production MC and model artifacts:

```bash
mkdir -p test_data/raw
# Copy a small number of representative detector runs into test_data/raw.
./run_pipeline.sh --test-data --nevents 1000
```

This checks ROOT file discovery, tree names, branch compatibility, directory
creation, and stage-to-stage plumbing. It does not replace unit tests and does
not establish detector calibration or physics validity from a small sample.

Use skip flags to exercise downstream integration against existing fixtures:

```bash
./run_pipeline.sh --test-data \
  --skip-preanalysis --skip-selection --skip-mc \
  --skip-features --skip-grid-search --skip-train
```

## Long-running boundaries

MC generation, full detector pre-analysis, training, and full reconstruction
are not part of ordinary pytest execution. Their lightweight contracts are
tested; production-scale execution remains an explicit analysis operation.
