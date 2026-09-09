# Two-Person AI Handoff Design

**Date:** 2026-09-09
**Status:** proposed for implementation
**Repository:** `AntoninoFulci/GRAAL_Analysis`

## Objective

Make a fresh GitHub clone sufficient for two collaborators, each assisted by
AI agents, to understand, validate, and continue the GRAAL analysis without
depending on chat history or undocumented local state.

The repository will carry code, durable project knowledge, current compact
inputs, reproducible outputs, maintenance commands, and a queryable Graphify
snapshot. Large binary artifacts will use Git LFS. Machine-specific caches,
credentials, virtual environments, and raw detector corpora remain local.

## Success criteria

A collaborator starting from an empty directory can:

1. clone the repository including Git LFS objects;
2. identify authoritative versus generated or legacy artifacts;
3. install Python dependencies using the same interpreter as PyROOT;
4. run syntax checks, manifest validation, ROOT-free tests, and the full suite
   when PyROOT is available;
5. query the checked-in Graphify graph and refresh it after code changes;
6. reproduce the accepted observable-run database from checked-in compact
   inputs and outputs;
7. work on one of two non-overlapping physics tracks with explicit handoff
   contracts and acceptance gates.

## Repository content policy

### Tracked normally

- source code, configuration, wiki, and all durable documentation;
- `AGENTS.md`, contributor/operator instructions, maintenance entry points,
  and dependency manifests;
- text and image outputs small enough for ordinary Git;
- Graphify report, graph, HTML viewer, labels, and portable manifest;
- generated run inventory, clearly marked non-authoritative;
- CSV and JSON analysis outputs below the Git LFS threshold when they are part
  of a reproducible, documented snapshot.

### Tracked through Git LFS

- ROOT files under the explicitly published `data/` and `results/` paths;
- NPZ files under explicitly published `results/` paths;
- any individual published artifact likely to approach GitHub's 100 MB
  ordinary-blob limit.

LFS patterns must be path-scoped. They must not silently publish raw detector
data, Monte Carlo corpora, or future scratch files merely because their suffix
is `.root` or `.npz`.

### Kept local and ignored

- `data/graal_data/`, `data/pre_analyzed/`, and `data/selected/` raw or
  event-level farm corpora unless a later reviewed data-release policy says
  otherwise;
- `03_mc_simulation/data/` and `04_bdt_training/data/`, currently several
  gigabytes and reproducible through pipeline commands;
- virtual environments, Python caches, pytest caches, worktrees, checkpoints,
  temporary directories, and failure scratch directories;
- Graphify interpreter/root pointers, extraction caches, temporary chunks,
  token-cost history, and other host-specific state;
- credentials, private keys, access tokens, and configuration containing them.

This policy interprets “include data, docs, graphify-out, and results” as
including their durable collaboration artifacts, not making every future raw
or temporary file automatically publishable.

## Initial published snapshot

### `data/`

Publish:

- `data/flux/flux.root` through Git LFS;
- `data/run_manifest.generated.csv` through ordinary Git, labeled generated
  and non-authoritative.

Continue using `config/run_manifest.csv` as authoritative curated manifest.
Do not publish absent raw/pre-analysis/selected corpora as placeholders.

### `results/`

Publish current artifacts with provenance documentation:

- `results/strip_energy_flux/` source bundle;
- freshly regenerated `results/observable_runs/` six-file curated bundle;
- `results/plots/` current diagnostic figures;
- `results/reco/` current ROOT outputs through Git LFS;
- existing run log as historical diagnostic evidence.

Current reconstruction ROOT files are legacy snapshots: they predate
`RunNumber`, `Polarization`, and `Xstrip` propagation. They may support old
plot reproduction but must be labeled invalid for run-flux normalization.
New physics work must regenerate metadata-bearing reconstruction outputs.

Every published result set needs a sidecar inventory recording:

- producing commit;
- command when known;
- size and SHA-256 for each artifact;
- role (`input`, `derived`, `legacy`, or `authoritative`);
- validity and allowed use;
- known limitations.

### `docs/`

Remove broad `docs/` ignore rule. Track durable designs and implementation
plans. Continue ignoring `.superpowers/`, because it contains per-session
agent ledgers, briefs, reports, and review packages rather than project
authority.

### `graphify-out/`

Refresh graph after all durable files are added, then publish:

- `graphify-out/GRAPH_REPORT.md`;
- `graphify-out/graph.json`;
- `graphify-out/graph.html`;
- `graphify-out/.graphify_labels.json`;
- `graphify-out/manifest.json`.

Keep ignored:

- `.graphify_python` and `.graphify_root`, which contain machine paths;
- `cache/`, whose current entries contain absolute paths and can be rebuilt;
- `cost.json`, temporary extraction files, chunk files, and update markers.

`AGENTS.md` must tell agents to query the existing graph first and run a
Graphify update after structural code or documentation changes.

## Clone and environment contract

Required host tools:

- Git;
- Git LFS 3.x;
- Python 3.10 or newer, using the interpreter against which PyROOT was built;
- ROOT with PyROOT;
- a POSIX shell for `run_pipeline.sh` and maintenance targets.

Required clone flow:

```bash
git lfs install
git clone https://github.com/AntoninoFulci/GRAAL_Analysis.git
cd GRAAL_Analysis
git lfs pull
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip setuptools
python -m pip install -r requirements-dev.txt
python -m pip install -e .
```

`requirements-dev.txt` must include direct Python dependencies used by the
repository, including `scipy` and `pytest`, while explaining that ROOT/PyROOT
is installed externally and must match the selected Python interpreter.

## Maintenance interface

A root `Makefile` will provide stable agent-friendly commands:

- `make help` — list targets and safety notes;
- `make setup` — install Python dependencies and editable package;
- `make syntax` — parse Python and validate shell syntax;
- `make test-root-free` — run tests that do not require PyROOT;
- `make test` — run full suite;
- `make validate-manifest` — validate 2711-run curated manifest;
- `make observable-runs` — rebuild curated database from checked-in snapshot;
- `make graph-update` — refresh Graphify outputs;
- `make verify` — syntax, manifest, tests, provenance, and Git diff checks.

Targets that execute expensive farm work must have explicit names and must not
run from default `make verify`. Documentation must preserve exact `--resume`
usage and exit-code semantics for strip-energy/flux processing.

## Agent operating contract

Root `AGENTS.md` will be tool-neutral and concise. It will define:

- authoritative entry points and data lineage;
- protected scientific invariants;
- rule that only good-run bundle with `observable_run_qa.valid=true` may
  normalize observables;
- rule that review/bad runs remain usable only for cuts and kinematics;
- test commands appropriate with and without PyROOT;
- prohibition on committing credentials, virtual environments, caches, raw
  detector corpora, or undocumented regenerated physics outputs;
- requirement to update docs, provenance, and Graphify snapshot when public
  interfaces or pipeline behavior change;
- branch/worktree, review, and commit expectations for multiple agents.

## Exactly two-person physics split

### Person 1: normalization and cross sections

Exclusive future ownership:

- `07_physics_normalization/` and its tests;
- `config/physics/normalization_v1.json`;
- `results/physics/normalization/`;
- `docs/physics/normalization.md`.

Responsibilities:

1. freeze accepted observable-run handoff;
2. regenerate metadata-bearing reconstruction outputs;
3. derive MC acceptance and efficiency through actual selection/reconstruction;
4. extract good-run-only yields;
5. apply versioned luminosity, target, branching-ratio, and efficiency factors;
6. produce total/differential cross sections and Ajaka-compatible closure.

### Person 2: polarization and beam asymmetry

Exclusive future ownership:

- `08_polarization/` and its tests;
- `config/physics/polarization_v1.json`;
- `results/physics/polarization/`;
- `docs/physics/polarization.md`.

Responsibilities:

1. obtain authoritative `Polarization` and `POL1/POL2` state mapping;
2. obtain Compton polarization `P(Eγ)` and uncertainty;
3. define and test periodic reaction/decay-plane angle φ;
4. implement acceptance-aware `cos(2φ)` fit;
5. run injected-asymmetry closure and sign-convention checks;
6. produce Σ tables, covariance, QA, and systematic components.

Neither person edits shared upstream artifacts during their track. Changes to
manifest, observable policy, channel registry, reconstruction schema, or shared
bin definitions require joint review.

## Handoffs and execution order

1. **Gate 0:** repository clone, LFS pull, environment checks, full provenance
   inventory, valid six-file observable bundle.
2. **Parallel contract work:** Person 1 freezes normalization/acceptance schema;
   Person 2 freezes polarization-state, φ, and fit schema.
3. **Parallel implementation:** Person 1 builds acceptance/yields; Person 2
   builds angles and injected-Σ closure using synthetic/MC inputs.
4. **Handoff 1→2:** versioned acceptance table with explicit bin keys,
   denominators, uncertainties, validity mask, commit, and input hashes.
5. **Independent results:** Person 1 produces cross-section closure; Person 2
   produces Σ and covariance.
6. **Joint release gate:** P0 benchmark requires normalization, acceptance,
   polarization mapping, fit validation, backgrounds, and systematic closures.

D2/neutron and η-prime tracks remain deferred until proton-channel P0 and
polarization contracts pass their gates.

## Verification and publication gates

Before commit:

- scan newly tracked text for credentials and absolute developer paths;
- verify all LFS-intended files are represented by LFS pointers in Git;
- regenerate and validate provenance inventories;
- validate observable QA and output hashes;
- run `make verify` in an environment with PyROOT;
- clone the candidate branch into a disposable directory and run bootstrap,
  LFS, graph query, and reproducibility smoke tests.

Before push, inspect total LFS payload and confirm GitHub accepts upload. A
failed or quota-limited LFS upload blocks publication; it must not be replaced
by ordinary Git blobs above GitHub limits.

## Out of scope

- publishing raw detector data or multi-gigabyte Monte Carlo samples;
- inventing missing dead-time, live-time, tagging-efficiency, polarization, or
  branching-ratio inputs;
- treating legacy reconstruction outputs as valid normalized physics data;
- implementing final cross-section or Sigma extraction in this repository
  packaging change.
