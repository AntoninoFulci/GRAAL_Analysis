# Commands and Configuration

The repository has one sequential full runner, `scripts/run_pipeline.py`, plus
the individual stage entry points. Each stage still validates its own boundary
and publishes explicit files. Run `--help` against the current checkout before
a production job; this page is a map, not a substitute for the parser.

## Command Matrix

| Area | Command or entry point | Main result |
|---|---|---|
| setup | `./scripts/setup.sh --mode local` | `.venv`, editable install, local data layout |
| full UV/VIS pipeline | `python scripts/run_pipeline.py --mode {test_data,production}` | shared calibration, isolated profile products, combined figures |
| pre-analysis | ROOT `AnalyzeAll(base_in, base_out, cuts_dir)` | `pre_analisi_<period>.root`, tree `h80` |
| selection | `python` with `02_event_selector/select_events.py` | selected ROOT files, tree `h85` |
| MC generation | `cd 03_mc_simulation/data` then `root -l -b -q '../generators/generate_eta_pi0_dataset.C(1000000)'` | `03_mc_simulation/data/eta_pi0_mc.root`, tree `mc` |
| MC inventory | `python -m mc_simulation.mc_status` | completeness/age report and exit status |
| beam spectrum | `python -m bdt_training.beam_spectrum ...` | `beam_spectrum.npz` |
| feature dataset | `python -m bdt_training.build_background_features ...` | `features_stage1.npz` |
| search | `python -m bdt_training.grid_search_stage1 ...` | CSV audit and best hyperparameters |
| training | `python -m bdt_training.train_bdt_stage1 ...` | Stage-1 runtime bundle and reports |
| chi-square reconstruction | `python -m reconstruction.reconstruct_eta_pi0_chi2 ...` | reference ROOT tree |
| BDT reconstruction | `python -m reconstruction.reconstruct_eta_pi0_bdt ...` | gated ROOT tree |
| sideband reconstruction | `python -m reconstruction.reconstruct_eta_pi0_bdt_sideband ...` | broad sideband ROOT tree |
| calibration manifest | `python 06_calibration/build_run_manifest.py --help` | run manifest CSV |
| strip/flux calibration | `python 06_calibration/build_strip_energy_flux.py ...` | exposure CSV/QA/ROOT set |
| observable extraction | `python 07_observable_extraction/beam_asymmetry.py ...` | asymmetry ROOT/PDF set |
| plots | `python -m plots.dalitz ...` | reconstruction comparison PDFs/ROOT |
| full verification | `pytest -q` | all configured tests |

Representative training sequence:

```bash
python -m bdt_training.beam_spectrum \
  --selected-dir data/03_selected \
  --output 04_bdt_training/data/beam_spectrum.npz

python -m bdt_training.build_background_features \
  --mc-dir 03_mc_simulation/data \
  --signal-channel eta_pi0 \
  --beam-spectrum 04_bdt_training/data/beam_spectrum.npz \
  --signal-prior 0.5 \
  --loss-seed 42 \
  --output features_stage1.npz

python -m bdt_training.grid_search_stage1 \
  --features features_stage1.npz \
  --out-dir 04_bdt_training/artifacts/stage1 \
  --n-iter 30 --seed 42

python -m bdt_training.train_bdt_stage1 \
  --features features_stage1.npz \
  --hyperparams 04_bdt_training/artifacts/stage1/best_hyperparams.json \
  --out-dir 04_bdt_training/artifacts/stage1 \
  --seed 42
```

## Launcher Options

```text
python scripts/run_pipeline.py --mode test_data [--output-dir results/test_NAME] [--phi-bins {8,12,16}]
python scripts/run_pipeline.py --mode production [--output-dir results/NAME] [--phi-bins {8,12,16}] [--force-selected] [--force-mc] [--force-bdt]
```

Both modes start from pre-analysis `h80` files. `test_data` generates 100000
attempted events per required channel and defaults to `results/test_data/`;
`production` generates 1000000 and defaults to `results/production/`.
`--phi-bins` defaults to 12 and selects one ratio-fit binning for both profiles
per campaign. Conditional likelihood remains unbinned. ROOT outputs record
the phi edges, and UV/VIS composition requires matching binning. Ratio Sigma
and its error use the fixed divisors 0.9003/0.9549/0.9745 for 8/12/16 bins;
provenance records the divisor, and corrected/uncorrected profiles cannot be
combined. See [estimator conventions](07-beam-asymmetry-estimators.md).
The launcher prints a validated run summary and asks `Avviare la pipeline? [s/N]:`
before creating or replacing campaign output. Only `s`, `si`, `sì`,
`y`, or `yes` starts work; Enter, another answer, or EOF cancels. The table
lists paths, channels, MC events, cache policy, force flags, and every stage.
Old production `h80` files appear in a separate warning table. Both tables
wrap within the terminal width and use color when supported; set `NO_COLOR=1`
for plain output.
Production output must be absent or empty; test output is replaced on each run
and must stay in `results/test_<campaign>/`. Production selection, MC, and BDT
are reused only with valid payloads/manifests younger than ten days. Force flags
override each artifact class. Launcher calibrates once, disables bootstrap and
sideband correction, and writes profile and combined plots under campaign root.

## Setup Options

```text
./scripts/setup.sh --mode local [--python PATH]
./scripts/setup.sh --mode farm --raw-target DIR [--python PATH]
```

| Option | Contract |
|---|---|
| `--mode local` | create environment and empty local `data/` directories |
| `--mode farm` | additionally create checked symlink to existing raw directory |
| `--python PATH` | select Python interpreter; default `python3`; must be >=3.10 and import ROOT |
| `--raw-target DIR` | farm directory containing acquisition-period folders |

Place farm `pre_analisi_*.root` files manually in flat `data/02_pre_analyzed/`.
Farm raw target must already exist. Setup accepts an existing symlink only when
it resolves to the requested target. It refuses broken links, different
targets, and ordinary files/directories at those link paths. It never replaces
data silently.

The script creates `.venv` with `--system-site-packages`, upgrades pip,
installs `04_bdt_training/requirements.txt`, performs `pip install -e`, creates
the four local data directories, and imports ROOT plus every project package.
Missing `data/00_external/flux.root` is a warning, not a setup failure.

## Stage Options

| Stage | Important options/defaults |
|---|---|
| full launcher | required `--mode`; optional absent/empty `--output-dir`; no resume |
| selection | input `data/02_pre_analyzed`, output `data/03_selected/{uv,vis}`, positive worker count |
| MC status | default data directory `03_mc_simulation/data`; optional `--data-dir` |
| beam spectrum | 150 bins over 0.5–2.0 GeV by default |
| feature build | default loss seed `42`; required beam spectrum; `0 < signal-prior < 1` |
| search | 30 deterministic sampled configurations by default; `--full-grid` runs all 1,296 |
| training | seed `42`, CPU device, `--nthread -1`; optional direct hyperparameters |
| reconstruction | input/output/tree, chi-square ceiling, recoil partner, missing-mass window; eta-pi0 paths also expose `--no-fit` and `--fit-cl` |
| calibration | thresholds, progress interval, ROOT threads, retained samples, repeatable custom binning |
| observables | nominal sample `raw_bdt`, estimator `both`, 8/12/16 phi bins (default 12), fixed 10 mass bins, bootstrap off by default |
| Dalitz plots | required `--chi2` and `--bdt`; output defaults to `results/plots` |
| fit resolution | default signal MC, BDT result, output directory, and `--n 20000` |

Exact calibration and observable options are tabulated in
[Calibration](06-calibration) and
[Observable Extraction](07-observable-extraction).

## Configuration Sources

Configuration has explicit owners:

| Source | Owns |
|---|---|
| CLI arguments | run-specific paths, resource counts, thresholds, seeds, selected modes |
| `00_common/physics/channels.py` | channel registry, masses, hypotheses, roles, generator filenames, cross sections |
| `00_common/physics/pairing.py` | shared pairing enumeration and chi-square convention |
| `config/run_manifest.csv` | run period, target, beam type, group, source provenance |
| Stage-1 provenance JSON | model hypothesis, feature order, training identity and detector-model status |
| `pyproject.toml` | package mapping, Python floor, pytest discovery/import mode |
| `04_bdt_training/requirements.txt` | Python runtime/test dependencies outside PyROOT |
| Stage source constants | fixed published grids, physics windows, and defaults documented beside their owner |

Do not create an untracked “master config” that duplicates these values. A
change belongs in the layer that enforces the invariant, with tests and
regenerated artifacts where required. Command logs should capture overrides,
input paths, seeds, source revision, and environment for reproducibility.
