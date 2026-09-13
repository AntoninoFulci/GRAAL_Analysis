# N3 Response and S4 Forward-Folding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate a content-addressed joint mass-phi N3 response, build deterministic N2-derived S4 evidence, fit Sigma by forward folding, and make S6 replay every scientific result.

**Architecture:** A strict schema/config layer supplies one trust boundary for every reader. A response parser reconstructs weighted covariance blocks; an N2 projector writes nominal and shared-event bootstrap counts; a joint Poisson fitter consumes both. S4 publishes an immutable three-file evidence bundle that S6 independently reparses and replays.

**Tech Stack:** Python 3, NumPy, SciPy, PyROOT only at N2 projection boundary, pytest, JSON/CSV/NPZ, SHA-256, Graphify.

**Spec:** `docs/superpowers/specs/2026-09-13-n3-response-forward-folding-design.md`

## Global Constraints

- N3 response is joint `(true mass,true phi) -> (reco mass,reco phi)` for both `parallel` and `perpendicular`.
- N3 handoff remains exactly three immutable files below `results/physics/normalization/handoffs/<acceptance_release_id>/`.
- S4 evidence contains exactly `azimuth_counts_v1.csv`, `sigma_fit_v1.csv`, and `sigma_fit_qa.json` below `results/physics/polarization_fits/<fit_release_id>/`.
- S6 remains exactly three files below `results/physics/polarization/`.
- Serialized paths are canonical repository-relative POSIX paths; absolute, dotted, backslash, symlink, missing, and non-file targets fail closed.
- `acceptance_qa_sha256` is canonical external trust anchor for N3.
- `schema_version=1`, `analysis_version=polarization-v1`, `status=approved`, and `blocked_reasons=[]` are mandatory for releasable S4/S6 output.
- Repository config stays blocked until real upstream authorities exist; tests use temporary synthetic authorities only.
- N4 output can never satisfy S4 provenance.
- N3 masks are exactly `valid`, `invalid_zero_generated`, `invalid_low_effective_statistics`, `invalid_nonphysical_weights`, and `invalid_incomplete_coverage`.
- No test creates or commits real physics output.

---

### Task 1: Portable Paths and Strict Analysis Config

**Files:**
- Create: `08_polarization/analysis_config.py`
- Modify: `08_polarization/contracts.py`
- Modify: `08_polarization/figure4_config.py`
- Modify: `config/physics/polarization_v1.json`
- Test: `08_polarization/tests/test_contracts.py`
- Test: `08_polarization/tests/test_analysis_config.py`
- Test: `08_polarization/tests/test_figure4_config.py`

**Interfaces:**
- Produces: `canonical_relative_file(root: Path, raw_path: object, label: str) -> tuple[str, Path]`
- Produces: `AnalysisConfig`, `ResponseValidationConfig`, `BootstrapConfig`
- Produces: `load_analysis_config(path: Path, root: Path, *, require_approved: bool) -> AnalysisConfig`
- Consumes: existing `PolarizationContractError`, `load_json`, and `sha256_file`.

- [ ] **Step 1: Write failing portable-path tests**

```python
@pytest.mark.parametrize("raw", ["/tmp/input.csv", "a/../b.csv", "./a.csv", "a\\b.csv", ""])
def test_canonical_relative_file_rejects_noncanonical_paths(tmp_path, raw):
    with pytest.raises(PolarizationContractError):
        canonical_relative_file(tmp_path, raw, "fixture")

def test_canonical_relative_file_returns_posix_identity(tmp_path):
    target = tmp_path / "data" / "input.csv"
    target.parent.mkdir()
    target.write_text("x\n")
    assert canonical_relative_file(tmp_path, "data/input.csv", "fixture") == (
        "data/input.csv", target.resolve()
    )
```

- [ ] **Step 2: Run path tests and verify failure**

Run: `python -m pytest -q 08_polarization/tests/test_contracts.py`

Expected: FAIL because `canonical_relative_file` does not exist and absolute paths remain accepted by `_resolved_regular_file`.

- [ ] **Step 3: Implement one canonical path validator and route existing readers through it**

```python
def canonical_relative_file(root: Path, raw_path: object, label: str) -> tuple[str, Path]:
    if not isinstance(raw_path, str) or not raw_path:
        raise PolarizationContractError(f"{label} path must be a non-empty string")
    if "\\" in raw_path or Path(raw_path).is_absolute() or PurePosixPath(raw_path).as_posix() != raw_path:
        raise PolarizationContractError(f"{label} path must be canonical repository-relative POSIX")
    parts = PurePosixPath(raw_path).parts
    if any(part in {"", ".", ".."} for part in parts):
        raise PolarizationContractError(f"{label} path contains forbidden component")
    # Walk without following symlinks, require regular file, then return identity and resolved path.
```

Replace `_resolved_regular_file` and `reco_inventory._inside_root_file` behavior with this shared contract; update fixtures to serialize only relative paths.

- [ ] **Step 4: Write and satisfy strict config tests**

```python
def test_release_config_requires_exact_approved_identity(valid_config, repo):
    payload = json.loads(valid_config.read_text())
    payload.update(schema_version=1, analysis_version="polarization-v1", status="approved", blocked_reasons=[])
    payload["acceptance"]["acceptance_qa_sha256"] = "a" * 64
    valid_config.write_text(json.dumps(payload))
    loaded = load_analysis_config(valid_config, repo, require_approved=True)
    assert loaded.acceptance_qa_sha256 == "a" * 64

@pytest.mark.parametrize("field,value", [("schema_version", 2), ("analysis_version", "other"), ("status", "blocked"), ("blocked_reasons", ["x"])])
def test_release_config_rejects_wrong_identity(valid_config, repo, field, value):
    # mutate one exact top-level field, then require PolarizationContractError
```

Implement frozen dataclasses, exact enums, finite threshold checks, exact response/bootstrap keys, two distinct reviewers, schema authority hash, approval ID, N3 QA digest, and `require_approved` behavior. Make `load_figure4_config` consume validated config instead of independently weakening sign validation.

Run: `python -m pytest -q 08_polarization/tests/test_contracts.py 08_polarization/tests/test_analysis_config.py 08_polarization/tests/test_figure4_config.py`

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
git add 08_polarization/analysis_config.py 08_polarization/contracts.py 08_polarization/figure4_config.py config/physics/polarization_v1.json 08_polarization/tests/test_contracts.py 08_polarization/tests/test_analysis_config.py 08_polarization/tests/test_figure4_config.py
git commit -m "fix(polarization): enforce release authorities"
```

### Task 2: N3 Schema Authority and Response Parser

**Files:**
- Create: `config/schemas/acceptance_phi_response_v1.schema.json`
- Create: `08_polarization/phi_response.py`
- Create: `08_polarization/tests/test_phi_response.py`
- Modify: `08_polarization/tests/conftest.py`

**Interfaces:**
- Consumes: `AnalysisConfig`, `ResponseValidationConfig`, `canonical_relative_file`.
- Produces: `RESPONSE_FIELDS: tuple[str, ...]`, `ResponseKey`, `TrueCellKey`, `PhiResponse`.
- Produces: `load_phi_response(path: Path, *, config: AnalysisConfig, expected_release_id: str) -> PhiResponse`.
- Produces: `PhiResponse.matrix(key: ResponseKey, orientation: str) -> np.ndarray` and `PhiResponse.covariance_blocks(...) -> tuple[np.ndarray, ...]`.

- [ ] **Step 1: Write failing schema and complete-grid tests**

```python
def test_response_requires_every_joint_mass_phi_cell(response_fixture, config):
    rows = response_fixture.rows
    rows.pop()  # omitted zero is forbidden
    response_fixture.write(rows)
    with pytest.raises(PolarizationContractError, match="complete Cartesian grid"):
        load_phi_response(response_fixture.path, config=config, expected_release_id="n3-test")

def test_response_reconstructs_mass_phi_matrix(response_fixture, config):
    result = load_phi_response(response_fixture.path, config=config, expected_release_id="n3-test")
    assert result.matrix(response_fixture.key, "parallel").shape == (24, 24)
```

- [ ] **Step 2: Run response tests and verify failure**

Run: `python -m pytest -q 08_polarization/tests/test_phi_response.py`

Expected: FAIL because schema authority and parser do not exist.

- [ ] **Step 3: Add exact schema authority and minimal strict parser**

Schema JSON must encode exact ordered columns from spec, allowed masks/orientations, `[0,pi)` coverage, normalization equations, approval ID, and matrix rules. Parser must reject duplicate rows, noncanonical ordering, inconsistent generated values, missing orientations, unequal true/reco axes, incomplete cells, wrong hashes/releases/config, and invalid masks.

```python
@dataclass(frozen=True)
class PhiResponse:
    keys: tuple[ResponseKey, ...]
    matrices: Mapping[tuple[ResponseKey, str], np.ndarray]
    covariance_by_true_cell: Mapping[tuple[ResponseKey, str, int], np.ndarray]
    validity: Mapping[tuple[ResponseKey, str, int], str]
    source_sha256: str
```

- [ ] **Step 4: Add weighted covariance and rejection tests, then pass them**

```python
def test_weighted_covariance_matches_equations(response_fixture, config):
    result = load_phi_response(response_fixture.path, config=config, expected_release_id="n3-test")
    block = result.covariance_blocks(response_fixture.key, "parallel")[0]
    np.testing.assert_allclose(block, response_fixture.expected_covariance, rtol=1e-12, atol=1e-14)

@pytest.mark.parametrize("mutation", ["negative_weight", "sum_probability_gt_one", "wrong_uncertainty", "negative_eigenvalue", "mixed_mask"])
def test_response_rejects_nonphysical_covariance(response_fixture, config, mutation):
    response_fixture.mutate(mutation)
    with pytest.raises(PolarizationContractError):
        load_phi_response(response_fixture.path, config=config, expected_release_id="n3-test")
```

Run: `python -m pytest -q 08_polarization/tests/test_phi_response.py`

Expected: PASS, including nonuniform-weight fixture and explicit inefficiency.

- [ ] **Step 5: Commit Task 2**

```bash
git add config/schemas/acceptance_phi_response_v1.schema.json 08_polarization/phi_response.py 08_polarization/tests/test_phi_response.py 08_polarization/tests/conftest.py
git commit -m "feat(polarization): validate joint N3 response"
```

### Task 3: Strengthen Immutable N3 Handoff

**Files:**
- Modify: `08_polarization/acceptance_handoff.py`
- Modify: `08_polarization/tests/test_acceptance_handoff.py`
- Modify: `08_polarization/tests/test_release.py`

**Interfaces:**
- Consumes: `load_phi_response`, `AnalysisConfig`, and exact schema authority.
- Produces: extended `AcceptanceHandoff` with `schema_path`, `schema_sha256`, `approval_id`, and parsed `response`.
- Changes: `validate_acceptance_handoff(release_dir, repository_root, *, config, expected_gate0_sha256) -> AcceptanceHandoff`.

- [ ] **Step 1: Write failing trust-anchor tests**

```python
def test_handoff_requires_config_pinned_qa_digest(valid_handoff, approved_config, repo):
    approved_config = dataclasses.replace(approved_config, acceptance_qa_sha256="f" * 64)
    with pytest.raises(PolarizationContractError, match="QA SHA-256"):
        validate_acceptance_handoff(valid_handoff, repo, config=approved_config)

def test_handoff_rejects_wholesale_self_consistent_replacement(valid_handoff, approved_config, repo):
    rewrite_triplet_and_internal_hashes(valid_handoff)
    with pytest.raises(PolarizationContractError, match="QA SHA-256"):
        validate_acceptance_handoff(valid_handoff, repo, config=approved_config)
```

- [ ] **Step 2: Run N3 tests and verify failure**

Run: `python -m pytest -q 08_polarization/tests/test_acceptance_handoff.py 08_polarization/tests/test_release.py`

Expected: FAIL because config does not anchor QA bytes and response content is not parsed.

- [ ] **Step 3: Implement transitive trust validation**

Validate exact directory shape, config release/path/QA digest, QA producer commit, Gate 0/N2 hashes, both CSV hashes, schema path/hash/approval, matrix/count/covariance/closure checks, and parsed response. Remove acceptance of literal schema-approval claims without schema bytes.

- [ ] **Step 4: Run focused and regression tests**

Run: `python -m pytest -q 08_polarization/tests/test_acceptance_handoff.py 08_polarization/tests/test_phi_response.py 08_polarization/tests/test_release.py`

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
git add 08_polarization/acceptance_handoff.py 08_polarization/tests/test_acceptance_handoff.py 08_polarization/tests/test_release.py
git commit -m "fix(polarization): anchor immutable N3 bytes"
```

### Task 4: N2 Projection and Shared-Event Bootstrap Counts

**Files:**
- Create: `08_polarization/azimuth_counts.py`
- Create: `08_polarization/tests/test_azimuth_counts.py`
- Modify: `08_polarization/root_events.py`
- Modify: `08_polarization/tests/test_root_events.py`
- Modify: `08_polarization/tests/test_root_events_integration.py`

**Interfaces:**
- Changes: `EventSample` gains `file_sha256: np.ndarray`, `tree_entry: np.ndarray`.
- Produces: `event_bootstrap_weight(file_sha256: str, tree: str, entry: int, replica_id: int, *, algorithm: str, seed: int) -> int`.
- Produces: `AzimuthCountTable`, including `sum_for(observable: str, replica_id: int) -> int`, and `build_azimuth_counts(sample: EventSample, *, config: AnalysisConfig, state_map, exposures, compton, mass_edges: Mapping[str, np.ndarray]) -> AzimuthCountTable`.
- Produces: `write_azimuth_counts(table: AzimuthCountTable, path: Path) -> str`.

- [ ] **Step 1: Write failing stable-event identity tests**

```python
def test_root_reader_preserves_file_hash_and_entry(root_fixture):
    sample = read_reco_root([root_fixture], tree_name="reco", vectors="kinematic_fit")
    assert sample.tree_entry.tolist() == [0, 2]
    assert set(sample.file_sha256) == {sha256_file(root_fixture)}
```

- [ ] **Step 2: Implement identity capture and verify integration boundary**

Track current TChain file SHA and local tree entry before selection; preserve original entry indices when `fit_converged != 1` is skipped.

Run: `python -m pytest -q 08_polarization/tests/test_root_events.py`

Expected: PASS. Run PyROOT integration later under `make test`.

- [ ] **Step 3: Write failing bootstrap/count tests**

```python
def test_bootstrap_multiplier_is_shared_across_observables(event_sample, authorities):
    table = build_azimuth_counts(event_sample, **authorities)
    totals = [table.sum_for(name, replica_id=7) for name in ("p_pi0", "p_eta", "eta_pi0")]
    assert len(set(totals)) == 1

def test_counts_publish_complete_nominal_and_replica_grids(event_sample, authorities):
    table = build_azimuth_counts(event_sample, **authorities)
    assert table.replica_ids == tuple(range(authorities["config"].bootstrap.replicas + 1))
    assert table.has_every_reco_cell()
```

- [ ] **Step 4: Implement deterministic Poisson inverse-CDF projection**

Use SHA-256 bytes as a big-endian integer mapped to open interval `(0,1)`, then exact cumulative Poisson(1) recurrence. Compute three observables once per event; apply same multiplier before histogramming. Require state-map, flux, Compton, Gate 0, N2, config, and input hashes on every serialized row. Sort by full schema key and reject N4-like provenance.

Run: `python -m pytest -q 08_polarization/tests/test_azimuth_counts.py 08_polarization/tests/test_root_events.py`

Expected: PASS and nonzero measured covariance between correlated synthetic observables.

- [ ] **Step 5: Commit Task 4**

```bash
git add 08_polarization/azimuth_counts.py 08_polarization/root_events.py 08_polarization/tests/test_azimuth_counts.py 08_polarization/tests/test_root_events.py 08_polarization/tests/test_root_events_integration.py
git commit -m "feat(polarization): build replayable S4 counts"
```

### Task 5: Joint Forward-Folded Sigma Fit

**Files:**
- Modify: `08_polarization/sigma_fit.py`
- Modify: `08_polarization/tests/test_sigma_fit.py`
- Modify: `08_polarization/tests/test_closure.py`

**Interfaces:**
- Keeps: `fit_sigma_binned(...) -> SigmaFitResult` as diagnostic-only API.
- Produces: `JointSigmaFitResult` with ordered `sigma`, `log_yield`, Hessian covariance, expected counts, residuals, deviance, ndof, convergence, and rank.
- Produces: `fit_sigma_forward_folded(counts: AzimuthCountTable, response: PhiResponse, *, config: AnalysisConfig, replica_id: int = 0) -> JointSigmaFitResult`.
- Produces: `bootstrap_sigma_covariance(results: Sequence[JointSigmaFitResult], bin_keys: Sequence[str]) -> np.ndarray`.

- [ ] **Step 1: Write failing Asimov mass-and-phi migration test**

```python
def test_joint_fit_recovers_sigma_with_mass_and_phi_migration(asimov_problem):
    result = fit_sigma_forward_folded(**asimov_problem)
    np.testing.assert_allclose(result.sigma, [-0.35, 0.20], atol=2e-4)
    assert abs(result.hessian_covariance[0, 1]) > 0.0
```

- [ ] **Step 2: Run fit test and verify failure**

Run: `python -m pytest -q 08_polarization/tests/test_sigma_fit.py -k forward_folded`

Expected: FAIL because joint fitter does not exist.

- [ ] **Step 3: Implement joint likelihood and analytic bin average**

```python
def azimuth_bin_average(low: np.ndarray, high: np.ndarray) -> np.ndarray:
    return (np.sin(2.0 * high) - np.sin(2.0 * low)) / (2.0 * (high - low))

def expected_counts(parameters, response, exposures, polarizations, signs, widths, averages):
    sigma, log_yield = split_parameters(parameters)
    truth = np.exp(log_yield)[:, None] * widths[None, :] / np.pi
    truth *= 1.0 + signs[:, None, None] * polarizations[:, None, None] * sigma[None, :, None] * averages[None, None, :]
    return exposures[:, None] * forward_fold(response, truth)
```

Use L-BFGS-B, exact bounds, deterministic initialization, Poisson deviance, Fisher rank, boundary checks, finite expectations, residual QA, and complete-response validation.

- [ ] **Step 4: Add bootstrap covariance and failure tests**

Cover orientation sign inversion, missing orientation, rank loss, boundary pathology, convergence failure, incomplete response, off-diagonal mass covariance, deterministic repeated fit, and bootstrap PSD/rank/failure fraction.

Run: `python -m pytest -q 08_polarization/tests/test_sigma_fit.py 08_polarization/tests/test_closure.py`

Expected: PASS while legacy scalar tests remain unchanged.

- [ ] **Step 5: Commit Task 5**

```bash
git add 08_polarization/sigma_fit.py 08_polarization/tests/test_sigma_fit.py 08_polarization/tests/test_closure.py
git commit -m "feat(polarization): forward-fold joint Sigma"
```

### Task 6: Response-Uncertainty Propagation

**Files:**
- Create: `08_polarization/response_uncertainty.py`
- Create: `08_polarization/tests/test_response_uncertainty.py`
- Modify: `08_polarization/sigma_fit.py`

**Interfaces:**
- Consumes: `PhiResponse`, `JointSigmaFitResult`, `fit_sigma_forward_folded`, response-validation tolerances.
- Produces: `ResponsePropagationResult(covariance, retained_modes, refits, valid)`.
- Produces: `propagate_response_covariance(counts, response, *, config) -> ResponsePropagationResult`.

- [ ] **Step 1: Write failing eigenmode propagation test**

```python
def test_eigenmode_propagation_matches_linear_reference(linear_response_problem):
    result = propagate_response_covariance(**linear_response_problem)
    expected = linear_response_problem["jacobian"] @ linear_response_problem["covariance"] @ linear_response_problem["jacobian"].T
    np.testing.assert_allclose(result.covariance, expected, rtol=2e-4, atol=1e-10)
```

- [ ] **Step 2: Run test and verify failure**

Run: `python -m pytest -q 08_polarization/tests/test_response_uncertainty.py`

Expected: FAIL because propagation module does not exist.

- [ ] **Step 3: Implement deterministic covariance eigenmodes**

Sort eigenpairs descending; reject material negative eigenvalues; fix eigenvector sign using largest-magnitude component positive; skip only eigenvalues below config tolerance. Perturb response within physical bounds using central differences where possible and one-sided differences otherwise. Refit full Sigma vector per retained mode and accumulate outer products.

- [ ] **Step 4: Add determinism, boundary, and shared-MC rejection tests**

```python
def test_propagation_repeats_byte_identically(problem):
    first = propagate_response_covariance(**problem)
    second = propagate_response_covariance(**problem)
    np.testing.assert_array_equal(first.covariance, second.covariance)

def test_v1_rejects_cross_block_shared_mc_claim(problem):
    problem["response"].qa["shared_mc_across_blocks"] = True
    with pytest.raises(PolarizationContractError):
        propagate_response_covariance(**problem)
```

Run: `python -m pytest -q 08_polarization/tests/test_response_uncertainty.py 08_polarization/tests/test_sigma_fit.py`

Expected: PASS.

- [ ] **Step 5: Commit Task 6**

```bash
git add 08_polarization/response_uncertainty.py 08_polarization/tests/test_response_uncertainty.py 08_polarization/sigma_fit.py
git commit -m "feat(polarization): propagate N3 statistics"
```

### Task 7: Atomic S4 Evidence CLI

**Files:**
- Create: `08_polarization/fit_sigma.py`
- Create: `08_polarization/fit_evidence.py`
- Create: `08_polarization/tests/test_fit_sigma_cli.py`
- Create: `08_polarization/tests/test_fit_evidence.py`
- Modify: `08_polarization/inventory_builder.py`
- Modify: `Makefile`

**Interfaces:**
- Produces: `FIT_EVIDENCE_FILENAMES`, `FitEvidence`, `validate_fit_evidence(directory: Path, root: Path, *, config: AnalysisConfig) -> FitEvidence`.
- Produces CLI described in spec, returning `0` valid, `1` runtime/QA failure, `2` usage error.
- Consumes all Task 1-6 APIs.

- [ ] **Step 1: Write failing exact-triplet and no-overwrite tests**

```python
def test_fit_cli_publishes_exact_atomic_triplet(valid_cli_inputs, repo):
    assert fit_main(valid_cli_inputs.argv) == 0
    output = repo / "results/physics/polarization_fits/fit-test-v1"
    assert {p.name for p in output.iterdir()} == FIT_EVIDENCE_FILENAMES

def test_fit_cli_never_overwrites_existing_release(valid_cli_inputs):
    assert fit_main(valid_cli_inputs.argv) == 0
    assert fit_main(valid_cli_inputs.argv) == 1
```

- [ ] **Step 2: Run CLI tests and verify failure**

Run: `python -m pytest -q 08_polarization/tests/test_fit_sigma_cli.py 08_polarization/tests/test_fit_evidence.py`

Expected: FAIL because CLI/evidence modules do not exist.

- [ ] **Step 3: Implement evidence serialization and independent reader**

Write ordered counts CSV, ordered fit CSV, then QA JSON into sibling staging directory. QA records every hash, optimizer setting, ordered bin key, nuisance, expected count, deviance, Hessian diagnostic, bootstrap statistical covariance, response covariance, retained modes, and QA decision. Validate staged bytes with independent reader before atomic rename.

- [ ] **Step 4: Add tamper, partial-output, legacy-path, and N4 rejection tests**

Mutate each CSV/QA field independently; add extra/missing files; simulate raised exceptions before and after staged validation; feed an N4 provenance record. Require failure, no destination, and no orphan staging directory.

Run: `python -m pytest -q 08_polarization/tests/test_fit_sigma_cli.py 08_polarization/tests/test_fit_evidence.py 08_polarization/tests/test_inventory_builder.py`

Expected: PASS.

- [ ] **Step 5: Commit Task 7**

```bash
git add 08_polarization/fit_sigma.py 08_polarization/fit_evidence.py 08_polarization/tests/test_fit_sigma_cli.py 08_polarization/tests/test_fit_evidence.py 08_polarization/inventory_builder.py 08_polarization/tests/test_inventory_builder.py Makefile
git commit -m "feat(polarization): publish immutable S4 evidence"
```

### Task 8: S6 Replay and Release Binding

**Files:**
- Modify: `08_polarization/release.py`
- Modify: `08_polarization/validate_sigma_release.py`
- Modify: `08_polarization/tests/test_release.py`
- Create: `08_polarization/tests/test_release_replay.py`

**Interfaces:**
- Consumes: `validate_fit_evidence`, response parser, joint fitter, bootstrap covariance, response propagation, strict config.
- Changes: `validate_sigma_release(..., replay_fit: bool = True) -> SigmaRelease` always requires approved config and pinned S4 evidence.
- Produces: replay comparison for Sigma, nuisances, expected counts, deviance, Hessian diagnostic, statistical covariance, and response covariance.

- [ ] **Step 1: Write failing replay/tamper tests**

```python
@pytest.mark.parametrize("target", ["counts", "response", "fit", "expected", "nuisance", "deviance", "stat_covariance", "response_covariance"])
def test_s6_replay_rejects_tampering(valid_release, target):
    valid_release.tamper(target)
    with pytest.raises(PolarizationContractError):
        validate_sigma_release(valid_release.path, valid_release.repo)
```

- [ ] **Step 2: Run replay tests and verify failure**

Run: `python -m pytest -q 08_polarization/tests/test_release_replay.py`

Expected: FAIL because current S6 trusts recorded claims and does not replay S4.

- [ ] **Step 3: Implement full replay gate**

Validate S6 exact triplet and hashes, load pinned S4 exact triplet, rerun response/count parsing, nominal and bootstrap fits, response propagation, and compare ordered arrays with approved absolute/relative tolerances. Require S6 statistical covariance equal replayed bootstrap covariance; require named `acceptance_response_statistics` systematic covariance equal replayed response covariance; recompute total covariance.

- [ ] **Step 4: Run release and end-to-end regressions**

Run: `python -m pytest -q 08_polarization/tests/test_release.py 08_polarization/tests/test_release_replay.py 08_polarization/tests/test_figure4_end_to_end.py`

Expected: PASS with synthetic temporary releases; blocked repository config still rejects production invocation.

- [ ] **Step 5: Commit Task 8**

```bash
git add 08_polarization/release.py 08_polarization/validate_sigma_release.py 08_polarization/tests/test_release.py 08_polarization/tests/test_release_replay.py
git commit -m "fix(polarization): replay S4 before S6 release"
```

### Task 9: Shared Documentation, Graph, Provenance, and Final Gates

**Files:**
- Modify: `docs/collaboration/two-person-physics-roadmap.md`
- Modify: `docs/physics/polarization.md`
- Modify: `docs/physics/normalization.md`
- Modify: `ARTIFACTS.json`
- Modify: portable files under `graphify-out/` produced by `make graph-update`
- Modify: `00_common/tests/test_repository_contract.py`

**Interfaces:**
- Consumes: all implemented CLI paths, schema identities, artifact directories, rejection rules, and release gates.
- Produces: public two-owner interface and regenerated provenance/knowledge graph.

- [ ] **Step 1: Write failing repository-contract tests**

```python
def test_roadmap_names_exact_s4_evidence_triplet(repo_root):
    text = (repo_root / "docs/collaboration/two-person-physics-roadmap.md").read_text()
    assert "results/physics/polarization_fits/<fit_release_id>/azimuth_counts_v1.csv" in text
    assert "results/physics/polarization_fits/<fit_release_id>/sigma_fit_v1.csv" in text
    assert "results/physics/polarization_fits/<fit_release_id>/sigma_fit_qa.json" in text

def test_docs_forbid_n4_as_s4_input(repo_root):
    assert documented_n4_to_s4_edges(repo_root) == []
```

- [ ] **Step 2: Run contract tests and verify failure**

Run: `python -m pytest -q 00_common/tests/test_repository_contract.py`

Expected: FAIL until roadmap/public docs name new schema and triplet exactly.

- [ ] **Step 3: Update public contracts and artifact policy**

Document response normalization/covariance, period pooling, bootstrap, S4 CLI, exact triplets, portable paths, N3 digest anchor, S6 replay, ownership, blocked production status, and N4 rejection. Register schema authority and S4 evidence policy without adding generated physics artifacts.

- [ ] **Step 4: Refresh graph and provenance**

Run: `make graph-update`

Expected: portable Graphify snapshot refreshed; semantic extraction succeeds through configured Gemini or host-agent path.

Run: `make artifact-inventory`

Expected: `ARTIFACTS.json` records exact tracked artifacts and source commit; inspect diff for local paths, caches, raw data, or unexpected binaries.

- [ ] **Step 5: Run complete verification gates**

Run: `git diff --check`

Run: `make verify`

Run: `make test`

Run: `rg -n '/Users/|/home/|\\\\' docs config ARTIFACTS.json graphify-out 08_polarization`

Expected: all tests pass with PyROOT; path scan has no machine-specific serialized paths; repository config remains intentionally blocked; worktree contains only intended changes.

- [ ] **Step 6: Commit Task 9**

```bash
git add docs/collaboration/two-person-physics-roadmap.md docs/physics/polarization.md docs/physics/normalization.md ARTIFACTS.json graphify-out 00_common/tests/test_repository_contract.py
git commit -m "docs(polarization): publish replay contract"
```

- [ ] **Step 7: Run two-owner review before push or merge**

Review full range from `97dfc7eae396728d8c9c840928463e25932845f6` through final HEAD against both repository standards and approved spec. Resolve every Critical/Important/Minor finding, rerun affected tests plus `make verify` and `make test`, then update PR #9. Merge only when PR is clean/mergeable, both owner reviews report no findings, and remote checks pass.
