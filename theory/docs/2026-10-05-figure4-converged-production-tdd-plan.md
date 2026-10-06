# Ajaka Figure 4 converged production: TDD implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task by task. Steps use checkbox (`- [ ]`) syntax for tracking. Do not spawn agents unless the user requests delegation.

**Goal:** Calculate, converge, and compare the twelve Ajaka Figure 4 theoretical beam-asymmetry curves from the sourced seven-family coherent model, without fitting the published strokes.

**Architecture:** Keep `reconstructed_full_tmatrix` as numerical authority; extend its bounded real-axis domain to 1.80 GeV, then accelerate only verified values through `StrongTGrid`. Integrate each nominal mass bin conditionally over its exact energy–mass support, form polarized cross-section moments, certify numerical convergence, and compare accepted segments against the independently digitized Ajaka strokes.

**Tech Stack:** Python ≥3.10; NumPy ≥1.24; SciPy ≥1.10; Matplotlib ≥3.7; pytest ≥7.4. All files remain under `theory/`.

**Spec:** `theory/docs/2026-10-05-figure4-converged-production-design.md`; conventions also in `theory/docs/2026-10-01-figure4-theory-design.md`.

**Execution gate, 2026-10-06:** Source-bounded strong amplitude, validated
grid, coherent model, conditional four-coordinate sampler, bin moments,
certification API, source trace, and output command exist. Real seven-family
publication-bin certification, PRC73 Fig. 18 numeric comparison, and all
twelve Ajaka curves remain open. The measured `p_eta` upper-energy `p5/p6`
normalization change is about `1.72%` against `<1%`; `p7` at default inner
`64/48` previously hit a near-tangent Eq. (25) failure. Task 3F's isolated
regression now passes, while the complete bin awaits a rerun. Complete same-order
`p6/p7` at `96/72` changes the denominator by `1.047245%`, failing `<1%`.
Task 3E and real Task 7–10
proofs govern the remaining work. Passing software tests does not change
this gate.

## Global constraints

- Target: four Ajaka energy intervals `[1.10,1.20)`, `[1.20,1.30)`, `[1.30,1.40)`, `[1.40,1.50]` GeV × three pair masses (`p_pi0`, `p_eta`, `eta_pi0`) × ten nominal bins per panel. Endpoints have measure zero in quadrature.
- Real-axis strong `W` support ends at **1.80 GeV**, exactly; label `W <= 1.60` as the source's qualitative scattering-agreement region, `1.60 < W <= 1.80` as source-used extension. Reject `W > 1.80`; preserve all equations, parameters, and `W <= 1.70` numerical fingerprints.
- Coherently sum all seven complete spin-amplitude families before squaring. Primary observable: `Sigma = 2∫cos(2φ)(w_V-w_H)/∫(w_V+w_H)`, with pair-sum azimuth and common events for both photon polarizations.
- Uniform incident-photon energy weighting is primary; measured flux and twelve-bin center fitting are separately labeled sensitivities. Never pick weighting or parameters by closeness to Ajaka strokes.
- Matrix grid error `<= max(1e-8 GeV^-1,1e-4*abs(T_direct))` elementwise; non-negligible polarized event-weight relative error `<=0.25%`; publication-bin `|Delta Sigma_grid-direct| <=0.002`.
- Energy `n/2n`: `|Delta Sigma|<=0.005`, each non-negligible polarized normalization `<1%`. Nonscrambled Sobol `p/p+1`: `|Delta Sigma|<=0.01`, total weight `<1%`, populated normalization bins (≥`1e-4` total) `<3%`. Scrambled-replicate `SE(Sigma)<=0.01`. `|Sigma|<=1` within roundoff.
- Digitization reading bound is `0.020`; add it conservatively to numerical error bound in residual gate. No invented high-energy systematic or theory-parameter fit.
- Preserve existing statuses and distinguish `masked_kinematic`, `masked_unsupported_domain`, `masked_nonconverged`, `unresolved`, `discrepant`, and `compatible` in records; only compatible/converged coverage of all physically accessible bins in twelve panels permits `reproduced`. Expected kinematic masks outside support are allowed.
- No Stage 07/08 edits, native-data fit, new channel, second-sheet pole, or parameter tuning. Existing uncommitted Stage 06/07 changes are outside task ownership; do not revert or stage them.

## File map and ownership

| File | Responsibility |
| --- | --- |
| `src/graal_theory/amplitudes/_reduced_t_core.py`, `pipi_n.py` | Shared bounded direct strong-T domain and existing equations. |
| `src/graal_theory/amplitudes/nstar1535_grid.py` | Immutable, fingerprinted, landmark-split adaptive strong-T interpolation and bounded in-memory cache. |
| `src/graal_theory/amplitudes/production_loops.py`, `resonance_photoproduction.py`, `chiral_photoproduction.py`, `decuplet_rescattering.py` | Measured, source-equivalent direct-quadrature throughput work; retain scalar oracle. |
| `src/graal_theory/models/eta_pi0_p_full.py` | Optional matching grid on existing seven-family model; direct default. |
| `src/graal_theory/amplitudes/resonance_photoproduction.py` | Active-source pole preflight. |
| `src/graal_theory/phase_space.py` | Conditional pair-mass sampling with canonical returned daughter order. |
| `src/graal_theory/figure4_integration.py` | Publication-bin energy support, polarized moments, covariance and convergence. Reuse `beam_asymmetry.py` sign and finite-φ fitter. |
| `src/graal_theory/figure4_comparison.py` | Figure 4 typed status, reference comparison, CSV/JSON/PDF/report writing. Reuse `figure4_reference.py` loader. |
| `src/graal_theory/cli.py` | One dedicated full-production Figure 4 command; legacy Eq. 43 commands remain partial. |
| `references/p73_figure18_full_1700.csv/.json` | Bounded independent high-energy full-model source reading. |
| `references/model_scope.md`, `figure4_amplitude_inventory.md`, `full_production_validation.md`, `README.md` | Updated scope, source-use limitation, and observed exit status. |
| `tests/test_nstar1535_grid.py`, `test_figure4_integration.py`, `test_figure4_comparison.py` | New behavior tests; extend responsible existing strong, phase-space, model, resonance and CLI tests. |

## Review focus

1. `p_eta` upper edge at 1.7873058993 GeV: no zero-filled or skipped accessible sliver; energy quadrature starts at exact onset and line stops at support.
2. VMD switch and channel threshold ± one ULP: grid returns correct side and never bridges the landmark.
3. Parameter/vector-mass replacement after grid build: mismatch raises before any family evaluation.
4. Numerically finite but unconverged result: stays masked, cannot enter comparison interpolation or a `reproduced` claim.
5. Published reference point outside physical support: remains an explicit `masked` comparison row, not silently omitted or treated as compatible.

## Task 1: Extend direct strong-T authority through 1.80 GeV

**Files:** Modify `src/graal_theory/amplitudes/_reduced_t_core.py`, `pipi_n.py`; modify `tests/test_nstar1535_reduced.py`, `test_pipi_n.py`, `test_nstar1535_pipi_n.py`, `test_nstar1535_full.py`, `test_nstar1535_vmd.py`, `test_nstar1535_charge_zero.py`, `test_production_loops.py`, `test_full_production_convergence.py` only where old `1.70` rejection is now false.

**Interfaces:** `reconstructed_full_tmatrix(w_gev, parameters, masses) -> complex128[6,6]` remains unchanged. Same shared domain applies to reduced/intermediate variants because they call `_reduced_t_core.validated_energy`.

- [ ] **RED:** Add `test_full_t_high_domain_solves_and_stops_at_source_ceiling`, parametrized at `1.70`, `1.75`, `1.80`, and `np.nextafter(1.80, np.inf)`. For accepted values, independently form `V=reconstructed_full_kernel`, `G=loop_functions`, and assert finite symmetric `T`, `max(abs((I-VG)@T-V))<=1e-9*max(1,max(abs(V)))`. Last value must raise `ValueError` naming `W`. Add checks for all six meson-baryon thresholds and every finite `switching_energies` value, with `np.nextafter(x, ±np.inf)` when inside domain; compare direct values at/below `1.70` to pre-edit fixed-sample fingerprints already tested in `test_full_production_convergence.py`.

  ```python
  @pytest.mark.parametrize("w", [1.70, 1.75, 1.80])
  def test_full_t_high_domain_solves_and_stops_at_source_ceiling(w, final_parameters, vector_masses):
      v = reconstructed_full_kernel(w, final_parameters, vector_masses)
      g = loop_functions(w, final_parameters)
      t = reconstructed_full_tmatrix(w, final_parameters, vector_masses)
      assert np.isfinite(t).all()
      np.testing.assert_allclose(t, t.T, rtol=1e-10, atol=1e-10)
      assert np.max(np.abs((np.eye(6) - v * g[None, :]) @ t - v)) <= 1e-9 * max(1., np.max(np.abs(v)))
  ```
- [ ] **RED command:** From `theory/`, `python -m pytest tests/test_nstar1535_full.py::test_full_t_high_domain_solves_and_stops_at_source_ceiling -q`. Expected failure: `W outside reduced real-axis domain` at `1.75`.
- [ ] **GREEN:** Change only two hard upper limits from `1.70` to `1.80`, retaining strict scalar, threshold, loop 48/96 quadrature, condition-number, and symmetry checks. Update old rejection parameter lists to reject `np.nextafter(1.80, np.inf)` and accept `1.701`; revise outdated test comments. Do not touch source constants or subtraction values.
- [ ] **Proof:** Run all strong-T, VMD, production-loop, and lower-domain fingerprint tests named above. A real high-energy quadrature failure remains a failure for diagnosis; never weaken `1e-3` loop consistency to make this task green.

## Task 2: Build and validate bounded `StrongTGrid`

**Files:** Create `src/graal_theory/amplitudes/nstar1535_grid.py`, `tests/test_nstar1535_grid.py`.

**Interfaces:** `build_strong_t_grid(parameters: ReducedTParameters, masses: VectorMasses, *, atol=1e-8, rtol=1e-4) -> StrongTGrid`; `StrongTGrid.evaluate(w_gev: float) -> NDArray[np.complex128]`; `StrongTGrid.matches(parameters, masses) -> bool`. Grid domain is lowest meson-baryon threshold through 1.80 GeV. Direct evaluator is always `reconstructed_full_tmatrix`.

Test module defines `REFERENCE_DIR = Path(__file__).resolve().parents[1] / "references"` and imports `EtaPi0PFullModel`, `reconstructed_full_tmatrix`, and `build_strong_t_grid`.

- [ ] **RED:** In `test_nstar1535_grid.py`, build sourced parameters; assert all `meson+baryon` thresholds and finite `switching_energies` are segment boundaries; at each boundary and at `np.nextafter` on both sides compare `evaluate(w)` with direct `T` elementwise using `abs(actual-direct) <= max(1e-8,1e-4*abs(direct))`. Add deterministic quarter/midpoint off-grid probes, an exactly zero-entry absolute-tolerance test, `W>1.80` rejection, and mutation attempt on returned matrix that cannot affect subsequent calls.

  ```python
  def test_grid_off_node_respects_direct_matrix_bound():
      p = EtaPi0PFullModel.from_files(REFERENCE_DIR).parameters
      grid = build_strong_t_grid(p.strong, p.vector_masses)
      for w in (1.612345, 1.735678, 1.799123):
          direct = reconstructed_full_tmatrix(w, p.strong, p.vector_masses)
          error = np.abs(grid.evaluate(w) - direct)
          assert np.all(error <= np.maximum(1e-8, 1e-4 * np.abs(direct)))
  ```
- [ ] **RED:** Replace one subtraction constant and one vector mass separately; `matches` must become false. Build twice with identical inputs and once after a version/tolerance change; verify cache reuse only for identical fingerprints. Force a sharp but finite toy interval via test-local direct-evaluator seam and require either refinement or direct fallback, never an out-of-tolerance interpolant.
- [ ] **RED command:** `python -m pytest tests/test_nstar1535_grid.py -q`. Expected failure: missing `nstar1535_grid` module.
- [ ] **GREEN:** Use immutable parameter tuples and vector masses in a SHA-256 key including domain endpoints, sorted landmarks, `atol`, `rtol`, 48/96 direct-loop rule identity, and implementation version. Memoize at most two built grids. Store matrix nodes in bytes-backed arrays. Split at every landmark; recursively check midpoint and both quarter points for each interval, using real/imaginary piecewise linear interpolation; if node budget is reached, mark that interval direct-only. Return a fresh `complex128[6,6]` copy or read-only bytes-backed view. Never interpolate across a switch or threshold.
- [ ] **Proof:** `python -m pytest tests/test_nstar1535_grid.py tests/test_nstar1535_full.py -q`; record grid nodes, direct-fallback intervals, and build/evaluation runtime for later report. The direct oracle must remain callable independent of grid cache.

## Task 3: Make direct production quadrature tractable

**Files:** Modify `src/graal_theory/amplitudes/production_loops.py`, `resonance_photoproduction.py`, `chiral_photoproduction.py`, `decuplet_rescattering.py` only where profiling identifies repeated work; extend `tests/test_production_loops.py`, `test_resonance_photoproduction.py`, `test_chiral_photoproduction.py`, `test_decuplet_rescattering.py`. Do not alter equations or public family signatures.

**Interfaces:** Preserve scalar `_integrate_complex_1d/_2d` as reference evaluators. Add private `_prepare_explicit_source(channel, event_pion, photon_momentum, polarization, production, tree) -> Callable[[float,float], NDArray[np.complex128]]` in `resonance_photoproduction.py`; it returns the same summed `(2,2)` source kernel as the current per-node closure. If preparation alone is insufficient, add `_integrate_complex_2d_array(integrand, q_lower, q_upper, x_lower, x_upper, *, settings, context) -> NDArray[np.complex128]` in `production_loops.py`, where `integrand(q_nodes, x_nodes)` returns a complex array with leading `(n_q,n_x)` axes. `QuadratureSettings` and source parameter records remain unchanged.

- [ ] **Baseline:** Profile sourced `E_gamma=1.2` and `1.5 GeV` fixed events, both H/V, each family at q/angle `32` and a representative higher order. Record strong-T time and per-family wall time; distinguish successful evaluations from quadrature failures. Existing local low-energy measurement is `~0.0013 s` per direct T and `~16.9 s` per seven-family event/polarization, with `~13.1 s` in explicit resonances. Treat numbers as baseline, not acceptance.
- [ ] **RED A:** Test `_prepare_explicit_source` against the current `delta1700_pi_delta_kernel + nstar1520_pi_delta_kernel + delta_kr_pole_kernel` at fixed `(q,x)` nodes for both charge channels and H/V polarizations, including inactive couplings. Also compare complete complex explicit-resonance event matrices at q/angle `32` and `64` for threshold-adjacent, open-cut, pole-adjacent, and upper-domain events; use `rtol=1e-10, atol=1e-10` for unchanged reduction order. Active zero-width pole and nonfinite values must retain context.

  ```python
  def test_prepared_explicit_source_matches_three_printed_kernels(production, tree, sample):
      pion = sample.momenta[0, 1]
      photon = np.array([0., 0., 0.7])
      epsilon = np.array([1., 0., 0.])
      q, x = 0.23, 0.37
      prepared = resonance._prepare_explicit_source(1, pion, photon, epsilon, production, tree)
      args = (1, q, x, pion, photon, epsilon, production, tree)
      expected = sum((resonance.delta1700_pi_delta_kernel(*args),
                      resonance.nstar1520_pi_delta_kernel(*args),
                      resonance.delta_kr_pole_kernel(*args)))
      np.testing.assert_allclose(prepared(q, x), expected, rtol=1e-10, atol=1e-10)
  ```
- [ ] **RED A command:** `python -m pytest tests/test_resonance_photoproduction.py -q`. New tests fail because `_prepare_explicit_source` is absent.
- [ ] **GREEN A:** Validate event/channel records once; precompute fixed polarization/spin factors and `nstar1520_width(w,...)` before q/x iterations. Use prepared source in the existing scalar Eq. (26) loop. Keep three public kernel functions and scalar loop as the independent oracle.
- [ ] **Measure A:** Run focused resonance/loop tests and a no-profiler timing. If projected full run still exceeds 24 hours on measured available hardware, start RED B; otherwise retain scalar quadrature and skip B. Record decision and arithmetic in report.
- [ ] **RED B when needed:** Test `_integrate_complex_2d_array` against scalar `_integrate_complex_2d` for analytic complex tensor integrands and both configured/doubled orders. For production paths, compare each optimized family with scalar oracle at fixed threshold/open-cut/pole-adjacent/upper-domain events, both polarizations and q/angle `32`/`64`; require agreement within the existing quadrature tolerance after any changed reduction order. Include principal-value imaginary sign, radial split, endpoint-pole error, and family/channel/invariant diagnostics.
- [ ] **RED B command:** `python -m pytest tests/test_production_loops.py tests/test_resonance_photoproduction.py tests/test_chiral_photoproduction.py tests/test_decuplet_rescattering.py -q`. New array-path tests fail because `_integrate_complex_2d_array` is absent.
- [ ] **GREEN B when needed:** Batch q/x evaluation within existing Eq. (8)/(26) integrals using NumPy arrays, retain principal-value subtraction and per-branch scalar fallback, and perform configured/doubled-order checks on complete complex sums. Hoist event-constant work in other profiled families. Do not add an unverified compiled dependency or replace direct quadrature with a fitted loop table.
- [ ] **Proof and feasibility gate:** Re-run focused tests and no-profiler timings for all seven families at both energies. Estimate total cost using actual planned events, H/V states, energy orders, replicas, grid/direct and Sobol refinements; include parallel workers only when benchmarked. Full 120-bin projection must be ≤24 hours on measured available hardware before Task 10. If larger, record `not_completed_runtime_bound` and revise numerical architecture; do not claim grid solved bottleneck.

### Task 3C: Measured throughput correction (added after execution audit)

The prepared source plus radial Eq. (26) array path initially reduced one
warm seven-family event/polarization at `E_gamma=1.5`, q/angle `32/32`, from
`~9.9 s` to `~0.60 s`. At sourced default `64/48`, it took `1.636 s`.
Subsequent Eq. (25) array integration reduces these to `~0.28 s` and
`~0.63 s`, respectively. Exactly **78 of 120** nominal bins are physically
accessible. Four measured processes deliver 4.206 event/polarization
evaluations per second versus 1.136 for one, but a real pilot now fails a
strict inner-loop convergence check (Task 3D). Full-run feasibility cannot
be declared from minimum-setting throughput alone. No Figure 4 reproduction
status follows from software tests or partial curves.

- [ ] **RED:** Freeze complete complex `internal_pi0` event matrices at
  `E_gamma=1.2,1.5`, H/V, and q/angle `32/32,64/48`; retain the present scalar
  Eq. (25) path as an independently callable oracle. Include channels 2,4,5,
  both open and closed first cuts, two simultaneous on-shell denominators,
  cutoff-adjacent poles, and branch thresholds. Assert matrix agreement within
  current configured/doubled quadrature tolerance, including imaginary cut
  sign and contextual errors. Tests must first fail for the absent array path.
- [ ] **GREEN:** Vectorize Eq. (25) q/x smooth factors and principal-value
  subtractions using `_integrate_complex_2d_array`; evaluate the on-shell
  residue per angular node and retain scalar fallback at removable near-pole
  nodes. Hoist one-dimensional q factors and checked pion form factors. Keep
  Eq. (25) equations and the scalar function intact. Cache physical resonance
  widths only with complete immutable source-parameter keys; shared values
  across channels/polarizations/conditional bins must not be recomputed.
- [ ] **Proof:** Run focused chiral, loop, resonance, decuplet and full-model
  tests; compare fixed scalar/array matrices at both orders and energies.
  Benchmark cold and warm all-family H/V events at `64/48` and at chosen
  higher order on one hardware worker, then benchmark actual process parallel
  scaling if parallelism is counted. Project all 78 accessible bins including
  `n/2n`, `p/p+1`, eight replicas and final grid/direct comparisons. Continue
  to Task 10 only if projected run fits 24 h and all numerical gates remain
  strict; otherwise retain `not_completed_runtime_bound` and revise this
  throughput task again.

### Task 3D: Resolve measured Eq. (25) tangent-cut event (completed for this event)

Resolved for the measured blocker event. The first real conditional pilot,
`p_eta`, energy `[1.40,1.50]`, mass `[1.60,1.64]`, energy order 4 and Sobol
power 4, originally failed in `internal_pi0`, channel 4 `K+Lambda`, at
`E_gamma=1.4069431844202973`, `M(eta p)=1.61009316501 GeV`. Scalar and
array Eq. (25) both failed; even `2048/1536` gave `0.000138061`. Exact
recoil-angle integration with the physical `+i0` logarithm now passes the
unchanged `64/48` check. The regression is an ordinary passing test. The
corresponding Eq. (26) radial-source treatment agrees with scalar oracle
within the targeted matrix tolerance. Other physical events still need the
publication-bin certification run.

- [ ] **RED:** Retain the strict xfail event, add a scalar-oracle diagnostic
  exposing configured and doubled complete complex Eq. (25) integrals and
  the two separate cut contributions. Verify recoil-root discriminant and
  opening angle from independent kinematics; include both sides of the
  tangent and a control event away from it. Convert xfail to ordinary test
  only after demonstrated convergence. Add tests for endpoint roots and
  simultaneous on-shell denominators, preserving the negative imaginary
  `+i0` sign.
- [ ] **GREEN:** Derive a source-equivalent finite representation at the
  coalescing recoil roots. Split angular support at the exact discriminant
  zero and radial support at the moving roots, using maps that regularize
  their joint square-root cusp; if separate Eq. (25) fractions develop
  numerically cancelling singularities, combine their regular parts before
  integration while keeping each physical residue and analytic logarithm.
  Validate against independent adaptive quadrature at the fixed event and
  nearby one-sided controls. Never replace the integral with a fitted table,
  add finite epsilon, drop the channel, or relax the `1e-5`/`1e-10` loop gate.
- [ ] **Proof:** Fixed blocker event passes at a measured practicable order;
  results stable under further radial/angle refinement. Repeat a small real
  conditional pilot for both H/V and all seven families at lower and upper
  Ajaka energies, then reproject total 78-bin cost with all certification
  checks. Task 10 remains closed until both this numerical gate and Task 3C
  throughput gate pass.

### Task 3E: Resolve publication-bin variance and runtime bound (blocking)

Exact global-azimuth averaging reduced the sampler to four Sobol coordinates,
but the real upper-energy `p_eta` bin still fails the raw normalization gate:
at `64/48`, energy order four, `p4/p5/p6` denominators are
`1.163684060/1.184197284/1.204877917`. `p5/p6` changes by about `1.72%`
against the fixed `<1%` limit. `p6` takes about `355 s` for one bin. Even
optimistic perfect scaling across four measured workers makes the complete
78-bin certification cost at least `26.9 h`; measured scaling is slower.
The host reports 14 logical CPUs. A warm 56-event/polarization benchmark
measured `6.04/11.62/15.13` evaluations per second at 4/8/14 workers,
respectively. Its 14-worker scaling suggests about `10.8 h` for the same
`p6` workload, but complete-bin scaling, inner-order failures and numerical
convergence are unmeasured. The full 24-hour gate remains undetermined;
Task 10 stays closed.
Before the Task 3F radial treatment, an attempted `p7` refinement encountered a near-tangent Eq. (25)
`K+Lambda` event at `M(eta p)=1.60914962014 GeV`. It fails the default
`64/48` internal check (`1.5179e-6` difference); isolated `96/72` and
`128/96` agree. Complete-bin `p7` at `96/72` passes every inner check but
gives `Sigma=-0.508868327`, denominator `1.217629483`, in `1288.9 s`;
same-order `p6` at `96/72` gives denominator `1.204877915` in `644.4 s`;
the formal `p6/p7` drift is `1.047245%`, failing `<1%`. Sigma changes by
`0.003429`, within its `0.01` gate.
With current panel-level task scheduling, applying that measured bin cost
to the upper `p_eta` panel's eight accessible bins and all 14 base-equivalent
passes projects `40.1 h` for that panel alone. This is an estimate because
other bins can differ, but it cannot establish the 24-hour launch gate.

- [ ] **RED:** Preserve this exact pilot as a nonconverged numerical fixture:
  check `p5/p6` `Sigma`, denominator, H/V normalization and source-extension
  fraction from raw moments, then assert the correct `sobol_total` reason.
  Use the same four-coordinate map and immutable model parameters. Confirm
  a second, low-energy bin to avoid optimizing one corner only.
- [ ] **Diagnosis:** Partition the four-coordinate integrand by pair mass,
  spectator polar angle, pair-frame polar angle and relative azimuth.
  Identify which coordinate and source-family interference drive the raw
  normalization drift. Compare deterministic and scrambled replicates;
  check that exact global-angle averaging and Jacobian preserve the same
  full-space constant-amplitude normalization. The tested `p_eta` window
  crosses the sourced `K+Lambda` threshold at `1.60936 GeV`. Fresh `p5/p6`
  denominator contributions change by `-0.00994` below threshold,
  `+0.02570` in `[1.60936,1.62)`, and `+0.00492` in `[1.62,1.64)`;
  diagnose the sharp region above threshold before selecting a mass
  stratification. For
  the new `p7` event,
  determine why a real recoil tangent just outside angular support
  (`|cos(theta_tangent)|=1.01657`) still defeats `64/48`; preserve the
  `96/72` to `128/96` isolated regression without globally changing orders
  before measuring cost.
- [ ] **GREEN:** Apply only a source-equivalent variance or throughput
  treatment at the responsible integration layer. Candidate actions must be
  measured before selection: stratified or quadrature pair mass, angle
  transformation around physical peaks, shared H/V event evaluation, or
  bin-level parallel scheduling. Four-to-fourteen worker scaling is now
  measured for one warm event, but panel-level scheduling limits utilization.
  Do not tune parameters, choose a favorable seed, change
  reference points, suppress a failing bin, or relax any acceptance bound.
**Failed mass-split probe:** Exact stratification at `1.60936 GeV`
  preserved phase-space volume and nested Sobol points in toy tests, but
  deterministic Sobol zero sampled the new threshold endpoint. Its Eq. (25)
  `K+Lambda` integral failed strict checks even at `512/384`. A fixed digital
  shift removed the endpoint, yet a nearby event at
  `M(eta p)=1.60929498643 GeV` still failed at `64/48` and `96/72`
  (`2.77055e-6` and `2.49252e-6` differences). The probe was reverted;
  no stratified physical bin or gate result is claimed. Resolve near-threshold
  Eq. (25) stability before trying a split again, and measure whole-bin cost.
- [ ] **Proof:** Demonstrate both `p/p+1` raw-normalization `<1%` and
  `Sigma <=0.01`, energy `n/2n`, eight-replica `SE<=0.01`, inner-loop and
  grid/direct checks on real upper- and lower-energy pilots. Measure actual
  complete per-bin cost and scaling at the selected settings. Recalculate
  all 78 accessible bins, including all mandatory passes; open Task 10 only
  if the projected twelve-panel run is `<=24 h`.

### Task 3F: Uniform Eq. (25) recoil treatment near the K+Lambda threshold

**Prerequisite for a new mass-split trial.** The shifted two-stratum pilot
samples `M(eta p)=1.6092949864266957 GeV`, tangent cosine magnitude
`1.00516`. Its isolated channel-4 integral fails strict configured/doubled
checks at `64/48`, `96/72`, and `128/96`, but passes at `192/144`,
`256/192`, and `512/384`, with stable matrix norm `0.02060225607`.
The exact `1.60936 GeV` threshold endpoint failed through `512/384`.
Raising every event to `192/144` is not an accepted throughput solution.

**Source-equivalence invariant:** The apparent missing pole-partner factor in
the analytic recoil-angle branch is not an error. With
`A=W-omega-E_left`, `B=W-omega-E_pi-E_right`, and
`R=(q0_on+omega)(W-omega+E_left)/(2W)`, the exact identity
`q_on^2-q^2=A*R` makes the first `R/(q_on^2-q^2)` term equal `1/A`.
The scalar/array subtraction then gives
`(1/A-1/B)/(B-A)=1/(A*B)`, which is the analytic-angle integrand.
On a physical recoil cut its logarithm has imaginary part `-pi/(q*p)`.
Do not add `R` or `1/(B-A)` to that branch; doing so would change Eq. (25).

**Isolated progress, 2026-10-06:** A RED regression at the measured `p7`
near-tangent event became GREEN by retrying the exact angular integral after
a checked tensor-quadrature convergence failure. The radial map now splits
at the recoil endpoint's stationary point; monotone pieces bracket both
cut roots even when they are closer than a fixed scan step. Evaluating the
endpoint denominator relative to a root or stationary point prevents
`c-E_right` from rounding to zero inside the logarithm. Isolated generated
events at `M(eta p)=1.6092949864266957`, `1.60936`, and `1.609361 GeV`
agree across `64/48`, `96/72`, and `192/144` at the unchanged check bound.
These checks do not certify a complete stratified bin or independent
adaptive-principal-value equivalence; the checkboxes below remain open.

- [ ] **RED:** Freeze both four-vectors as source-independent regression
  inputs, plus one event on each side of the threshold and a far-from-cut
  control. Compare scalar Eq. (25), array Eq. (25), and independent adaptive
  principal-value integration at each event; record real and imaginary
  components, both physical cuts, tangent discriminant, and runtime. Test
  the `-i*pi` sign and source-equivalent `192/144` to `512/384` result.
  Use the identity above as an algebraic cross-check when comparing the
  analytic-angle branch; a passing self-comparison alone is insufficient.
- [ ] **Derivation:** Analyze the recoil denominator after exact angular
  integration as a function of radial momentum. Locate its closest approach
  to zero when the tangent lies just outside `[-1,1]`, and the exact branch
  point when it lies inside. Derive a single radial split/map that remains
  stable as the tangent approaches the endpoint from either side. Use stable
  complex logarithm evaluation near coincident arguments. Do not add a
  finite-width epsilon or choose a sample-specific branch threshold.
- [ ] **GREEN:** Implement the derived source-equivalent radial treatment in
  the Eq. (25) owner. Keep the scalar oracle callable. If the exact-threshold
  integral is mathematically singular, demonstrate that from the source
  integral and exclude only that measure-zero sampler endpoint with a fixed,
  documented nested digital shift; never silently mask an open mass interval.
- [ ] **Proof:** Run the frozen near-threshold events at practicable order
  with unchanged `1e-5/1e-10` checks, both H/V, then re-run stratified
  `p4/p5/p6` and Task 3E's eight-replica and `n/2n` pilots. Retain the split
  only if it lowers complete-bin cost and passes every gate; otherwise
  restore the unsplit sampler and record `masked_nonconverged`.

## Task 4: Connect grid to coherent model and repair dormant resonance preflight

**Files:** Modify `src/graal_theory/models/eta_pi0_p_full.py`, `src/graal_theory/amplitudes/resonance_photoproduction.py`; extend `tests/test_eta_pi0_p_full.py`, `test_resonance_photoproduction.py`.

**Interfaces:** Add `strong_grid: StrongTGrid | None = None` to frozen `EtaPi0PFullModel`; `from_files(reference_dir, *, strong_grid=None)` retains direct default. `polarized_matrix_element_squared` and all seven family signatures stay unchanged.

- [ ] **RED:** Build model with a grid for its parameters and a fixed `ThreeBodySample`; compare direct/grid H and V complex family matrices and final event weights. For direct event weights at least `max(1e-14,1e-6*max(direct_weights))`, require relative error ≤0.0025; below that scale require absolute error ≤`0.0025*max(1e-14,1e-6*max(direct_weights))`. Assert mismatched strong parameters or vector masses raise during model construction, before family evaluation. Assert direct default still invokes `reconstructed_full_tmatrix`.
- [ ] **RED:** For explicit resonances, set `f_delta_n_pi=0`, both `N* Delta pi` couplings to zero, Delta width to zero, and nonzero unrelated strong transition. Expect exact zero for dormant source and no hidden-pole error. With one active coupling restored, expect current contextual `zero-width ... pole` error. Keep malformed parameter validation strict even when source dormant.
- [ ] **RED command:** `python -m pytest tests/test_eta_pi0_p_full.py tests/test_resonance_photoproduction.py -q`. New tests fail on absent grid field and dormant-source pole guard.
- [ ] **GREEN:** Validate grid fingerprint in `EtaPi0PFullModel.__post_init__`; change its existing `strong_t` closure to use matching grid if supplied. In explicit-resonance loop, validate parameter records first, then identify active source contributions; return exact zero for dormant terms before their pole checks. Keep active pole checks before integration. Do not create an arbitrary strong-model injection interface.
- [ ] **Proof:** Re-run focused tests plus `tests/test_eta_pi0_p_model.py`, `test_delta1700_amplitude.py`, `test_full_production_convergence.py` preservation tests. If prior physical-audit tests still assert upper-energy domain masking, replace those stale expected outcomes with domain-open but convergence-uncertified status; do not assert acceptance without measured convergence.

## Task 5: Conditional mass-window phase space

**Files:** Modify `src/graal_theory/phase_space.py`; extend `tests/test_phase_space.py`.

**Interfaces:** `sample_three_body_mass_window(sqrt_s, masses, pair: tuple[int,int], mass_range_gev: tuple[float,float], config: SobolConfig) -> ThreeBodySample | None`; `None` means zero-width kinematic intersection. Returned `momenta` and `masses` keep canonical `(eta,pi0,proton)` order, and returned `s12_gev2` still means canonical `M(eta pi0)^2`.

Add `invariant_mass` import to `test_phase_space.py` for the canonical-order assertion.

- [ ] **RED:** For each of `(0,1)`, `(0,2)`, `(1,2)`, sample a partly accessible interval and assert every `M(pair)` lies in its intersection with `[m_i+m_j, sqrt_s-m_spectator]`; validate four-momentum and on-shell conservation. Check `s12_gev2` against returned canonical daughter four-vectors for permuted pairs. Fully inaccessible windows return `None`; reversed/NaN ranges or invalid pair raise `ValueError`.

  ```python
  @pytest.mark.parametrize("pair", [(0, 1), (0, 2), (1, 2)])
  def test_conditional_sampler_restores_canonical_order(pair):
      spectator = ({0, 1, 2} - set(pair)).pop()
      low = MASSES[pair[0]] + MASSES[pair[1]] + .02
      high = 2.0 - MASSES[spectator] + .05
      sample = sample_three_body_mass_window(2.0, MASSES, pair, (low, high), SobolConfig(8))
      assert sample is not None
      validate_final_state(sample.initial, sample.momenta, MASSES, atol=1e-12)
      np.testing.assert_allclose(sample.s12_gev2,
          invariant_mass(sample.momenta[:, 0] + sample.momenta[:, 1])**2, atol=1e-12)
  ```
- [ ] **RED:** For constant amplitude, compare `mean(weights_gev2)` with an independent one-dimensional integral over `s_pair ∈ [max(a,threshold)^2, min(b,limit)^2]` using the existing `phase_space_volume_quad` density formula with permuted masses; require ≤0.5% at Sobol power 16. Partition full kinematic range into adjacent windows and require sum of their constant-amplitude integrals to equal `phase_space_volume_quad` to same tolerance. Preserve exact old `sample_three_body` arrays/fingerprint for fixed config.
- [ ] **RED command:** `python -m pytest tests/test_phase_space.py -q`. New tests fail because conditional sampler is missing.
- [ ] **GREEN:** Factor existing five-coordinate phase-space transform into a private helper accepting `s_pair_min/max` and permutation. Use `ds_pair = s_max-s_min` in the existing Jacobian; restore canonical momenta and recompute canonical `s12_gev2` after permutation. Leave public `sample_three_body` path and Sobol ordering unchanged.
- [ ] **Proof:** `python -m pytest tests/test_phase_space.py tests/test_kinematics.py -q`.

## Task 6: Publication-bin polarized observable and exact energy support

**Files:** Create `src/graal_theory/figure4_integration.py`, `tests/test_figure4_integration.py`.

**Interfaces:** `project_polarized_moments(phi, vertical, horizontal, weights) -> tuple[float,float]` computes the weighted numerator/denominator. `predict_figure4_bin(model, pair: str, energy_range_gev: tuple[float,float], mass_range_gev: tuple[float,float], *, energy_order: int, sobol: SobolConfig) -> Figure4BinMoment`. `Figure4BinMoment` stores raw numerator, denominator, V/H normalizations, denominator-weighted mass, accessible energy/mass bounds, and denominator fraction with `M(eta p)>1.60`; `sigma` is derived from raw ratio, not average of event ratios. Pair IDs follow `figure4_reference.PAIR_MASS_AXES`.

- [ ] **RED:** Analytic toy weights `w_V=A(1+s cos(2φ))`, `w_H=A(1-s cos(2φ))` on uniform φ give `Sigma=s` and swap V/H gives `-s`; isotropic weights give zero. Test all three pair-sum azimuths with a rotated fixed event. A 12-bin center fit on integrated toy yields attenuates the continuous moment by `sin(π/6)/(π/6)=3/π`; record both rather than changing primary sign.

  ```python
  def test_polarized_moment_has_ajaka_sign_and_normalization():
      phi = (np.arange(128) + .5) * (2*np.pi/128)
      s = .3
      vertical, horizontal = 1+s*np.cos(2*phi), 1-s*np.cos(2*phi)
      numerator, denominator = project_polarized_moments(phi, vertical, horizontal, np.ones(128))
      assert numerator/denominator == pytest.approx(s, abs=1e-12)
      opposite, same = project_polarized_moments(phi, horizontal, vertical, np.ones(128))
      assert opposite/same == pytest.approx(-s, abs=1e-12)
  ```
- [ ] **RED:** Choose one upper-edge mass window with onset `E_on=((m_low+m_spectator)^2-m_p^2)/(2m_p)` inside published energy interval. Assert every integration node lies in `[max(E_low,E_on),E_high]`, and total energy normalization retains subinterval width divided by full published width; entirely inaccessible bin is `masked_kinematic`. Compare a near-onset constant-amplitude integral against independent 2-D SciPy quadrature in energy and restricted `s_pair`, including the exact energy measure. Use a deliberately varying numerator/denominator toy to catch average-of-ratios error.
- [ ] **RED command:** `python -m pytest tests/test_figure4_integration.py -q`. Expected failure: missing module/API.
- [ ] **GREEN:** Reuse `s_from_lab_photon_energy`, `sample_three_body_mass_window`, `GEV2_TO_MICROBARN`, and `beam_asymmetry` H/V basis and sign. Map Gauss-Legendre nodes to accessible energy subinterval and multiply weights by its width/full interval width. For each node, evaluate H/V on identical sample; accumulate `2*cos(2φ)*(V-H)` and `V+H` separately with phase-space/flux factors, plus extension-only denominator and mass numerator. Reject negative/nonfinite amplitudes; mask zero denominator. Keep pilot Eq. 43 path unchanged.
- [ ] **Proof:** `python -m pytest tests/test_figure4_integration.py tests/test_beam_asymmetry.py tests/test_phi_fit.py -q`.

**Variance-reduction amendment after real pilot:** The first successful
seven-family `p_eta` bin at `E_gamma=[1.40,1.50]`, mass `[1.60,1.64]`,
`64/48` and energy order four failed the five-coordinate Sobol `p/p+1`
gate. Derive the exact global
azimuth average from complex H/V interference, prove it against a 256-angle
rotated-polarization quadrature and full-model rotation covariance, then use
four-coordinate conditional Sobol with fixed global azimuth. Check canonical
momenta, restricted phase-space volume, nested `p/p+1`, and equal integrated
H/V normalizations. Repeat a high-energy pilot without changing physical
parameters or acceptance thresholds. A failed pilot stays nonconverged.

## Task 7: Covariance and numerical convergence gate

**Files:** Extend `src/graal_theory/figure4_integration.py`, `tests/test_figure4_integration.py`.

**Interfaces:** `covariance_from_replicates(sigma_by_replica: NDArray[np.float64]) -> NDArray[np.float64]` returns covariance of the replica mean. `integrate_figure4_panel(model, pair, energy_range_gev, mass_edges_gev, *, energy_order, sobol_power, replica_seeds) -> Figure4PanelResult`; `certify_figure4_panel(...) -> Figure4PanelResult` drives `n/2n`, `p/p+1`, scrambled replicas, and direct/grid checks. Each bin has status/reason and numerical error bound; covariance rows align with nominal mass-bin indices.

- [ ] **RED:** Feed deterministic toy `Figure4BinMoment` arrays with known correlated fluctuations into covariance helper; assert symmetric finite covariance and standard error from *independent replicate estimates*, not individual QMC events. Replicate IDs are shared across conditional mass bins. A zero-denominator or nonfinite replicate produces typed mask. Require at least eight distinct fixed seeds, starting `2026..2033`; more may be added without changing prior seeds.

  ```python
  def test_covariance_uses_replica_means_and_cross_bin_correlation():
      replicas = np.array([[.05, .1], [.1, .2], [.15, .3], [.2, .4],
                           [.25, .5], [.3, .6], [.35, .7], [.4, .8]])
      actual = covariance_from_replicates(replicas)
      expected = np.cov(replicas, rowvar=False, ddof=1) / len(replicas)
      np.testing.assert_allclose(actual, expected, rtol=1e-14, atol=1e-14)
      assert actual[0, 1] > 0
  ```
- [ ] **RED:** Synthetic convergence cases independently violate each gate: energy `Delta Sigma>0.005`, V or H normalization ≥1%, Sobol `Delta Sigma>0.01`, total ≥1%, populated normalization ≥3%, replicate `SE>0.01`, `|Sigma|>1+roundoff`, and grid/direct `Delta Sigma>0.002`. Assert exact typed `masked_nonconverged` reason, no accepted curve segment, and no tolerance relaxation. A low-weight bin below `1e-4` does not count as a populated normalization bin, but still needs finite `Sigma` and replica error to be publishable.
- [ ] **RED:** For constant-amplitude toys, sum ten nominal mass-window polarized integrals for each of three pair axes. Each sum must match the same full-space polarized total within `max(1% of total, 3 combined replicate SE)`; failure masks affected panel. Verify source-used fraction lies in `[0,1]` and vanishes for events with `M(eta p)<=1.60`.
- [ ] **RED command:** `python -m pytest tests/test_figure4_integration.py -q`. Expected failure: missing covariance/certification API or incorrect gate.
- [ ] **GREEN:** Keep covariance from sample covariance of complete replica-bin `Sigma` vectors divided by replica count. Compare all raw polarized normalizations before forming ratios. Estimate numerical error bound as maximum of replica SE and observed refinement/grid-direct differences; retain each component separately in output. Run nonscrambled `p/p+1` as independent bias check, using nested old sampler property. If any mandatory check cannot be completed, mark `masked_nonconverged` with `not_completed` reason, never pass by omission.
- [ ] **Proof:** Run focused tests; then measure real seven-family high-impact events at lower and upper domain with configured/doubled `QuadratureSettings`. Record order, event invariant, family, difference, runtime, and failure reason. Choose higher production settings only from these measurements; direct mode remains authority.

## Task 8: Bounded PRC73 Figure 18 high-energy source check

**Files:** Create `references/p73_figure18_full_1700.csv`, `.json`; extend `tests/test_full_production_validation.py` or add `tests/test_figure18_reference.py`; update `references/full_production_validation.md` after computation.

**Interfaces:** Reference CSV columns `mass_gev,dsigma_dmass_microbarn_per_gev,reading_error`; JSON records PRC73 PDF SHA-256 `19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb`, Fig. 18, `E_gamma=1.7 GeV`, line identity, calibration, method, ambiguity and supported mass interval.

- [ ] **RED:** Add source-record test: at least two monotone points with `mass_gev<=1.80`, finite nonnegative density and positive reading bound, exact PDF digest, no duplicate/unknown columns; a point `>1.80` or mismatched digest must fail validation. Keep Figure 18 records separate from Ajaka reference CSV.
- [ ] **Source reading:** Render source Fig. 18 panel at high resolution and trace only identifiable full-model solid stroke through `M(eta p)<=1.80`. Record raw plot calibration and any overlap ambiguity. Do not use calculated curve to select traced points. This step supplies actual numbers; no invented fixture values.
- [ ] **RED command:** `python -m pytest tests/test_figure18_reference.py -q`. Expected failure: absent reference records/loader.
- [ ] **GREEN:** Add narrow loader/comparison using direct full-model mass spectrum at `E_gamma=1.7`; use source reading bound plus numerical error and retain `compatible`/`discrepant`/`masked` statuses. Do not extrapolate model or compare beyond 1.80. A disagreement remains documented; it cannot be repaired by fitting Figure 18 or Ajaka strokes.
- [ ] **Proof:** Run source-record tests and one convergence-certified high-energy source comparison. Record status separately from twelve-panel Ajaka outcome.

## Task 9: Twelve-panel comparison and reproducible outputs

**Files:** Create `src/graal_theory/figure4_comparison.py`, `tests/test_figure4_comparison.py`; extend `src/graal_theory/cli.py`, `tests/test_cli.py`; update `pyproject.toml` package data only if needed by new reference assets.

**Interfaces:** `compare_figure4(prediction: Mapping[tuple[int,str], Figure4PanelResult], published: tuple[PublishedCurvePoint,...]) -> Figure4Comparison`; `write_figure4_run(output_dir, panels, comparison, provenance, *, experimental_points=None) -> Path`. From `theory/`, CLI: `graal-theory figure4-full --output outputs/<run-name>` with explicit numerical flags; direct/grid mode recorded.

- [ ] **RED:** Synthetic panel with accepted neighbors and a middle mask: reference point in the gap stays `masked`, while a point bracketed by adjacent accepted bin positions interpolates. A point before first/after last accepted support, or outside exact physical support, stays `masked` with reason. `abs(residual)==reading_error+numerical_error` is compatible; just above is discrepant. `unresolved` survives ambiguous source mapping. A single discrepant panel makes whole-run status `calculated_discrepant`, while an accessible bin missing convergence makes it `incomplete`; expected `masked_kinematic` bins outside support are allowed, and only twelve otherwise complete compatible panels yield `reproduced`.
- [ ] **RED:** Output test requires four energy rows × three pair columns, ten nominal-bin records per panel, explicit nominal/accessible bounds, weighted mass, `Sigma`, error components, covariance row ID, status/reason, `source_used_extension_fraction`, direct/grid mode, source/parameter/code fingerprints, H/V normalizations, energy order and Sobol settings. PDF line segments stop at every mask. CSV/JSON residual rows preserve all published reference points, including unsupported ones. Inject optional experimental points only when explicitly requested.
- [ ] **RED command:** `python -m pytest tests/test_figure4_comparison.py tests/test_cli.py -q`. Expected failure: missing comparison module and `figure4-full` command.
- [ ] **GREEN:** Reuse `load_published_theory_curves` and its SHA-audited metadata. Interpolate only adjacent accepted calculated weighted-mass positions, never through a mask. Combine reading bound and numerical bound additively. Write predictions CSV/JSON, covariance JSON, residual CSV, 4×3 comparison PDF and Markdown validation report under ignored `theory/outputs/` run directory; refuse accidental overwrite without an explicit replace flag. CLI exit `0` for reproduced, `2` for completed negative/incomplete scientific result, `1` for invalid input/runtime failure.
- [ ] **Proof:** Run new tests, `tests/test_figure4_reference.py`, `tests/test_packaged_references.py`, and wheel packaging check. Open rendered PDF for visual QA: no joined segments over masks and no experimental points by default.

## Task 10: Real calculation, alignment audit, and claim gate

**Files:** Update `references/model_scope.md`, `figure4_amplitude_inventory.md`, `full_production_validation.md`, `README.md`; generated files only under `outputs/`.

- [ ] **Baseline:** Record exact git status and parameter/source SHA-256 hashes. Freeze primary uniform weighting, physical parameters, energy/mass binning and reference CSV before looking at Figure 4 residuals. `python -m pytest -q` from `theory/` supplies regression baseline; name any pre-existing failure.
- [ ] **Convergence run:** Build grid; run all 120 nominal bins (four intervals × three pairs × ten mass bins) with deterministic seeds. For every physically populated bin, refine inner production loops, grid/direct checks, `n/2n`, `p/p+1`, and scrambled replicas until all specified gates pass or record a typed nonconvergence/unsupported mask. Record runtime and settings; do not replace missing runs with interpolated points.
- [ ] **Physical cross-check:** Compare three pair-mass polarized totals, PRC73 Fig. 18 bounded high-energy spectrum, lower-domain fingerprints, source-used extension fractions, and continuous versus finite-φ diagnostic. Investigate disagreements as possible implementation or source-convention errors before judging Ajaka residuals; never adjust a parameter to match the stroke.
- [ ] **Comparison:** Generate 4×3 figure and per-point residual table against `ajaka2008_figure4_theory.csv`. Review each panel independently. Report count of `compatible`, `discrepant`, `unresolved`, and `masked`, all physical-bin convergence outcomes, and exact overall status. A complete negative result is scientifically valid and must name discrepant panels; a masked physical bin is incomplete, not reproduced.
- [ ] **Documentation:** Replace now-stale `1.70 GeV` domain and “Eq. 43 only” descriptions where they describe the *current full-model capability*, while retaining explicit Eq. 43 pilot limitations. State PRC65 scattering-validation range, PRC73 source-use extension, and no quantitative uncertainty assigned to that limitation. Leave Stage 07/08 files and native-data fitting untouched.
- [ ] **Final proof:** From `theory/`, run `python -m pytest -q`; run one cold CLI `figure4-full` calculation with fixed configuration and check its manifest/CSV/JSON/PDF/report. Review changed files and git status for scope. Report software correctness, numerical convergence, and physics compatibility as **three separate conclusions** with commands and actual results.

## Spec-coverage and objective audit

| Design requirement | Owning task / proof |
| --- | --- |
| Source-bounded high `W`, unchanged old physics | 1; direct equation, landmarks, fingerprints |
| Grid speed without changing model | 2 and 4; off-grid matrix, event weights, final-bin direct comparison |
| Direct-loop throughput without changing equations | 3; profiled bottleneck, scalar-oracle equivalence, measured run projection |
| Dormant resonance corner case | 4; dormant exact zero and active pole error |
| Conditional phase-space, edge support, energy onset | 5–6; independent restricted integral and 2-D edge integral |
| Ajaka sign, pairs, finite-φ diagnostic | 6; analytic polarized toy, three azimuths |
| Numerical covariance and all acceptance gates | 7; targeted failing gate cases and real refinements |
| Independent PRC73 high-energy guard | 8; source-only digitization to 1.80 GeV |
| Twelve panels, masks, residuals, provenance, PDF | 9–10; schema and real comparison |
| Reproduction claim only if scientifically earned | 9–10; explicit negative/incomplete statuses |

**Execution rule:** Every code task runs RED test before implementation, focused GREEN test after, then relevant regressions. Preserve all pre-existing uncommitted changes. No commit is required until user requests one; if committing, stage only task-owned `theory/` paths.
