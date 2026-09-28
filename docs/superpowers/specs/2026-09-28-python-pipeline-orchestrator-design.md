# Python Pipeline Orchestrator Design

## Objective

Replace the two shell orchestrators with one Python application that can plan,
run, resume, validate, and explain the GRAAL analysis pipeline through physics
observable extraction.

The application must:

- inspect existing artifacts and begin at the earliest stage that is actually
  required;
- distinguish valid reusable artifacts from missing, invalid, stale, old, or
  untracked artifacts;
- guide an interactive user through observable extraction while also supporting
  reproducible unattended farm jobs;
- use the same stage graph for production, smoke validation, and farm
  validation;
- support multiple analysis final states without treating Monte Carlo
  background samples as analysis channels;
- expose beam-asymmetry extraction now and leave cross-section extraction
  visible but disabled until it is implemented;
- preserve known-good outputs when a rebuild fails;
- remove `run_pipeline.sh` and
  `scripts/run_beam_asymmetry_overnight.sh` after feature parity is verified.

## Scope and non-goals

This design covers orchestration, artifact state, validation, command-line and
interactive interfaces, logging, migration, and documentation. It does not
change the physics algorithms implemented by pre-analysis, event selection,
training, reconstruction, calibration, or observable extraction.

The orchestrator is not a general plugin framework. Final states, observables,
and stages are described by small in-repository registries. Adding a future
final state or observable requires an explicit implementation and validator; a
registry entry alone must never make an unsupported analysis appear runnable.

Monte Carlo channels and analysis final states remain distinct concepts. The
nine `MCChannel` entries describe generated signal/background samples used by
training. The interactive analysis menu lists only reconstructible physics final
states such as `eta_pi0` and, once fully supported, `2pi0`.

## Package and entry points

Add a root-level Python package:

```text
graal_pipeline/
├── __init__.py
├── __main__.py
├── cli.py
├── model.py
├── registry.py
├── planner.py
├── state.py
└── runner.py
```

Responsibilities are deliberately narrow:

- `cli.py` owns `argparse`, the interactive wizard, and presentation.
- `model.py` owns immutable stage, artifact, status, plan, and run-result data
  types.
- `registry.py` owns final-state, observable, and stage descriptions, including
  descriptions used by both the wizard and CLI help.
- `planner.py` traverses dependencies, obtains artifact state from `state.py`,
  applies user policies, and emits an executable plan.
- `state.py` owns validators, fingerprints, checkpoints, legacy adoption, and
  run-state persistence.
- `runner.py` owns subprocess execution, logs, locks, retry behavior, staging,
  output validation, and publication.
- `__main__.py` delegates to `cli.main`.

Install the official command through `pyproject.toml`:

```toml
[project.scripts]
graal-pipeline = "graal_pipeline.cli:main"
```

The equivalent module invocation is `python -m graal_pipeline`. The initial
implementation uses the Python standard library (`argparse`, `json`,
`subprocess`, and `pathlib`) plus dependencies already required by pipeline
stages. Python 3.11 and newer use `tomllib`; Python 3.10 uses the conditional
compatibility dependency `tomli>=2`. It does not add a terminal UI dependency.

## Registry model

Use frozen dataclasses rather than abstract plugin interfaces.

A `FinalStateSpec` contains:

- stable key, display label, and one-line description;
- enabled/disabled state and an optional disabled reason;
- reconstruction hypothesis and configured model directory;
- supported reconstruction and observable targets.

An `ObservableSpec` contains:

- stable key, display label, and one-line description;
- enabled/disabled state and reason;
- supported final-state keys;
- explicit production, first-pass, and validation target keys; unsupported
  targets are absent and carry a disabled reason in the capability registry.

A `StageSpec` contains:

- stable stage key and user-facing description;
- required and configuration-dependent dependencies;
- declared input and output artifacts;
- command builder;
- validator;
- source files or modules responsible for its code fingerprint;
- maximum age, or no age policy for source inputs;
- checkpoint scope: shared, final-state-specific, or observable-specific;
- final-state and observable applicability.

The initial capability matrix is:

| Final state | Reconstruction | Beam asymmetry | Cross section |
|---|---|---|---|
| `eta_pi0` | enabled | enabled | visible, disabled |
| `2pi0` | existing basic reconstruction only | visible, disabled | visible, disabled |

Disabled entries appear in the wizard with a short explanation. They cannot be
selected. Equivalent CLI requests fail during planning, before any stage runs,
with exit code 2 and a message naming the missing implementation.

## Stage graph

The initial graph unifies the current top-level pipeline and beam-asymmetry
overnight workflow:

```text
raw detector
└── preanalysis
    ├── event_selection
    │   ├── beam_spectrum
    │   │   └── feature_build
    │   │       ├── grid_search
    │   │       └── bdt_training
    │   ├── reco_chi2_raw
    │   ├── reco_bdt_raw
    │   ├── reco_bdt_fit
    │   └── reco_data_sideband
    └── flux_calibration

signal_mc_generation
└── signal_mc_adapter
    └── reco_signal_mc_sideband

flux_calibration + reco_bdt_raw
└── beam_asymmetry_first_pass

flux_calibration
+ reco_chi2_raw
+ reco_bdt_raw
+ reco_bdt_fit
+ reco_data_sideband
+ reco_signal_mc_sideband
└── beam_asymmetry_full
```

BDT reconstruction depends on a compatible model bundle. If the configured
bundle is missing or invalid, planning traverses back through feature building
and training. Grid search is required only when the selected training
configuration consumes its optimized hyperparameters. Training with explicit
or default hyperparameters depends directly on features.

Existing plotting commands remain optional targets. They are not prerequisites
for observable extraction.

Planning begins at the requested target, not at a user-selected starting stage.
The planner walks dependencies backward, inspects every required artifact, and
selects the earliest stage that must execute. Existing valid `selected` data can
therefore bypass raw pre-analysis, while valid pre-analysis can bypass raw input
and start at event selection.

## Configuration and paths

Add a versioned project configuration at `config/pipeline.toml`.

The precedence order is:

```text
command-line option > selected profile > pipeline.toml > code default
```

Initial defaults are relative to the repository root:

```toml
[paths]
raw_dir = "data/01_raw/graal_data"
preanalysis_dir = "data/02_pre_analyzed/pre_analisi"
selected_dir = "data/03_selected"
external_flux = "data/00_external/flux.root"
run_manifest = "config/run_manifest.csv"
results_dir = "results"

[checkpoint]
max_age_days = 30
verification = "fast"
old_policy = "ask"
stale_policy = "ask"
untracked_policy = "ask"
```

Relative paths are resolved from the repository root regardless of the caller's
working directory. Explicit command-line or TOML overrides may be absolute for
farm deployments. Defaults must never begin at filesystem `/data`.

New outputs are namespaced by analysis final state:

```text
results/
├── .pipeline/
├── shared/
│   └── strip_energy_flux/
├── eta_pi0/
│   ├── reconstruction/
│   ├── plots/
│   └── observables/
│       ├── beam_asymmetry/
│       └── cross_section/
└── 2pi0/
```

The existing eta-pi0 Stage-1 model bundle remains at
`04_bdt_training/artifacts/stage1` initially. The final-state registry supplies
the model path, so future final states can use separate bundles without forcing
an unrelated model migration.

Legacy outputs such as `results/reco/*.root` are not moved or deleted
automatically. They can be adopted in place or rebuilt into the canonical
layout.

## Artifact state model

Every required artifact receives exactly one planning state:

| State | Meaning | Default behavior |
|---|---|---|
| `FRESH` | Validator passes; checkpoint matches inputs, config, and code | Reuse |
| `OLD` | Semantically fresh, but older than its age policy | Ask in wizard |
| `UNTRACKED` | Validator passes but no compatible checkpoint exists | Ask to adopt |
| `STALE` | Validator passes; input, config, code, or schema changed | Recommend rebuild |
| `MISSING` | Required output is absent | Build |
| `INVALID` | Output exists but validator fails | Rebuild or stop; never reuse |

Source detector data and external inputs do not become old solely because of
age. Derived models, calibration, reconstruction, and observable products use a
default 30-day age warning. Configuration may override or disable the threshold
per stage.

Age is measured from checkpoint completion for produced or adopted artifacts.
Before adoption, an untracked artifact uses its newest required output mtime for
display only; it remains `UNTRACKED` regardless of age.

Semantic staleness and chronological age are separate. Input, configuration,
model, or responsible-code changes produce `STALE` even when the output is only
minutes old. An unchanged 31-day-old output is `OLD`, not `STALE`.

Rebuilding a stage makes every downstream checkpoint stale. Reusing an old or
stale artifact is recorded in the run report so the resulting provenance cannot
look fully fresh.

## Checkpoint persistence

Store orchestrator state under the configured state directory, defaulting to:

```text
results/.pipeline/
├── checkpoints/shared/<stage>.json
├── checkpoints/<final-state>/<stage>.json
├── checkpoints/<final-state>/<observable>/<stage>.json
├── runs/<run-id>/plan.json
├── runs/<run-id>/summary.json
├── logs/<run-id>/<stage>.log
└── latest.json
```

`--state-dir` overrides this location.

Each stage declares its checkpoint scope. Shared artifacts such as detector
pre-analysis and flux calibration have one checkpoint. Reconstruction and model
artifacts are scoped by final state. Observable products are scoped by both
final state and observable. This prevents duplicate checkpoints from assigning
different states to the same physical artifact.

Checkpoint writes are atomic. A stage checkpoint is written only after its
command succeeds, its staged outputs pass validation, and publication succeeds.
Each checkpoint records:

- checkpoint schema version;
- stage, final state, observable, and profile;
- normalized effective configuration;
- command and working directory;
- input and output fingerprints;
- responsible-code fingerprint;
- validator name, level, and result;
- provenance, including `produced` or `adopted_legacy_output`;
- start/end times, duration, and run ID.

An unknown checkpoint schema never counts as fresh. It is reported as stale
with a schema-version reason.

## Fingerprints

Fast verification is designed for multi-gigabyte ROOT datasets:

- small configuration and metadata files use SHA-256;
- code uses the Git commit plus hashes of dirty responsible files;
- large ROOT files use resolved path, size, nanosecond mtime, ROOT schema/tree
  metadata, required branches, and entry counts;
- directories use a stable manifest of expected files and their fast
  fingerprints.

Full verification adds complete SHA-256 hashes for large files. Digests are
cached against path, size, and nanosecond mtime so repeated full validation does
not reread unchanged files.

Fingerprint comparison must explain which field caused staleness. The wizard
and `status` command show these reasons instead of only printing `STALE`.

## Validators

Fast validation runs automatically during every planning operation. Full
validation is used by validation profiles, `--verify full`, and the matching
wizard action.

Validators are stage-specific and reuse existing package loaders and schemas
where possible:

- pre-analysis requires readable `pre_*.root` files, tree `h80`, and required
  branches;
- event selection requires the complete expected output set, readable `h85`
  trees, and `RunNumber`, `Polarization`, and `Xstrip`;
- Monte Carlo validation uses the channel registry, expected ROOT trees, and
  generator metadata;
- feature and model validation uses the existing NPZ and runtime-bundle schema
  readers, including final-state/hypothesis provenance;
- flux calibration requires its QA artifact and schema-v2 run/strip exposure
  table, including coverage of required selected-data keys;
- reconstruction requires the expected tree, kinematic branches, exposure
  metadata, model provenance when gated, and basic finite/count checks;
- beam-asymmetry output requires readable ROOT points, exact bin metadata, fit
  status, covariance products, and the documented PDF products.

The orchestrator must not duplicate physics formulas. A validator checks the
contract of the responsible package; it does not recalculate the observable.

## Legacy adoption

Existing valid outputs without Python checkpoints appear as `UNTRACKED`.

The interactive choices are:

1. validate and adopt;
2. rebuild;
3. show validation details;
4. abort.

Adoption records current fingerprints, effective configuration, code version,
and `adopted_legacy_output` provenance. When the original configuration cannot
be inferred with confidence, adoption succeeds only as `STALE`; it never
manufactures `FRESH` provenance.

Non-interactive adoption is controlled by
`--untracked-policy ask|adopt|rebuild|fail`. `ask` is invalid in a non-interactive
run when a decision is needed.

## Planning policies

The common options are:

```text
--config PATH
--profile NAME
--state-dir PATH
--dry-run
--non-interactive
--yes
--force-stage STAGE
--old-policy ask|rebuild|reuse|fail
--stale-policy ask|rebuild|reuse|fail
--untracked-policy ask|adopt|rebuild|fail
--verify fast|full
--keep-failed-work
```

`--dry-run` performs discovery, validation, and planning without executing or
publishing stages. `--yes` confirms the final plan but does not silently choose
old, stale, or untracked policies. A non-interactive invocation fails before
execution when it encounters an unresolved decision. Missing and invalid
artifacts schedule rebuilds; invalid artifacts are never eligible for reuse.

Before execution, the plan lists each required stage as `REUSE`, `ADOPT`,
`REBUILD`, `RUN`, or `BLOCKED`, includes reasons, and shows a duration estimate
when historical timing exists.

## Execution, failure, and publication

Stages run in dependency order. A failed stage blocks its downstream
dependents, while independent branches continue. This retains the useful
diagnostic behavior of the overnight runner without duplicating its stage list.

Interactive failure choices are retry, continue independent branches, show the
log, or abort. A non-interactive run continues independent branches and exits
nonzero if any required stage fails or is blocked.

Every rebuild writes into a run-specific staging area on the same filesystem as
its destination. After the command succeeds, the validator checks staged
outputs. Valid singleton files are published with `os.replace`; directory
outputs use `graal_common.io.filesystem.atomic_output_directory`. A prior
known-good output remains in place until replacement is ready.

The checkpoint is published last. A crash after output publication but before
checkpoint publication yields `UNTRACKED`, which is safe and explainable on the
next run. Failed temporary products are removed by default while logs and
failure metadata remain. `--keep-failed-work` retains staged failed products for
debugging.

Only one mutating run may own a state directory at a time. The lock records PID
and run ID. `status`, `plan`, and `--dry-run` remain read-only and available
during an active run. A stale lock is reported and never removed automatically.

## Interactive wizard

Running `graal-pipeline` without arguments opens the Italian-language wizard:

```text
GRAAL Pipeline

1. Continua ultima esecuzione
   Riparte dal primo checkpoint incompleto o scelto per il rifacimento.

2. Prepara dati e modelli
   Esegue preanalisi, selezione, MC, feature e training necessari.

3. Ricostruisci final state
   Produce campioni standard, BDT, fit e controlli sideband.

4. Estrai osservabile
   Calcola quantità fisiche usando ricostruzione, flusso e correzioni.

5. Valida pipeline
   Esegue profili ridotti o completi e produce un report.

6. Controlla checkpoint e output
   Mostra validità, età, dipendenze e motivi dello stato.

7. Esci
```

The observable submenu initially shows:

```text
1. Asimmetria del fascio
   Estrae Sigma da campioni polarizzati, flusso e sideband.

2. Sezione d'urto [non disponibile]
   Estrarrà yield corretto per flusso, efficienza e accettanza.
```

The beam-asymmetry submenu offers final extraction, uncorrected first-pass
extraction, validation, advanced estimator/bootstrap configuration, and status.
Every choice has a one-line description. Extended help is available with `?`
in the wizard and `--help` on the CLI.

Wizard text and user explanations are Italian. Stable commands, option names,
status tokens, and technical logs are English.

## Non-interactive CLI

The primary commands are:

```bash
graal-pipeline resume
graal-pipeline status
graal-pipeline plan extract beam-asymmetry --final-state eta_pi0
graal-pipeline extract beam-asymmetry --final-state eta_pi0
graal-pipeline validate beam-asymmetry --final-state eta_pi0 --profile smoke
graal-pipeline validate beam-asymmetry --final-state eta_pi0 --profile farm
graal-pipeline validate full --final-state eta_pi0
```

The CLI and wizard obtain labels, descriptions, disabled reasons, and target
definitions from the same registry.

## Validation profiles

Three validation layers have different claims:

1. Automated tests use controlled executors and small generated data to verify
   the orchestrator, schemas, and failure behavior. They are part of `pytest`.
2. The `smoke` profile uses a configured reduced ROOT fixture under
   `test_data/` to exercise real stage integration and validators quickly. If
   the fixture is absent, planning fails with copy/setup instructions instead
   of synthesizing physics data. Its report explicitly says `integration only`
   and makes no physics-validity claim.
3. The `farm` profile is the functional successor of the overnight runner. It
   uses real farm configuration, isolated outputs, full validation, independent
   branch continuation, and a final `PASSED`, `FAILED`, `BLOCKED`, `REUSED`, and
   `SKIPPED` report.

Production extraction uses the `production` profile and canonical output paths.
Smoke and farm validation write under an isolated validation result root keyed
by run ID. Profile overrides may reduce signal-MC event counts and bootstrap
replicas without changing the graph.

`test_data/` remains unversioned for local ROOT samples. Automated tests
generate small synthetic contract fixtures rather than committing large binary
files; production smoke validation does not replace real stage inputs with test
doubles.

## Migration and deletion

Migration order is safety-critical:

1. implement the Python package, configuration, registries, planner, state
   engine, runner, wizard, and CLI;
2. add focused automated coverage and run the complete repository suite;
3. exercise smoke validation;
4. verify command parity for current pipeline and overnight targets;
5. replace shell contract tests with Python CLI and orchestration tests;
6. delete `run_pipeline.sh`;
7. delete `scripts/run_beam_asymmetry_overnight.sh`;
8. remove obsolete shell documentation and tests;
9. run the full suite again.

No compatibility wrappers remain. Documentation and examples must use only the
Python entry points after migration.

## Documentation

Create a dedicated normal-prose guide at:

```text
wiki/pipeline-orchestrator.md
```

It must document:

- installation and both entry points;
- the complete wizard hierarchy;
- every supported CLI command and common option;
- final states and observables, including disabled entries;
- checkpoint states and stale/untracked policies;
- TOML configuration and path precedence;
- resume, planning, dry-run, validation, and production examples;
- smoke, farm, and production profiles and the claims each can support;
- input/output layout;
- legacy adoption;
- locks, logs, exit behavior, and troubleshooting;
- migration from the removed shell commands.

This wiki file must be written in Italian using clear, conventional prose. It
must not use caveman style. Update `wiki/_Sidebar.md`, `wiki/pipeline.md`,
`wiki/testing.md`, `wiki/06-observable-extraction.md`, and any README references
so no obsolete shell command remains.

## Verification strategy

Automated tests must cover:

- dependency traversal and minimal plans;
- all artifact-state transitions;
- 30-day age handling separate from semantic staleness;
- fast and full fingerprint modes;
- checkpoint schema mismatch;
- legacy adoption and uncertain-provenance staleness;
- interactive descriptions and disabled choices;
- non-interactive policy enforcement;
- retry, abort, independent-branch continuation, and final exit codes;
- lock acquisition, cleanup, and stale-lock reporting;
- preservation of prior good output on failure;
- staged validation and publication;
- crash-safe `UNTRACKED` recovery;
- final-state/observable capability checks;
- smoke profile isolation;
- command help and configuration precedence.

The complete existing repository suite must pass before shell scripts are
deleted and again after deletion. Farm validation remains an explicit
long-running operation outside ordinary `pytest`.

## Acceptance criteria

The work is complete when:

1. `graal-pipeline` opens the documented wizard and every entry has a concise
   description.
2. `python -m graal_pipeline` and the installed console command behave
   equivalently.
3. Planning from beam-asymmetry extraction reuses fresh prerequisites and
   schedules only missing, invalid, stale, forced, or user-approved old stages.
4. Legacy artifacts can be validated and explicitly adopted without claiming
   unknown provenance as fresh.
5. Failed rebuilds preserve previous valid outputs and block only dependent
   stages.
6. Smoke and farm validation use the production graph and isolated outputs.
7. Beam asymmetry for `eta_pi0` is enabled; cross section and unsupported final
   states are visible but disabled.
8. New outputs follow the final-state layout and the default selected-data path
   is `data/03_selected`.
9. Both shell orchestrators and their obsolete tests/references are removed.
10. The dedicated wiki guide documents all supported commands in normal prose.
11. The full automated test suite passes.
