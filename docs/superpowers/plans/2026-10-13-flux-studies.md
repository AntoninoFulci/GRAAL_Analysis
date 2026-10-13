# Missing Flux Studies Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Deliver standalone stage 07 for missing-flux audit and experimentally validated method comparison, moving observable extraction to stage 08 without changing production physics.

**Architecture:** Calibration owns measured input contracts and its QA sidecar. The new `flux_studies` package owns diagnostic inventory, external acquisition metadata, baseline/ML comparison and experimental artifacts. Production extraction continues to consume only measured calibrated flux; the launcher enables studies explicitly.

**Tech Stack:** Existing Python >=3.10 environment compatible with PyROOT, NumPy, scikit-learn, matplotlib and pytest; setuptools package mapping. No new mandatory dependency.

**Spec:** [Approved design](../specs/2026-10-13-flux-studies-design.md).

## Global Constraints

- `06_calibration/` → `07_flux_studies/` → `08_observable_extraction/`; Python name `observable_extraction` remains stable.
- `--flux-study off|audit|study`, default `off`; output `results/<campagna>/missing_flux/`.
- Never replace measured histograms, update source files, or consume synthetic flux in Σ.
- Never equate missing calibrated coverage with missing raw histograms.
- Compatibility requires documented period, target, beam, laser and instrument configuration; run-number proximity is not time proximity.
- No independent normalization means shape-only predictions, with unknown absolute integral.
- Split before fit/scaling/tuning; causal mode excludes future training, donors and interval calibration.
- Missing scientific prerequisites yield explicit non-executable/exploratory outcomes, not invented numbers.
- Preserve existing modified and untracked files; no blanket staging, reset, cleanup or history rewriting.
- Source migration does not rewrite archived campaign outputs, dated reports or graph snapshots.
- Source-file CLI paths change to 08; document migration and refresh editable package mappings.

## Review Focus

1. Stale QA from another calibrated file must not certify run coverage: Task 2 identity test and Task 4 integration test.
2. Symlink/hardlink aliases or an output directory containing an input must not overwrite measurements: Task 4 publication tests.
3. Equal/overlapping acquisition times must not create zero-width interpolation or future leakage: Tasks 3, 5 and 6.
4. All-zero BREM is valid raw data but has no normalized shape: Tasks 4, 5 and 7.
5. Methods with fewer successful predictions must not appear superior by silently dropping hard hold-outs: Task 7 paired-coverage test.

## Execution baseline and file ownership

Current branch at planning time: `codex/dalitz-completion`. The working tree has
substantial earlier work, including untracked source files in the directory to
rename. A worktree created from HEAD alone would omit these changes. At execution
time follow the isolation skill, preserve a file inventory and hashes, and either
use the existing workspace or copy the complete relevant working state to an
isolated worktree before editing. Do not commit earlier work as part of this task.
Record the execution choice and baseline failures in the delivery report.

Files and responsibilities:

| Owner | Files | Responsibility |
|---|---|---|
| Migration | `07_observable_extraction/` → `08_observable_extraction/`, `pyproject.toml`, live callers and wiki | Physical paths and package mapping only |
| Calibration | `06_calibration/calibration_qa.py`, `build_strip_energy_flux.py` | Persist and validate measured calibration provenance |
| Input diagnostics | `06_calibration/flux_inspection.py` | Read every ROOT key/cycle without fail-fast policy |
| Metadata | `07_flux_studies/metadata.py` | External conditions, exposure units and compatibility |
| Audit | `07_flux_studies/audit_flux.py` | Inventory, cause classification and audit CLI |
| Methods | `07_flux_studies/methods.py` | Numerical baseline and Ridge predictions |
| Validation | `07_flux_studies/validation.py` | Fold masks, tuning, residuals and correlated replicas |
| Study/output | `07_flux_studies/study_missing_flux.py`, `reporting.py` | Orchestration, ROOT/CSV/plots and protected publication |
| Integration | `scripts/run_pipeline.py` | Opt-in common stage, argv and error propagation |

Tests live beside their owner; repository integration tests remain under `tests/`.
Use existing atomic directory publisher with `overwrite=False`, existing
`RunRecord`/`validate_manifest`, and existing `write_qa_json` serialization.
Do not route stage code through launcher/cache internals to reuse a hash helper:
streaming SHA-256 belongs in the calibration provenance module that needs it.

All pytest commands below use the chosen PyROOT-compatible interpreter as
`python3`. If another interpreter is needed, use its explicit path consistently.
Run the named failing test first, implement, then run the task's focused suite.
Commit each independently verified change only if its diff can exclude earlier
work; otherwise retain scoped patches and make a final reviewed scoped commit.

### Task 1: Migrate observable extraction without changing behavior

**Files:** move `07_observable_extraction/` to `08_observable_extraction/`;
modify `pyproject.toml`, `scripts/run_pipeline.py`, `scripts/plot_campaign.py`,
`scripts/audit_bdt_backgrounds.py`, `theory/src/graal_theory/{beam_asymmetry,pilot_panel5}.py`,
live references found by `rg`, `tests/{test_packaging,test_run_pipeline,test_wiki}.py`,
README files, `docs/runbooks/`, and `wiki/`.

**Interfaces:** all existing `observable_extraction.*` imports remain valid;
filesystem entry points and reference CSVs resolve under 08.

- [ ] Add this assertion to `tests/test_packaging.py`, then run that test and
  confirm failure on the existing 07 path:

```python
def test_observable_extraction_uses_stage08_directory():
    from pathlib import Path
    import observable_extraction
    root = Path(__file__).resolve().parents[1]
    assert Path(observable_extraction.__file__).resolve().parent == root / "08_observable_extraction"
```

- [ ] Snapshot relative file names and SHA-256 values under the current 07,
  including untracked files but excluding generated `__pycache__`. Rename with
  `Path("07_observable_extraction").rename("08_observable_extraction")` only
  after checking that the destination does not exist. Verify every inventoried
  byte before changing any internal path references.
- [ ] Change `observable_extraction = "08_observable_extraction"` and pytest
  testpaths in `pyproject.toml`. Update live callers and documentation found by:

```bash
rg -n '07_observable_extraction|Stage[- ]07|stage[- ]07' scripts tests theory/src README.md pyproject.toml wiki docs/runbooks 08_observable_extraction
```

- [ ] Rename the four wiki pages `07-{observable-extraction,beam-asymmetry-estimators,background-correction,systematics-and-outputs}.md`
  to corresponding `08-` names. Update their incoming links, sidebar and
  `tests/test_wiki.py` page/section maps. Preserve their existing content changes.
  Do not use a repository-wide replacement over archived reports or data.
- [ ] Refresh the editable installation without fetching dependencies:
  `python3 -m pip install -e . --no-deps --no-build-isolation` in the selected
  execution environment; use a temporary environment with existing system
  packages if the active environment must not be modified.
- [ ] Run `python3 -m pytest -q tests/test_packaging.py tests/test_repository_layout.py tests/test_run_pipeline.py tests/test_plot_campaign.py tests/test_wiki.py`.
  Expected: renamed import test and previously passing integration tests pass;
  any baseline failures remain separately documented, never silently waived.
- [ ] Review migration-only diff; commit message `refactor: move observable extraction to stage 08`.

### Task 2: Persist calibration QA bound to the produced ROOT file

**Files:** create `06_calibration/calibration_qa.py` and
`06_calibration/tests/test_calibration_qa.py`; modify
`06_calibration/build_strip_energy_flux.py` and its existing tests.

**Interfaces:**

- `sha256_file(path: Path) -> str`: chunked SHA-256, input opened read-only.
- `write_calibration_qa(path: Path, calibrated_path: Path, *, inputs: dict, coverage: list[dict], diagnostics: dict) -> None`.
- `load_calibration_qa(path: Path, calibrated_path: Path, *, expected_inputs: dict) -> dict`:
  verifies schema and content hashes; returns no authoritative coverage on mismatch.

- [ ] Add identity and publication-failure tests. A minimal identity test needs
  no ROOT parsing and uses this real payload contract:

```python
def test_qa_rejects_changed_calibrated_file(tmp_path):
    import pytest
    from calibration.calibration_qa import write_calibration_qa, load_calibration_qa
    root = tmp_path / "flux_calibrated.root"
    root.write_bytes(b"first")
    qa = tmp_path / "flux_calibrated.qa.json"
    write_calibration_qa(qa, root, inputs={}, coverage=[], diagnostics={})
    root.write_bytes(b"second")
    with pytest.raises(ValueError, match="identity"):
        load_calibration_qa(qa, root, expected_inputs={})
```

- [ ] Run `python3 -m pytest -q 06_calibration/tests/test_calibration_qa.py`;
  expect missing-module failure before implementation.
- [ ] Implement `schema_version: 1`, `calibrated_sha256`, `inputs`, `coverage`
  and `diagnostics`. Inputs identify manifest/raw flux with hashes, and h80
  files with resolved paths, sizes and modification times. Snapshot and compare
  identities across the existing scan; do not hash multi-gigabyte h80 inputs.
  Coverage rows enumerate selected run/state combinations, with h80 presence,
  observed strip count/range and calibration acceptance/reason.
- [ ] After successful `_write_calibrated_flux_root_atomic`, persist existing
  pre-write QA plus returned writer QA to `flux_calibrated.qa.json`. Use
  `write_qa_json` on a temporary sibling then `Path.replace`. Hash the published
  calibrated ROOT. A crash between ROOT and JSON publication cannot authorize
  stale QA because the hash check fails. Preserve an earlier sidecar on write
  failure; do not label it as belonging to the new ROOT.
- [ ] Extend `_validate_output_location` to cover the sidecar as well as ROOT.
  Add tests for sidecar/input aliases and failed ROOT generation producing no
  new success sidecar. Change existing `test_cli_writes_only_root_file_in_requested_directory`
  to expect exactly ROOT plus sidecar and inspect its coverage.
- [ ] Run `python3 -m pytest -q 06_calibration/tests/test_calibration_qa.py 06_calibration/tests/test_build_strip_energy_flux.py`.
  Expected: pass without changing the calibrated histogram contents.
- [ ] Review/commit `feat(calibration): persist flux coverage QA`.

### Task 3: Validate acquisition metadata and compatibility

**Files:** create `07_flux_studies/{__init__,metadata}.py`,
`07_flux_studies/tests/{__init__,test_metadata}.py`; extend `pyproject.toml`
with `flux_studies`, `flux_studies.tests`, mapping and testpath.

**Interfaces:** `RunKey = tuple[int, str]`; `load_metadata(path: Path | None,
manifest: Sequence[RunRecord]) -> dict[RunKey, dict]`; `compatible(a: dict,
b: dict) -> bool`; `acquisition_midpoint(record: dict) -> float` in UTC seconds.
Normalized records contain manifest period/target/beam, state, source,
`start_utc`, `end_utc`, `configuration_id`, `laser_id`, optional
`experiment_group` and optional `exposure`.

- [ ] Add tests from a complete JSON document, deleting one property per case:

```json
{
  "schema_version": 1,
  "records": [{
    "run_number": 7, "state": "POL1", "source": "acquisition log",
    "source_period": "1998_uv", "target": "P", "beam_type": "UV",
    "start_utc": "1998-01-01T10:00:00Z", "end_utc": "1998-01-01T10:05:00Z",
    "configuration_id": "setup-A", "laser_id": "UV-A",
    "exposure": {"value": 100.0, "error": 2.0, "unit": "s",
                 "definition": "live_time", "uncertainty_group": "clock-A"}
  }]
}
```

```python
def test_unknown_configuration_is_not_compatible():
    from flux_studies.metadata import compatible
    left = dict(source_period="1998_uv", target="P", beam_type="UV",
                state="POL1", configuration_id=None, laser_id="UV-A")
    assert not compatible(left, dict(left))
```

- [ ] Run new metadata tests, confirm missing-module/function failure, then
  implement parsing with timezone-aware `datetime.fromisoformat` after replacing
  terminal `Z` with `+00:00`. Reject reversed intervals, naive timestamps,
  duplicate run/state, unknown states/runs, conflicting classifications and
  nonfinite numbers. Missing fields remain `None` with reasons; never infer
  configuration from the run number or label alone.
- [ ] Exposure value must be positive, error nonnegative and finite, unit and
  definition nonempty. Missing uncertainty is not equivalent to zero uncertainty:
  allow shape-only study and report absolute uncertainty unavailable. Matching
  uncertainty groups require matching physical meaning and use common draws.
- [ ] Reject interpolation at duplicate donor midpoints; interval-overlap rules
  are enforced by the fold/method tasks. Add metadata tests for explicit zero
  error, missing error, unknown configuration and inconsistent exposure units.
- [ ] Refresh package mapping and run `python3 -m pytest -q 07_flux_studies/tests/test_metadata.py tests/test_packaging.py`.
- [ ] Review/commit `feat(flux): validate acquisition metadata`.

### Task 4: Build tolerant inventory and protected audit CLI

**Files:** create `06_calibration/flux_inspection.py`,
`06_calibration/tests/test_flux_inspection.py`,
`07_flux_studies/{audit_flux,reporting}.py`,
`07_flux_studies/tests/{test_flux_audit,test_publication}.py`.

**Interfaces:**

- `inspect_histograms(path: Path, *, axis_kind: str) -> list[dict]`: one entry
  per relevant key/cycle, including malformed objects; raises on unreadable file.
- `audit_flux(*, manifest: Path, raw_flux: Path, calibrated_flux: Path | None = None,
  calibration_qa: Path | None = None, run_metadata: Path | None = None,
  target: str = "P", beam_type: str | None = None, periods: tuple[str, ...] = ()) -> dict`.
- Audit result keys: `schema_version`, `inputs`, `summary`, `rows`, `strips`,
  `metadata`, `histograms`. `histograms` maps RunKey to usable raw arrays for
  in-memory study; writers exclude that internal map from summary JSON.
- `write_audit(directory: Path, result: dict) -> None` and
  `publish_output(destination: Path, inputs: Sequence[Path])`: context manager
  yielding a temporary directory and enforcing immutable-input/exclusive-output rules.

- [ ] Create tiny ROOT fixtures using `TFile(..., "RECREATE")`, `TH1D` and
  repeated `Write()` to represent cycles. Reuse patterns from calibration tests.
  Create a two-run `RunRecord` manifest; build the following case:

```python
def test_raw_present_calibration_missing_is_not_missing_raw(tmp_path):
    import ROOT
    from calibration.run_manifest import RunRecord, write_manifest
    from flux_studies.audit_flux import audit_flux
    manifest = tmp_path / "manifest.csv"
    write_manifest([RunRecord(7, "1998_uv", "P", "UV", "P_UV", "manual",
                              "1998_uv/run7.root")], manifest)
    raw, calibrated = tmp_path / "raw.root", tmp_path / "cal.root"
    with ROOT.TFile(str(raw), "RECREATE") as output:
        for state in ("POL1", "POL2", "BREM"):
            hist = ROOT.TH1D(f"run7_{state}", "", 128, 0, 128)
            for strip in range(1, 129):
                hist.SetBinContent(strip, 0 if state == "BREM" else 10)
            hist.Write()
    with ROOT.TFile(str(calibrated), "RECREATE"):
        pass
    result = audit_flux(manifest=manifest, raw_flux=raw, calibrated_flux=calibrated)
    pol1 = next(row for row in result["rows"] if row["state"] == "POL1")
    assert "missing_raw" not in pol1["problems"]
    assert "missing_calibrated" in pol1["problems"]
    assert pol1["coverage"] == "unknown"
```

- [ ] Run the new tests to observe failure, then implement inspector using
  `GetListOfKeys()` rather than `Get(name)` so no duplicate disappears. Retain
  key names, cycles, dimension, class, 128-bin check, finite/increasing edges,
  raw edges 0..128, values/errors and underflow/overflow. Catch object-level
  defects into problem records; do not catch unreadable-file errors as missing data.
- [ ] Join manifest × three states against raw, calibrated and verified QA.
  Preserve multiple problems and per-strip extraction eligibility. Compare
  contents by strip index; distinguish negative raw clamp from missing input.
  Verify the QA identities against the current raw and manifest as well as ROOT.
  If a supplied QA is stale, record `qa_identity_mismatch`, ignore its coverage,
  and continue inventory with `coverage: unknown`.
- [ ] Implement module CLI with `main(argv=None) -> int`, required input flags
  and optional calibration/metadata/filter flags from the spec. Audit defects
  return 0 with counts; invalid configuration/unreadable files return 1 and no
  published success directory. Serialize invalid numeric bins as `null` plus
  reasons, using JSON `allow_nan=False`.
- [ ] Implement publication guard: resolve input/output paths, reject output
  equal to or ancestor of any input, reject existing destination (including
  symlink/dangling symlink), and use `atomic_output_directory(..., overwrite=False)`.
  Hash input files before/after the operation; mismatch cancels publication.
  Input file aliases are recognized with `samefile` where both paths exist.
- [ ] Add tests for absent key, duplicate cycle, alias, TH2/wrong bin count,
  NaN/negative values, raw-present/missing-calibration, stale QA, zero BREM,
  incompatible calibrated axes, symlink output, input inside destination and
  concurrent destination claim. Assertions inspect causes and original hashes.
- [ ] Run `python3 -m pytest -q 06_calibration/tests/test_flux_inspection.py 07_flux_studies/tests/test_flux_audit.py 07_flux_studies/tests/test_publication.py`.
- [ ] Review/commit `feat(flux): add immutable missing flux audit`.

### Task 5: Implement baseline and Ridge numerical methods

**Files:** create `07_flux_studies/methods.py` and
`07_flux_studies/tests/test_methods.py`.

**Interfaces:**

- `normalize_shape(values: np.ndarray) -> np.ndarray`: finite nonnegative input,
  positive sum, normalization on final axis; rejects all-zero shape.
- `project_shape(values: np.ndarray) -> np.ndarray`: finite prediction,
  clip at zero then normalize; rejects zero resulting sum.
- `baseline_prediction(method: str, times: np.ndarray, values: np.ndarray,
  query_time: float) -> dict`: keys `values`, `donor_indices`, `status`, `reason`;
  methods `nearest`, `mean`, `median`, `linear`, inputs already compatible/allowed.
- `fit_ridge(features: np.ndarray, targets: np.ndarray, *, alpha: float)`:
  returns fitted sklearn Pipeline; no fit occurs during module import.

- [ ] Add precise numerical cases, then run `python3 -m pytest -q 07_flux_studies/tests/test_methods.py` expecting missing-module failure:

```python
def test_linear_prediction_uses_time_not_run_number():
    import numpy as np
    from flux_studies.methods import baseline_prediction
    left = np.zeros(128); left[0] = 1
    right = np.zeros(128); right[1] = 1
    result = baseline_prediction("linear", np.array([10., 30.]),
                                 np.array([left, right]), 15.)
    np.testing.assert_allclose(result["values"][:2], [.75, .25])
    assert result["donor_indices"] == [0, 1]
```

- [ ] Implement nearest with deterministic earlier-time tie breaking, mean and
  coordinate median templates, and bracketing linear interpolation. Return
  `not_reconstructible` for absent donors, missing bracket or duplicate bracket
  times; never relabel a one-sided prediction as interpolation. Caller records
  whether nearest donor is before/after target and validates its interval coverage.
- [ ] Implement normalization and nonnegative projection separately: negative
  measured data must not be silently repaired by the prediction projection.
  Mean/median inputs are normalized forms in shape mode, exposure-corrected
  per-strip rates in absolute mode. Median with zero support is unavailable.
- [ ] Use existing sklearn primitives for the multi-output fit:

```python
def fit_ridge(features, targets, *, alpha):
    from sklearn.linear_model import Ridge
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler
    model = make_pipeline(StandardScaler(), Ridge(alpha=alpha))
    return model.fit(features, targets)
```

  Validate shapes, finite values and positive alpha before fitting. Ridge
  predicts either shape components or rates; the validation caller applies
  nonnegative projection and, for rates, target independent exposure.
- [ ] Test mean/median, no donor, one side, duplicate times, zero BREM shape,
  negative measured bins, negative predicted bins, zero projected sum and a
  tiny multi-output regression with known coefficients. Confirm scaler means
  depend only on supplied training features.
- [ ] Run focused methods suite. Review/commit `feat(flux): add baseline and Ridge methods`.

### Task 6: Enforce blocked masking and nested training isolation

**Files:** create `07_flux_studies/validation.py` and
`07_flux_studies/tests/test_validation.py`.

**Interfaces:**

- `blocked_folds(metadata: dict[RunKey, dict], *, mode: str, n_splits: int) -> list[dict]`:
  each fold has `fold_id`, compatibility group, `train_runs`, `test_runs`.
- `evaluate_holdouts(audit: dict, *, mode: str, n_splits: int, mask_patterns: tuple[tuple[str, ...], ...], seed: int) -> dict`:
  returns `predictions`, `folds`, `excluded`, `residuals` and training traces.
  Predictions identify run/state/method/pattern/domain/fold, donor keys,
  training keys, selected alpha, estimate and separately attached test truth.

- [ ] Add a fixture builder inside `test_validation.py`: at least 30 runs in
  one explicit configuration, all three states with distinct positive 128-bin
  vectors and separated UTC intervals. Add another period with disjoint flux
  scale. The audit dict uses the exact Task 4 schema; no ROOT file is needed.
  Record seed 42. First test disjoint run folds:

```python
def test_all_states_of_test_runs_are_excluded_from_training(metadata_fixture):
    from flux_studies.validation import blocked_folds
    for fold in blocked_folds(metadata_fixture, mode="offline", n_splits=5):
        assert set(fold["train_runs"]).isdisjoint(fold["test_runs"])
```

- [ ] Run new tests, then partition unique run acquisition intervals per
  compatibility group into contiguous blocks with `np.array_split`. Keep
  overlapping intervals in the same block. Offline training uses other blocks;
  causal training uses only blocks whose latest end is before test start.
  With fewer eligible blocks than requested, reduce recorded fold count;
  no valid training/test split yields explicit `insufficient_data`.
- [ ] Within each outer training set, create inner blocked folds with the same
  causality rules. Select alpha from `(0.1, 1.0, 10.0, 100.0)` by mean shape L1
  error on inner hold-outs, choosing the larger alpha for exact ties. Refit a
  fresh scaler/Ridge on outer training only. If inner splits are insufficient,
  report Ridge unavailable; baseline evaluation can still proceed.
- [ ] Construct feature schema per mask pattern from known acquisition times
  and available unmasked other-state shapes plus observed integrals/exposures
  when permitted. Never include the target state or any masked state as input.
  Use identical masking on training examples. In causal mode, another state's
  data are usable only if its acquisition ended by target prediction time.
  If required context is missing, report method unavailable; do not insert truth.
- [ ] Predict with an explicit map that omits all masked keys. Attach truth
  only after prediction. All states of outer test runs are excluded from model
  fitting; unmasked test-state context may be used solely as an available
  predictor. Log donor/training membership and fold identity.
- [ ] Add metamorphic test: multiply only the hidden outer target vector by
  1000 and rerun that fold; predictions, alpha and scaler must stay unchanged,
  while evaluation residual changes. Test two-state and three-state masks,
  period separation, future exclusion, overlap grouping and insufficient data.
  No masking pattern may cross group boundaries for convenience.
- [ ] Run `python3 -m pytest -q 07_flux_studies/tests/test_validation.py 07_flux_studies/tests/test_methods.py`.
- [ ] Review/commit `feat(flux): isolate blocked holdout validation`.

### Task 7: Quantify paired performance and correlated uncertainty

**Files:** extend `07_flux_studies/validation.py`; create
`07_flux_studies/tests/test_uncertainty.py`.

**Interfaces:**

- `paired_metrics(predictions: list[dict]) -> dict`: total eligible targets,
  successes/failures by method, common-target pairwise differences and strata.
  `coverage[method]` has integer `eligible` and `success` counts; `pairs` records
  common target keys and differences. Each input row has `target_key`, `method`,
  `status`, `truth` and `estimate` (the latter is `None` when unavailable), plus
  optional domain/fold/stratum fields preserved from Task 6.
- `joint_replicas(predictions: list[dict], training_residuals: list[dict], *,
  seed: int, n_replicas: int) -> dict`: aligned replica IDs, target keys,
  arrays shaped `(replica, target, strip)` and per-target covariance matrices.
  Training traces from Task 6 supply donor/model inputs for refitting.

- [ ] Add paired-coverage and correlation tests, run and observe missing API:

```python
def test_failed_predictions_remain_in_method_denominator():
    import numpy as np
    from flux_studies.validation import paired_metrics
    truth = np.full(128, 1 / 128)
    rows = [
        dict(target_key=(run, "POL1", "offline", 0), method=method,
             status="ok", truth=truth, estimate=truth.copy())
        for run in (7, 8) for method in ("nearest", "ridge")
    ]
    rows[-1].update(status="not_reconstructible", estimate=None)
    result = paired_metrics(rows)
    assert result["coverage"]["ridge"]["eligible"] == 2
    assert result["coverage"]["ridge"]["success"] == 1
    assert result["coverage"]["nearest"]["success"] == 2
```

  For the covariance test, give two predictions the same donor and exposure
  uncertainty group, with the second target exposure twice the first. Remove
  residual noise in that controlled fixture: `joint_replicas` must produce
  second-target fluctuations twice the first, and cross-covariance twice the
  first variance. Then use independent groups and check absence of the forced
  identity. This tests generated draws, not just NumPy's covariance function.
- [ ] Calibrate residual uncertainty exclusively using out-of-fold residuals
  from outer-training data. Inner alpha selection for a calibration residual
  must exclude that residual's target as well; nesting must not reuse tuning
  residuals as unbiased calibration data. Outer-test residuals are reserved
  for empirical coverage evaluation, never interval construction.
- [ ] Resample contiguous training blocks once per replica/compatibility group,
  refit model/template and use shared donor multiplicities for all target
  predictions. Draw exposure nuisances once per declared uncertainty group;
  use positive lognormal multipliers with mean 1 and supplied relative variance.
  Zero declared uncertainty gives multiplier 1; missing uncertainty disables
  absolute interval claims. Preserve covariance using aligned replicas.
- [ ] Add training residual innovations by sampled block and state pattern.
  Separate uncertainty of the estimated mean (donor/model bootstrap) from
  target predictive variation (residuals); report both and evaluate coverage
  of the final combined intervals on outer hold-outs. Record model assumptions
  and warn that coverage is empirical, not guaranteed by the bootstrap.
- [ ] A replica unable to form a bracket is invalid for that target, not zero.
  Store validity masks and valid replica counts. Estimate covariance only from
  jointly valid draws, record pairwise counts, and omit unsupported matrices.
  A single donor with no independent calibration residuals gives unavailable
  predictive uncertainty, never a zero-width certainty claim.
- [ ] Calculate per-strip residuals/bias, shape L1, integral relative error
  only for positive measured truth and identifiable absolute predictions, and
  marginal 68%/95% interval coverage. All-zero truth is counted separately.
  Compare methods on identical target keys and report each method's full
  eligible/success denominator, including failures and unavailable intervals.
- [ ] Add tests for lower apparent MSE caused by dropped targets, shared versus
  independent exposure groups, deterministic seeds, no valid replicas, single
  donor, test-truth perturbation leaving intervals unchanged, and a controlled
  hold-out ensemble with documented nominal coverage and Monte Carlo tolerance.
- [ ] Run `python3 -m pytest -q 07_flux_studies/tests/test_uncertainty.py 07_flux_studies/tests/test_validation.py`.
- [ ] Review/commit `feat(flux): report paired metrics and covariance`.

### Task 8: Publish study artifacts and experimental candidates

**Files:** create `07_flux_studies/study_missing_flux.py`; extend
`07_flux_studies/reporting.py`; create
`07_flux_studies/tests/{test_study_cli,test_reporting}.py`.

**Interfaces:** `run_study(audit: dict, *, mode: str, n_splits: int, seed: int,
n_replicas: int, mask_patterns: tuple[tuple[str, ...], ...]) -> dict`;
`write_study(directory: Path, audit: dict, study: dict) -> None`;
`main(argv=None) -> int` for module CLI.

- [ ] Test no-metadata execution before implementation:

```python
def test_missing_metadata_produces_protocol_not_synthetic_flux(audit_fixture):
    from flux_studies.study_missing_flux import run_study
    result = run_study(audit_fixture, mode="offline", n_splits=5, seed=42,
                       n_replicas=200, mask_patterns=(("POL1",),))
    assert result["status"] == "not_executable"
    assert result["reasons"]
    assert result["candidates"] == []
```

  Define `audit_fixture` in this test module with the same small ROOT/manifest
  construction as Task 4 and no metadata. Add CLI checks for exit codes and
  published file set, not just the Python return value.
- [ ] Implement `--mode offline|causal` (default offline), `--folds` (default 5),
  `--seed` (default 42), `--replicas` (default 200), repeatable `--mask-states`
  taking comma-separated distinct states; default masks each state separately.
  Require folds >=2 and replicas >=2; invalid CLI input is a technical failure.
  Metadata absent means audit plus `study.json` protocol, exit 0 and visible
  scientific status. Catch only expected input/scientific availability errors.
- [ ] Produce descriptive hold-out results without claiming automatic adoption.
  No numeric adoptions thresholds are invented. Status is `exploratory` when
  comparable results exist, `insufficient_data` or `not_executable` otherwise.
  Emit candidates only for truly absent raw histograms with sufficient compatible
  inputs, keeping each method separate. Do not overwrite invalid measured bins,
  duplicate keys or missing calibration with synthetic content.
- [ ] Write audit CSV/JSON, `study.json`, `validation.csv`, `study.root` and
  diagnostic plots. `study.root` namespaces: `measured/`, `holdout/`,
  `uncertainty/`, `metadata/`. Candidate file has `synthetic/` namespace and
  explicit status/method/domain; never top-level production `runN_POL1` names.
  Save strip-index histograms, per-target matrices and aligned replica records
  with validity masks so cross-target covariance can be reconstructed.
- [ ] ROOT metadata includes schema, input hashes, compatibility domain,
  measured/synthetic label, acquisition evidence, donor/training keys, mask,
  fold, seed, method, absolute-integral availability and reasons. Reopen every
  written ROOT in tests and verify content and metadata; reject a candidate
  file as a calibrated production input in an extraction regression test.
- [ ] Plot absolute integrals only when identifiable; label shape panels as
  unit normalized. Include paired method errors, residual/coverage diagnostics,
  and separate single-donor/period-edge/multiple-missing strata. For documented
  Vinci groups, compare requested r−1/r/r+1 only when present and compatible;
  report rejected neighbors and use acquisition time in interpolation weights.
- [ ] Test shape-only candidates, no-missing domain, all-zero BREM exclusion,
  invalid measurements not imputed, unknown Vinci identity, metadata-free
  execution without importing sklearn, and ROOT metadata round-trip.
- [ ] Run `python3 -m pytest -q 07_flux_studies/tests/test_study_cli.py 07_flux_studies/tests/test_reporting.py 07_flux_studies/tests/test_publication.py 08_observable_extraction/tests/test_calibration_io.py`.
- [ ] Review/commit `feat(flux): publish experimental study artifacts`.

### Task 9: Integrate optional common stage and operational documentation

**Files:** modify `scripts/run_pipeline.py`, `tests/test_run_pipeline.py`,
`README.md`, `docs/runbooks/full-pipeline.md`, `wiki/{Home,_Sidebar,workflow,repository-structure,commands-and-configuration}.md`,
`tests/test_wiki.py`; create `docs/runbooks/missing-flux.md` and
`wiki/07-flux-studies.md`.

**Interfaces:** extend `build_pipeline_plan` keyword arguments with
`flux_study: str = "off"` and `flux_study_metadata: Path | None = None`;
add CLI flags `--flux-study`, `--flux-study-metadata` with identical semantics.

- [ ] Add launcher default/ordering test and run before implementation:

```python
def test_flux_audit_is_opt_in_and_runs_after_calibration(tmp_path):
    from scripts import run_pipeline as pipeline
    config = pipeline.mode_config("production", tmp_path)
    paths = pipeline.build_paths(config)
    checked = pipeline.PreflightResult("/usr/bin/root")
    default = pipeline.build_pipeline_plan(config, paths, checked)
    enabled = pipeline.build_pipeline_plan(config, paths, checked, flux_study="audit")
    assert not any(stage.name.startswith("common:flux_") for stage in default)
    assert enabled[0] == default[0]
    assert enabled[1].name == "common:flux_audit"
    assert enabled[2:] == default[1:]
```

- [ ] Build `common:flux_audit` or `common:flux_study` after the calibration
  command. Invoke `python -m flux_studies.audit_flux` or
  `python -m flux_studies.study_missing_flux` with raw, manifest, calibrated,
  QA sidecar and campaign output paths. Forward metadata only when supplied.
  Invalid mode or metadata file is rejected before starting expensive work;
  metadata with `off` is an explicit configuration error, not silently ignored.
- [ ] Preserve default plan, extraction flux arguments and cache behavior.
  Print selected study mode in run summary. Existing executor handles stage
  command logging and nonzero status. An unavailable scientific study still
  records its reason and returns 0; a technical failure stops execution.
- [ ] Add study mode argv, metadata paths with spaces, default-off, invalid
  flags, absent metadata file, unchanged extraction input and executor failure
  tests. Keep existing namespace defaults for test fixtures via `getattr` where
  appropriate, without hiding invalid explicitly supplied values.
- [ ] Document standalone audit before/without successful calibration, full
  launcher opt-in, metadata schema/example, shape-only limits, output statuses,
  no synthetic Σ input and 07→08 source path migration. Add wiki page with
  `Inputs and Preconditions`, `Audit and Study Modes`, `Validation`, and
  `Products and Limits` sections, updating page/section assertions and sidebar.
- [ ] Run `python3 -m pytest -q tests/test_run_pipeline.py tests/test_packaging.py tests/test_repository_layout.py tests/test_wiki.py tests/test_wiki_sync.py`.
- [ ] Review/commit `feat(pipeline): integrate optional flux studies`.

### Task 10: Run local audit and close with reproducible evidence

**Files:** create `docs/reports/2026-10-13-missing-flux.md`; update only the
03 row/status in `docs/plans/2026-10-12-graal/{README,03-flussi-mancanti}.md`
to distinguish software delivery, local audit and scientific validation.

- [ ] Run the final focused integration suite, combining the suites already
  named above. Include all `07_flux_studies/tests`, calibration tests and 08
  calibration/CLI tests after the final integration change. Record command,
  interpreter, test counts, baseline failures and any unavailable dependency.
- [ ] Check live references with the Task 1 `rg` query, verify fresh imports
  resolve to 08, and run both new module CLIs with `--help`. Check original input
  hashes remain unchanged in the fixture integration runs.
- [ ] Select an unused campaign output directory, then audit the local inputs:

```bash
python3 -m flux_studies.audit_flux \
  --manifest config/run_manifest.csv \
  --raw-flux data/00_external/flux.root \
  --calibrated-flux data/00_external/flux_calibrated.root \
  --output-dir results/missing-flux-audit-20261013/missing_flux
```

  Do not overwrite an existing directory; choose a new explicit suffix if needed.
  The calibrated input here is not assumed to be the historical production
  campaign. Record its identity and compare historical counts only when domains
  actually match. If the calibrated input is absent, run raw-only audit and
  record the missing comparison; do not regenerate massive h80 calibration.
- [ ] If real acquisition metadata remain absent, run study on the same inputs
  in a different unused output directory without metadata. Expected: complete
  audit, protocol, `not_executable`, no candidate ROOT. If real metadata are
  available, execute the corresponding eligible hold-outs and report their
  actual coverage; never substitute a toy result for experimental validation.
- [ ] Inspect generated diagnostic plots where present. Write report with
  recomputed counts per period/state, raw versus calibration exclusions,
  immutable input evidence, available metadata, tests and scientific limits.
  Mark completed software checkboxes accurately; leave scientific validation
  unchecked when prerequisites prevent it.
- [ ] Obtain final code review using the selected execution workflow. Fix
  material findings and rerun only affected checks. Review scoped diff so
  earlier uncommitted work is neither lost nor falsely attributed to this task.
- [ ] Deliver paths, test evidence, actual audit outcome and remaining scientific
  limitations. Do not run new Σ inference, train production BDTs, merge or publish
  remotely as part of this task.

## Verification-to-spec map

| Spec requirement | Tasks |
|---|---|
| Numbered stage, preserved package and working state | 1, 9 |
| QA identity, h80/strip coverage and raw/calibrated distinction | 2, 4 |
| External metadata, exposure meaning, group compatibility | 3, 6 |
| Baselines, Ridge, positivity, independent normalization | 5, 6, 8 |
| Block masking, causal/offline distinction, no leakage | 6, 7 |
| Paired metrics, residual calibration, shared covariance | 7 |
| Separate ROOT/CSV, provenance, Vinci panels, protected inputs | 4, 8 |
| Opt-in launcher and unchanged production extraction | 9 |
| Real audit, honest negative outcomes, final proof | 10 |

## Documentation consulted for the ML boundary

Context7 resolved `/scikit-learn/scikit-learn` on 13 October 2026. The documented
Pipeline pattern fits preprocessing within each training fold; Ridge supports
multi-output targets. References: scikit-learn `doc/common_pitfalls.rst`,
`doc/modules/cross_validation.rst`, `doc/getting_started.rst` and
`sklearn/linear_model/_ridge.py`. Explicit blocked folds and causal donor rules
remain application-owned; a generic random split would violate this design.

## Execution handoff

Native execution approved and completed on 13 October 2026, with independent
final review and a RED→GREEN fix pass. Tasks 1–10 delivered in the working tree;
scoped commits deferred to preserve earlier uncommitted work. The original
checkboxes above remain the detailed planned procedure, not a claim that every
example filename or intermediate commit was used literally. See
[delivery evidence](../../reports/2026-10-13-missing-flux.md) for actual tests,
interface refinements, audit results and scientific limits.
