# Reduced N*(1535) T Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (- [ ]) syntax for tracking.

**Goal:** Calculate and verify the real-axis charge-+1 six-channel reduced N*(1535) transition matrix without changing the existing eta pi0 p photoproduction model.

**Architecture:** A reaction-specific module owns fixed channel coefficients, source-linked inputs, the WT kernel, physical-sheet loop, and matrix solve. A separate reference module converts charge amplitudes to the plotted S11 convention and compares them with an independently read PRC 73 Fig. 1 dashed line. Nothing is wired into Eq. (43), Stage 07/08, or the package CLI.

**Tech Stack:** Python >=3.10, NumPy >=1.24, pytest >=7.4, existing graal_theory.sources provenance types, Poppler for PDF inspection. Work directly on main, as requested.

**Spec:** theory/docs/2026-10-01-nstar1535-reduced-tmatrix-design.md. Equation audit: theory/references/nstar_1535_tmatrix_source_map.md.

## Global Constraints

- Reduced means no t-channel vector correction and no pi pi N correction; use P65 Eq. (9), not Eq. (28), subtraction constants.
- Channel order: (pi0 p, pi+ n, eta p, K+ Sigma0, K+ Lambda, K0 Sigma+). Array indices zero-based; citations one-based.
- Internal energy unit GeV; scalar finite real W from lightest pi N threshold through 1.70 GeV; complex128 T has GeV^-1 units.
- Use P73 Table I charge coefficients and P65 Eqs. (5)-(7), (9), (10). No curve-fitted parameters.
- Use source-linked PDG 2024 masses, including source locators; do not claim these are authors' unpublished original numerical mass list.
- Keep EtaPi0PModel, Eq. (43), Stage 07/08, existing generated outputs and CLI unchanged. Avoid all currently dirty theory files.
- No new dependency, generic channel interface, vector correction, pi pi N loop, pole search, or Ajaka twelve-panel output.

## File ownership

| File | Responsibility |
| --- | --- |
| theory/references/sources.json | Add P65 bibliographic key only. |
| theory/references/nstar1535_reduced_parameters.json | Freeze 18 source-linked scalar inputs. |
| theory/src/graal_theory/amplitudes/nstar1535_reduced.py | Validate inputs; fixed C; WT kernel; G; reduced T. |
| theory/tests/test_nstar1535_reduced.py | Parameter, kernel, loop, threshold, solve, and unitarity tests. |
| theory/references/p73_fig1_reduced.csv and .json | Independent dashed-line readings and trace metadata. |
| theory/src/graal_theory/reduced_t_reference.py | S11 projection, audited reference loading, residual computation. |
| theory/tests/test_reduced_t_reference.py | Phase/projection, reference integrity, and comparison tests. |
| theory/references/p73_fig1_reduced_comparison.md | Measured comparison and claim boundary. |

## Review Focus

1. Malformed, nonfinite, negative, or wrong-unit mass/fit input must fail before matrix evaluation — Task 1 tests.
2. Energies just below/on/above each relevant threshold must stay finite, with closed-channel imaginary part zero and open-channel sign correct — Task 2 tests.
3. Physical-sheet complex-log choice must reproduce P65 Eq. (7); a branch mistake must fail a numerical test — Task 2 tests.
4. Ill-conditioned/singular matrix solve must raise a clear error, never return silent NaNs — Task 2 tests.
5. Wrong PDF bytes, mixed experimental symbols, reversed isospin phase, or overconfident Fig. 1 agreement must be caught/documented — Task 3 tests and visual audit.

---

### Task 1: Versioned reduced inputs and WT kernel

**Files:**
- Modify: theory/references/sources.json
- Create: theory/references/nstar1535_reduced_parameters.json
- Create: theory/src/graal_theory/amplitudes/nstar1535_reduced.py
- Create: theory/tests/test_nstar1535_reduced.py

**Interfaces:**
- Consumes: SourceRef, PhysicalParameter, load_source_registry from graal_theory.sources.
- Produces: CHANNELS; C_COEFFICIENTS; ReducedTParameters; load_reduced_parameters(parameter_path: Path, source_path: Path) -> ReducedTParameters; wt_kernel(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.float64].

- [ ] **Step 1: Write failing tests for parameter identity, malformed input, and a WT matrix element.**

Use these cases in theory/tests/test_nstar1535_reduced.py. PARAM and SOURCES point to packaged theory/references files via Path(__file__).resolve().parents[1] / "references". Use copy.deepcopy/json for the malformed-fixture write; pytest tmp_path owns that file.

~~~python
def test_reduced_inputs_and_channel_order():
    p = load_reduced_parameters(PARAM, SOURCES)
    assert CHANNELS == ("pi0_p", "pi_plus_n", "eta_p",
                        "k_plus_sigma0", "k_plus_lambda", "k0_sigma_plus")
    assert p.mu_gev == 1.2
    assert p.subtraction_constants == (2.0, 2.0, 0.2, -2.8, 1.6, -2.8)
    np.testing.assert_allclose(p.decay_constants_gev,
                               (.093, .093, .093 * 1.3,
                                .093 * 1.22, .093 * 1.22, .093 * 1.22))

def test_wt_charge_coefficients_and_symmetry():
    p = load_reduced_parameters(PARAM, SOURCES)
    v = wt_kernel(1.5, p)
    np.testing.assert_allclose(v, v.T, atol=1e-13)
    assert C_COEFFICIENTS[0, 1] == pytest.approx(np.sqrt(2))
    assert C_COEFFICIENTS[0, 2] == C_COEFFICIENTS[1, 2] == 0
    e = (1.5**2 + p.baryon_masses_gev[0]**2 -
         p.meson_masses_gev[0]**2) / (2 * 1.5)
    ej = (1.5**2 + p.baryon_masses_gev[1]**2 -
          p.meson_masses_gev[1]**2) / (2 * 1.5)
    expected = (-np.sqrt(2) * (3.0 - p.baryon_masses_gev[0] -
                p.baryon_masses_gev[1]) / (4 * .093**2) *
                np.sqrt((p.baryon_masses_gev[0] + e) /
                        (2 * p.baryon_masses_gev[0])) *
                np.sqrt((p.baryon_masses_gev[1] + ej) /
                        (2 * p.baryon_masses_gev[1])))
    assert v[0, 1] == pytest.approx(expected)

def test_reduced_inputs_reject_bad_mass_unit_and_value(tmp_path):
    raw = json.loads(PARAM.read_text())
    raw["neutron_mass"]["unit"] = "MeV"
    changed = tmp_path / "wrong-unit.json"
    changed.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="neutron_mass"):
        load_reduced_parameters(changed, SOURCES)
    raw["neutron_mass"]["unit"] = "GeV"
    raw["neutron_mass"]["value"] = -1
    changed.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="neutron_mass"):
        load_reduced_parameters(changed, SOURCES)

def test_reduced_inputs_reject_nonfinite_unknown_source_and_missing_key(tmp_path):
    original = json.loads(PARAM.read_text())
    changed = tmp_path / "bad.json"
    for field, replacement in (("value", float("nan")),
                               ("source_key", "not_a_source")):
        raw = copy.deepcopy(original)
        raw["a_piN"][field] = replacement
        changed.write_text(json.dumps(raw))
        with pytest.raises(ValueError, match="a_piN"):
            load_reduced_parameters(changed, SOURCES)
    raw = copy.deepcopy(original)
    del raw["a_piN"]
    changed.write_text(json.dumps(raw))
    with pytest.raises(ValueError, match="names"):
        load_reduced_parameters(changed, SOURCES)
~~~

- [ ] **Step 2: Run red test.**

Run from theory: python -m pytest -q tests/test_nstar1535_reduced.py

Expected: collection fails because graal_theory.amplitudes.nstar1535_reduced does not yet exist.

- [ ] **Step 3: Add exact source-linked inputs.**

Add "inoue_2002" to sources.json with DOI 10.1103/PhysRevC.65.035204 and citation "T. Inoue, E. Oset, M. J. Vicente Vacas, Physical Review C 65, 035204 (2002)". Use existing "pdg_2024" for masses. Create JSON entries in the established {value,unit,source_key,locator} format:

| Name | Value | Unit | Source locator |
| --- | ---: | --- | --- |
| pi0_mass | 0.1349768 | GeV | PDG 2024 meson summary, pi0 |
| charged_pion_mass | 0.13957039 | GeV | PDG 2024 meson summary, pi+/- |
| eta_mass | 0.547862 | GeV | PDG 2024 meson summary, eta |
| charged_kaon_mass | 0.493677 | GeV | PDG 2024 meson summary, K+/- |
| neutral_kaon_mass | 0.497611 | GeV | PDG 2024 meson summary, K0 |
| proton_mass | 0.93827208816 | GeV | PDG 2024 baryon summary, proton |
| neutron_mass | 0.93956542052 | GeV | PDG 2024 baryon summary, neutron |
| sigma0_mass | 1.192642 | GeV | PDG 2024 baryon summary, Sigma0 |
| sigma_plus_mass | 1.18937 | GeV | PDG 2024 baryon summary, Sigma+ |
| lambda_mass | 1.115683 | GeV | PDG 2024 baryon summary, Lambda |
| f_pi | 0.093 | GeV | P65 p. 035204-2 after Eq. (5) |
| f_k_over_f_pi | 1.22 | 1 | P65 p. 035204-2 after Eq. (5) |
| f_eta_over_f_pi | 1.3 | 1 | P65 p. 035204-2 after Eq. (5) |
| mu | 1.2 | GeV | P65 Eq. (9) |
| a_piN | 2.0 | 1 | P65 Eq. (9) |
| a_etaN | 0.2 | 1 | P65 Eq. (9) |
| a_KLambda | 1.6 | 1 | P65 Eq. (9) |
| a_KSigma | -2.8 | 1 | P65 Eq. (9) |

The ten mass values are explicit PDG 2024 choices, not a claim about unprinted 2002 input precision. Use source_key pdg_2024 for masses and inoue_2002 for the other eight. No change to central_parameters.json.

- [ ] **Step 4: Implement loader, fixed C, and WT kernel.**

Use a frozen dataclass with tuple fields meson_masses_gev, baryon_masses_gev, decay_constants_gev, subtraction_constants, and mu_gev; validate six-element tuple lengths, finite values, positive masses/f/mu, and real finite subtraction constants in __post_init__. In load_reduced_parameters, require exactly the 18 names above and each entry's four keys; compare unit to the table, ensure source key exists, construct PhysicalParameter with SourceRef, then assemble channel tuples. The three core operations are:

~~~python
@dataclass(frozen=True)
class ReducedTParameters:
    meson_masses_gev: tuple[float, ...]
    baryon_masses_gev: tuple[float, ...]
    decay_constants_gev: tuple[float, ...]
    subtraction_constants: tuple[float, ...]
    mu_gev: float

    def __post_init__(self) -> None:
        for name in ("meson_masses_gev", "baryon_masses_gev",
                     "decay_constants_gev", "subtraction_constants"):
            values = getattr(self, name)
            if len(values) != 6 or not np.all(np.isfinite(values)):
                raise ValueError(f"{name} requires six finite values")
            if name != "subtraction_constants" and any(v <= 0 for v in values):
                raise ValueError(f"{name} requires positive values")
        if not np.isfinite(self.mu_gev) or self.mu_gev <= 0:
            raise ValueError("mu_gev must be finite and positive")

_MASS_NAMES = ("pi0_mass", "charged_pion_mass", "eta_mass",
               "charged_kaon_mass", "neutral_kaon_mass", "proton_mass",
               "neutron_mass", "sigma0_mass", "sigma_plus_mass", "lambda_mass")
_FIT_UNITS = {"f_pi": "GeV", "f_k_over_f_pi": "1",
              "f_eta_over_f_pi": "1", "mu": "GeV",
              "a_piN": "1", "a_etaN": "1", "a_KLambda": "1", "a_KSigma": "1"}
_UNITS = {**dict.fromkeys(_MASS_NAMES, "GeV"), **_FIT_UNITS}

def load_reduced_parameters(parameter_path: Path, source_path: Path) -> ReducedTParameters:
    raw = json.loads(parameter_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != set(_UNITS):
        raise ValueError("reduced parameter names differ from source schema")
    sources = load_source_registry(source_path)
    values: dict[str, float] = {}
    for name, expected_unit in _UNITS.items():
        entry = raw[name]
        if (not isinstance(entry, dict)
                or set(entry) != {"value", "unit", "source_key", "locator"}
                or entry["unit"] != expected_unit):
            raise ValueError(f"invalid unit or source fields for {name}")
        key = entry["source_key"]
        if key not in sources or not isinstance(entry["value"], (int, float)) or isinstance(entry["value"], bool):
            raise ValueError(f"invalid source or value for {name}")
        source = sources[key]
        ref = SourceRef(key, source.get("doi") or source.get("arxiv"),
                        entry["locator"])
        values[name] = float(PhysicalParameter(name, float(entry["value"]),
                                               expected_unit, ref).value)
        if name in _MASS_NAMES and values[name] <= 0:
            raise ValueError(f"{name} must be positive")
    f_pi = values["f_pi"]
    f_k = f_pi * values["f_k_over_f_pi"]
    f_eta = f_pi * values["f_eta_over_f_pi"]
    return ReducedTParameters(
        meson_masses_gev=(values["pi0_mass"], values["charged_pion_mass"],
                          values["eta_mass"], values["charged_kaon_mass"],
                          values["charged_kaon_mass"], values["neutral_kaon_mass"]),
        baryon_masses_gev=(values["proton_mass"], values["neutron_mass"],
                           values["proton_mass"], values["sigma0_mass"],
                           values["lambda_mass"], values["sigma_plus_mass"]),
        decay_constants_gev=(f_pi, f_pi, f_eta, f_k, f_k, f_k),
        subtraction_constants=(values["a_piN"], values["a_piN"],
                               values["a_etaN"], values["a_KSigma"],
                               values["a_KLambda"], values["a_KSigma"]),
        mu_gev=values["mu"],
    )

CHANNELS = ("pi0_p", "pi_plus_n", "eta_p",
            "k_plus_sigma0", "k_plus_lambda", "k0_sigma_plus")
C_COEFFICIENTS = np.array([
    [0, np.sqrt(2), 0, -.5, -np.sqrt(3)/2, 1/np.sqrt(2)],
    [np.sqrt(2), 1, 0, 1/np.sqrt(2), -np.sqrt(3/2), 0],
    [0, 0, 0, -np.sqrt(3)/2, -1.5, -np.sqrt(3/2)],
    [-.5, 1/np.sqrt(2), -np.sqrt(3)/2, 0, 0, np.sqrt(2)],
    [-np.sqrt(3)/2, -np.sqrt(3/2), -1.5, 0, 0, 0],
    [1/np.sqrt(2), 0, -np.sqrt(3/2), np.sqrt(2), 0, 1],
], dtype=float)
C_COEFFICIENTS.setflags(write=False)

def _validated_energy(w_gev: float, parameters: ReducedTParameters) -> float:
    if isinstance(w_gev, bool) or not isinstance(w_gev, (int, float, np.integer, np.floating)):
        raise ValueError("W must be a finite real scalar")
    w = float(w_gev)
    threshold = min(np.add(parameters.meson_masses_gev,
                           parameters.baryon_masses_gev))
    if not np.isfinite(w) or not threshold <= w <= 1.70:
        raise ValueError("W outside reduced real-axis domain")
    return w

def wt_kernel(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.float64]:
    w = _validated_energy(w_gev, parameters)
    m = np.asarray(parameters.meson_masses_gev)
    baryon = np.asarray(parameters.baryon_masses_gev)
    f = np.asarray(parameters.decay_constants_gev)
    e = (w*w + baryon*baryon - m*m) / (2*w)
    norm = np.sqrt((baryon + e) / (2*baryon))
    return (-C_COEFFICIENTS * (2*w - baryon[:, None] - baryon[None, :])
            * norm[:, None] * norm[None, :]
            / (4*f[:, None]*f[None, :]))
~~~

_validated_energy requires a finite non-bool scalar from min(meson+baryon) through 1.70 GeV, with a ValueError naming W for invalid input. Treat C as immutable internally (e.g. read-only array) so callers cannot silently alter source coefficients.

- [ ] **Step 5: Run green and focused parameter checks.**

Run from theory: python -m pytest -q tests/test_nstar1535_reduced.py tests/test_sources.py tests/test_packaged_references.py

Expected: all pass. Also inspect the exact source values and packaged JSON path; no existing tree-loader behavior changes.

- [ ] **Step 6: Commit only Task 1 paths.**

~~~bash
git add theory/references/sources.json theory/references/nstar1535_reduced_parameters.json theory/src/graal_theory/amplitudes/nstar1535_reduced.py theory/tests/test_nstar1535_reduced.py
git diff --cached --check
git commit -m "feat(theory): add reduced N-star WT kernel"
~~~

### Task 2: Physical-sheet loop and on-shell reduced T

**Files:**
- Modify: theory/src/graal_theory/amplitudes/nstar1535_reduced.py
- Modify: theory/tests/test_nstar1535_reduced.py

**Interfaces:**
- Consumes: ReducedTParameters and wt_kernel from Task 1.
- Produces: loop_functions(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.complex128]; reduced_tmatrix(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.complex128].

- [ ] **Step 1: Add failing loop, threshold, solve, and unitarity tests.**

Add these cases. Use q_i = sqrt((W²-(M_i+m_i)²)*(W²-(M_i-m_i)²))/(2W), and rho_i = M_i*q_i/(4*pi*W) for an open channel.

~~~python
def test_loop_imaginary_part_eq7_and_closed_channels():
    p = load_reduced_parameters(PARAM, SOURCES)
    w = 1.50
    g = loop_functions(w, p)
    for i in range(6):
        m, baryon = p.meson_masses_gev[i], p.baryon_masses_gev[i]
        if w > m + baryon:
            q = np.sqrt((w*w-(m+baryon)**2)*(w*w-(m-baryon)**2))/(2*w)
            assert g[i].imag == pytest.approx(-baryon*q/(4*np.pi*w), abs=1e-11)
        else:
            assert abs(g[i].imag) < 1e-11

def test_loop_finite_across_thresholds():
    p = load_reduced_parameters(PARAM, SOURCES)
    thresholds = sorted(set(np.add(p.meson_masses_gev, p.baryon_masses_gev)))
    for threshold in thresholds[1:]:
        if threshold < 1.70:
            for w in (threshold-1e-6, threshold, threshold+1e-6):
                assert np.all(np.isfinite(loop_functions(w, p)))

def test_t_symmetry_coupled_transition_and_unitarity():
    p = load_reduced_parameters(PARAM, SOURCES)
    w = 1.55
    t = reduced_tmatrix(w, p)
    assert t.shape == (6, 6)
    np.testing.assert_allclose(t, t.T, rtol=1e-10, atol=1e-10)
    assert abs(t[0, 2]) > 1e-8
    rho = np.zeros(6)
    for i, (m, baryon) in enumerate(zip(p.meson_masses_gev, p.baryon_masses_gev)):
        if w > m + baryon:
            q = np.sqrt((w*w-(m+baryon)**2)*(w*w-(m-baryon)**2))/(2*w)
            rho[i] = baryon*q/(4*np.pi*w)
    np.testing.assert_allclose((t-t.conj().T)/(2j),
                               -t @ np.diag(rho) @ t.conj().T,
                               rtol=2e-9, atol=2e-9)

def test_t_satisfies_both_linear_equations():
    p = load_reduced_parameters(PARAM, SOURCES)
    w = 1.55
    v, g, t = wt_kernel(w, p), loop_functions(w, p), reduced_tmatrix(w, p)
    np.testing.assert_allclose((np.eye(6)-v*g[None, :]) @ t, v, rtol=1e-11)
    np.testing.assert_allclose(t @ (np.eye(6)-g[:, None]*v), v, rtol=1e-11)

@pytest.mark.parametrize("w", [0.5, 1.701, float("nan"), float("inf"), True])
def test_invalid_real_axis_energy_is_rejected(w):
    p = load_reduced_parameters(PARAM, SOURCES)
    with pytest.raises(ValueError, match="W"):
        reduced_tmatrix(w, p)

def test_singular_matrix_is_reported(monkeypatch):
    p = load_reduced_parameters(PARAM, SOURCES)
    def fail(*args, **kwargs):
        raise np.linalg.LinAlgError("singular")
    monkeypatch.setattr(nstar1535_reduced.np.linalg, "solve", fail)
    with pytest.raises(ValueError, match="singular"):
        reduced_tmatrix(1.55, p)
~~~

Import the nstar1535_reduced module itself for the monkeypatch target.

- [ ] **Step 2: Run red test.**

Run from theory: python -m pytest -q tests/test_nstar1535_reduced.py

Expected: collection succeeds, newly imported loop_functions/reduced_tmatrix fail or new tests fail because functions are absent.

- [ ] **Step 3: Implement P65 Eq. (6) loop and P73 Eq. (5) solve.**

Use complex128 principal logs and the positive-imaginary subthreshold momentum, then verify Eq. (7) rather than forcing its sign after evaluation:

~~~python
def loop_functions(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.complex128]:
    w = _validated_energy(w_gev, parameters)
    s = w*w
    m = np.asarray(parameters.meson_masses_gev)
    baryon = np.asarray(parameters.baryon_masses_gev)
    a = np.asarray(parameters.subtraction_constants)
    delta = baryon*baryon - m*m
    q = np.sqrt(((s-(baryon+m)**2)*(s-(baryon-m)**2)).astype(complex))/(2*w)
    logs = (np.log(s-delta+2*w*q) + np.log(s+delta+2*w*q)
            - np.log(-s+delta+2*w*q) - np.log(-s-delta+2*w*q))
    return (2*baryon/(4*np.pi)**2 *
            (a + np.log(m*m/parameters.mu_gev**2)
             + (delta+s)/(2*s)*np.log(baryon*baryon/(m*m))
             + q/w*logs)).astype(np.complex128)

def reduced_tmatrix(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.complex128]:
    v = wt_kernel(w_gev, parameters)
    g = loop_functions(w_gev, parameters)
    try:
        t = np.linalg.solve(np.eye(6, dtype=complex)-v*g[None, :], v)
    except np.linalg.LinAlgError as exc:
        raise ValueError("reduced T linear solve is singular") from exc
    if not np.all(np.isfinite(t)):
        raise ValueError("reduced T is nonfinite")
    return np.asarray(t, dtype=np.complex128)
~~~

If the physical-sheet tests fail, inspect q/log branches using P65 Eq. (7); do not flip the output sign or add a fitted offset. A clear failure is better than an ad hoc fix.

- [ ] **Step 4: Run green and full standalone theory suite.**

Run from theory: python -m pytest -q tests/test_nstar1535_reduced.py

Expected: all focused tests pass. Then run from theory: python -m pytest -q

Expected: full theory suite passes; note unrelated pre-existing failures distinctly if present.

- [ ] **Step 5: Commit only Task 2 paths.**

~~~bash
git add theory/src/graal_theory/amplitudes/nstar1535_reduced.py theory/tests/test_nstar1535_reduced.py
git diff --cached --check
git commit -m "feat(theory): solve reduced N-star T"
~~~

### Task 3: Signed S11 projection and published reduced comparison

**Files:**
- Create: theory/src/graal_theory/reduced_t_reference.py
- Create: theory/tests/test_reduced_t_reference.py
- Create: theory/references/p73_fig1_reduced.csv
- Create: theory/references/p73_fig1_reduced.json
- Create: theory/references/p73_fig1_reduced_comparison.md

**Interfaces:**
- Consumes: ReducedTParameters and reduced_tmatrix from Task 2.
- Produces: isospin_half_s11_eta(w_gev: float, parameters: ReducedTParameters) -> complex; load_fig1_reduced(csv_path: Path, metadata_path: Path, pdf_path: Path) -> tuple[Fig1Point, ...]; compare_fig1_reduced(parameters: ReducedTParameters, points: tuple[Fig1Point, ...]) -> list[dict[str, float]].

- [ ] **Step 1: Write failing projection and source-integrity tests.**

Use the P65 phase note |pi+> = -|1,1> and standard Clebsch-Gordan states. In the physical charge basis, the I=1/2 vector is (+1/sqrt(3), +sqrt(2/3)); the P73 pi N C block gives eigenvalue 2. Define the dimensionless S11 by applying P65 Eq. (10) to each charged initial channel, then combining them.

~~~python
def test_isospin_half_phase_is_fixed_by_charge_basis():
    u = np.array([1/np.sqrt(3), np.sqrt(2/3)])
    np.testing.assert_allclose(C_COEFFICIENTS[:2, :2] @ u, 2*u)
    p = load_reduced_parameters(PARAM, SOURCES)
    w = 1.54
    t = reduced_tmatrix(w, p)
    rho = []
    for i in (0, 1, 2):
        m, baryon = p.meson_masses_gev[i], p.baryon_masses_gev[i]
        q = np.sqrt((w*w-(m+baryon)**2)*(w*w-(m-baryon)**2))/(2*w)
        rho.append(baryon*q/(4*np.pi*w))
    expected = -np.sqrt(rho[2]) * (
        u[0]*np.sqrt(rho[0])*t[0, 2] +
        u[1]*np.sqrt(rho[1])*t[1, 2])
    assert isospin_half_s11_eta(w, p) == pytest.approx(expected)

def test_fig1_reference_rejects_changed_pdf(tmp_path):
    altered = tmp_path / "wrong.pdf"
    altered.write_bytes(b"not PRC 73")
    with pytest.raises(ValueError, match="PDF"):
        load_fig1_reduced(FIG1_CSV, FIG1_META, altered)

def test_fig1_reference_has_signed_both_components():
    points = load_fig1_reduced(FIG1_CSV, FIG1_META, P73_PDF)
    assert [p.energy_gev for p in points] == pytest.approx(
        [1.50, 1.52, 1.54, 1.56, 1.58, 1.60, 1.62, 1.64])
    assert all(np.isfinite((p.real_s11, p.imag_s11, p.reading_error)).all()
               and p.reading_error > 0 for p in points)
    assert points[0].real_s11 > 0 and points[-1].real_s11 < 0
    assert all(p.imag_s11 >= 0 for p in points)
~~~

Define P73_PDF as repository-root / "tmp/pdfs/10.1103@PhysRevC.73.045209.pdf"; the known SHA-256 is 19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb.

- [ ] **Step 2: Run red test.**

Run from theory: python -m pytest -q tests/test_reduced_t_reference.py

Expected: new reference module/data are absent.

- [ ] **Step 3: Implement projection and strict reference loading.**

Fig1Point fields: energy_gev, real_s11, imag_s11, reading_error. CSV columns have those exact names and only eight predeclared energies. JSON metadata must state source_pdf_sha256, source_page=3, printed_page="045209-3", figure=1, curve="dashed: reduced without t-channel vector exchange and pi pi N", trace_method, axis_calibration, and uncertainty_method. Reject missing fields, wrong PDF hash, nonfinite values, nonpositive error, duplicate/nonincreasing energies, and any changed grid.

~~~python
def isospin_half_s11_eta(w_gev: float, parameters: ReducedTParameters) -> complex:
    t = reduced_tmatrix(w_gev, parameters)
    rho = np.zeros(3)
    for i in range(3):
        m = parameters.meson_masses_gev[i]
        baryon = parameters.baryon_masses_gev[i]
        if w_gev <= m + baryon:
            raise ValueError("S11 eta projection requires open pi N and eta p channels")
        q = np.sqrt((w_gev*w_gev-(m+baryon)**2) *
                    (w_gev*w_gev-(m-baryon)**2))/(2*w_gev)
        rho[i] = baryon*q/(4*np.pi*w_gev)
    return complex(-np.sqrt(rho[2]) *
                   (np.sqrt(rho[0]/3)*t[0, 2] +
                    np.sqrt(2*rho[1]/3)*t[1, 2]))

@dataclass(frozen=True)
class Fig1Point:
    energy_gev: float
    real_s11: float
    imag_s11: float
    reading_error: float

_FIG1_GRID = (1.50, 1.52, 1.54, 1.56, 1.58, 1.60, 1.62, 1.64)
_FIG1_COLUMNS = ("energy_gev", "real_s11", "imag_s11", "reading_error")

def load_fig1_reduced(
    csv_path: Path, metadata_path: Path, pdf_path: Path,
) -> tuple[Fig1Point, ...]:
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if (not isinstance(metadata, dict) or metadata.get("figure") != 1
            or metadata.get("source_page") != 3
            or metadata.get("printed_page") != "045209-3"
            or metadata.get("curve") !=
            "dashed: reduced without t-channel vector exchange and pi pi N"
            or not isinstance(metadata.get("axis_calibration"), dict)
            or not metadata["axis_calibration"]
            or any(not isinstance(metadata.get(key), str)
                   or not metadata[key].strip()
                   for key in ("trace_method", "uncertainty_method"))):
        raise ValueError("invalid PRC 73 Figure 1 metadata")
    digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    if metadata.get("source_pdf_sha256") != digest:
        raise ValueError("PDF digest differs from reviewed PRC 73 source")
    with csv_path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != _FIG1_COLUMNS:
            raise ValueError("invalid Figure 1 CSV columns")
        rows = list(reader)
    if len(rows) != len(_FIG1_GRID):
        raise ValueError("Figure 1 needs eight predeclared energies")
    points = []
    for row, energy in zip(rows, _FIG1_GRID):
        if set(row) != set(_FIG1_COLUMNS):
            raise ValueError("invalid Figure 1 CSV row")
        point = Fig1Point(*(float(row[key]) for key in _FIG1_COLUMNS))
        if (not np.isclose(point.energy_gev, energy, rtol=0, atol=1e-10)
                or not np.all(np.isfinite(tuple(vars(point).values())))
                or point.reading_error < 0.02):
            raise ValueError("invalid Figure 1 point")
        points.append(point)
    return tuple(points)

def compare_fig1_reduced(
    parameters: ReducedTParameters, points: tuple[Fig1Point, ...],
) -> list[dict[str, float]]:
    result = []
    for point in points:
        predicted = isospin_half_s11_eta(point.energy_gev, parameters)
        result.append({
            "energy_gev": point.energy_gev,
            "predicted_real": predicted.real, "predicted_imag": predicted.imag,
            "reference_real": point.real_s11, "reference_imag": point.imag_s11,
            "residual_real": predicted.real-point.real_s11,
            "residual_imag": predicted.imag-point.imag_s11,
            "reading_error": point.reading_error,
        })
    return result
~~~

The comparator never changes parameters or uses observed values to calculate T.

- [ ] **Step 4: Independently read Fig. 1 dashed strokes and freeze metadata.**

Run Poppler against PDF page 3, preferably vector extraction:

~~~bash
pdftocairo -f 3 -l 3 -svg ../tmp/pdfs/10.1103@PhysRevC.73.045209.pdf /private/tmp/p73_fig1_reduced.svg
~~~

Inspect dashed paths separate from solid paths and black data circles, and cross-check a 400-dpi raster. Calibrate each axis from printed ticks, then read both panels at W = 1500, 1520, 1540, 1560, 1580, 1600, 1620, 1640 MeV. Write actual signed readings to CSV; record vector/raster method, affine tick coordinates, PDF digest, source page, stroke overlap, and a conservative absolute reading_error (one value per point; use at least 0.02 unless a larger overlap error is justified). Do not read model output before freezing reference. If the line cannot be separated, record which energies are unreadable; do not fabricate points or claim a complete reference.

- [ ] **Step 5: Run green reference tests, calculate residuals, and write report.**

Run from theory: python -m pytest -q tests/test_reduced_t_reference.py

Expected: all reference/projection tests pass. Use this inspection command from theory to print the model/reference table, then copy its actual numeric output into p73_fig1_reduced_comparison.md:

~~~bash
python -c 'from pathlib import Path; from graal_theory.amplitudes.nstar1535_reduced import load_reduced_parameters; from graal_theory.reduced_t_reference import load_fig1_reduced, compare_fig1_reduced; root=Path("."); p=load_reduced_parameters(root/"references/nstar1535_reduced_parameters.json",root/"references/sources.json"); pts=load_fig1_reduced(root/"references/p73_fig1_reduced.csv",root/"references/p73_fig1_reduced.json",root/"../tmp/pdfs/10.1103@PhysRevC.73.045209.pdf"); [print(row) for row in compare_fig1_reduced(p,pts)]'
~~~

Report the exact comparison command, both real and imaginary residuals, reading bounds, PDG 2024 mass caveat, charge-to-isospin phase derivation, P65 Eq. (10) normalization, and hashes of P65 PDF, P73 PDF, parameter JSON, and reference CSV. State "within reading bound" only if every absolute real and imaginary residual is no larger than that point's recorded reading_error; otherwise state "discrepant" and list failing points. Either status describes this chosen PDG input set, not exact recovery of unprinted 2002 masses. If comparing signs is not defensible after inspection, document evidence and status "convention-blocked"; do not force a pass. Compare against Fig. 1 dashed only, not Fig. 15 full. Run full theory suite from theory: python -m pytest -q.

- [ ] **Step 6: Commit only Task 3 paths.**

~~~bash
git add theory/src/graal_theory/reduced_t_reference.py theory/tests/test_reduced_t_reference.py theory/references/p73_fig1_reduced.csv theory/references/p73_fig1_reduced.json theory/references/p73_fig1_reduced_comparison.md
git diff --cached --check
git commit -m "test(theory): compare reduced S11 source"
~~~

## Final proof and handoff

Run from theory: python -m pytest -q. Run at repository root: git diff --check and git status --short. Inspect commit ranges and unchanged EtaPi0PModel/Stage 07/08 paths. Report the number of focused/full tests, numerical agreement or discrepancy at each published point, exact model scope, and unresolved mass/phase limitations. No coherent-amplitude or twelve-panel reproduction claim follows from these tests.
