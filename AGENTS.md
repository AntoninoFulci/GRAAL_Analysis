# GRAAL Analysis: maintenance contract

## Work discipline

- Preserve unrelated edits. Work in an isolated Git worktree; do not reset,
  checkout, or delete another contributor's changes.
- Raw/local inputs, working data, caches, and virtual environments are user
  data even when ignored by Git. Agents must not delete or overwrite them
  without explicit authorization.
- Use `make setup` for a fresh Python environment, `make verify` for the
  non-farm maintenance gate, and `make test` only where the selected Python
  can import the installed external ROOT/PyROOT.
- This is a two-person project: one owner changes a physics area at a time.
  Both owners must review any shared interface (manifest, serialized artifact
  schema, QA policy, common package, Make targets, or public documentation)
  before it is merged.
- Physics continuation has exactly two non-overlapping workstreams documented
  in `docs/collaboration/two-person-physics-roadmap.md`. Treat its Gate 0 and
  acceptance/`Σ` handoff hashes as release blockers; D2/neutron and eta-prime
  remain deferred until proton P0 passes its joint release gate.

## Pipeline and packages

| Stage | Directory | Python package / responsibility |
| --- | --- | --- |
| Shared | `00_common/` | `graal_common`: channels, pairing, manifests, flux and observable-run logic |
| 1 | `01_pre_analysis/` | ROOT macros: raw detector data to inclusive `h80` |
| 2 | `02_event_selector/` | `event_selector`: `h80` to selected `h85` |
| 3 | `03_mc_simulation/` | `mc_simulation`: signal and background generation |
| 4–6 | `04_bdt_training/` | `bdt_training`: features, search, and stage-1 BDT |
| 7 | `05_reconstruction/` | `reconstruction`: chi2/BDT reconstruction and fit |
| 8 | `06_plots/` | `plots`: diagnostic and publication plots |

The directory order is not enough: reconstruction runs after MC and BDT
training because it consumes the model. `run_pipeline.sh` is the full-pipeline
entry point.

## Scientific authorities and protected rules

- `config/run_manifest.csv` is the authoritative curated run metadata and must
  pass `make validate-manifest`. `data/run_manifest.generated.csv` is a
  published, derived convenience copy; it is not an authority.
- `data/flux/flux.root` is the checked-in compact flux input. Inclusive `h80`
  and the strip-energy source bundle are the inputs to flux construction.
- For normalization, use only the same accepted observable bundle containing
  `results/observable_runs/run_manifest_observables.csv` and the matching
  flux/lookup CSVs when `observable_run_qa.valid=true`. `review/bad` runs stay
  available for cuts and kinematics in the complete manifest, but must never
  normalize an observable.
- `results/reco/` is legacy diagnostic output. It predates `RunNumber`,
  `Polarization`, and `Xstrip` propagation and is not valid for run-flux
  normalization; regenerate metadata-bearing reconstruction for new physics.
- Read `docs/artifact-policy.md` and `ARTIFACTS.json` before treating a
  published artifact as an input. Do not commit raw detector/MC/training
  corpora, credentials, or undocumented regenerated physics output. Fetch
  binary snapshots with `git lfs pull`.

## Flux farm operation

Validate first, then use the explicit farm command:

```bash
python scripts/build_run_manifest.py --validate config/run_manifest.csv
python scripts/build_strip_energy_flux.py \
  --preanalysis-dir data/pre_analyzed \
  --manifest config/run_manifest.csv \
  --flux data/flux/flux.root \
  --output-dir results/strip_energy_flux
```

Exit `0` is a complete valid publication; `1` is a completed diagnostic/QA
failure or runtime input failure and is not usable for physics; `2` is command
syntax/usage failure and writes no QA. Preserve and report the full output (or
the `Failure QA:` sibling reported on stderr). Use `--resume` only after a
post-scan failure with the identical manifest, pre-analysis inventory, and
options: its checkpoint fingerprint must match. Never mix output files from
different publications.

## Graph, provenance, and documentation

Query an existing graph before exploring code relationships:

```bash
make graph-query QUERY="How does the observable-run handoff reach normalization?"
```

`make setup` installs the supported project-local `graphifyy==0.9.7` package;
its CLI is invoked through the selected project Python, not a user-global
tool. After structural code or documentation changes, refresh it with `make
graph-update`, then regenerate provenance with `make artifact-inventory` and
review its diff. Semantic documentation updates require Gemini
(`GEMINI_API_KEY` or `GOOGLE_API_KEY`) or host-agent extraction; code-only
updates require neither. Only portable Graphify files are publishable; local
interpreter/root paths and cache state remain local.

When public behavior changes, update the relevant wiki/design docs, tests,
provenance inventory, and graph snapshot in the same review.
