# Ajaka Figure 4 and GRAAL-data fit: TDD implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` task by task. Steps use checkbox (`- [ ]`) syntax. Do not spawn agents unless the user explicitly requests delegation.

**Goal:** Fit a small, identifiable set of physical production couplings to our Stage 07 binned beam asymmetries using certified fast predictions, while keeping the sourced Ajaka Figure 4 reproduction test independent.

**Architecture:** Prove an exact three-term event-amplitude basis for the two sourced `Delta*(1700)` electromagnetic couplings, integrate its Hermitian interference moments once per bin, and reconstruct every parameter-trial prediction algebraically. Read only nominal UV `raw_bdt/ratio` points and aligned covariance from Stage 07. Keep direct seven-family amplitudes and the existing Figure 4 certification path as oracles; a failed factorization, numerical gate, data gate or rank gate prevents a physical fit claim.

**Tech Stack:** Python >=3.10; NumPy >=1.24; SciPy >=1.10; Matplotlib >=3.7; pytest >=7.4; `uproot>=5` through the existing optional `flux` extra (add a `fit` extra only if needed by installation UX). No new compiled dependency.

**Spec:** `theory/docs/2026-10-06-figure4-fit-and-reproduction-design.md`; sourced numerical gates remain in `theory/docs/2026-10-05-figure4-converged-production-design.md` and its TDD plan.

## Global constraints

- Work stays in `theory/` for fit code and tests. Stage 07 output is an input artifact; do not edit Stage 07 estimator code as a shortcut.
- The first candidate coordinates are the **internal** real `tree.g1_prime` (GeV^-1) and `tree.g2_prime` (GeV^-2). Source records are `-0.260 m_N^-1` and `+0.270 m_N^-2`; the loader divides by the sourced proton mass. Hold `g_eta_delta`, strong T, all masses, widths and other production inputs fixed. If event-level affine identity fails, stop basis work and report the failed source dependency before changing candidate parameters.
- No arbitrary family scale, gauge-partner separation, fit to digitized Ajaka theory strokes, invented source prior or tolerance relaxation. A parameter-domain limit requires a prefit source or numerical-validity record; a merely convenient optimizer bound is not a physics constraint.
- Preserve the exact seven-family complex sum before spin squaring. `Sigma=N/D` requires finite `D>0`. Separate publication-bin uniform photon-energy weighting from native-bin measured exposure and estimator transfer.
- No physical fit until every admitted theory point passes its direct-oracle, energy, Sobol, replica and grid checks; source and off-source basis checks pass; data covariance and Jacobian rank pass. A computationally incomplete point is masked, not silently dropped to improve fit quality.
- Current `results/production-20261006-113738/uv/beam_asymmetry/beam_asymmetry.root` is **pilot only**: uncorrected background, no run bootstrap and unresolved best-quartet selection. Final data need reviewed sideband correction, positive run bootstrap, covariance/acceptance QA and explicit limitation record.
- Before any fit (including a synthetic optimizer test), bootstrap, full theory suite or expensive integration, give user exact command, measured or labeled-unmeasured duration estimate, CPU/memory assumptions, input/output paths and success/fail signals. User runs it and returns artifacts. Focused short tests that do not invoke a fit may run locally.
- Preserve all pre-existing dirty paths. The sourced-prediction plan owns its existing Task 3G/3I and Tasks 7–10; this plan must not mark them complete by proxy.

## File map and interfaces

| File | Responsibility |
| --- | --- |
| `src/graal_theory/models/delta_em_basis.py` | Exact three-term complex amplitude basis for fixed non-EM parameters and `g1_prime/g2_prime`; no integration. |
| `src/graal_theory/quadratic_moments.py` | Hermitian numerator/denominator and state/azimuth quadratic forms; coefficient contraction and validation. |
| `src/graal_theory/native_sigma.py` | Read Stage 07 ROOT identity, ordered nominal points and covariance submatrix; pilot/final provenance gate. |
| `src/graal_theory/photon_flux.py` | Extend existing calibrated-flux loader with explicit selected-run filter, retaining its old default. |
| `src/graal_theory/figure4_basis.py` | Integrate/certify basis moments in publication and native bins, with source-equivalent phase space, weighting and typed masks. |
| `src/graal_theory/figure4_fit.py` | Whitened GLS residuals, identifiability, optimizer, diagnostics and separate source/fitted reports. |
| `src/graal_theory/cli.py` | Thin `figure4-basis-build` and `figure4-fit` dispatch, preflight, checkpoint/resume and distinct run output. |
| `tests/test_delta_em_basis.py`, `test_quadratic_moments.py`, `test_native_sigma.py`, `test_figure4_basis.py`, `test_figure4_fit.py`, `test_cli.py` | Focused RED/GREEN proofs at owning boundaries. |
| `references/full_production_validation.md`, `docs/2026-10-05-figure4-converged-production-tdd-plan.md` | Status and distinct sourced/fit gates; no premature reproduction claim. |

## Review focus

1. A copied basis with altered width/strong parameters must fail fingerprint validation; Task 1 test.
2. A valid ROOT tree with shuffled point rows must retain its own covariance-row order, while duplicate bin keys fail; Task 3 tests.
3. Ratio and likelihood from the same events, or three pair projections without bootstrap, must not be stacked as independent final observations; Task 3 and Task 7 tests.
4. A basis accurate at sourced values but inaccurate at an off-source point must fail certification; Tasks 1 and 5 tests.
5. An interrupted bin output or changed data/parameter fingerprint must not resume as a certified result; Task 7 tests.

---

## Task 1: Prove exact `g1_prime/g2_prime` event basis

**Files:** Create `src/graal_theory/models/delta_em_basis.py`; create `tests/test_delta_em_basis.py`; do not alter sourced parameter files or the physical `EtaPi0PFullModel.amplitude` method.

**Interfaces:** `delta_em_event_basis(model: EtaPi0PFullModel, sample: ThreeBodySample, polarization: NDArray) -> DeltaEMBasis`; `DeltaEMBasis.matrices` has shape `(3,N,2,2)` and read-only complex128 values; `DeltaEMBasis.coefficients(g1_prime: float, g2_prime: float) -> NDArray[float64]` returns `[1,g1-g1_source,g2-g2_source]`; `DeltaEMBasis.reconstruct(g1_prime, g2_prime) -> NDArray[complex128]`; `DeltaEMBasis.validate_model(model) -> None` rejects changes to fixed inputs. Fingerprint all fixed parameter blocks, grid identity and source anchor.

- [ ] **Step 1 RED:** Freeze a small physical event at lower and upper Ajaka energies. For both H/V, compare `reconstruct` with independent `EtaPi0PFullModel(replace(parameters, tree=replace(tree, g1_prime=a, g2_prime=b)), strong_grid=...).amplitude(...)` at source, `(a+0.04,b-0.03)` and `(a-0.06,b+0.05)` in internal units. Assert `rtol=1e-10, atol=1e-10`, dtype/shape/read-only arrays, and `validate_model` rejection of mismatched strong, width or production fingerprints. Include an event near an open recoil cut.

  ```python
  basis = delta_em_event_basis(source_model, sample, vertical)
  trial = replace(source_model.parameters, tree=replace(
      source_model.parameters.tree, g1_prime=a, g2_prime=b))
  direct = EtaPi0PFullModel(trial, source_model.strong_grid).amplitude(sample, vertical)
  np.testing.assert_allclose(basis.reconstruct(a, b), direct, rtol=1e-10, atol=1e-10)
  ```
- [ ] **Step 2 RED command:** `cd theory && python -m pytest tests/test_delta_em_basis.py -q`. Expected: import of absent `delta_em_basis` fails.
- [ ] **Step 3 GREEN:** Evaluate full seven-family amplitude at source and at one-unit internal perturbation of each EM coupling, using the same sample/polarization and unchanged width/T inputs. Store `(M_source, M_g1-M_source, M_g2-M_source)` as read-only basis. Validate finite inputs and fixed-input fingerprint when attaching the basis to an integration run; reject parameter variation outside these two coordinates. Do not cache mutable event arrays.

  ```python
  coefficients = np.array([1.0, g1_prime-anchor_g1, g2_prime-anchor_g2])
  amplitude = np.einsum("a,anij->nij", coefficients, matrices)
  ```
- [ ] **Step 4 GREEN command:** Re-run focused file; expected all physical event/oracle tests pass. If an off-source matrix fails, stop and record source-level nonlinear dependency; do not increase tolerance or proceed to Task 2.
- [ ] **Step 5 review/commit:** Inspect source-unit conversion and changed paths; commit only Task 1 files after review, with message `feat(theory): prove Delta EM amplitude basis`.

## Task 2: Contract exact Hermitian moment matrices

**Files:** Create `src/graal_theory/quadratic_moments.py`, `tests/test_quadratic_moments.py`.

**Interfaces:** `quadratic_moments(vertical_basis, horizontal_basis, phi, weights) -> QuadraticMoments`; matrices `numerator` and `denominator` are `(3,3)` complex Hermitian. `QuadraticMoments.evaluate(coefficients) -> (numerator: float, denominator: float, sigma: float)` validates finite coefficients and positive denominator. `azimuth_state_moments(vertical_basis, horizontal_basis, phi, weights, polarization_vertical, polarization_horizontal) -> NDArray[complex128]` returns `(2,12,3,3)` finite-phi V/H expected-count matrices before flux multiplication.

- [ ] **Step 1 RED:** Use complex toy spin matrices with nonzero H/V interference and nonuniform nonnegative weights. For three coefficient vectors, compare contracted `N,D,Sigma` to `project_azimuth_averaged_moments(phi, Mv, Mh, weights)`. Assert Hermitian conjugacy and `D>0`; negative weights, nonfinite coefficients, mismatched shapes and an all-zero denominator raise. For finite-phi state matrices, sum twelve azimuth bins and compare independent analytic `cos(2phi)` integration plus a direct 48-bin angular toy.

  ```python
  q = quadratic_moments(v_basis, h_basis, phi, weights)
  v = np.einsum("a,anij->nij", c, v_basis)
  h = np.einsum("a,anij->nij", c, h_basis)
  expected_n, expected_d = project_azimuth_averaged_moments(phi, v, h, weights)
  assert q.evaluate(c)[:2] == pytest.approx((expected_n, expected_d))
  ```
- [ ] **Step 2 RED command:** `cd theory && python -m pytest tests/test_quadratic_moments.py -q`. Expected: missing module.
- [ ] **Step 3 GREEN:** Form spin-trace Gram entries for V, H and their Hermitian cross term, contract with exact global-azimuth factors, then sum with original phase-space weights. Build 12 finite-phi state matrices using analytic azimuth-bin integrals; keep numerical summation order deterministic. Store matrices read-only after finite/Hermitian checks.

  ```python
  gram_v = np.einsum("anij,bnij,n->ab", v_basis.conj(), v_basis, weights) / 2
  gram_h = np.einsum("anij,bnij,n->ab", h_basis.conj(), h_basis, weights) / 2
  denominator = gram_v + gram_h
  # Form numerator with the same per-event cos(2*phi) and H/V cross terms
  # as project_azimuth_averaged_moments, before summing over events.
  ```
- [ ] **Step 4 GREEN command:** Focused tests pass; run existing `tests/test_figure4_integration.py` focused toy tests only. No real full-bin integration.
- [ ] **Step 5 review/commit:** Commit only Task 2 files with `feat(theory): add coherent quadratic moments`.

## Task 3: Read ordered Stage 07 points and covariance

**Files:** Create `src/graal_theory/native_sigma.py`, `tests/test_native_sigma.py`; modify `pyproject.toml` only if a dedicated optional `fit = ["uproot>=5"]` improves installation.

**Interfaces:** `BinKey = tuple[str,int,int]`; `load_native_sigma_root(path: Path, *, require_final: bool=False) -> NativeSigmaData`. Record ordered `keys: tuple[BinKey,...]`, energy/mass edges, measured sigma, original tree indices, aligned `C_total`, optional `C_bootstrap`, provenance and source SHA-256. Always select `sample=raw_bdt`, `estimator=ratio`, `profile=uv`; expose likelihood only through a separate diagnostic read, not concatenation.

- [ ] **Step 1 RED:** Mock a ROOT adapter with noncontiguous, shuffled nominal rows and a known `(6,6)` covariance. Assert selected vector keeps tree order and covariance equals `C[np.ix_(selected_indices,selected_indices)]`. Reject malformed/duplicate `id_mapping`, duplicate nominal bin key, bad profile/edges, covariance dimension/order mismatch, nonfinite sigma, nonsymmetric or nonpositive covariance. `require_final=True` rejects pilot provenance `background=uncorrected` or absent `covariance/bootstrap_run`; `False` labels it `pilot`.

  ```python
  data = load_native_sigma_root(root_path)
  np.testing.assert_array_equal(data.tree_indices, [4, 1, 5])
  np.testing.assert_allclose(data.covariance, full_cov[np.ix_([4, 1, 5], [4, 1, 5])])
  ```
- [ ] **Step 2 RED command:** `cd theory && python -m pytest tests/test_native_sigma.py -q`. Expected: missing loader.
- [ ] **Step 3 GREEN:** Use `uproot` for `sigma_points`, `id_mapping`, `provenance`, `binning/energy_edges`, `covariance/total`, optional `covariance/bootstrap_run`. Parse mappings strictly, validate each selected record, slice covariance once by original indices, retain point order and exact bin edges. Use Cholesky only after symmetry/positive-definite preflight; never add a hidden ridge. Leave Stage 07 files untouched.

  ```python
  indices = np.flatnonzero((sample_ids == raw_bdt_id) & (estimator_ids == ratio_id))
  selected_covariance = full_covariance[np.ix_(indices, indices)]
  np.linalg.cholesky(selected_covariance)
  ```
- [ ] **Step 4 GREEN command:** Focused synthetic tests pass. Short read-only smoke on current UV ROOT confirms 109 `raw_bdt/ratio` rows and `pilot` status; do not claim a final covariance.
- [ ] **Step 5 review/commit:** Commit only Task 3 files with `feat(theory): read native Sigma covariance`.

## Task 4: Match Stage 07 run set and energy exposure

**Files:** Modify `src/graal_theory/photon_flux.py`, `tests/test_photon_flux.py`; create native-flux tests in `tests/test_figure4_basis.py`.

**Interfaces:** Extend `load_calibrated_flux(root_path, manifest_path, energy_range_gev, *, selected_run_numbers: frozenset[int] | None=None) -> FluxSpectrum`; omitted filter preserves existing behavior. `selected_uv_runs(reco_root: Path) -> frozenset[int]` reads `RunNumber` from nominal `reco_eta_pi0_bdt` tree. `native_flux_spectrum(flux_root: Path, manifest: Path, reco_root: Path, energy_range_gev: tuple[float,float]) -> FluxSpectrum` uses both; its fingerprint includes reco ROOT, flux ROOT and manifest identities.

- [ ] **Step 1 RED:** Synthetic flux ROOT/manifest has two complete runs with distinct photon spectra; nominal reco ROOT contains only one run. Assert selected spectrum contains only that run and changes predicted weighted moment; preserve old unfiltered test. Reject an empty selected set, missing `RunNumber`, duplicate ROOT cycles and a selected run with no complete POL1/POL2/BREM triplet. Assert energy bounds follow Stage 07's four UV intervals.

  ```python
  spectrum = load_calibrated_flux(root, manifest, (1.2, 1.3),
                                  selected_run_numbers=frozenset({run_a}))
  assert spectrum.selected_runs == 1
  assert spectrum.complete_runs == 1
  ```
- [ ] **Step 2 RED command:** `cd theory && python -m pytest tests/test_photon_flux.py tests/test_figure4_basis.py -q`. Expected: unsupported selected-run argument/helper.
- [ ] **Step 3 GREEN:** Filter manifest P/UV run IDs by selected reconstructed run IDs *before* reading exposures. Preserve run-atomic completeness, state-specific flux/polarization and old no-filter API. Read only `RunNumber` from reconstructed ROOT; do not load 115 MB of event vectors.

  ```python
  selected = selected_uv_runs(reco_root)
  spectrum = load_calibrated_flux(flux_root, manifest, energy_range_gev,
                                  selected_run_numbers=selected)
  ```
- [ ] **Step 4 GREEN command:** Focused tests pass. A short local smoke compares selected-run count against Stage 07 extraction log and reports mismatch as preflight failure.
- [ ] **Step 5 review/commit:** Commit only Task 4 files with `feat(theory): match native selected runs`.

## Task 5: Integrate and certify basis moments in each bin

**Files:** Create `src/graal_theory/figure4_basis.py`, `tests/test_figure4_basis.py`; reuse `figure4_integration.py`, `phase_space.py`, `beam_asymmetry.py`, and Task 2 moments. Change those owners only to expose a concrete reusable helper if exact duplication would result.

**Interfaces:** `integrate_basis_bin(model, pair, energy_range_gev, mass_range_gev, *, energy_rule, sobol, flux_spectrum=None) -> BasisBinMoment`; `certify_basis_bin(model, pair, energy_range_gev, mass_range_gev, *, energy_rule, energy_order, sobol_power, replica_seeds, flux_spectrum=None) -> BasisBinCertificate`; `BasisBinMoment.evaluate(coefficients) -> BinPrediction` with `numerator`, `denominator`, `intrinsic_sigma` and, for native mode, `ratio_sigma`; `BasisBinCertificate.predict(coefficients) -> BinPrediction` rejects uncertified vectors. `energy_rule="uniform"` is Ajaka primary; `"native_flux"` requires selected-run spectrum and produces intrinsic plus 12-bin expected ratio forms. Certificate stores source/off-source `N,D,Sigma` differences for `n/2n`, `p/p+1`, eight fixed scrambled replicas and direct/grid; status/reason and matrix-level numerical covariance stay available.

- [ ] **Step 1 RED:** Constant-amplitude toys reproduce independent restricted three-body phase-space volume for all three pair choices and energy-onset edge bins. Complex basis toy reproduces direct full-model `Sigma` at source and two off-source points for H/V. Native toy with unequal V/H exposure and polarization compares `azimuth_state_moments` plus the existing `fit_binned_asymmetry` transfer with an explicit-azimuth integration. Reject mixed uniform/native weights, unsupported `M(eta p)>1.80 GeV`, nonpositive denominator and a model/grid fingerprint mismatch.
- [ ] **Step 2 RED command:** `cd theory && python -m pytest tests/test_figure4_basis.py -q`. Expected: missing integration/certificate API.
- [ ] **Step 3 GREEN:** Reuse exact energy-onset split and `sample_three_body_mass_window` from the existing Figure 4 path. On common events compute Task 1 V/H bases, Task 2 Hermitian moments, and exact state/phi forms for native ratio transfer. Apply either uniform GL weights or selected-run flux weights, never both. Save raw matrix sums before contracting any parameter vector; propagate source-use fraction and masks.

  ```python
  source = bin_moment.evaluate(source_coefficients)
  trial = bin_moment.evaluate(off_source_coefficients)
  assert source.denominator > 0 and trial.denominator > 0
  ```
- [ ] **Step 4 GREEN:** Apply existing Figure 4 checks to contracted sourced and off-source moments; also monitor each matrix entry/replica so cancellation cannot make an unstable basis appear converged. For native points require the propagated numerical `Sigma` bound to be at most `min(0.01, 0.2*stat_error)` for that point; a failing candidate receives `masked_nonconverged`, not a finite fit prediction. Refine the measured-flux energy grouping until doubling its resolution changes each non-negligible H/V normalization by `<1%` and `Sigma` by `<=0.005`. Use measured adaptive per-bin powers from sourced Task 3G/3I; if they are absent, keep this task at synthetic/isolated-pilot proof and do not launch all bins.

  ```python
  numerical_bound = max(replica_se, abs(sobol_fine.sigma - base.sigma),
                        abs(energy_fine.sigma - base.sigma), grid_direct_delta)
  if numerical_bound > min(0.01, 0.2 * data_stat_error):
      return replace(certificate, status="masked_nonconverged",
                     reason=("fit_precision",))
  ```
- [ ] **Step 5 focused proof:** Run Task 1/2/5 focused tests. Run a bounded source and one off-source **single-event** oracle; provide user command and estimate before any real full-bin campaign. If an isolated direct/bin mismatch remains, stop before Task 6.
- [ ] **Step 6 review/commit:** Commit only Task 5 files with `feat(theory): certify quadratic bin moments`.

## Task 6: Fit identifiable couplings with covariance-aware residuals

**Files:** Create `src/graal_theory/figure4_fit.py`, `tests/test_figure4_fit.py`.

**Interfaces:** `build_gls(data: NativeSigmaData, predictions: Mapping[BinKey,BasisBinCertificate]) -> GLSObjective`; `GLSObjective.residuals(theta: NDArray[float64]) -> NDArray[float64]`; `fit_delta_em(objective, initial_theta) -> FitResult`. `BinKey` is defined in Task 3. Keys match exactly and masks never enter a physical objective. Store source/fitted coefficients in internal and source units, whitened residuals, chi-square, degrees of freedom, Jacobian singular values, parameter covariance if identifiable, boundary/invalid-evaluation status, data/model fingerprints.

- [ ] **Step 1 RED:** Inject a two-parameter quadratic toy over at least six bins with known positive-definite correlated covariance. Recover source-shifted injected couplings within toy precision using `scipy.optimize.least_squares`. Assert exact `r=L^{-1}(d-mu)` with `C=LL^T`. Tests reject duplicate or missing theory keys, masked prediction, nonpositive covariance, theory error above data precision, denominator zero and a rank-one Jacobian; a rank failure returns `not_identifiable` without a misleading parameter covariance.

  ```python
  expected = np.linalg.solve(np.linalg.cholesky(covariance), data_sigma - predicted_sigma)
  np.testing.assert_allclose(objective.residuals(theta), expected)
  ```
- [ ] **Step 2 RED command:** `cd theory && python -m pytest tests/test_figure4_fit.py -q`. Expected: absent GLS/fit module.
- [ ] **Step 3 GREEN:** Align predictions by explicit `(pair,energy_bin,mass_bin)` key, Cholesky-whiten once, call certificate's finite fast evaluator, and use SciPy `least_squares`. Compute numerical Jacobian rank against covariance-whitened sensitivity; if rank < number of fitted coordinates, stop or explicitly reduce to a documented one-coupling diagnostic fit. Do not manufacture a prior or silently drop an outlying bin.

  ```python
  factor = np.linalg.cholesky(data.covariance)
  def residuals(theta):
      coefficients = np.array([1.0, theta[0]-anchor_g1, theta[1]-anchor_g2])
      prediction = np.array([certificates[key].predict(coefficients).ratio_sigma
                             for key in data.keys])
      return np.linalg.solve(factor, data.sigma - prediction)
  result = scipy.optimize.least_squares(residuals, initial_theta)
  ```
- [ ] **Step 4 GREEN command:** Give user `cd theory && python -m pytest tests/test_figure4_fit.py -q` with expected seconds-scale duration, input (synthetic fixtures only), no production output, and expected PASS. User runs and returns output. Measure one objective evaluation locally without optimizer; give user a separate 20-evaluation synthetic fit benchmark command and use its returned timing for the later production estimate.
- [ ] **Step 5 review/commit:** Commit only Task 6 files with `feat(theory): fit source couplings to native Sigma`.

## Task 7: CLI, checkpoint and separate scientific reports

**Files:** Modify `src/graal_theory/cli.py`, `tests/test_cli.py`; create `src/graal_theory/figure4_fit_output.py`, `tests/test_figure4_fit_output.py`; reuse `figure4_comparison.py` for Ajaka statuses.

**Interfaces:** `graal-theory figure4-basis-build --target ajaka|native --output <dir> [--data-root ... --reco-root ... --flux-root ... --run-manifest ...] --workers N --resume`; `graal-theory figure4-fit --data-root <root> --basis-native <dir> --basis-ajaka <dir> --output <dir> [--require-final]`. Native build requires all four input paths; Ajaka build refuses them. Fit requires both completed basis manifests so sourced and fitted Ajaka comparisons cannot accidentally reuse native energy weighting. Completed bins are atomic files plus per-bin metadata and fingerprint; manifest is complete only after all required bins/certificates exist.

- [ ] **Step 1 RED:** Parser tests reject missing native inputs, mixed Ajaka/native flags, identical source/fitted output path and fit with incomplete manifest. Check checkpoint resume skips a completed matching bin, recomputes an incomplete bin, and rejects changed source parameters, input ROOT hashes, energy weighting, numerical settings or code fingerprint. With a toy bundle, verify `sourced/` and `fitted/` Ajaka comparison tables have distinct parameters; a sourced discrepancy cannot be relabeled reproduced by fitted agreement. Fit command refuses digitized theory CSV as input data.
- [ ] **Step 2 RED command:** `cd theory && python -m pytest tests/test_cli.py tests/test_figure4_fit_output.py -q`. Expected: absent commands/writer.
- [ ] **Step 3 GREEN:** Dispatch thin CLI functions to Tasks 3–6. Write bin files through temporary sibling plus atomic rename; compare exact immutable manifest fingerprints on `--resume`, hashing relevant source-file contents as well as source/data artifacts so a dirty checkout cannot impersonate `HEAD`; never advertise a partial run as complete. Emit progress after each bin and a final summary with counts, masks, timing and next missing bin. Write source and fit JSON/CSV, numerical/data covariance and 4x3 comparison PDFs in distinct paths, with explicit `reproduced`, `calculated_discrepant`, `incomplete`, `fit_validated` or `fit_unavailable` status.

  ```python
  if resume and saved_manifest["fingerprint"] != current_fingerprint:
      raise ValueError("basis run fingerprint mismatch")
  temporary.write_bytes(serialized_bin)
  temporary.replace(completed_bin_path)
  ```
- [ ] **Step 4 GREEN command:** Focused CLI/output tests pass. Check emitted JSON/CSV and open one tiny synthetic PDF for masked segments and source-versus-fitted labels; no real long run.
- [ ] **Step 5 review/commit:** Commit only Task 7 files with `feat(theory): add resumable Figure 4 fit workflow`.

## Task 8: User-run data release, production proof and scientific claim

**Files:** Update `references/full_production_validation.md`, `references/model_scope.md` and the two Figure 4 TDD plans only with measured outcomes; generated artifacts stay in `theory/outputs/` and `results/` without Git staging.

- [ ] **Step 1 preflight:** Verify final Stage 07 sideband and reconstructed signal-MC inputs exist; current `results/production-20261006-113738/uv/` does not contain matching sideband files. Verify nominal reco ROOT, calibrated flux, manifest, run IDs and input hashes. If prerequisites are absent, prepare separate user-run commands from `wiki/07-observable-extraction.md` to produce them; do not call existing first-pass ROOT final.
- [ ] **Step 2 user-run Stage 07:** Give user complete `beam_asymmetry.py` command with sideband pair and reviewed positive bootstrap replicas, distinct output directory, input hashes, CPU/memory estimate from a small measured pilot, expected `background=sideband-corrected` and `covariance/bootstrap_run`. User runs; inspect logs and ROOT QA before fit. A lost bin or unstable covariance blocks final release.
- [ ] **Step 3 user-run basis campaigns:** After sourced Task 3G/3I pilots pass and throughput is measured, give user exact `figure4-basis-build` commands for Ajaka and native targets with per-bin power policy, worker count, expected duration, memory and output paths. User runs; inspect all 78 physically accessible publication bins and all selected native bins, numerical certificate, three-projection total, direct/grid audit and resume manifest. Failure remains `incomplete`.
- [ ] **Step 4 user-run fit:** Only after final data, acceptance QA, basis certification and rank preflight, give user exact `figure4-fit` command and expected short optimizer runtime; user runs. Re-evaluate optimum using the direct seven-family model at representative events/bins and compare against basis predictions. Repeat ratio fit interpretation with likelihood points only as a separate sensitivity study, never as extra independent data.
- [ ] **Step 5 claim and docs:** Compare sourced parameters to Ajaka theory strokes using existing `0.020` reading bound and numerical bound; compare fitted parameters to GRAAL data with full covariance; compare fitted curves to Ajaka separately. Report all twelve panel statuses, native chi-square/dof, fitted coupling values in source units, identifiability, numerical/data uncertainty, source-used high-W fractions, acceptance and best-quartet limitations. Do not claim reproduction from software tests, fit quality alone or a visually similar line.
- [ ] **Step 6 verification:** Run focused new tests locally; prepare full `cd theory && python -m pytest -q` and wheel check for the user because baseline suite took `218.94 s`. Inspect returned exit codes and logs, `git diff --check`, scoped file status, output manifests and PDFs before declaring software completion.

## Spec coverage and handoff

| Approved design requirement | Owning proof |
| --- | --- |
| Exact sourced production coupling basis; no new physics | Task 1 event oracles and fingerprints |
| Coherent interference and fast parameter trials | Task 2 Gram tests; Task 6 benchmark |
| Source-equivalent bin convergence, source/off-source checks | Task 5 plus sourced Task 3G/3I and 7–10 |
| Native selected runs, flux/polarization and ratio estimator | Tasks 3–5; acceptance gate in Task 8 |
| Covariance alignment, bootstrap and no double counting | Task 3/6 tests; Task 8 final Stage 07 QA |
| Identifiability and defensible physical fit | Task 6 synthetic recovery and rank gate; Task 8 direct recheck |
| Separate sourced and fitted Ajaka comparisons | Task 7 output tests; Task 8 panel review |
| User launches long work; interruption remains recoverable | Task 7 resume tests and Task 8 command handoff |

**Execution rule:** Every code task runs focused RED before implementation and focused GREEN after. Task 8 is scientific production, not a unit-test substitute. Do not implement against unreviewed source/fit parameter assumptions. Before implementation, user reviews this plan; native execution uses `superpowers:executing-plans`. Do not spawn agents without explicit user request.
