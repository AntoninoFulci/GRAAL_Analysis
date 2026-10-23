# Coherent gamma p -> eta pi0 p Production Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the source-linked, seven-family complex production amplitude of Döring, Oset, and Strottman for `gamma p -> eta pi0 p`, ready for later Ajaka Figure 4 bin integration and native-data fitting.

**Architecture:** Four focused amplitude modules evaluate the production loops and six missing production/rescattering families on one `ThreeBodySample`; the existing Eq. (43) tree supplies the seventh family. A new model composes sourced parameters and the existing reconstructed-full six-channel strong T matrix, sums complex spin matrices before squaring, and exposes physical full-model plus explicit diagnostic APIs.

**Tech Stack:** Python 3.10+, NumPy, SciPy quadrature, pytest, existing Sobol phase space and spin algebra, Poppler only for source/reference audit.

**Spec:** `theory/docs/2026-10-02-eta-pi0-p-coherent-production-design.md`

## Global Constraints

- Work directly on `main`, as explicitly requested. Preserve every pre-existing dirty/untracked file and stage only task-owned paths.
- Increment A only: complete coherent amplitude and its validation. Do not generate Ajaka's twelve curves, read `beam_asymmetry.root`, fit data, or import Stage 07/08 code.
- Principal source is PRC 73, 045209, local SHA-256 `19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb`; supporting sources are the four PDFs named in the spec.
- Baseline strong interaction is `reconstructed_full_tmatrix`; reduced/intermediate strong variants remain separately callable and numerically unchanged.
- Use GeV internally. Every new physical number requires exact `value`, `unit`, `source_key`, and page/equation/table `locator`; no fallback constants.
- Baseline conventions are Butler decuplet phases; `g_eta = 1.7 - 1.4i`; `g_K = 3.3 + 0.7i`; SU(3) factor `1.15`; first-loop cutoff `1.4 GeV`; pion monopole cutoff `1.25 GeV`. Record these as conventions, never tune them to curves.
- Preserve PRC 73 channel order `(pi0 p, pi+ n, eta p, K+ Sigma0, K+ Lambda, K0 Sigma+)` and exact printed zeros/coefficient signs.
- Required gauge partners are indivisible in physical APIs: Eq. (8)+(9), Fig. 8(c)+(d), and Delta KR+pion-pole Eq. (32).
- Every family returns finite `complex128[event, final_spin, initial_spin]`; all seven matrices are summed before one final spin sum and average.
- Direct quadrature is authoritative. Add no interpolation until profiling proves it necessary; any later cache is value-keyed by every immutable physics/numerical input and returns immutable data.
- Closed channels follow the source analytic continuation. Invalid branches, poles, failed convergence, malformed polarization, and nonfinite results raise contextual `ValueError`; never clip or cast them silently.
- Preserve existing Eq. (43) amplitude/predictions at `rtol=1e-12`; preserve all current strong-T tests and standalone outputs.
- Validation traces are independent evidence only. No model output enters digitization and no digitized point enters parameter estimation.

## Review Focus

1. Threshold/closed-channel loop points must remain finite through the prescribed analytic continuation, while a true denominator pole must raise with family/channel/invariant context; pin in Tasks 2–5.
2. Gauge-paired terms must enter exactly once and cannot be disabled separately by the physical model; pin in Tasks 3, 4, and 6.
3. Complex interference must be preserved: opposite family phases can cancel at amplitude level and must not become an incoherent sum of positive weights; pin in Task 6.
4. Any bool, complex value in a real field, NaN, infinity, wrong unit/source, malformed polarization, or wrong sample mass order must raise before quadrature; pin in Tasks 1, 2, and 6.
5. Ambiguous/overlapping published strokes or nonconverged bins must be marked unresolved/masked, not counted as agreement or connected by a line; pin in Tasks 7–8.

## File Map

- Create `theory/references/eta_pi0_p_full_parameters.json`: sourced inputs absent from existing central/strong parameter records.
- Create `theory/src/graal_theory/amplitudes/production_loops.py`: numerical configuration, finite complex quadrature, Eq. (8)–(9) loop primitives, monopole form factor.
- Create `theory/src/graal_theory/amplitudes/chiral_photoproduction.py`: Fig. 6–8 / Eqs. (21), (24), (25).
- Create `theory/src/graal_theory/amplitudes/resonance_photoproduction.py`: Fig. 9 / Eqs. (26)–(37), including N*(1520) width.
- Create `theory/src/graal_theory/amplitudes/decuplet_rescattering.py`: Fig. 10 / Eqs. (39)–(42), including Sigma*(1385) propagation.
- Create `theory/src/graal_theory/models/eta_pi0_p_full.py`: parameter composition, strong-T closure, coherent sum, physical/diagnostic observables.
- Create focused tests `test_production_parameters.py`, `test_production_loops.py`, `test_chiral_photoproduction.py`, `test_resonance_photoproduction.py`, `test_decuplet_rescattering.py`, `test_eta_pi0_p_full.py`, and `test_full_production_validation.py`.
- Modify clean `theory/tests/test_packaged_references.py`: require new packaged parameter/reference records. Do not edit dirty `theory/pyproject.toml`.
- Create `theory/references/p73_full_production_curves.csv` and `.json`: audited readings from Figs. 12–14 and 19 not already represented by existing records.
- Create `theory/src/graal_theory/full_production_validation.py`: reference loader, component/full comparisons, convergence report writer.
- Modify `theory/references/figure4_amplitude_inventory.md`: mark each implemented family and its verification status. Do not edit dirty README/model-scope/CLI/pilot files.

---

### Task 1: Source-linked production parameter block

**Files:**
- Create: `theory/references/eta_pi0_p_full_parameters.json`
- Create: `theory/src/graal_theory/amplitudes/production_loops.py`
- Create: `theory/tests/test_production_parameters.py`
- Modify: `theory/tests/test_packaged_references.py`

**Interfaces:**
- Produces `QuadratureSettings(q_order: int = 64, angle_order: int = 48, relative_tolerance: float = 1e-5, absolute_tolerance: float = 1e-10)`.
- Produces immutable `ProductionParameters` with scalar fields for `e`, `D`, `F`, `b6D`, `b6F`, both cutoffs, N*(1520) mass/width/couplings, Sigma*(1385) mass/width, complex `g_K`, and `sigma_star_su3_correction`.
- Produces `load_production_parameters(parameter_path: Path, source_path: Path) -> ProductionParameters`.
- Tasks 2–6 consume these exact names; existing `Delta1700Parameters`, `ReducedTParameters`, and `VectorMasses` remain separate blocks.

- [ ] **Step 1: Write the source record and closed-schema tests.** Enter values fixed by PRC 73 and NPA 695: `e=0.3027`, `D=0.75`, `F=0.51`, `b6D=2.40`, `b6F=1.82`, first-loop cutoff `1.4 GeV`, pion-form-factor cutoff `1.25 GeV`, N*(1520) mass `1.520 GeV`, N*pi pole partial width `0.066 GeV`, `f_tilde_Nstar_Delta_pi=-1.061`, `g_tilde_Nstar_Delta_pi=0.640`, `g1_Nstar=0.782 m_N^-1`, `g2_Nstar=-0.410 m_N^-2`, `g_rho_Nstar=5.09`, common Sigma*(1385) mass `1.385 GeV`, Sigma* rest width `0.036 GeV`, `g_K=(3.3+0.7i)`, and correction `1.15`. Give each record its actual source key and locator: PRC 73 Table III/Eqs. (21),(25),(40)–(42), NPA 695 Eqs. (13)–(16)/Table A3, or PDG mass record. Encode `g_K` as `{"real": 3.3, "imag": 0.7}`.

```python
def test_production_parameter_record_is_closed_and_sourced():
    p = load_production_parameters(PARAMETERS, SOURCES)
    assert p.b6d == pytest.approx(2.40)
    assert p.b6f == pytest.approx(1.82)
    assert p.first_loop_cutoff_gev == pytest.approx(1.4)
    assert p.pion_form_factor_cutoff_gev == pytest.approx(1.25)
    assert p.g_k_sigma_star == pytest.approx(3.3 + 0.7j)
    assert p.sigma_star_su3_correction == pytest.approx(1.15)
```

Parameterize bad copies over missing/extra keys, bad unit, blank/URL locator, unknown/wrong source key, bool/string/NaN/infinity, nonpositive masses/cutoffs, negative widths, and complex values in real fields. Assert `ValueError` names the offending parameter. Add the JSON filename to `test_packaged_references.py`.

- [ ] **Step 2: Run RED.** From `theory/`: `python -m pytest tests/test_production_parameters.py tests/test_packaged_references.py -q`. Expected failure: missing `ProductionParameters`/loader or reference file.

- [ ] **Step 3: Implement strict immutable loading.** Follow `load_central_parameters` and `load_vector_masses`: exact top-level and entry keys, exact units/source keys, conversion through `SourceRef` and `PhysicalParameter`, then construction of a frozen dataclass. Store the validated provenance mapping on the dataclass with `repr=False, compare=False`.

```python
@dataclass(frozen=True)
class ProductionParameters:
    electric_charge: float
    axial_d: float
    axial_f: float
    b6d: float
    b6f: float
    first_loop_cutoff_gev: float
    pion_form_factor_cutoff_gev: float
    nstar1520_mass_gev: float
    nstar1520_npi_width_gev: float
    f_tilde_nstar_delta_pi: float
    g_tilde_nstar_delta_pi: float
    g1_nstar_per_gev: float
    g2_nstar_per_gev2: float
    g_rho_nstar: float
    sigma_star_mass_gev: float
    sigma_star_width_gev: float
    g_k_sigma_star: complex
    sigma_star_su3_correction: float
    quadrature: QuadratureSettings
    provenance: Mapping[str, PhysicalParameter] = field(repr=False, compare=False)
```

Convert `m_N^-1` and `m_N^-2` source values using the sourced proton mass, matching `Delta1700Parameters.from_parameters`. Validate quadrature orders as non-bool integers `>=16` and tolerances as finite positive reals.

- [ ] **Step 4: Run GREEN and wheel proof.** Run the RED command again. Build a wheel in `mktemp -d` and assert `graal_theory/references/eta_pi0_p_full_parameters.json` exists inside it; do not modify `pyproject.toml`.

- [ ] **Step 5: Stage only four owned paths and commit.** Commit message: `feat(theory): source coherent production inputs`.

### Task 2: Authoritative production-loop primitives

**Files:**
- Modify: `theory/src/graal_theory/amplitudes/production_loops.py`
- Create: `theory/tests/test_production_loops.py`

**Interfaces:**
- Consumes `ProductionParameters` and `QuadratureSettings` from Task 1.
- Produces `pion_monopole(momentum_squared_gev2: ArrayLike, pion_mass_gev: float, cutoff_gev: float) -> NDArray[np.float64]` implementing NPA 695 Eq. (74).
- Produces `eta_photoproduction_amplitude(sqrt_s: float, polarization: NDArray, production: ProductionParameters, strong_parameters: ReducedTParameters, strong_t: Callable[[float], NDArray]) -> NDArray[np.complex128]` implementing PRC 73 Eqs. (8)–(9), shape `(2,2)`.
- Produces `eq26_rescattering_loop(sample, event_index, channel_index, source_kernel, intermediate_propagator, transition, production, strong_parameters, context) -> complex128[2,2]`; `source_kernel(q_gev, cos_theta)` returns a spin matrix and `intermediate_propagator(invariant_gev)` returns one complex scalar.
- Produces `_integrate_complex_1d` and `_integrate_complex_2d`, private deterministic Gauss–Legendre helpers that compare base and doubled order and raise contextual errors.

- [ ] **Step 1: Write failing independent numerical tests.** Check the monopole equals `(Lambda^2-m_pi^2)/(Lambda^2-p^2)` and raises at its pole. Compare each complex integral helper with analytic integrals (`int_0^1 exp(ix) dx` and `int_-1^1 int_0^1 (x+i q^2) dq dx`) without using the helper for expected values. Force nonfinite integrands and base/doubled-order disagreement; assert messages contain supplied family/channel/invariant labels.

For Eqs. (8)–(9), inject a deterministic synthetic diagonal `strong_t(w)` and compare KR and meson-pole pieces to independent high-order (`192x192`) Gauss–Legendre test integration at `sqrt_s=1.62 GeV`. Assert exact Table II zero channels stay zero and `KR+MP` changes when either nonzero test component is omitted. Test `eq26_rescattering_loop` with constant source/propagator/transition against an independent direct Eq. (26) integral, and prove channel masses come from the requested six-channel index.

```python
def test_eta_photoproduction_keeps_kr_and_pole_pair(parameters):
    full = eta_photoproduction_amplitude(1.62, EX, parameters, synthetic_t)
    expected = independent_kr(1.62, EX) + independent_mesonic_pole(1.62, EX)
    assert full.shape == (2, 2)
    np.testing.assert_allclose(full, expected, rtol=2e-5, atol=1e-9)
```

Parameterize bool/complex/NaN/infinite/out-of-domain energy, malformed polarization, bad T shape/nonfinite T, cutoff pole, and unsupported branch.

- [ ] **Step 2: Run RED.** `python -m pytest tests/test_production_loops.py -q`. Expected failure: missing loop functions.

- [ ] **Step 3: Implement direct quadrature and Eqs. (8)–(9).** Use `numpy.polynomial.legendre.leggauss`, explicit interval Jacobians, and complex accumulation. Evaluate both configured and doubled orders; accept only when `abs(high-low) <= atol + rtol*abs(high)`. Keep Table II arrays immutable and in six-channel order.

```python
KR_A = np.array([0, -1, 0, 0, np.sqrt(2/3), 0.0])
KR_B = np.array([0, 0, 0, -1/np.sqrt(2), -1/np.sqrt(6), 0.0])
BBM_A = np.array([1/np.sqrt(2), 1, 1/np.sqrt(6), 0, -np.sqrt(2/3), 0.0])
BBM_B = np.array([0, 0, -np.sqrt(2/3), 1/np.sqrt(2), 1/np.sqrt(6), 1.0])
MESON_CHARGE = np.array([0, -1, 0, -1, -1, 0.0])
```

Contract spin dependence with `PAULI`; do not return a scalar shortcut. Evaluate strong T only at its source-prescribed invariant and require `(6,6)` complex finite output.

```python
def eq26_rescattering_loop(
    sample, event_index, channel_index, source_kernel,
    intermediate_propagator, transition, production, strong_parameters,
    context,
):
    return _integrate_complex_2d(
        lambda q, x: _eq26_integrand(
            sample, event_index, channel_index, q, x,
            source_kernel(q, x), intermediate_propagator, transition,
            strong_parameters),
        0.0, production.first_loop_cutoff_gev, -1.0, 1.0,
        settings=production.quadrature, context=context,
    )
```

- [ ] **Step 4: Run GREEN and focused convergence sweep.** Run tests at threshold+`1e-6`, `1.62`, and the model endpoint. Require base/doubled-order agreement; closed channels must not raise merely because momentum is imaginary.

- [ ] **Step 5: Commit owned paths.** Message: `feat(theory): add converged production loops`.

### Task 3: Fig. 6–8 chiral photoproduction families

**Files:**
- Create: `theory/src/graal_theory/amplitudes/chiral_photoproduction.py`
- Create: `theory/tests/test_chiral_photoproduction.py`

**Interfaces:**
- Produces `chiral_contact_amplitude(sample, polarization, production, strong_parameters, strong_t) -> complex128[N,2,2]` for Eq. (21).
- Produces `external_pi0_amplitude(sample, polarization, production, strong_parameters, strong_t) -> complex128[N,2,2]` for Eq. (24), calling the complete Eq. (8)+(9) function.
- Produces `internal_pi0_amplitude(sample, polarization, production, strong_parameters, strong_t) -> complex128[N,2,2]` for Eq. (25), with Fig. 8(c)+(d) inseparable.
- All functions accept `ThreeBodySample`, `NDArray[float64](3,)`, `ProductionParameters`, `ReducedTParameters`, and `Callable[[float], complex128[6,6]]` in that order. Channel masses and decay constants come only from `ReducedTParameters`, never duplicated in the production record.

- [ ] **Step 1: Write coefficient, shape, and independent-limit tests.** Pin PRC 73 Table III arrays exactly:

```python
X1 = np.array([0, np.sqrt(2), 0, 1/2, -1/(2*np.sqrt(3)), 0.0])
Y1 = np.array([0, np.sqrt(2), 0, -1/2, -np.sqrt(3)/2, 0.0])
INTERNAL = {
    1: (-1/np.sqrt(2), -1, 0, 0),
    3: (1/np.sqrt(6), np.sqrt(2/3), 1/np.sqrt(6), -1/np.sqrt(6)),
    4: (1/np.sqrt(6), 0, 1/np.sqrt(6), -1/np.sqrt(2)),
}
```

Use zero/single-entry synthetic T matrices to prove only printed nonzero channels contribute. With `b6d=0,b6f=1`, verify Eq. (21) reduces to the ordinary magnetic term. Check every family returns finite `(N,2,2)` complex arrays, becomes zero when its source coefficient is zeroed, and changes under transverse polarization rotation.

For Eq. (24), monkeypatch/call-count `eta_photoproduction_amplitude` once per event invariant and compare its propagator/spin factor independently. For Eq. (25), compare a fixed 3-event sample to a separate doubled-order direct integration and show removing the pole multiplier changes the result.

- [ ] **Step 2: Run RED.** `python -m pytest tests/test_chiral_photoproduction.py -q`. Expected import failure for the three family functions.

- [ ] **Step 3: Implement Eq. (21), then run its focused tests.** Derive `z=M(eta p)` from sample four-vectors; compute `sum_j (b6d*X1[j]+b6f*Y1[j]) G_j(z) T[j,eta](z)` using existing strong loop conventions. Multiply the spin matrix `sigma dot (k cross epsilon)` and sourced decay constants. Reject samples not ordered `(eta, pi0, proton)`.

```python
spin = np.einsum("aij,a->ij", PAULI, np.cross(k, epsilon))
coefficient = production.b6d * X1 + production.b6f * Y1
g = loop_functions(z, strong_parameters)
t = strong_t(z)
scalar = -1j * np.sum(
    coefficient * production.electric_charge * g * t[:, 2]
    / (4 * strong_parameters.decay_constants_gev[0]
       * np.asarray(strong_parameters.decay_constants_gev)
       * 2 * strong_parameters.baryon_masses_gev[0])
)
result[event] = scalar * spin
```

- [ ] **Step 4: Implement Eq. (24), then run its focused tests.** Use the event pion four-vector and nucleon-energy denominators printed in Eq. (24), complete `eta_photoproduction_amplitude`, and `sigma dot p_pi`. A denominator within `32*eps*scale` raises `ValueError("external_pi0: singular nucleon denominator")`.

```python
eta_photo = eta_photoproduction_amplitude(
    z, epsilon, production, strong_parameters, strong_t)
denominator = nucleon_energy(k) - pion[0] - nucleon_energy(k + pion[1:])
prefactor = ((production.axial_d + production.axial_f)
             / (2 * f_pi) * proton_mass / nucleon_energy(k + pion[1:]))
result[event] = prefactor / denominator * (
    eta_photo @ np.einsum("aij,a->ij", PAULI, -pion[1:]))
```

- [ ] **Step 5: Implement Eq. (25), then run its focused tests.** Sum only channels indices `1,3,4`; implement both baryon denominators, the angle-averaged pion monopole, and the printed `(1-q_on^2/(3 q_on^0 k^0))` pole partner. Reuse Task 2 converged quadrature; error messages name `internal_pi0`, event, channel, and `z`.

```python
for channel in (1, 3, 4):
    a, a_prime, b, b_prime = INTERNAL[channel]
    left = a * (D + F) + b * (D - F)
    right = a_prime * (D + F) + b_prime * (D - F)
    channel_matrix = _integrate_complex_2d(
        lambda q, x: eq25_integrand(
            q, x, event, channel, left, right, strong_t(z)[channel, 2]),
        0.0, production.first_loop_cutoff_gev, -1.0, 1.0,
        settings=production.quadrature,
        context=f"internal_pi0 event={event} channel={channel} z={z}",
    )
    result[event] += channel_matrix
```

- [ ] **Step 6: Run GREEN and commit.** `python -m pytest tests/test_chiral_photoproduction.py tests/test_production_loops.py -q`. Commit message: `feat(theory): add chiral production families`.

### Task 4: Fig. 9 explicit-resonance family

**Files:**
- Create: `theory/src/graal_theory/amplitudes/resonance_photoproduction.py`
- Create: `theory/tests/test_resonance_photoproduction.py`

**Interfaces:**
- Produces `nstar1520_width(energy_gev, production, tree, strong_parameters) -> float` from NPA 695 Eqs. (13)–(16).
- Produces diagnostic kernels `delta1700_pi_delta_kernel(charge_channel, q_gev, cos_theta, event_pion, photon_momentum, polarization, production, tree)`, `nstar1520_pi_delta_kernel(charge_channel, q_gev, cos_theta, event_pion, photon_momentum, polarization, production, tree)`, and `delta_kr_pole_kernel(charge_channel, q_gev, cos_theta, event_pion, photon_momentum, polarization, production, tree)`, each returning `complex128[2,2]` before Eq. (26) rescattering.
- Produces physical `explicit_resonance_amplitude(sample, polarization, production, tree, strong_parameters, strong_t) -> complex128[N,2,2]`, coherently combining Eqs. (28)–(35) inside Eq. (26).

- [ ] **Step 1: Write failing source-identity and width tests.** Pin `f_tilde/g_tilde=(-1.325,0.146)` for Delta*(1700) from existing tree width parameters and `(-1.061,0.640)` for N*(1520). Test Eq. (33) factor `1/(2*sqrt(2))`, Eq. (34) factor `sqrt(2)`, and exact Eq. (35) zero. At N*(1520) pole, assert width equals sum of independently integrated N*pi, Delta*pi, and N*rho pieces within quadrature tolerance; below each threshold its partial width is exactly zero and total is finite/nonnegative.

- [ ] **Step 2: Write failing kernel and Eq. (26) tests.** Compare each kernel on fixed momenta against direct NumPy translations of Eqs. (30)–(32), including the pion pole factor in Eq. (32). Inject single-entry T to prove Eq. (26) uses only channels 1–2 for this family and multiplies the intermediate Delta propagator once. Verify a deliberately phase-flipped kernel changes interference, while individual norms remain unchanged.

- [ ] **Step 3: Run RED.** `python -m pytest tests/test_resonance_photoproduction.py -q`.

- [ ] **Step 4: Implement N*(1520) widths and kernels.** Reuse `p_wave_width`, `breit_wigner`, `TRANSITION`, `PAULI`, and existing Delta*(1700) width. Implement N*pi d-wave `q^5`, finite-width Delta*pi convolution, and N*rho double integral from NPA 695. Kernel formulas preserve complex signs and source factors exactly.

```python
gamma_npi = production.nstar1520_npi_width_gev * (q / q_pole) ** 5
gamma_delta_pi = quad(delta_pi_spectral_integrand, lower, upper, **quad_options)[0]
gamma_nrho = _integrate_complex_2d(
    nrho_integrand, pion_mass, upper_omega1, pion_mass, upper_omega2,
    settings=production.quadrature, context="nstar1520 N-rho width",
).real
gamma = gamma_npi + gamma_delta_pi + gamma_nrho
propagator = breit_wigner(
    sqrt_s, production.nstar1520_mass_gev, gamma)
```

- [ ] **Step 5: Implement Eq. (26) wrapper.** Use first-loop cutoff `1.4 GeV`, base/doubled-order checks, event-specific pion momentum, `z=M(eta p)`, and channel-specific meson/baryon masses. Sum the three kernels coherently into `t_Delta_i` before multiplying `T[i,eta](z)`; never square inside this module.

```python
def source_for(channel):
    return lambda q, x: np.add.reduce((
        delta1700_pi_delta_kernel(
            channel, q, x, pion, k, epsilon, production, tree),
        nstar1520_pi_delta_kernel(
            channel, q, x, pion, k, epsilon, production, tree),
        delta_kr_pole_kernel(
            channel, q, x, pion, k, epsilon, production, tree),
    ))

result[event] = sum(
    eq26_rescattering_loop(
        sample, event, channel,
        source_kernel=source_for(channel),
        intermediate_propagator=delta_propagator,
        transition=strong_t(z)[channel, 2], production=production,
        strong_parameters=strong_parameters,
        context=f"explicit_resonances event={event} channel={channel} z={z}")
    for channel in (0, 1)
)
```

- [ ] **Step 6: Run GREEN, preservation tests, and commit.** Run this module plus `test_delta1700_amplitude.py` and `test_propagators.py`. Commit message: `feat(theory): add explicit resonance production`.

### Task 5: Fig. 10 eta-Delta and K-Sigma* rescattering families

**Files:**
- Create: `theory/src/graal_theory/amplitudes/decuplet_rescattering.py`
- Create: `theory/tests/test_decuplet_rescattering.py`

**Interfaces:**
- Produces `eta_delta_rescattering_amplitude(sample, polarization, production, tree, strong_parameters, strong_t) -> complex128[N,2,2]` for Eq. (39) inserted in Eq. (26), channel 3.
- Produces `k_sigma_star_rescattering_amplitude(sample, polarization, production, tree, strong_parameters, strong_t) -> complex128[N,2,2]` for Eqs. (40)–(42) inserted in Eq. (26): nonzero channel indices 4–5 (paper channels 5–6), with paper channel 4 exactly zero.
- Produces private `_sigma_star_propagator(invariant_mass, production, daughter_masses)` using `36 MeV` rest width and p-wave scaling.

- [ ] **Step 1: Write failing phase/coefficient tests.** Pin Eq. (39) coefficient `-sqrt(2/3) g_eta f_DeltaNpi/m_pi`; verify reuse of `delta1700_eta_delta_vertex` rather than a second Eq. (39) implementation. Pin Eq. (40) factor `1.15*sqrt(24/25)*(D+F)/(2 f_pi)`, Eq. (41) factor `(2D+F)/(5*sqrt(2)*f_pi)`, and Eq. (42) factor `-1.15*e*sqrt(4/3)/25*((D+F)/(2f_pi))^2` in the adopted Butler phase convention.

- [ ] **Step 2: Write failing channel/propagator tests.** Inject one nonzero T entry at a time: eta-Delta uses paper channel 3 (zero-based index 2); K-Sigma* uses paper channels 5–6 (indices 4–5), while paper channel 4 (index 3) remains exactly zero. At Sigma* pole require Breit–Wigner denominator with `0.036 GeV`; below daughter threshold width is zero, above it follows `q^3 M/E`. Compare base/doubled Eq. (26) integrations and require contextual failure on forced nonconvergence.

- [ ] **Step 3: Run RED.** `python -m pytest tests/test_decuplet_rescattering.py -q`.

- [ ] **Step 4: Implement eta-Delta through shared Eq. (39).** Call existing `delta1700_eta_delta_vertex`, then the Eq. (26) loop with channel 3 and intermediate Delta propagator. Do not include Eq. (43)'s external Delta propagator here; Eq. (43) remains a separate seventh family.

```python
eq39 = delta1700_eta_delta_vertex(
    sqrt_s, k, pion_momentum[None, :], epsilon, tree)[0]
result[event] = eq26_rescattering_loop(
    sample, event, channel_index=2,
    source_kernel=lambda q, x: eq39,
    intermediate_propagator=delta_propagator,
    transition=strong_t(z)[2, 2], production=production,
    strong_parameters=strong_parameters,
    context=f"eta_delta event={event} channel=2 z={z}")
```

- [ ] **Step 5: Implement K-Sigma* and inseparable Sigma* KR.** Build Eqs. (40)–(41) with complex `g_K`, add Eq. (42) coherently to paper channel 5, and replace intermediate Delta propagator by Sigma* as directed after Eq. (42). Keep paper channel 4 in an immutable coefficient map as exact zero, but integrate only nonzero paper channels 5–6. The public function has no switch for omitting Eq. (42).

```python
sources = {
    3: np.zeros((2, 2), dtype=np.complex128),
    4: eq40_k_sigma_star(
        pion, k, epsilon, production, tree, strong_parameters)
       + eq42_sigma_star_kr(
        pion, epsilon, production, strong_parameters),
    5: eq41_k_sigma_star(
        pion, k, epsilon, production, tree, strong_parameters),
}
result[event] = sum(
    eq26_rescattering_loop(
        sample, event, channel_index=i,
        source_kernel=lambda q, x, i=i: sources[i],
        intermediate_propagator=sigma_star_propagator,
        transition=strong_t(z)[i, 2], production=production,
        strong_parameters=strong_parameters,
        context=f"k_sigma_star event={event} channel={i} z={z}")
    for i in (4, 5)
)
```

- [ ] **Step 6: Run GREEN and commit.** Run new tests plus existing Delta/tree tests. Commit message: `feat(theory): add decuplet rescattering`.

### Task 6: Seven-family coherent full model

**Files:**
- Create: `theory/src/graal_theory/models/eta_pi0_p_full.py`
- Create: `theory/tests/test_eta_pi0_p_full.py`

**Interfaces:**
- Produces frozen `FullModelParameters(tree: Delta1700Parameters, strong: ReducedTParameters, vector_masses: VectorMasses, production: ProductionParameters)`.
- Produces `EtaPi0PFullModel.from_files(reference_dir: Path) -> EtaPi0PFullModel` loading existing central/reduced/final/VMD records plus Task 1 record.
- Produces `family_amplitudes(sample, polarization) -> Mapping[str, complex128[N,2,2]]` for diagnostics only, with immutable keys `chiral_contact`, `external_pi0`, `internal_pi0`, `explicit_resonances`, `eta_delta_rescattering`, `k_sigma_star_rescattering`, `eq43_tree`.
- Produces physical `amplitude`, `polarized_matrix_element_squared`, and `matrix_element_squared`; physical methods always include all seven families.
- Produces diagnostic `selected_amplitude(sample, polarization, families: tuple[str,...])` and `selected_matrix_element_squared(sample, families: tuple[str,...], polarizations=None)`; invalid/duplicate/empty family selections raise.
- `FullModelParameters.proton_mass_gev` delegates read-only to `tree.proton_mass_gev`, and the model exposes `masses`, so existing `observables.predict_energy` can consume the full physical model by duck typing without modifying dirty observable/CLI code.

- [ ] **Step 1: Write failing construction and shape tests.** Assert composed parameter blocks equal independently loaded blocks and are frozen. Validate sample masses/order, initial energy consistency, unit transverse polarization, family keys, every family shape/dtype/finiteness, and read-only diagnostic mapping/arrays.

- [ ] **Step 2: Write the critical coherence test.** Monkeypatch seven family functions to return fixed complex matrices with cancellation. Assert physical amplitude equals elementwise complex sum and polarized result equals `sum(abs(sum(families))**2)/2`, while explicitly proving it differs from `sum_families sum(abs(family)**2)/2`.

```python
expected_amplitude = sum(families.values())
expected_weight = np.sum(np.abs(expected_amplitude) ** 2, axis=(1, 2)) / 2
np.testing.assert_allclose(model.amplitude(sample, EX), expected_amplitude)
np.testing.assert_allclose(
    model.polarized_matrix_element_squared(sample, EX), expected_weight)
assert not np.allclose(expected_weight, incoherent_weight)
```

- [ ] **Step 3: Write physical/diagnostic boundary tests.** Assert `amplitude` calls every family exactly once and accepts no family-selection argument. Assert `selected_amplitude` and `selected_matrix_element_squared` select only requested diagnostic families, but cannot split KR/pole subterms because those names do not exist. Verify two transverse polarized weights are nonnegative and their mean equals the unpolarized result; verify basis-rotation invariance. Pass the full model to existing `predict_energy` and require a finite physical prediction without changing `observables.py`.

- [ ] **Step 4: Run RED.** `python -m pytest tests/test_eta_pi0_p_full.py -q`.

- [ ] **Step 5: Implement construction and strong-T closure.** Load reduced parameters, replace with final-fit subtractions, load VMD masses, and close:

```python
@property
def proton_mass_gev(self) -> float:
    return self.tree.proton_mass_gev

def strong_t(w_gev: float) -> NDArray[np.complex128]:
    return reconstructed_full_tmatrix(
        w_gev, self.parameters.strong, self.parameters.vector_masses)
```

Call the six new family functions plus existing `tree_amplitude`; use a `MappingProxyType` for diagnostics and mark arrays read-only only after computation.

- [ ] **Step 6: Implement one final spin sum.** `amplitude` performs `np.add.reduce(tuple(families.values()))`; `polarized_matrix_element_squared` validates polarization then computes one spin sum/initial-spin average. `matrix_element_squared` validates an orthonormal transverse basis and averages the two photon states exactly as existing `EtaPi0PModel` does.

```python
def amplitude(self, sample, polarization):
    families = self.family_amplitudes(sample, polarization)
    return np.add.reduce(tuple(families.values()))

def polarized_matrix_element_squared(self, sample, polarization):
    full = self.amplitude(sample, polarization)
    return np.sum(np.abs(full) ** 2, axis=(1, 2)) / 2.0
```

- [ ] **Step 7: Run GREEN and preservation tests; commit.** Run new tests plus `test_eta_pi0_p_model.py`, `test_delta1700_amplitude.py`, and all N*(1535) tests. Commit message: `feat(theory): compose coherent eta pi0 p model`.

### Task 7: Primary-source component and full-model comparisons

**Files:**
- Create: `theory/references/p73_full_production_curves.csv`
- Create: `theory/references/p73_full_production_curves.json`
- Create: `theory/src/graal_theory/full_production_validation.py`
- Create: `theory/tests/test_full_production_validation.py`
- Modify: `theory/tests/test_packaged_references.py`

**Interfaces:**
- Produces `load_full_production_reference(reference_dir: Path) -> Mapping[str, ReferenceCurve]`.
- Produces `compare_full_production(prediction, references) -> FullProductionValidation`, separating `compatible`, `discrepant`, `unresolved`, and `masked_nonconverged` counts.
- Produces `write_full_production_report(output_dir, result, metadata) -> (json_path, markdown_path)` with atomic replacement.

- [ ] **Step 1: Create independent reference records.** Digitize only visible, identifiable strokes needed from PRC 73 Figs. 12–14 and 19. CSV columns are `figure,curve,x_gev,y,reading_error`; JSON records PDF SHA, printed page/figure, axis calibration, curve/line-style mapping, units, reading method, and ambiguity notes. Reuse existing Fig. 14 Eq. (43) and Fig. 19 records instead of duplicating their points; JSON links them by filename.

- [ ] **Step 2: Write failing audit tests.** Assert exact PDF hash, closed columns, monotonic x within each curve, finite nonnegative uncertainties, required line mappings, no duplicate points, and packaging. A deliberately ambiguous record must load as `unresolved`, never `compatible`.

- [ ] **Step 3: Write failing comparison/report tests.** Synthetic curves pin tolerance rule `abs(pred-ref) <= reading_error + numerical_error + 0.20*abs(ref)` (paper quotes roughly 20–25% theory uncertainty). Nonfinite/nonconverged points become masked with reason; zero-reference points use absolute uncertainty only. Report counts must sum to total and preserve model/convention/provenance metadata.

- [ ] **Step 4: Run RED.** `python -m pytest tests/test_full_production_validation.py tests/test_packaged_references.py -q`.

- [ ] **Step 5: Implement strict loader/comparator/writer.** Follow existing `validation.py` records, but keep this increment in a new module. Never interpolate across masked points; compare only overlapping x domains and identify every result by family/figure/energy.

```python
residual = abs(prediction - reference.y)
tolerance = (
    reference.reading_error + numerical_error
    + np.where(reference.y != 0.0, 0.20 * np.abs(reference.y), 0.0)
)
status = np.where(residual <= tolerance, "compatible", "discrepant")
status[~converged] = "masked_nonconverged"
status[reference.unresolved] = "unresolved"
```

Write JSON and Markdown to sibling temporary files in `output_dir`, `fsync`, then `Path.replace`; validate counts and metadata before replacement so a failed run cannot destroy the prior report.

- [ ] **Step 6: Generate baseline comparisons without tuning.** Evaluate isolated Fig. 12 components, Fig. 13 resonance components, Fig. 14 eta-Delta/tree/full/reduced curves, and Fig. 19 total at source energies. For component curves, a private validation-only adapter delegates `masses`/`proton_mass_gev` and calls `selected_matrix_element_squared`; the physical model remains all-family. Persist command/config, Sobol power, quadrature settings, git commit, parameter file hashes, PDF hash, and convention list.

- [ ] **Step 7: Run GREEN and commit.** Commit message: `test(theory): validate coherent production curves`.

### Task 8: Convergence, preservation, inventory, and final review

**Files:**
- Create: `theory/tests/test_full_production_convergence.py`
- Modify: `theory/references/figure4_amplitude_inventory.md`
- Create: `theory/references/full_production_validation.md`

**Interfaces:**
- No new public API. This task gates Increment A and records readiness for Increment B.

- [ ] **Step 1: Add end-to-end convergence tests.** At threshold-adjacent, `E_gamma=1.2 GeV`, and upper publication-grid energies, compare loop base/doubled orders and Sobol powers `p`/`p+1`. Require total cross section change `<1%` and each populated bin carrying at least `1e-4` of total weight `<3%`; otherwise record mask/reason instead of a plotted connection.

- [ ] **Step 2: Add preservation fingerprints.** Store no newly fitted golden parameters. Recompute current Eq. (43) fixed-sample complex amplitude and spectrum before/after full-model imports and assert `rtol=1e-12`; invoke existing reduced, pion-corrected, and reconstructed-full strong-T tests unchanged.

- [ ] **Step 3: Update amplitude inventory.** For all seven families record source equation/figure, implementation module/function, parameter source record, unit test, convergence status, comparison curve/status, and remaining discrepancy. State explicitly: “code complete” is independent of “curve compatible.”

- [ ] **Step 4: Write validation summary.** `full_production_validation.md` reports component/full compatible, discrepant, unresolved, and masked counts; numerical settings; runtime; convention baseline; no-tuning statement; and exact handoff API for Increment B. Do not claim reproduced Ajaka Figure 4 in this increment.

- [ ] **Step 5: Run focused and full verification.** From `theory/`:

```bash
python -m pytest tests/test_production_parameters.py tests/test_production_loops.py \
  tests/test_chiral_photoproduction.py tests/test_resonance_photoproduction.py \
  tests/test_decuplet_rescattering.py tests/test_eta_pi0_p_full.py \
  tests/test_full_production_validation.py tests/test_full_production_convergence.py -q
python -m pytest -q
```

Expected: all tests pass, no warnings hiding nonfinite values, and existing test count only increases.

- [ ] **Step 6: Request fresh code/science review.** Reviewer checks equations/signs/channel indices/gauge pairing first, then numerical convergence/error context, then repository isolation. Resolve all blocking findings and rerun full suite.

- [ ] **Step 7: Stage only Task 8 paths and commit.** Message: `docs(theory): complete coherent production audit`.

## Increment A Exit Gate

- All seven families source-linked and independently callable for diagnostics.
- Physical API always sums seven complex spin matrices before squaring.
- Required gauge partners cannot be separated in physical configuration.
- Direct loop integration converged at representative thresholds/resonances/endpoints.
- Eq. (43) and three strong-T variants preserved.
- Figs. 12–14/19 comparisons recorded without tuning, with discrepancies and ambiguity explicit.
- Full model accepts immutable parameter replacement, enabling Increment B integration over Ajaka's 4x3 bins and later Increment C covariance-aware fitting.
