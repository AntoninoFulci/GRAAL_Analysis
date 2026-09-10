# Person 2 Polarization and Sigma Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build Person 2's fail-closed polarization and beam-asymmetry software, synthetic closure, and release validators without inventing missing experimental inputs or publishing a physics result before shared gates pass. Add a framework-native diagnostic reproducing only the requested four-by-three comparison structure, never published numeric or visual content.

**Architecture:** Keep all new physics code inside Person 2's exclusive `08_polarization/` area. Pure NumPy/SciPy modules validate provenance-bearing configuration, compute the periodic reaction-plane angle, fit an acceptance-aware Poisson model, exercise injected-`Sigma` closure, and validate release artifacts. Repository config records blocked external inputs explicitly; real output publication remains impossible until Gate 0, signed state mapping, authoritative Compton input, and Person 1 acceptance exist.

**Tech Stack:** Python 3.10+, NumPy, SciPy, pytest, CSV, JSON, NPZ, SHA-256

**Spec:** `docs/collaboration/two-person-physics-roadmap.md`

## Global Constraints

- Person 2 owns only `08_polarization/`, `08_polarization/tests/`, `config/physics/polarization_v1.json`, `results/physics/polarization/`, and `docs/physics/polarization.md`.
- Do not edit shared manifest, observable policy, channel registry, reconstruction schema, common binning, Make targets, or published handoff schemas without both reviewers.
- Reject missing, unhashed, unapproved, ambiguous, non-finite, extrapolated, or inconsistent scientific inputs.
- Do not treat `POL1`/`POL2` histogram names as polarization orientations.
- Do not use `results/reco/` for normalized physics.
- Keep `Sigma` bounded to `[-1, 1]`; keep `phi` in `[0, pi)` and mark degenerate planes invalid.
- No real `results/physics/polarization/` artifacts may be emitted while required upstream QA is absent or invalid.
- Comparison output may use publication-compatible bin structure, but must not ingest published points, curves, digitization, code, or styling. Mark it diagnostic and non-release.

## Approved comparison extension

- [x] Implement flux-normalized conditional likelihood with explicit H/V flux and period polarization.
- [x] Bind each approved state to an explicit flux component; never infer mapping.
- [x] Compute three pair masses and pair-sum azimuth from reconstructed four-vectors.
- [x] Build four energy rows, three pair columns, ten mass bins, and twelve azimuth bins.
- [x] Render original project-native PNG and serialize every valid/invalid fit point.
- [x] Add metadata-bearing ROOT reader and reject legacy/partial schemas.
- [x] Add provenance QA sidecar and fail closed on missing Gate 0 or authorities.

---

### Task 1: Provenance and Configuration Contracts

**Files:**
- Create: `08_polarization/contracts.py`
- Create: `08_polarization/tests/test_contracts.py`
- Create: `config/physics/polarization_v1.json`

**Interfaces:**
- Consumes: JSON paths, files named by JSON, lowercase SHA-256 digests, Gate 0 handoff path.
- Produces: `PolarizationContractError`, `sha256_file(path)`, `load_json(path)`, `validate_source(source, root)`, `validate_gate0_handoff(path, repository_root)`.

- [ ] **Step 1: Write failing tests for source provenance and Gate 0**

```python
def test_source_requires_existing_file_matching_hash_and_two_approvals(tmp_path):
    source = tmp_path / "signed-state-map.pdf"
    source.write_bytes(b"approved source")
    payload = valid_source(source)
    assert validate_source(payload, tmp_path) == source.resolve()
    payload["sha256"] = "0" * 64
    with pytest.raises(PolarizationContractError, match="SHA-256"):
        validate_source(payload, tmp_path)


def test_gate0_rejects_missing_handoff_and_invalid_qa(tmp_path):
    with pytest.raises(PolarizationContractError, match="HANDOFF"):
        validate_gate0_handoff(tmp_path / "HANDOFF.json", tmp_path)
```

- [ ] **Step 2: Run tests and verify RED**

Run: `python -m pytest -q 08_polarization/tests/test_contracts.py`

Expected: FAIL because `contracts.py` does not exist.

- [ ] **Step 3: Implement strict contract helpers**

```python
class PolarizationContractError(ValueError):
    pass


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()
```

`validate_source` must require `path`, `sha256`, `authority`, `approval_id`, and two distinct non-empty reviewers. `validate_gate0_handoff` must require QA-valid status, curated-manifest identity, declared bundle files, and matching file hashes.

- [ ] **Step 4: Add blocked repository config**

`config/physics/polarization_v1.json` must declare schema/analysis versions, sign convention, `[0, pi)` angle range, required Gate 0 and acceptance paths, and explicit `blocked` records for unsigned state mapping and missing authoritative Compton data. It must contain no guessed orientations or polarization values.

- [ ] **Step 5: Run focused tests and commit**

Run: `python -m pytest -q 08_polarization/tests/test_contracts.py`

Expected: PASS.

Commit: `feat(polarization): add fail-closed input contracts`

---

### Task 2: S1 State Mapping and S2 Compton Polarization

**Files:**
- Create: `08_polarization/state_mapping.py`
- Create: `08_polarization/compton.py`
- Create: `08_polarization/validate_state_mapping.py`
- Create: `08_polarization/validate_compton_polarization.py`
- Create: `08_polarization/tests/test_state_mapping.py`
- Create: `08_polarization/tests/test_compton.py`

**Interfaces:**
- Consumes: validated config and source records.
- Produces: `StateInterval`, `resolve_orientation(run_number, state_code, intervals)`, `PolarizationCurve`, `PolarizationCurve.evaluate(energy_mev)`.

- [ ] **Step 1: Write failing state-map tests**

```python
def test_mapping_resolves_only_unique_approved_interval():
    intervals = [StateInterval(100, 199, 2, "parallel")]
    assert resolve_orientation(150, 2, intervals) == "parallel"
    with pytest.raises(PolarizationContractError, match="unmapped"):
        resolve_orientation(200, 2, intervals)


def test_mapping_rejects_overlap_and_non_orientation_labels():
    with pytest.raises(PolarizationContractError, match="overlap"):
        validate_intervals(overlapping_intervals())
```

- [ ] **Step 2: Verify state-map RED, then implement minimal interval validation**

Run: `python -m pytest -q 08_polarization/tests/test_state_mapping.py`

Expected: FAIL because `state_mapping.py` does not exist. Implement closed integer intervals, exact labels `parallel|perpendicular`, unique `(run,state)` coverage, and no filename inference.

- [ ] **Step 3: Write failing Compton tests**

```python
def test_curve_interpolates_value_and_covariance_without_extrapolation():
    curve = PolarizationCurve([600.0, 800.0], [0.4, 0.8], [[0.01, 0.002], [0.002, 0.04]])
    value, variance = curve.evaluate(700.0)
    assert value == pytest.approx(0.6)
    assert variance == pytest.approx(0.0135)
    with pytest.raises(PolarizationContractError, match="extrapolation"):
        curve.evaluate(500.0)
```

- [ ] **Step 4: Verify Compton RED, then implement linear interpolation**

Run: `python -m pytest -q 08_polarization/tests/test_compton.py`

Expected: FAIL because `compton.py` does not exist. Interpolate with weight vector `w`; return `w @ values` and `w @ covariance @ w`; require increasing energy, physical values `[0,1]`, symmetric positive-semidefinite covariance, and no extrapolation.

- [ ] **Step 5: Implement CLI validators and verify**

Run:

```bash
python 08_polarization/validate_state_mapping.py --config config/physics/polarization_v1.json --handoff results/observable_runs/HANDOFF.json
python 08_polarization/validate_compton_polarization.py --config config/physics/polarization_v1.json
```

Expected on current repository: both exit `1` with concise missing-authority diagnostics. Fixture-backed pytest cases must exit `0` for valid synthetic contracts.

Commit: `feat(polarization): validate states and Compton inputs`

---

### Task 3: S3 Periodic Reaction-Plane Angle

**Files:**
- Create: `08_polarization/angles.py`
- Create: `08_polarization/test_phi_periodicity.py`
- Create: `08_polarization/tests/test_angles.py`

**Interfaces:**
- Consumes: beam direction, polarization reference axis, analyzed final-state momentum; each shape `(3,)`.
- Produces: `PhiResult(value: float, valid: bool, reason: str | None)` and `reaction_plane_phi(beam, reference, momentum, tolerance=1e-12)`.

- [ ] **Step 1: Write failing known-angle and degeneracy tests**

```python
@pytest.mark.parametrize("degrees", [0.0, 30.0, 90.0, 179.999])
def test_phi_matches_hand_constructed_transverse_vectors(degrees):
    angle = np.deg2rad(degrees)
    momentum = np.array([np.cos(angle), np.sin(angle), 0.3])
    result = reaction_plane_phi([0, 0, 1], [1, 0, 0], momentum)
    assert result.valid
    assert result.value == pytest.approx(angle % np.pi)


def test_phi_marks_collinear_plane_degenerate():
    result = reaction_plane_phi([0, 0, 1], [1, 0, 0], [0, 0, 3])
    assert not result.valid
    assert np.isnan(result.value)
```

- [ ] **Step 2: Verify RED**

Run: `python -m pytest -q 08_polarization/tests/test_angles.py`

Expected: FAIL because `angles.py` does not exist.

- [ ] **Step 3: Implement signed projected angle modulo pi**

Normalize beam, project reference and momentum transverse to beam, compute `atan2(beam dot (reference cross momentum), reference dot momentum) % pi`, reject non-finite/zero vectors and degenerate projections.

- [ ] **Step 4: Add executable periodicity validation**

`test_phi_periodicity.py` must test `phi(v) == phi(-v)`, continuity of `cos(2phi)` across `0/pi`, and stable sign under positive rescaling. It exits `0` only when all checks pass.

- [ ] **Step 5: Run tests and commit**

Run:

```bash
python -m pytest -q 08_polarization/tests/test_angles.py
python 08_polarization/test_phi_periodicity.py --config config/physics/polarization_v1.json
```

Commit: `feat(polarization): define periodic reaction-plane angle`

---

### Task 4: S4 Acceptance-Aware Fit and S5 Injected Closure

**Files:**
- Create: `08_polarization/sigma_fit.py`
- Create: `08_polarization/fit_sigma.py`
- Create: `08_polarization/closure_injected_sigma.py`
- Create: `08_polarization/tests/test_sigma_fit.py`
- Create: `08_polarization/tests/test_closure.py`

**Interfaces:**
- Consumes: arrays of `phi`, orientation sign (`-1|+1`), polarization `(0,1]`, acceptance `(0,1]`, exposure `>0`, and observed count `>=0`.
- Produces: `SigmaFitResult(sigma, stat_uncertainty, covariance, converged, goodness_of_fit, residuals)` and `fit_sigma_binned(...)`.

- [ ] **Step 1: Write failing likelihood-fit tests**

```python
def test_acceptance_aware_fit_recovers_exact_asimov_sigma():
    sample = asimov_sample(sigma=0.35, unequal_acceptance=True)
    result = fit_sigma_binned(**sample)
    assert result.converged
    assert result.sigma == pytest.approx(0.35, abs=2e-3)


def test_fit_rejects_missing_acceptance_and_incomplete_phi_coverage():
    with pytest.raises(PolarizationContractError, match="acceptance"):
        fit_sigma_binned(**sample_with_zero_acceptance())
```

- [ ] **Step 2: Verify RED, implement bounded Poisson likelihood**

Run: `python -m pytest -q 08_polarization/tests/test_sigma_fit.py`

Expected: FAIL because `sigma_fit.py` does not exist. Fit `mu_i = exposure_i * acceptance_i * scale_state * (1 + sign_i * P_i * Sigma * cos(2 phi_i))`; optimize `Sigma` and positive state scales; reject non-positive model means, failed convergence, and insufficient angular rank.

- [ ] **Step 3: Write failing injected-closure tests**

```python
@pytest.mark.parametrize("injected", [-0.6, -0.2, 0.0, 0.3, 0.7])
def test_asimov_closure_recovers_injected_sigma_and_sign_flip(injected):
    closure = run_injected_closure(injected, seed=17)
    assert abs(closure.bias) <= closure.bias_threshold
    assert closure.sign_check_passed
```

- [ ] **Step 4: Verify RED, implement deterministic closure and CLIs**

Run: `python -m pytest -q 08_polarization/tests/test_closure.py`

Expected: FAIL because closure API does not exist. Generate fixed-seed Poisson ensembles plus exact Asimov sample, include nonuniform acceptance, calculate bias/pull, swap state signs, and require fitted `Sigma` sign inversion.

- [ ] **Step 5: Run focused suite and commit**

Run: `python -m pytest -q 08_polarization/tests/test_sigma_fit.py 08_polarization/tests/test_closure.py`

Commit: `feat(polarization): fit Sigma with acceptance closure`

---

### Task 5: S6 Release and S7 Publication-Binning Validation

**Files:**
- Create: `08_polarization/release.py`
- Create: `08_polarization/validate_sigma_release.py`
- Create: `08_polarization/validate_publication_binning.py`
- Create: `08_polarization/tests/test_release.py`
- Create: `docs/physics/polarization.md`

**Interfaces:**
- Consumes: `sigma_v1.csv`, `sigma_covariance.npz`, `polarization_qa.json`, optional P1/P2 mapping files.
- Produces: read-only validation; never repairs or rewrites candidate results.

- [ ] **Step 1: Write failing release tests**

```python
def test_release_accepts_cross_hashed_csv_npz_and_valid_qa(tmp_path):
    release = write_valid_release(tmp_path)
    validate_sigma_release(release)


def test_release_rejects_bin_order_hash_and_covariance_mismatch(tmp_path):
    release = write_valid_release(tmp_path)
    reverse_npz_bin_keys(release)
    with pytest.raises(PolarizationContractError, match="bin_keys"):
        validate_sigma_release(release)
```

- [ ] **Step 2: Verify RED, implement strict release validator**

Run: `python -m pytest -q 08_polarization/tests/test_release.py`

Expected: FAIL because `release.py` does not exist. Require exact CSV columns, unique bin keys, finite values, physical `Sigma`, symmetric positive-semidefinite covariance, exact NPZ order, valid QA, fit/closure/sign checks, systematic sources, and matching hashes.

- [ ] **Step 3: Implement publication-binning validator**

Require every aggregate bin to reference released elementary bin keys, reject duplicates and partial covariance loss, and reject P1/P2 publication while QA lacks recorded P0 gate approval.

- [ ] **Step 4: Document conventions and current blockers**

`docs/physics/polarization.md` must document equations, orientation-sign convention, angle axes, degeneracy policy, interpolation/covariance rules, closure thresholds, CLI commands, handoff schemas, and current missing inputs. It must label Figure 7 code as theoretical reproduction, not authoritative period-by-period `P(Egamma)` input.

- [ ] **Step 5: Run full verification and refresh derived metadata**

Run:

```bash
python -m pytest -q 08_polarization/tests
make verify
make graph-update
make artifact-inventory
git diff --check
```

Review Graphify and inventory diffs. No real polarization result files are added until all scientific gates pass.

Commit: `feat(polarization): validate Sigma release contracts`
