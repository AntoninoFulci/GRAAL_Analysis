# Troubleshooting

Most failures are intentional trust-boundary checks. Preserve the error text,
the command, and the existing validated output. Fix the producer, path, or
configuration that violated the contract; do not weaken validation or delete
the last good artifact as a first response.

## Setup Failures

| Symptom | Likely cause | Action |
|---|---|---|
| `Python interpreter not found` | bad `--python` path or unloaded environment | locate the interpreter used with ROOT and pass its absolute path |
| `Python 3.10 or newer is required` | selected interpreter below project floor | choose a compatible PyROOT build on Python >=3.10 |
| `selected Python cannot import ROOT` | ROOT environment not loaded or interpreter/ROOT ABI mismatch | load ROOT setup, verify `PATH`/library paths, then run `python -c 'import ROOT'` before setup |
| `.venv cannot import ROOT` | virtual environment cannot see system PyROOT | remove only an incomplete environment after inspection, rerun supported setup with the correct base interpreter and system site packages |
| `existing .venv is incomplete` | `.venv` exists without executable `bin/python` | preserve any needed files, then replace that incomplete environment and rerun setup |
| farm target is not a directory | wrong or unmounted external path | mount/locate the dataset and pass an existing directory |
| existing symlink has different target | checkout already points at another dataset | verify which dataset is intended; update manually only after preserving the existing link target |
| path exists and is not expected symlink | local content occupies a farm-link path | inspect and relocate it deliberately; setup will not overwrite it |
| project package import fails after setup | editable install failed or wrong environment active | activate `.venv`, rerun `pip install -e .`, then run packaging tests |

Missing `data/00_external/flux.root` is only a setup warning. Calibration will
still need an actual flux file passed through `--flux`.

## Missing or Invalid Data

| Symptom | Cause boundary | Recovery |
|---|---|---|
| input directory does not exist or contains no matching ROOT files | wrong stage path or upstream stage not run | inspect [Workflow](workflow), generate/copy the required upstream artifact, rerun with explicit paths |
| ROOT file is zombie/unreadable | corrupt, incomplete, or incompatible file | validate with ROOT, recover/regenerate from upstream; do not treat it as empty |
| `missing TTree` with available keys listed | wrong file or wrong tree contract | choose the correct stage artifact/tree; never rename a different tree just to satisfy the reader |
| required branches missing | stale producer or wrong reconstruction mode | compare against the stage schema and regenerate with the current producer |
| selected `h85` output absent after selection | no valid `h80` inputs or validation failure | fix input discovery/tree contract; atomic publication preserves the prior selected directory |
| MC status reports missing channels | generator outputs absent from `03_mc_simulation/data` | run the listed channel generators or point `mc_status`/feature builder at the correct directory |
| `signal MC ... not found` in fit-resolution plot | required truth-bearing `mc` file absent | generate signal MC or pass `--signal` to the correct file |
| event has no run/strip exposure | calibration lacks that selected stratum | inspect calibration QA and manifest; main observable workflow warns and drops affected events |

An empty file/tree and a missing file/tree are different failures. Do not use an
empty placeholder to advance the pipeline.

## Model Compatibility

| Symptom | Likely cause | Action |
|---|---|---|
| missing model, threshold, or provenance | incomplete Stage-1 runtime bundle | restore or retrain all runtime members together |
| invalid/extra provenance key or wrong type | stale or manually edited provenance schema | regenerate with the current trainer; do not add permissive defaults |
| hypothesis mismatch | model trained for a different physics hypothesis | select a compatible bundle or retrain for the requested reconstruction |
| feature count/order mismatch | dataset, provenance, model, and runtime code from different revisions | rebuild features and retrain as one release |
| threshold cannot be parsed or is non-finite | corrupt `stage1_threshold.txt` | regenerate threshold from training output |
| XGBoost import/model load error | missing dependency or model/version incompatibility | activate configured environment, verify pinned XGBoost, and retrain/convert under a reviewed migration if necessary |
| implausibly perfect performance or unstable retraining | leakage, inconsistent weights, seeds, or inputs | verify photon shuffling, feature schema, beam spectrum, channel registry, signal prior, seeds, and exact input artifacts |

Metrics PNGs are diagnostic only; successful images do not prove the runtime
bundle is complete or compatible.

## Calibration and Fit Failures

| Symptom | Meaning | Action |
|---|---|---|
| manifest classification unresolved | run target/beam/group not safely known | classify the run manually and validate sorted unique rows |
| malformed flux triplet | missing/duplicate/ambiguous `POL1`, `POL2`, or `BREM` object | correct the external flux ROOT structure |
| nonzero flux without lookup | strip carries exposure but no energy assignment | fix `h80` coverage/strip mapping; do not discard nonzero flux |
| monotonic direction undetermined or inversion exceeds tolerance | strip-energy lookup is physically inconsistent | inspect affected run/strips and calibration inputs before adjusting any tolerance |
| negative flux warning | histogram bin was clamped to zero | inspect external flux production and QA list; warning alone does not invalidate output |
| invalid exposure rows skipped | non-positive selected `POL1`/`POL2` | inspect affected run/strip; Stage 07 excludes them |
| no flux exposure for energy bin | events exist where no calibrated exposure was selected | reconcile energy range, manifest group, and lookup |
| not enough populated phi bins | sparse ratio data after valid-error mask | combine more data only through a reviewed binning change; the nominal grid is fixed |
| diagnostic ratio fit also underpopulated | p-value triggered fallback but fewer than four bins survived | inspect counts/exposures; bin is skipped rather than forcing a fit |
| conditional likelihood fit failed | non-positive rates or numerical minimization failure | inspect state labels, flux, polarization, phi, and physical domain |
| Sigma at physical boundary with pressure | extended positivity fit prefers magnitude beyond one | report boundary diagnostic; do not publish the unbounded result as physical |
| signal leakage exceeds 5% | selected signal MC contaminates hard sideband too strongly | correct signal selection/model before background correction |
| sideband and signal-MC arguments must be supplied together | incomplete correction inputs | provide both validated inputs or neither |
| bootstrap replica lost fitted bins | resampled run blocks cannot reproduce nominal vector | inspect run balance and sparse bins; do not pad missing replicas silently |
| no beam-asymmetry bins could be fitted | no bin met estimator preconditions | trace event selection, exposure join, polarization states, and bin occupancy |

### Safe diagnostic sequence

1. Re-run the failing command with the same inputs and capture the complete
   first error, not only the final exception.
2. Check paths, ROOT keys/trees/branches, schema versions, and provenance.
3. Run the focused tests for the producer and consumer boundary.
4. Inspect QA JSON or rejection counters where provided.
5. Regenerate only the stale/invalid artifact from its owning stage.
6. Run the downstream focused suite, then `pytest -q`.

If an old valid output exists, keep it until replacement completes. Atomic
publishers already follow this rule; direct ROOT/plot writers require operator
care.
