# Pipeline and entry points

`run_pipeline.sh` is the primary application entry point. It runs a batch
analysis from detector ROOT files through reconstructed events and plots.

```bash
./run_pipeline.sh [options]
./run_pipeline.sh --help
```

Before any stage, it verifies that `graal_common`, `event_selector`,
`mc_simulation`, `bdt_training`, `reconstruction`, and `plots` are importable.
Run `python -m pip install -e .` when this preflight fails.

## Stage flow

| Stage | Command or implementation | Input | Output |
|---:|---|---|---|
| 1 | ROOT `AnalyzeAll` in `PreAnalysis.C` | `data/01_raw/graal_data/` | `data/02_pre_analyzed/pre_analisi/pre_*.root`, tree `h80` |
| 2 | `python -m event_selector.select_events` | pre-analysis ROOT files | `data/03_selected/*.root`, tree `h85` |
| 3 | ROOT channel generators | registry-defined macros | `03_mc_simulation/data/*_mc.root`, tree `mc` |
| 4 | `bdt_training.beam_spectrum` and `build_background_features` | selected data and MC | beam and feature NPZ files |
| 5 | `bdt_training.grid_search_stage1` | Stage-1 feature NPZ | search CSV and best hyperparameters |
| 6 | `bdt_training.train_bdt_stage1` | features and optional hyperparameters | Stage-1 runtime bundle and reports |
| 7 | two reconstruction entry points | selected data and optional BDT bundle | χ² and BDT ROOT trees |
| 8 | `plots.dalitz` and optional `plots.kinfit_resolution` | reconstructed data and signal MC | PDFs and `istogrammi.root` |

Runtime detector inputs live under `data/`; rebuilt analysis products live
under `results/`. Both are ignored by Git.

## Options

| Option | Default | Effect |
|---|---:|---|
| `--test-data` | off | Remap detector data and results to `test_data/`; MC and model stay unchanged |
| `--raw-dir DIR` | `data/01_raw/graal_data` | Raw run-directory root; may be a farm symlink |
| `--pre-dir DIR` | `data/02_pre_analyzed/pre_analisi` | Pre-analysis ROOT input/output directory; may be a farm symlink |
| `--selected-dir DIR` | `data/03_selected` | Selected ROOT output and downstream input directory |
| `--nevents N` | `1000000` | Events generated per MC channel |
| `--input-tree NAME` | `auto` | Use named preselection tree, or auto-detect `h85` then `h80` |
| `--signal-channel NAME` | `eta_pi0` | Signal class for feature building and training |
| `--signal-prior F` | `0.5` | Training-weight share assigned to signal |
| `--partner NAME` | `proton` | Reconstruction partner: `proton`, `neutron`, or `deuteron` |
| `--grid-search-niter N` | `30` | Randomized grid-search iterations |
| `--skip-preanalysis` | off | Skip stage 1 |
| `--force-preanalysis` | off | Re-run stage 1 even when pre-analysis output exists |
| `--skip-selection` | off | Skip stage 2 |
| `--skip-mc` | off | Skip MC generation regardless of missing channels |
| `--force-mc` | off | Regenerate MC even when all channels exist |
| `--skip-features` | off | Skip stage 4 |
| `--skip-grid-search` | off | Skip stage 5 |
| `--skip-train` | off | Skip stages 5 and 6 |
| `--skip-reco` | off | Skip stage 7 |
| `--skip-plots` | off | Skip stage 8 |

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `PYTHON` | `python` | Interpreter used for Python stages |
| `ROOT_EXEC` | `root` | ROOT executable used for macros |

## Reuse and failure behavior

- Stage 1 reuses existing `pre_*.root` files unless
  `--force-preanalysis` is set.
- `mc_simulation.mc_status` returns 0 when all registry channels exist, 1 when
  at least one is absent, and 2 on internal failure. Only exit 1 can trigger
  ordinary regeneration. Stale files warn but remain usable.
- Stage 4 always remeasures beam spectrum from selected detector data. Missing
  selected data is fatal because channel weights require measured beam flux.
- Stage 5 requires feature NPZ. Stage 6 uses `best_hyperparams.json` only when
  present.
- Stage 7 writes both standard χ² and BDT-gated ηπ⁰ reconstruction outputs.
- Stage 8 requires both reconstruction files for comparison. It skips plotting
  when either is absent. Fit-resolution plots additionally require signal MC.

## Test-data mode

| Purpose | Normal path | `--test-data` path |
|---|---|---|
| Raw detector input | `data/01_raw/graal_data` | `test_data/raw` |
| Pre-analysis | `data/02_pre_analyzed/pre_analisi` | `test_data/pre_analyzed` |
| Selected events | `data/03_selected` | `test_data/selected` |
| Reconstruction output | `results/reco` | `test_data/results/reco` |
| Plot output | `results/plots` | `test_data/results/plots` |

MC remains in `03_mc_simulation/data`; Stage-1 artifacts remain in
`04_bdt_training/artifacts/stage1`. Test-data mode exercises file integration,
not an independent training universe. Explicit `--raw-dir`, `--pre-dir`, or
`--selected-dir` values override the corresponding test-data mapping.

## Focused entry points

Each Python stage can run independently after editable installation:

```bash
python -m mc_simulation.mc_status --data-dir 03_mc_simulation/data
python -m bdt_training.beam_spectrum --help
python -m bdt_training.build_background_features --help
python -m bdt_training.grid_search_stage1 --help
python -m bdt_training.train_bdt_stage1 --help
python -m reconstruction.reconstruct_eta_pi0_chi2 --help
python -m reconstruction.reconstruct_eta_pi0_bdt --help
python -m reconstruction.reconstruct_2pi0 --help
python -m plots.dalitz --help
```

Calibration commands are documented in [Calibration and flux](calibration-and-flux).
Beam-asymmetry extraction is documented in
[06 — Beam asymmetry](06-observable-extraction). It remains outside
`run_pipeline.sh` until farm dry-run validation.
