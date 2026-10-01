# Production pipeline launcher design

Date: 2026-10-01
Status: approved in chat before specification

## Goal

Provide one deliberately small launcher that runs the existing
`gamma p -> eta pi0 p` analysis from pre-analysis ROOT files through the final
combined UV/VIS Ajaka comparison. The first version exists to prove the full
workflow on the server and expose full-statistics physics results. It is not a
general scheduler.

The launcher supports exactly two execution modes:

- `test_data`: the two local pre-analysis periods, one UV and one VIS;
- `production`: every available proton-target UV and VIS period on the server.

Both modes start from `pre_analisi_*.root` files containing tree `h80`. Raw
`h70` processing is outside this launcher.

Success means one command performs common calibration once, runs independent
UV and VIS chains, trains fresh profile-specific Stage-1 models, extracts both
asymmetries, and combines only the final result plots.

## Design principles

- Reuse existing stage entry points. The launcher coordinates them; it does
  not duplicate physics or file-format logic.
- Keep UV and VIS independent wherever beam profile affects data selection,
  Monte Carlo, weighting, model training, reconstruction, or extraction.
- Share only profile-independent preparation, especially manifest validation
  and strip/flux calibration.
- Stop on the first nonzero child-process exit code.
- Let existing warning policy stand. Version one does not promote known
  incomplete-run, exposure-domain, or sparse-bin warnings to errors.
- Prefer explicit paths over changing stage-global defaults during a run.
- Add no resume graph, scheduler, queue integration, container, or new
  configuration language.

## Command-line contract

The supported entry point is:

```bash
python scripts/run_pipeline.py --mode test_data
python scripts/run_pipeline.py --mode production
```

An optional `--output-dir PATH` changes the complete result root. Defaults are:

```text
results/test_data/
results/production/
```

The runner refuses an unknown mode. It also refuses a nonempty output root so
an interrupted or previous campaign cannot be mistaken for the new run. It
does not delete or clean existing data. Operators choose another output path
or move the old result deliberately.

All Python child commands use `sys.executable`, preserving the interpreter that
successfully imported PyROOT. ROOT macros use the `root` executable found by
the preflight.

## Mode configuration

Mode differences live in one immutable Python configuration record inside the
launcher. No YAML/TOML master configuration is introduced.

| Setting | `test_data` | `production` |
|---|---|---|
| pre-analysis input | `test_data/pre_analyzed` | `data/02_pre_analyzed/pre_analisi` |
| output root | `results/test_data` | `results/production` |
| attempted MC events/channel | `100000` | `1000000` |
| manifest | `config/run_manifest.csv` | same |
| raw flux | `data/00_external/flux.root` | same |
| hyperparameters | `04_bdt_training/artifacts/stage1/best_hyperparams.json` | same |
| Ajaka reference | versioned Stage-07 reference CSV | same |

The smaller test MC is a smoke-test resource choice, not a scientific
production setting. Production keeps one million attempted events per channel,
matching the validated local VIS workflow.

## Preflight

Preflight is intentionally permissive. It checks only conditions that would
otherwise make the run fail later or use the wrong input:

1. Python is at least 3.10.
2. `import ROOT` succeeds and the `root` executable exists.
3. Required Python runtime packages import.
4. Repository-owned scripts, generators, manifest, flux input,
   hyperparameters, and Ajaka reference exist.
5. The configured pre-analysis directory exists.
6. At least one UV and one VIS pre-analysis file match the profile patterns.
7. The output parent is writable and the chosen output directory is empty or
   absent.
8. The checked-in run manifest passes its existing validator.

Preflight does not enforce free-space thresholds, CPU counts, expected run
counts, warning budgets, or server-specific paths. It does not require
administrator privileges.

## Common branch

Common work runs once before either profile branch:

1. Validate `config/run_manifest.csv` through the existing calibration
   manifest command.
2. Build one calibrated flux ROOT file from all configured pre-analysis files,
   the manifest, and `data/00_external/flux.root`.
3. Publish it at:

```text
<output>/common/flux_calibrated.root
```

Both profile extractors consume that exact file. Calibration remains
run-specific internally, so sharing its container does not average UV and VIS
exposures or polarization.

The launcher does not rebuild the manifest from raw detector directories,
because version one starts from pre-analysis and the repository already owns
the reviewed run classification.

## Profile isolation

The profile file patterns are:

```text
UV:  pre_analisi_*uv*.root
VIS: pre_analisi_*vis*.root
```

The UV pattern deliberately includes `fuv` periods. Each pattern is passed to
event selection with a separate output directory. This prevents VIS beam
spectrum and model training from seeing low-energy UV events, and prevents UV
training from depending on VIS acquisition periods.

Each profile owns its complete downstream tree:

```text
<output>/<profile>/
|-- selected/
|-- mc/
|-- bdt/
|   |-- beam_spectrum.npz
|   |-- features_stage1.npz
|   `-- artifacts/stage1/
|-- reco/
|   |-- reco_eta_pi0_chi2.root
|   `-- reco_eta_pi0_bdt.root
`-- beam_asymmetry/
```

No UV or VIS model, selected tree, reconstruction, or asymmetry ROOT file is
shared with the other profile.

## Per-profile processing

The launcher runs UV first and VIS second. Ordering exists only for readable
logs; no profile consumes the other.

### Event selection

Run `event_selector.select_events` against the configured pre-analysis
directory using the profile pattern. The existing atomic directory publisher
owns selected-data replacement and validation.

### Monte Carlo

Generate profile-specific samples using existing ROOT macros and explicit
energy limits from `graal_common.physics.beam_profiles`.

UV requires all registered training channels:

```text
eta_pi0, pi0pi0, 3pi0, eta_2pi0, omega_pi0, etaprime,
eta_via_3pi0, 4pi0, eta_pi0_via_3pi0
```

VIS requires only channels physically available below `1.10 GeV`:

```text
eta_pi0, pi0pi0, 3pi0, eta_via_3pi0, 4pi0,
eta_pi0_via_3pi0
```

Run `mc_simulation.mc_status` after generation. Missing required channels stop
the pipeline through its existing exit status.

### Beam spectrum and Stage-1 model

For each profile:

1. Measure beam spectrum from that profile's selected directory with explicit
   `--profile`.
2. Build Stage-1 features from that profile's MC directory and spectrum.
3. Train a fresh model and threshold into that profile's artifact directory.

Version one reuses the checked-in `best_hyperparams.json` for both profiles.
It does not run a new grid search. Training data, trees, validation split,
threshold, reports, and provenance are regenerated independently for UV and
VIS.

### Reconstruction

Run both reconstruction paths on each profile's selected data:

- chi-square reconstruction for comparison;
- BDT-gated reconstruction using only that profile's newly trained model.

BDT reconstruction receives explicit `--profile`, activating existing model
profile and energy-range validation. One BDT reconstruction tree contains both
raw and fitted vectors, so the observable extractor may use that same file for
`raw_bdt` and `raw_bdt_fit` samples.

### Asymmetry extraction

Run Stage 07 separately for UV and VIS with:

- profile-specific chi-square and BDT reconstruction paths;
- explicit profile;
- shared calibrated flux ROOT;
- checked-in manifest;
- estimator `both`;
- bootstrap replicas `0`.

Sideband background correction is not part of version one. Current
uncorrected extraction behavior remains explicit in ROOT provenance.

## Final composition

After both profile extractors succeed, run `observable_extraction.combine_profiles`
with explicit UV ROOT, VIS ROOT, versioned Ajaka CSV, and output path:

```text
<output>/combined/
|-- figure4_experimental.pdf
|-- figure4_comparison_ajaka2008.pdf
|-- comparison_estimators.pdf
`-- fit_diagnostics.pdf
```

Only Stage-07 point products are combined. Event trees, exposures, covariance
matrices, and models remain profile-local.

The Ajaka digitized CSV moves from ignored `test_data/` into a tracked
Stage-07 reference location so a clean server clone contains it. The combined
plotter defaults change from local `test_data` paths to the production layout,
while the launcher always passes all four paths explicitly.

## Process execution and reporting

The launcher wraps each child command in one helper that:

1. prints stage name;
2. prints a shell-escaped command for audit and manual reproduction;
3. records start time;
4. runs child process with inherited stdout/stderr;
5. records elapsed wall time and exit code;
6. raises immediately on failure.

A small `<output>/pipeline_commands.log` records stage names, commands,
durations, and exit codes. Child output remains on terminal; version one does
not implement log multiplexing or structured telemetry.

Warnings remain visible and do not alter control flow when the owning command
returns success.

## Failure and publication behavior

- Preflight failure creates no stage output.
- Child-process failure stops remaining stages and returns nonzero.
- Completed earlier stages remain on disk for diagnosis, but version one never
  treats them as resumable checkpoints.
- No automatic deletion occurs.
- Existing atomic publication remains in force where stage implementations
  already provide it.
- Reconstruction and other direct writers retain their current publication
  semantics; adding transactionality across the whole campaign is deferred.

## Code ownership

Planned changes remain narrow:

- `scripts/run_pipeline.py`: orchestration, mode configuration, preflight,
  command construction, timing, and command log;
- `tests/test_run_pipeline.py`: orchestration contract tests using a fake
  command executor and temporary paths;
- `07_observable_extraction/combine_profiles.py`: production-oriented defaults;
- `07_observable_extraction/references/ajaka2008_figure4_digitized.csv`:
  tracked comparison data;
- `05_reconstruction/runtime/stage1_gate.py`: remove obsolete
  `run_pipeline.sh` guidance;
- repository README, runbooks, and wiki pages: current launcher and Stage
  06-to-07 handoff documentation.

Physics algorithms, theory code, current uncommitted theory work, and existing
calibration edits are outside this task.

## Testing

Automated tests cover:

- exact mode defaults and output layouts;
- UV/VIS pre-analysis patterns;
- required UV and VIS MC channel lists;
- test versus production MC event counts;
- one shared calibration command;
- independent selection, spectrum, training, reconstruction, and extraction
  commands for both profiles;
- BDT artifact path isolation;
- final composition only after both extractors;
- subprocess failure stopping later commands;
- preflight errors for missing ROOT, input directories, flux, manifest,
  hyperparameters, Ajaka CSV, or either profile's pre-analysis files;
- refusal of nonempty output directories;
- command-log records;
- updated combined-plot defaults and versioned Ajaka reference;
- removal of obsolete `run_pipeline.sh` text.

Tests mock command execution; normal unit tests do not generate millions of MC
events or train XGBoost. Verification before completion includes the full
repository test suite and one command-planning/preflight smoke test for each
mode. A real `test_data` end-to-end launch is the manual acceptance test; it
may take substantial CPU time because it intentionally exercises MC generation
and training.

## Documentation updates

Documentation must state:

- launcher starts from pre-analysis, not raw data;
- `test_data` is a smoke mode and `production` uses all matching periods;
- calibration is shared while UV/VIS downstream artifacts are isolated;
- fresh UV and VIS models are trained;
- grid search, bootstrap, sideband correction, resume, warning policy changes,
  and queue integration are deferred;
- Stage 07 already reads calibrated ROOT exposures;
- combined plot inputs and Ajaka reference no longer depend on ignored local
  files;
- server needs ROOT/PyROOT plus normal Python dependencies, not a batch queue
  or administrator-only service.

## Explicitly deferred

- resuming from a selected stage;
- freshness checks and dependency graph execution;
- bootstrap covariance production policy;
- sideband background correction in the launcher;
- profile-specific hyperparameter searches;
- warning budgets or strict campaign QA gates;
- disk-space and CPU policy;
- parallel UV/VIS execution;
- scheduler, queue, container, or service integration;
- raw `h70` pre-analysis;
- full-campaign atomic rollback;
- changes to theory implementation or its current worktree.
