# N*(1535) ππN Correction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add and validate P65/P73's physical real-axis `ππN` kernel correction as a separately labeled intermediate charge-`+1` strong amplitude.

**Architecture:** A small `ππN` module owns P65's energy-dependent vertices and directly integrated three-body loop. A separate final-fit input record and a charge-`+1` adapter add P73 Eq. (6) to the existing WT kernel, then reuse the existing meson–baryon loops and linear solve. Reduced-T and Eq. (43) behavior remain unchanged; VMD and photoproduction are later milestones.

**Tech Stack:** Python ≥3.10, NumPy ≥1.24, SciPy ≥1.10 for an independent quadrature test, pytest ≥7.4, existing provenance helpers. Work on `main` as requested; preserve unrelated dirty files.

**Spec:** `theory/docs/2026-10-02-nstar1535-pipi-n-design.md`. Source audit: `theory/references/nstar_1535_tmatrix_source_map.md`.

## Global Constraints

- GeV throughout. `v₁₁,v₃₁`: `GeV⁻³`; `G̃`: `GeV⁵`; `δV,T`: `GeV⁻¹`.
- Use P65 Eqs. (25)–(30) and P73 Eq. (6), not P70's low-energy constant-vertex approximation. `Re G̃=0`.
- Baseline common loop masses: PDG-2024 charged pion `0.13957039 GeV` and `(M_p+M_n)/2` from the existing sourced mass record. These are implementation choices, not paper-specified masses.
- At/below `M_N+2m_π`, `G̃=0`. Above threshold compare 48×48 and 96×96 Gauss–Legendre integration; accept only if `|G̃₉₆−G̃₄₈| ≤ max(10⁻¹² GeV⁵, 10⁻³|G̃₉₆|)`.
- Use a separate final-fit subtraction record with `μ=1.2 GeV` and `(a_πN,a_ηN,a_KΛ,a_KΣ)=(2.0,0.1,1.5,−2.8)`. Do not alter the reduced record `(2.0,0.2,1.6,−2.8)`.
- `ππN`-only is neither reduced nor full. No VMD, pole search, curve matching, Figure 4 output, Stage 07/08 integration, or change to existing generated outputs.
- Do not edit already-dirty `theory/README.md`, `theory/pyproject.toml`, CLI, Eq. (43) model, or Stage 07/08 files. Existing `pyproject.toml` already packages `references/*.json`.

## File ownership

| File | Responsibility |
| --- | --- |
| `theory/src/graal_theory/amplitudes/pipi_n.py` | P65 polynomials, physical-domain `Im G̃`, convergence guard. |
| `theory/tests/test_pipi_n.py` | Polynomial, threshold, sign, domain, normalization, quadrature, validation tests. |
| `theory/references/nstar1535_final_subtractions.json` | P65 Eq. (28) final-fit values with source locators. |
| `theory/src/graal_theory/amplitudes/nstar1535_final_fit.py` | Validate final record and return a new numerical parameter set. |
| `theory/src/graal_theory/amplitudes/nstar1535_pipi_n.py` | P73 Eq. (6) charge-`+1` correction and intermediate T. |
| `theory/src/graal_theory/amplitudes/_reduced_t_core.py` | Share the existing guarded six-channel linear solve. |
| `theory/tests/test_nstar1535_pipi_n.py` | Provenance, block structure, absorption, T equation, reduced regression. |
| `theory/references/pipi_n_loop_comparison.md` | Source/hash, Fig. 11 scale/shape check, common-mass sensitivity and scope. |

## Review Focus

1. `bool`, NaN, complex, negative, zero or out-of-domain energy/mass inputs must raise `ValueError` rather than produce a misleading zero: Task 1 tests.
2. Very near threshold, the loop must be exactly zero at/below threshold and finite/nonpositive just above it: Task 1 tests.
3. A failed 48/96 quadrature comparison must raise, not return an unconverged value: Task 1 test.
4. Wrong unit/source or `bool`/nonfinite final subtraction must fail before matrix evaluation; reduced inputs remain unchanged: Task 2 tests.
5. P73 correction must touch only the pion block, retain ordinary (not absolute) squares, and not be checked with closed six-channel unitarity: Task 3 tests.

---

### Task 1: P65 vertices and physical three-body loop

**Files:**
- Create: `theory/src/graal_theory/amplitudes/pipi_n.py`
- Create: `theory/tests/test_pipi_n.py`

**Interfaces:**
- Produces: `pipi_n_potentials(w_gev: float, pion_mass_gev: float) -> tuple[float, float]`; `pipi_n_loop(w_gev: float, pion_mass_gev: float, nucleon_mass_gev: float) -> complex`.
- `pipi_n_loop` returns pure imaginary `GeV⁵`, not the two-body `G_i` of P65 Eq. (6).

- [ ] **Step 1: Write failing tests for source polynomials, threshold, input validation, and sign.**

```python
def test_p65_polynomial_anchors():
    m = 0.13957039
    assert pipi_n_potentials(1.213, m)[0] == pytest.approx(4 / m**3)
    assert pipi_n_potentials(1.470, m)[1] == pytest.approx(0, abs=1e-12)

def test_loop_threshold_and_absorptive_sign():
    m, nucleon = 0.13957039, (0.93827208816 + 0.93956542052) / 2
    threshold = nucleon + 2*m
    assert pipi_n_loop(threshold - 1e-5, m, nucleon) == 0j
    assert pipi_n_loop(threshold, m, nucleon) == 0j
    for w in (threshold + 1e-4, 1.45, 1.65):
        value = pipi_n_loop(w, m, nucleon)
        assert np.isfinite(value)
        assert value.real == 0
        assert value.imag < 0

@pytest.mark.parametrize("bad", [True, 0, -1, np.nan, np.inf, 1+0j])
def test_invalid_w_or_mass_rejected(bad):
    with pytest.raises(ValueError):
        pipi_n_loop(bad, 0.13957039, 0.939)
    with pytest.raises(ValueError):
        pipi_n_loop(1.45, bad, 0.939)
    with pytest.raises(ValueError):
        pipi_n_loop(1.45, 0.13957039, bad)

def test_loop_domain_ends_at_1p70_gev():
    with pytest.raises(ValueError, match="W"):
        pipi_n_loop(1.701, 0.13957039, 0.939)
```

- [ ] **Step 2: Run red test.** From `theory/`: `python -m pytest -q tests/test_pipi_n.py`. Expected: import fails because `pipi_n.py` does not exist.

- [ ] **Step 3: Implement P65 Eqs. (26), (29), (30) with explicit physical bounds.** Validate real finite scalar inputs before testing threshold. With `s23=W²+m²−2Wω₁`, integrate `ω₁` from `m` to `(W²+m²−(M+m)²)/(2W)`. At each `ω₁`, compute `E₂*=(s23+m²−M²)/(2√s23)`, `q₂*=√λ(s23,m²,M²)/(2√s23)`, `q₁=√(ω₁²−m²)`, then `ω₂±=((W−ω₁)E₂*±q₁q₂*)/√s23`. Map a second Gauss–Legendre rule to `[ω₂−,ω₂+]`; each term includes both interval Jacobians. The integrand is `B=M²+2q₁²+2q₂²−(W−ω₁−ω₂)²`; multiply by `−M/[4(2π)³]`. Clip only tiny negative radicands from floating-point roundoff, never broad unphysical regions. A private `_loop_at_order(..., order)` permits the test to compare orders.

```python
def _finite_positive(value: float, name: str) -> float:
    if (isinstance(value, (bool, np.bool_))
            or not isinstance(value, (int, float, np.integer, np.floating))):
        raise ValueError(f"{name} must be a finite positive real scalar")
    result = float(value)
    if not np.isfinite(result) or result <= 0:
        raise ValueError(f"{name} must be a finite positive real scalar")
    return result

def pipi_n_potentials(w_gev: float, pion_mass_gev: float) -> tuple[float, float]:
    w, m = _finite_positive(w_gev, "W"), _finite_positive(pion_mass_gev, "m_pi")
    x = (w - 1.470) / m
    v11 = (4.0 + (w - 1.213) / m) / m**3
    v31 = (-5.60*x - 1.05*x**2 + 1.77*x**3 + 0.66*x**4
           - 0.17*x**5 - 0.07*x**6) / m**3
    return v11, v31

def _loop_at_order(w: float, m: float, nucleon: float, order: int) -> float:
    nodes, weights = np.polynomial.legendre.leggauss(order)
    e1_max = (w*w + m*m - (nucleon+m)**2) / (2*w)
    scale = (e1_max-m)/2
    e1 = m + scale*(nodes+1)
    q1 = np.sqrt(np.maximum(e1*e1-m*m, 0))
    s23 = w*w + m*m - 2*w*e1
    root = np.sqrt(s23)
    lam = (s23-(nucleon+m)**2)*(s23-(nucleon-m)**2)
    q2_star = np.sqrt(np.maximum(lam, 0))/(2*root)
    e2_star = (s23+m*m-nucleon*nucleon)/(2*root)
    center = (w-e1)*e2_star/root
    half_width = q1*q2_star/root
    e2 = center[:, None] + half_width[:, None]*nodes[None, :]
    q2_sq = np.maximum(e2*e2-m*m, 0)
    e_nucleon = w-e1[:, None]-e2
    b = (nucleon*nucleon + 2*q1[:, None]**2 + 2*q2_sq
         - e_nucleon**2)
    if np.min(b) < -1e-12:
        raise ValueError("unphysical pi pi N integration domain")
    integral = scale*np.sum(weights[:, None]*weights[None, :]
                            *half_width[:, None]*np.maximum(b, 0))
    return float(-nucleon*integral/(4*(2*np.pi)**3))

def pipi_n_loop(w_gev: float, pion_mass_gev: float,
                nucleon_mass_gev: float) -> complex:
    w = _finite_positive(w_gev, "W")
    if w > 1.70:
        raise ValueError("W outside pi pi N real-axis domain")
    m = _finite_positive(pion_mass_gev, "m_pi")
    nucleon = _finite_positive(nucleon_mass_gev, "M_N")
    if w <= nucleon + 2*m:
        return 0j
    low, high = _loop_at_order(w, m, nucleon, 48), _loop_at_order(w, m, nucleon, 96)
    if abs(high - low) > max(1e-12, 1e-3*abs(high)):
        raise ValueError("pi pi N loop quadrature did not converge")
    return complex(0.0, high)
```

- [ ] **Step 4: Independently check integration and forced failure.** At `W=(1.25,1.45,1.65)`, use SciPy adaptive integration over the direct triangle `m≤ω₁≤W−M−m`, `m≤ω₂≤W−M−ω₁`; set integrand to zero unless `|A|≤1` with `A` from P65 Eq. (27). This domain and angular mask are independent of the production code's boosted-`πN` bounds. Split at the kinematic strip boundaries if SciPy's error estimate warns; compare with `pipi_n_loop(...).imag` within `5e-3` relative or `2e-12 GeV⁵` absolute. Check MeV conversion by confirming `G[GeV⁵]×10¹⁵` equals the same formula evaluated with all inputs in MeV. Monkeypatch `_loop_at_order` so 48/96 values disagree and assert the public function raises the convergence error.

```python
from scipy.integrate import quad

def triangle_reference(w, m, nucleon):
    def integrand(e2, e1):
        q1_sq, q2_sq = e1*e1-m*m, e2*e2-m*m
        if q1_sq <= 0 or q2_sq <= 0:
            return 0.0
        e_nucleon = w-e1-e2
        if e_nucleon < nucleon:
            return 0.0
        q1, q2 = np.sqrt(q1_sq), np.sqrt(q2_sq)
        a = (e_nucleon**2-nucleon**2-q1_sq-q2_sq)/(2*q1*q2)
        if abs(a) > 1:
            return 0.0
        return nucleon**2+2*q1_sq+2*q2_sq-e_nucleon**2

    def inner(e1):
        return quad(lambda e2: integrand(e2, e1), m, w-nucleon-e1,
                    epsabs=1e-12, epsrel=1e-3, limit=300)[0]

    area = quad(inner, m, w-nucleon-m,
                epsabs=1e-12, epsrel=1e-3, limit=300)[0]
    return -nucleon*area/(4*(2*np.pi)**3)

def test_nonconverged_loop_is_rejected(monkeypatch):
    monkeypatch.setattr(pipi_n, "_loop_at_order",
                        lambda w, m, nucleon, order: -1e-7 if order == 48 else -2e-7)
    with pytest.raises(ValueError, match="did not converge"):
        pipi_n_loop(1.45, 0.13957039, 0.939)
```

- [ ] **Step 5: Run green tests and commit only these files.** `python -m pytest -q tests/test_pipi_n.py`; expected PASS. `git add -- src/graal_theory/amplitudes/pipi_n.py tests/test_pipi_n.py`; `git commit -m "feat(theory): add pi pi N loop"`.

### Task 2: Source-linked final subtraction set

**Files:**
- Create: `theory/references/nstar1535_final_subtractions.json`
- Create: `theory/src/graal_theory/amplitudes/nstar1535_final_fit.py`
- Create or modify: `theory/tests/test_nstar1535_pipi_n.py`
- Modify: `theory/tests/test_packaged_references.py`

**Interfaces:**
- Consumes: `ReducedTParameters`, `load_reduced_parameters` from `nstar1535_reduced.py`, and provenance helpers from `sources.py`.
- Produces: `load_final_fit_parameters(base: ReducedTParameters, parameter_path: Path, source_path: Path) -> ReducedTParameters` (new immutable numerical value; class name is retained for compatibility, not a claim that final values are reduced).

- [ ] **Step 1: Write failing source, value, immutability, and package-resource tests.**

```python
def test_final_fit_is_distinct_and_sourced():
    base = load_reduced_parameters(REDUCED_JSON, SOURCES)
    final = load_final_fit_parameters(base, FINAL_JSON, SOURCES)
    assert base.subtraction_constants == (2, 2, .2, -2.8, 1.6, -2.8)
    assert final.subtraction_constants == (2, 2, .1, -2.8, 1.5, -2.8)
    assert final.mu_gev == base.mu_gev == 1.2
    assert final.meson_masses_gev == base.meson_masses_gev
    assert files("graal_theory.references").joinpath(
        "nstar1535_final_subtractions.json").is_file()

@pytest.mark.parametrize("field,value", [("unit", "MeV"), ("value", True),
                                          ("value", float("nan")),
                                          ("source_key", "missing")])
def test_final_fit_rejects_bad_entry(tmp_path, field, value):
    raw = json.loads(FINAL_JSON.read_text())
    raw["a_etaN"][field] = value
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="a_etaN"):
        load_final_fit_parameters(load_reduced_parameters(REDUCED_JSON, SOURCES), bad, SOURCES)

def test_final_fit_rejects_missing_key_and_wrong_mu(tmp_path):
    base = load_reduced_parameters(REDUCED_JSON, SOURCES)
    raw = json.loads(FINAL_JSON.read_text())
    del raw["a_KSigma"]
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="names"):
        load_final_fit_parameters(base, bad, SOURCES)
    raw = json.loads(FINAL_JSON.read_text())
    raw["mu"]["value"] = 1.1
    bad.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="mu"):
        load_final_fit_parameters(base, bad, SOURCES)
```

- [ ] **Step 2: Run red test.** `python -m pytest -q tests/test_nstar1535_pipi_n.py`; expected import failure for `nstar1535_final_fit`.

- [ ] **Step 3: Add final values and validated loader.** JSON has exactly `mu`, `a_piN`, `a_etaN`, `a_KLambda`, `a_KSigma`; each is `{value, unit, source_key, locator}` with source key `inoue_2002`, locator `Eq. (28)`, `mu` unit `GeV`, others `1`. Values are `1.2, 2.0, 0.1, 1.5, -2.8` respectively. Reject missing/extra keys, wrong units/source, bool, complex, nonfinite, and nonpositive `mu`. Use `PhysicalParameter`/`SourceRef`, then `dataclasses.replace(base, mu_gev=..., subtraction_constants=(a_piN,a_piN,a_etaN,a_KSigma,a_KLambda,a_KSigma))`. Reject `mu` mismatching `base.mu_gev` so the two records cannot silently encode incompatible scales. No copy of PDG masses is needed. Add the filename to `test_packaged_references.py`.

```python
def _validated_final_values(raw: dict, sources: dict) -> dict[str, float]:
    values = {}
    for name in ("mu", "a_piN", "a_etaN", "a_KLambda", "a_KSigma"):
        entry = raw[name]
        unit = "GeV" if name == "mu" else "1"
        if (not isinstance(entry, dict)
                or set(entry) != {"value", "unit", "source_key", "locator"}
                or entry["unit"] != unit
                or entry["source_key"] != "inoue_2002"
                or not isinstance(entry["locator"], str)
                or not entry["locator"].strip()
                or not isinstance(entry["value"], (int, float))
                or isinstance(entry["value"], bool)):
            raise ValueError(f"invalid final fit entry {name}")
        source = sources["inoue_2002"]
        ref = SourceRef("inoue_2002", source["doi"], entry["locator"])
        values[name] = float(PhysicalParameter(
            name, float(entry["value"]), unit, ref).value)
    if values["mu"] <= 0:
        raise ValueError("final fit mu must be positive")
    return values

def load_final_fit_parameters(base: ReducedTParameters, parameter_path: Path,
                              source_path: Path) -> ReducedTParameters:
    raw = json.loads(parameter_path.read_text(encoding="utf-8"))
    required = {"mu", "a_piN", "a_etaN", "a_KLambda", "a_KSigma"}
    if not isinstance(raw, dict) or set(raw) != required:
        raise ValueError("final fit parameter names differ from source schema")
    values = _validated_final_values(raw, load_source_registry(source_path))
    if values["mu"] != base.mu_gev:
        raise ValueError("final fit mu differs from base mu")
    return replace(base, subtraction_constants=(values["a_piN"], values["a_piN"],
        values["a_etaN"], values["a_KSigma"], values["a_KLambda"], values["a_KSigma"]))
```

- [ ] **Step 4: Run green tests and commit only these files.** `python -m pytest -q tests/test_nstar1535_pipi_n.py tests/test_packaged_references.py`; expected PASS. `git add -- references/nstar1535_final_subtractions.json src/graal_theory/amplitudes/nstar1535_final_fit.py tests/test_nstar1535_pipi_n.py tests/test_packaged_references.py`; `git commit -m "feat(theory): source final Nstar fit inputs"`.

### Task 3: P73 pion-block correction and intermediate T

**Files:**
- Create: `theory/src/graal_theory/amplitudes/nstar1535_pipi_n.py`
- Modify: `theory/src/graal_theory/amplitudes/_reduced_t_core.py`
- Modify: `theory/tests/test_nstar1535_pipi_n.py`
- Run unchanged: `theory/tests/test_nstar1535_reduced.py`, `theory/tests/test_nstar1535_charge_zero.py`, `theory/tests/test_eta_pi0_p_model.py`

**Interfaces:**
- Consumes: `pipi_n_potentials`, `pipi_n_loop`, `ReducedTParameters`, `wt_kernel`, `loop_functions`.
- Produces: `pipi_n_kernel_correction(w_gev: float, pion_mass_gev: float, nucleon_mass_gev: float) -> NDArray[np.complex128]`; `pipi_n_tmatrix(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.complex128]`; shared `_reduced_t_core.solve_tmatrix(v, g) -> NDArray[np.complex128]`.

- [ ] **Step 1: Write failing equation/block/T tests.** Compute `A,B,D` directly in test from P73 Eq. (6), independently of production helper. The `2×2` correction equals `G̃ [[A²+B², AB+BD],[AB+BD,B²+D²]]`; other rows/columns are exactly zero. Its imaginary part must be negative semidefinite. `pipi_n_tmatrix` must be symmetric, finite, solve its matrix equation, and differ from a matrix using the same final-fit constants without `ππN`.

```python
def test_p73_eq6_block_and_absorption():
    w, m, nucleon = 1.55, 0.13957039, (0.93827208816+0.93956542052)/2
    v11, v31 = pipi_n_potentials(w, m)
    a = -np.sqrt(2)*v31/3 - v11/(3*np.sqrt(2))
    b = (v31-v11)/3
    d = -v31/(3*np.sqrt(2)) - np.sqrt(2)*v11/3
    expected = pipi_n_loop(w, m, nucleon)*np.array(
        [[a*a+b*b, a*b+b*d], [a*b+b*d, b*b+d*d]])
    delta = pipi_n_kernel_correction(w, m, nucleon)
    np.testing.assert_allclose(delta[:2, :2], expected, rtol=1e-12)
    np.testing.assert_array_equal(delta[2:, :], 0)
    np.testing.assert_array_equal(delta[:, 2:], 0)
    assert np.max(np.linalg.eigvalsh(delta.imag)) <= 1e-12

def test_p73_uses_products_not_absolute_squares(monkeypatch):
    # Synthetic complex vertices distinguish a*a from abs(a)**2.
    monkeypatch.setattr(nstar1535_pipi_n, "pipi_n_potentials",
                        lambda w, m: (1+2j, 3-1j))
    monkeypatch.setattr(nstar1535_pipi_n, "pipi_n_loop",
                        lambda w, m, nucleon: -1j)
    v11, v31 = 1+2j, 3-1j
    a = -np.sqrt(2)*v31/3 - v11/(3*np.sqrt(2))
    b = (v31-v11)/3
    d = -v31/(3*np.sqrt(2)) - np.sqrt(2)*v11/3
    delta = pipi_n_kernel_correction(1.55, .13957039, .939)
    assert delta[0, 0] == pytest.approx(-1j*(a*a+b*b))
    assert delta[0, 1] == pytest.approx(-1j*(a*b+b*d))
    assert delta[1, 1] == pytest.approx(-1j*(b*b+d*d))

def test_intermediate_t_equation_and_reduced_regression():
    base = load_reduced_parameters(REDUCED_JSON, SOURCES)
    final = load_final_fit_parameters(base, FINAL_JSON, SOURCES)
    w = 1.55
    delta = pipi_n_kernel_correction(
        w, final.meson_masses_gev[1],
        (final.baryon_masses_gev[0]+final.baryon_masses_gev[1])/2)
    v, g, t = wt_kernel(w, final)+delta, loop_functions(w, final), pipi_n_tmatrix(w, final)
    np.testing.assert_allclose((np.eye(6)-v*g[None, :]) @ t, v, rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose(t, t.T, rtol=1e-10, atol=1e-10)
    assert np.max(abs(t - reduced_tmatrix(w, final))) > 1e-6
    assert np.all(np.isfinite(t))
```

- [ ] **Step 2: Run red test.** `python -m pytest -q tests/test_nstar1535_pipi_n.py`; expected import failure for `nstar1535_pipi_n`.

- [ ] **Step 3: Reuse guarded solve and implement correction.** Extract the condition-number check and `np.linalg.solve` body of `_reduced_t_core.reduced_tmatrix` verbatim into `solve_tmatrix(v,g)`. Keep `reduced_tmatrix` calling `solve_tmatrix(wt_kernel(...), loop_functions(...))`; do not change its numerical inputs. `pipi_n_tmatrix` validates W with `_reduced_t_core.validated_energy`, chooses common baseline `m_pi=parameters.meson_masses_gev[1]`, `M_N=(parameters.baryon_masses_gev[0]+parameters.baryon_masses_gev[1])/2`, then adds the correction once and uses `solve_tmatrix`.

```python
def solve_tmatrix(v: NDArray[np.float64] | NDArray[np.complex128],
                  g: NDArray[np.complex128]) -> NDArray[np.complex128]:
    size = v.shape[0]
    system = np.eye(size, dtype=complex) - v*g[None, :]
    try:
        condition = np.linalg.cond(system)
        if not np.isfinite(condition) or condition > 1e12:
            raise ValueError("strong T linear system is ill-conditioned")
        t = np.linalg.solve(system, v)
    except np.linalg.LinAlgError as exc:
        raise ValueError("strong T linear solve is singular") from exc
    if not np.all(np.isfinite(t)):
        raise ValueError("strong T is nonfinite")
    return np.asarray(t, dtype=np.complex128)

# In the existing reduced_tmatrix, replace only its inline solve with:
# return solve_tmatrix(v, g)

def pipi_n_kernel_correction(w_gev: float, pion_mass_gev: float,
                             nucleon_mass_gev: float) -> NDArray[np.complex128]:
    v11, v31 = pipi_n_potentials(w_gev, pion_mass_gev)
    g = pipi_n_loop(w_gev, pion_mass_gev, nucleon_mass_gev)
    a = -np.sqrt(2)*v31/3 - v11/(3*np.sqrt(2))
    b = (v31-v11)/3
    d = -v31/(3*np.sqrt(2)) - np.sqrt(2)*v11/3
    delta = np.zeros((6, 6), dtype=np.complex128)
    delta[:2, :2] = g*np.array([[a*a+b*b, a*b+b*d],
                                [a*b+b*d, b*b+d*d]])
    return delta

def pipi_n_tmatrix(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.complex128]:
    w = _reduced_t_core.validated_energy(w_gev, parameters)
    m = parameters.meson_masses_gev[1]
    nucleon = (parameters.baryon_masses_gev[0]+parameters.baryon_masses_gev[1])/2
    v = wt_kernel(w, parameters) + pipi_n_kernel_correction(w, m, nucleon)
    return _reduced_t_core.solve_tmatrix(v, loop_functions(w, parameters))
```

- [ ] **Step 4: Run focused and preservation tests; commit only these files.** `python -m pytest -q tests/test_nstar1535_pipi_n.py tests/test_nstar1535_reduced.py tests/test_nstar1535_charge_zero.py tests/test_eta_pi0_p_model.py`; expected PASS. `git add -- src/graal_theory/amplitudes/nstar1535_pipi_n.py src/graal_theory/amplitudes/_reduced_t_core.py tests/test_nstar1535_pipi_n.py`; `git commit -m "feat(theory): add P73 pi pi N kernel"`.

### Task 4: External check, mass sensitivity, and milestone handoff

**Files:**
- Create: `theory/references/pipi_n_loop_comparison.md`
- Run unchanged: all `theory/tests/`

**Interfaces:**
- Consumes: `pipi_n_loop`, `pipi_n_tmatrix`, source PDFs, parameter records.
- Produces: auditable comparison note only; no Figure 4 curve or public CLI.

- [ ] **Step 1: Compute a frozen readout at `W=(1.25,1.35,1.45,1.55,1.65) GeV`.** Run from `theory/`:

```bash
PYTHONPATH=src python -c 'from graal_theory.amplitudes.pipi_n import pipi_n_loop; m=.13957039; n=(.93827208816+.93956542052)/2; print([(w, pipi_n_loop(w,m,n).imag/1e-7) for w in (1.25,1.35,1.45,1.55,1.65)])'
```

Record those values in units `10⁸ MeV⁵` (`1 unit = 10⁻⁷ GeV⁵`) with the command, source hashes, the 48/96 difference, and the fact that the common masses are PDG choices. Compare the sign, rise, and approximate scale to P65 Fig. 11 on printed p. 035204-8, stating visual-reading uncertainty; no fitted normalization factor. If Fig. 11 disagrees materially, report mismatch and do not call the loop validated.

- [ ] **Step 2: Record mass-choice sensitivity without changing baseline.** At the same energy grid, evaluate charged pion with proton and neutron separately, and neutral pion with the nucleon average. Report maximal absolute and relative changes versus baseline, including how thresholds shift. This is an uncertainty/convention diagnostic, not a refit. Do not change the baseline without a new source decision.

- [ ] **Step 3: Run complete theory suite and inspect scope.** From `theory/`: `python -m pytest -q`. From repository root: `git diff --check`; `git status --short`. Confirm no Stage 07/08 files were touched by this milestone and no existing dirty files were staged. If tests fail, diagnose and fix the owning task before reporting success.

- [ ] **Step 4: Commit comparison note alone and report boundary.** From `theory/`: `git add -- references/pipi_n_loop_comparison.md`; `git commit -m "docs(theory): audit pi pi N loop"`. State explicitly: `ππN` intermediate complete/incomplete per evidence; VMD remains next, then coherent production, twelve panels, and native-bin fit. No full-model claim.
