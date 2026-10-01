# Reduced N*(1535) Charge-Basis Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Compute the P65 charge-zero reduced six-channel amplitude, preserve the P73 charge-`+1` calculation, and compare both against the frozen P73 Fig. 1 dashed trace without fitting.

**Architecture:** A private numerical core receives one immutable six-channel parameter record and one fixed coefficient matrix. Existing charge-`+1` public functions remain wrappers with unchanged signatures; a separate charge-zero module owns P65 Table I order, coefficients, and source-linked mass mapping. Reference code owns isospin projection and residuals, not the physics kernel.

**Tech Stack:** Python >=3.10, NumPy >=1.24, pytest >=7.4; existing source registry and packaged reference files. Work on `main`, as requested; no new dependency or worktree.

**Spec:** `theory/docs/2026-10-01-nstar1535-charge-basis-design.md`. Primary-source audit: `theory/references/nstar_1535_tmatrix_source_map.md`; mass uncertainty: `theory/references/nstar1535_mass_input_audit.md`.

## Global Constraints

- Reduced means P65 Sec. II A only: Eqs. (5)-(7), (9), (10); `f_pi=93 MeV`, `f_K/f_pi=1.22`, `f_eta/f_pi=1.3`, `mu=1200 MeV`, `(a_piN,a_etaN,a_KLambda,a_KSigma)=(2.0,0.2,1.6,-2.8)`. Never substitute P65 Eq. (28).
- Charge zero uses **P65 Table I** order `(K+ Sigma-, K0 Sigma0, K0 Lambda, pi- p, pi0 n, eta n)`, not the different prose order. Charge `+1` retains P73 order `(pi0 p, pi+ n, eta p, K+ Sigma0, K+ Lambda, K0 Sigma+)`.
- Internal energy GeV. `W` must be a finite real scalar from the basis's lightest physical threshold through `1.70 GeV`; `V,T` have `GeV^-1`, `G` has `GeV`, `S11` is dimensionless.
- Charge-zero `C` comes from P65 Table I, PDF page 2, printed `035204-2`; charge-`+1` `C` stays P73 Table I. Both arrays read-only.
- Reuse source-linked PDG 2024 species masses; add only `Sigma-` with its own locator. Keep `theory/references/nstar1535_reduced_parameters.json` schema and charge-`+1` public API/results unchanged. Modern masses are not claimed to be unpublished author inputs.
- Reference is the existing eight-point `p73_fig1_reduced.csv`, guarded by its existing PDF/CSV hashes. Do not redigitize, fit, tune a sign, or revise reading bounds.
- No full strong model, VMD, `pi pi N`, photon-production amplitude, Ajaka panels, Stage 07/08 wiring, optimizer, or fit to our data. Preserve dirty user files outside task ownership.

## File ownership and interfaces

| File | Responsibility |
| --- | --- |
| `theory/src/graal_theory/amplitudes/_reduced_t_core.py` | Shared WT, physical-sheet loop, energy guard and matrix solve; receives fixed `C` and immutable parameters. |
| `theory/src/graal_theory/amplitudes/nstar1535_reduced.py` | Existing charge-`+1` constants, loader, record and unchanged public wrapper signatures. |
| `theory/references/nstar1535_charge_zero_extra.json` | One PDG-sourced `sigma_minus_mass` input; no duplication of the 18 existing inputs. |
| `theory/src/graal_theory/amplitudes/nstar1535_charge_zero.py` | P65 Table I channels/`C`, explicit charge-zero parameter mapping and thin wrappers. |
| `theory/src/graal_theory/reduced_t_reference.py` | Existing Fig. 1 loader and `+1` comparison, plus charge-zero projection/comparison. |
| `theory/tests/test_nstar1535_reduced.py` | Frozen charge-`+1` numerical grid and core-delegation regression. |
| `theory/docs/2026-10-01-nstar1535-charge-basis-plan.md` | This approved execution record; committed with Task 1. |
| `theory/tests/test_nstar1535_charge_zero.py` | Charge-zero inputs, P65 table, symmetry, thresholds, loop sign, unitarity, solve and malformed input. |
| `theory/tests/test_reduced_t_reference.py` | CG phase, Eq. (10), both eight-point residual paths and convention guard. |
| `theory/references/p73_fig1_reduced_comparison.md` | Reproducible two-basis residuals, thresholds, bound exceedances and limits of inference. |

## Review Focus

1. P65 prose order accidentally paired with Table I values: Task 2 asserts complete ordered matrix and six mapped mass pairs.
2. `Sigma-` JSON with wrong unit, source, nonfinite/complex/bool value, extra field or mutable input: Task 2 rejects each before matrix evaluation.
3. Energy exactly at and just across a threshold, especially closed strange channels: Task 2 checks finite loops, zero closed-channel imaginary part and P65 Eq. (7) open-channel sign.
4. A singular/ill-conditioned charge-zero solve or broken two-body unitarity: Task 2 checks explicit equations, condition error and unitarity identity.
5. Charge-state/`eta N` phase ambiguity, altered Fig. 1 trace or false agreement claim: Task 3 checks CG eigenvector, Eq. (10), frozen hash loader and per-component reading-bound flags; report labels signed comparison conditional on stated phase.

---

### Task 1: Freeze charge-`+1` numbers and extract numerical core

**Files:**
- Create: `theory/src/graal_theory/amplitudes/_reduced_t_core.py`
- Modify: `theory/src/graal_theory/amplitudes/nstar1535_reduced.py`
- Modify: `theory/tests/test_nstar1535_reduced.py`

**Interfaces:**
- Consumes: existing `ReducedTParameters`, existing immutable `C_COEFFICIENTS`.
- Produces: private `validated_energy(w_gev, parameters) -> float`, `wt_kernel(w_gev, parameters, coefficients) -> NDArray[np.float64]`, `loop_functions(w_gev, parameters) -> NDArray[np.complex128]`, `reduced_tmatrix(w_gev, parameters, coefficients) -> NDArray[np.complex128]`. Existing public four function names/signatures remain unchanged.

- [ ] **Step 1: Add charge-`+1` numeric regression test before refactor.** Append to `test_nstar1535_reduced.py`:

```python
def test_charge_plus_one_grid_is_frozen():
    from graal_theory.reduced_t_reference import isospin_half_s11_eta
    p = load_reduced_parameters(PARAM, SOURCES)
    energies = (1.50, 1.52, 1.54, 1.56, 1.58, 1.60, 1.62, 1.64)
    expected = np.array([
        [ 0.208470845706157, 0.240612778280716],
        [ 0.137447699010282, 0.422724541038566],
        [-0.0899104594703734, 0.432547480238677],
        [-0.190358055793633, 0.266178397794420],
        [-0.167720733393300, 0.141591721442651],
        [-0.127123075987937, 0.0768778655603441],
        [-0.0989879586984333, 0.0374499912385641],
        [-0.0816296402031595, 0.00666205708376796],
    ])
    actual = np.array([[z.real, z.imag] for w in energies
                       for z in (isospin_half_s11_eta(w, p),)])
    np.testing.assert_allclose(actual, expected, rtol=2e-11, atol=2e-11)
```

- [ ] **Step 2: Prove frozen baseline passes.** From `theory/`, run `python -m pytest -q tests/test_nstar1535_reduced.py::test_charge_plus_one_grid_is_frozen`. Expected: `1 passed`.
- [ ] **Step 3: Add failing core-delegation test.** Append:

```python
def test_public_charge_plus_one_calls_shared_core_exactly():
    from graal_theory.amplitudes import _reduced_t_core as core
    p = load_reduced_parameters(PARAM, SOURCES)
    w = 1.55
    for public, shared in (
        (wt_kernel(w, p), core.wt_kernel(w, p, C_COEFFICIENTS)),
        (loop_functions(w, p), core.loop_functions(w, p)),
        (reduced_tmatrix(w, p), core.reduced_tmatrix(w, p, C_COEFFICIENTS)),
    ):
        np.testing.assert_allclose(public, shared, rtol=0, atol=0)
```

Run `python -m pytest -q tests/test_nstar1535_reduced.py::test_public_charge_plus_one_calls_shared_core_exactly`; expected: import FAIL with missing `_reduced_t_core`.
- [ ] **Step 4: Create core and turn old public functions into delegates.** Move the existing exact bodies of `_validated_energy`, `wt_kernel`, `loop_functions`, and `reduced_tmatrix` to the private module. Core's WT and solve use passed `coefficients`, not an imported basis constant. Matrix solve uses `size = len(parameters.meson_masses_gev)` and `np.eye(size, dtype=complex)`; retain condition cutoff `1e12`, `np.linalg.solve`, finite-output check and current `ValueError` messages. In old module keep `ReducedTParameters`, `CHANNELS`, `C_COEFFICIENTS`, loader; implement delegates:

```python
def _validated_energy(w_gev: float, parameters: ReducedTParameters) -> float:
    return _reduced_t_core.validated_energy(w_gev, parameters)

def wt_kernel(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.float64]:
    return _reduced_t_core.wt_kernel(w_gev, parameters, C_COEFFICIENTS)

def loop_functions(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.complex128]:
    return _reduced_t_core.loop_functions(w_gev, parameters)

def reduced_tmatrix(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.complex128]:
    return _reduced_t_core.reduced_tmatrix(w_gev, parameters, C_COEFFICIENTS)
```

Core math must remain byte-for-byte equivalent except replacing global `C_COEFFICIENTS` with argument and fixed `6` with `size`; do not change log branches or mass arithmetic. Use `TYPE_CHECKING` for the `ReducedTParameters` annotation inside core, so core has no runtime import cycle. Put `from graal_theory.amplitudes import _reduced_t_core` in old module. `ReducedTParameters` remains defined there, preserving class identity/import path.
- [ ] **Step 5: Run green.** From `theory/`, `python -m pytest -q tests/test_nstar1535_reduced.py tests/test_reduced_t_reference.py`. Expected: all pass, including frozen grid, singular-solve and exact core-delegation tests.
- [ ] **Step 6: Commit only owned paths.** From root: `git add theory/docs/2026-10-01-nstar1535-charge-basis-plan.md theory/src/graal_theory/amplitudes/_reduced_t_core.py theory/src/graal_theory/amplitudes/nstar1535_reduced.py theory/tests/test_nstar1535_reduced.py`; then `git diff --cached --check`; then `git commit -m "refactor(theory): share reduced six-channel core"`. If commit touches unrelated staged user changes, unstage those paths first without discarding their work.

### Task 2: Add P65 charge-zero basis and source-linked mass

**Files:**
- Create: `theory/references/nstar1535_charge_zero_extra.json`
- Create: `theory/src/graal_theory/amplitudes/nstar1535_charge_zero.py`
- Create: `theory/tests/test_nstar1535_charge_zero.py`

**Interfaces:**
- Consumes: Task 1 private core; public `ReducedTParameters` and `load_reduced_parameters(parameter_path, source_path)`.
- Produces: `CHANNELS_ZERO`, `C_COEFFICIENTS_ZERO`, `CHANNEL_INDEX_ZERO`; `load_charge_zero_parameters(parameter_path: Path, source_path: Path, extra_path: Path) -> ReducedTParameters`; `charge_zero_wt_kernel`, `charge_zero_loop_functions`, `charge_zero_tmatrix` with `(w_gev, parameters)` signatures.

- [ ] **Step 1: Write failing channel/input/table tests.** Create test file with `ROOT = Path(__file__).resolve().parents[1]`, `REFERENCES = ROOT / "references"`, `PARAM = REFERENCES / "nstar1535_reduced_parameters.json"`, `SOURCES = REFERENCES / "sources.json"`, `EXTRA = REFERENCES / "nstar1535_charge_zero_extra.json"`; import NumPy, pytest, json, `dataclasses.replace`, and Task 2 symbols. Use the exact expected arrays below, then:

```python
def test_p65_table_i_order_coefficients_and_inputs():
    assert CHANNELS_ZERO == (
        "k_plus_sigma_minus", "k0_sigma0", "k0_lambda",
        "pi_minus_p", "pi0_n", "eta_n")
    assert CHANNEL_INDEX_ZERO == {name: i for i, name in enumerate(CHANNELS_ZERO)}
    np.testing.assert_allclose(C_COEFFICIENTS_ZERO, expected_c,
                               rtol=0, atol=1e-15)
    np.testing.assert_allclose(C_COEFFICIENTS_ZERO,
                               C_COEFFICIENTS_ZERO.T, atol=0)
    assert not C_COEFFICIENTS_ZERO.flags.writeable
    p = load_charge_zero_parameters(PARAM, SOURCES, EXTRA)
    np.testing.assert_allclose(p.meson_masses_gev, expected_meson)
    np.testing.assert_allclose(p.baryon_masses_gev, expected_baryon)
    np.testing.assert_allclose(p.decay_constants_gev, expected_f)
    assert p.subtraction_constants == expected_subtraction
    assert p.mu_gev == 1.2
```

Run `python -m pytest -q tests/test_nstar1535_charge_zero.py`; expected: import FAIL before implementation.

```python
expected_c = np.array([
    [1, -np.sqrt(2), 0, 0, -1/np.sqrt(2), -np.sqrt(3/2)],
    [-np.sqrt(2), 0, 0, -1/np.sqrt(2), -1/2, np.sqrt(3)/2],
    [0, 0, 0, -np.sqrt(3/2), np.sqrt(3)/2, -3/2],
    [0, -1/np.sqrt(2), -np.sqrt(3/2), 1, -np.sqrt(2), 0],
    [-1/np.sqrt(2), -1/2, np.sqrt(3)/2, -np.sqrt(2), 0, 0],
    [-np.sqrt(3/2), np.sqrt(3)/2, -3/2, 0, 0, 0],
], dtype=float)
expected_meson = (0.493677, 0.497611, 0.497611,
                  0.13957039, 0.1349768, 0.547862)
expected_baryon = (1.197449, 1.192642, 1.115683,
                   0.93827208816, 0.93956542052, 0.93956542052)
expected_f = (0.093*1.22, 0.093*1.22, 0.093*1.22,
              0.093, 0.093, 0.093*1.3)
expected_subtraction = (-2.8, -2.8, 1.6, 2.0, 2.0, 0.2)
```

- [ ] **Step 2: Add explicit provenance and mapping.** New JSON is exactly:

```json
{
  "sigma_minus_mass": {
    "value": 1.197449,
    "unit": "GeV",
    "source_key": "pdg_2024",
    "locator": "PDG 2024 baryon summary, Sigma- mass"
  }
}
```

Check `pdg_2024` source record and cited species value before commit; if value cannot be verified from PDG 2024, stop this task and report evidence gap rather than silently substituting another source. Loader must require outer key set exactly `{"sigma_minus_mass"}` and inner set exactly `{"value","unit","source_key","locator"}`; `unit == "GeV"`, `source_key == "pdg_2024"`, nonempty locator, finite positive real numeric value excluding bool/complex. Validate through `SourceRef`/`PhysicalParameter` and `load_source_registry`. Build immutable `ReducedTParameters` by explicit index mapping from charge-`+1` loader result `p`:

```python
return ReducedTParameters(
    meson_masses_gev=(p.meson_masses_gev[3], p.meson_masses_gev[5],
                      p.meson_masses_gev[5], p.meson_masses_gev[1],
                      p.meson_masses_gev[0], p.meson_masses_gev[2]),
    baryon_masses_gev=(sigma_minus, p.baryon_masses_gev[3],
                       p.baryon_masses_gev[4], p.baryon_masses_gev[0],
                       p.baryon_masses_gev[1], p.baryon_masses_gev[1]),
    decay_constants_gev=(p.decay_constants_gev[3],)*3 +
                        (p.decay_constants_gev[0], p.decay_constants_gev[1],
                         p.decay_constants_gev[2]),
    subtraction_constants=(p.subtraction_constants[3],)*2 +
                          (p.subtraction_constants[4], p.subtraction_constants[0],
                           p.subtraction_constants[1], p.subtraction_constants[2]),
    mu_gev=p.mu_gev,
)
```

The new module defines P65 `expected_c` above as its own read-only constant; it must not import P73 `C_COEFFICIENTS`. Each wrapper passes `C_COEFFICIENTS_ZERO` to Task 1 core, except loop wrapper, which only passes parameters.
- [ ] **Step 3: Add failing validation and physics tests.** Use `tmp_path` copies of the one-field JSON and these cases; all malformed source records must fail before WT evaluation. Add direct immutable-record checks through `dataclasses.replace` for complex/mutable mass tuples.

```python
@pytest.mark.parametrize("field,value", [
    ("unit", "MeV"), ("source_key", "inoue_2002"),
    ("value", -1), ("value", float("nan")),
    ("value", True), ("value", "1.197449+0j"),
    ("locator", ""),
])
def test_sigma_minus_source_record_rejects_bad_fields(tmp_path, field, value):
    raw = json.loads(EXTRA.read_text(encoding="utf-8"))
    raw["sigma_minus_mass"][field] = value
    changed = tmp_path / "bad.json"
    changed.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(ValueError, match="sigma_minus_mass"):
        load_charge_zero_parameters(PARAM, SOURCES, changed)

def test_charge_zero_threshold_branches_and_eq7():
    p = load_charge_zero_parameters(PARAM, SOURCES, EXTRA)
    lightest = min(np.add(p.meson_masses_gev, p.baryon_masses_gev))
    for i, (m, baryon) in enumerate(zip(p.meson_masses_gev,
                                         p.baryon_masses_gev)):
        threshold = m + baryon
        for w in (threshold-1e-6, threshold, threshold+1e-6):
            if not lightest <= w <= 1.70:
                continue
            g = charge_zero_loop_functions(w, p)
            assert np.all(np.isfinite(g))
            if w <= threshold:
                assert abs(g[i].imag) < 1e-9
            else:
                q = np.sqrt((w*w-threshold**2) *
                            (w*w-(baryon-m)**2))/(2*w)
                assert g[i].imag == pytest.approx(
                    -baryon*q/(4*np.pi*w), abs=1e-10)

def test_charge_zero_solve_and_two_body_unitarity():
    p = load_charge_zero_parameters(PARAM, SOURCES, EXTRA)
    w = 1.55
    v = charge_zero_wt_kernel(w, p)
    g = charge_zero_loop_functions(w, p)
    t = charge_zero_tmatrix(w, p)
    np.testing.assert_allclose(v, v.T, atol=1e-13)
    np.testing.assert_allclose(t, t.T, rtol=1e-10, atol=1e-10)
    np.testing.assert_allclose((np.eye(6)-v*g[None, :]) @ t, v,
                               rtol=1e-11, atol=1e-11)
    rho = np.zeros(6)
    for i, (m, baryon) in enumerate(zip(p.meson_masses_gev,
                                         p.baryon_masses_gev)):
        if w > m+baryon:
            q = np.sqrt((w*w-(m+baryon)**2)*
                        (w*w-(baryon-m)**2))/(2*w)
            rho[i] = baryon*q/(4*np.pi*w)
    np.testing.assert_allclose((t-t.conj().T)/(2j),
                               -t @ np.diag(rho) @ t.conj().T,
                               rtol=2e-9, atol=2e-9)
```

Also test omitted/extra outer or inner JSON keys; `replace(p, baryon_masses_gev=list(p.baryon_masses_gev))` and `replace(p, baryon_masses_gev=(complex(p.baryon_masses_gev[0]),) + p.baryon_masses_gev[1:])` must each raise `ValueError` naming `baryon_masses_gev`. Test malformed `W` values `(1+0j, True, nan, lightest-1e-6, 1.701)`; singular `np.linalg.solve` monkeypatch and `cond > 1e12` monkeypatch. Run `python -m pytest -q tests/test_nstar1535_charge_zero.py`; expected: FAIL until guards and wrappers are complete.
- [ ] **Step 4: Implement minimal charge-zero wrappers and guards, then run green.** From `theory/`, run `python -m pytest -q tests/test_nstar1535_charge_zero.py tests/test_nstar1535_reduced.py`. Expected: all pass; `+1` frozen grid unchanged. Do not adjust subtractions or masses to reduce reference residuals.
- [ ] **Step 5: Commit only Task 2 paths.** From root: `git add theory/references/nstar1535_charge_zero_extra.json theory/src/graal_theory/amplitudes/nstar1535_charge_zero.py theory/tests/test_nstar1535_charge_zero.py`; `git diff --cached --check`; `git commit -m "feat(theory): add P65 charge-zero reduced basis"`.

### Task 3: Project charge-zero S11 and report two-basis diagnostic

**Files:**
- Modify: `theory/src/graal_theory/reduced_t_reference.py`
- Modify: `theory/tests/test_reduced_t_reference.py`
- Modify: `theory/references/p73_fig1_reduced_comparison.md`

**Interfaces:**
- Consumes: `charge_zero_tmatrix`, `CHANNEL_INDEX_ZERO`, existing `load_fig1_reduced`, `compare_fig1_reduced`, `Fig1Point` and both parameter records.
- Produces: `isospin_half_s11_eta_charge_zero(w_gev: float, parameters: ReducedTParameters) -> complex`; `compare_fig1_charge_zero(parameters: ReducedTParameters, points: tuple[Fig1Point, ...]) -> list[dict[str, float]]`. Existing `+1` projection/comparison signatures and results stay unchanged.

- [ ] **Step 1: Write failing CG/Eq. (10) and frozen-reference tests.** Import new functions and module, then use this explicit projection check at `W=1.54`:

```python
def test_charge_zero_projection_uses_p65_table_order_and_cg():
    from graal_theory.amplitudes.nstar1535_charge_zero import (
        C_COEFFICIENTS_ZERO, charge_zero_tmatrix, load_charge_zero_parameters)
    p = load_charge_zero_parameters(PARAM, SOURCES,
                                    REFERENCES / "nstar1535_charge_zero_extra.json")
    pion = np.array([-np.sqrt(2/3), 1/np.sqrt(3)])
    np.testing.assert_allclose(
        C_COEFFICIENTS_ZERO[np.ix_((3, 4), (3, 4))] @ pion,
        2*pion, atol=1e-14)
    w = 1.54
    rho = {}
    for i in (3, 4, 5):
        m, baryon = p.meson_masses_gev[i], p.baryon_masses_gev[i]
        q = np.sqrt((w*w-(m+baryon)**2)*(w*w-(m-baryon)**2))/(2*w)
        rho[i] = baryon*q/(4*np.pi*w)
    t = charge_zero_tmatrix(w, p)
    expected = -np.sqrt(rho[5]) * (
        pion[0]*np.sqrt(rho[3])*t[3, 5] +
        pion[1]*np.sqrt(rho[4])*t[4, 5])
    assert isospin_half_s11_eta_charge_zero(w, p) == pytest.approx(expected)
```

P65's `|pi+> = -|1,+1>` and Condon-Shortley lowering give the `(pi- p,pi0 n)` vector shown. State separately that `eta n` is taken with positive relative phase; no sign choice based on Fig. 1. Test closed `eta n` at `W=1.48` raises `ValueError` mentioning `open`. Load frozen points with `load_fig1_reduced(FIG1_CSV,FIG1_META,P73_PDF)`; test eight charge-zero rows retain exact reference values, residual = prediction minus reference, and `abs(residual) > reading_error` computes each component's flag. Re-run existing PDF/CSV digest-rejection tests. Run focused tests; expected: import FAIL before implementation.
- [ ] **Step 2: Implement projection and reuse one residual builder.** Use `CHANNEL_INDEX_ZERO` rather than literal indices in production code. Keep old `isospin_half_s11_eta` unchanged. New projection's central calculation is:

```python
def isospin_half_s11_eta_charge_zero(
    w_gev: float, parameters: ReducedTParameters,
) -> complex:
    t = charge_zero_tmatrix(w_gev, parameters)  # validates real-axis W first
    pion_indices = (CHANNEL_INDEX_ZERO["pi_minus_p"],
                    CHANNEL_INDEX_ZERO["pi0_n"])
    eta_index = CHANNEL_INDEX_ZERO["eta_n"]
    rho = {}
    for i in (*pion_indices, eta_index):
        m, baryon = parameters.meson_masses_gev[i], parameters.baryon_masses_gev[i]
        if w_gev <= m + baryon:
            raise ValueError("S11 eta projection requires open pi N and eta n channels")
        q = np.sqrt((w_gev*w_gev-(m+baryon)**2) *
                    (w_gev*w_gev-(baryon-m)**2))/(2*w_gev)
        rho[i] = baryon*q/(4*np.pi*w_gev)
    u = (-np.sqrt(2/3), 1/np.sqrt(3))
    return complex(-np.sqrt(rho[eta_index]) * sum(
        coefficient*np.sqrt(rho[i])*t[i, eta_index]
        for coefficient, i in zip(u, pion_indices)))
```

Factor existing `compare_fig1_reduced` row creation into private `_compare_fig1_projection(parameters, points, projector)` with the existing exact dict keys and list return type. Make `compare_fig1_reduced` call it with `isospin_half_s11_eta`; make `compare_fig1_charge_zero` call it with `isospin_half_s11_eta_charge_zero`.
- [ ] **Step 3: Run green and compute report numbers.** From `theory/`, run `python -m pytest -q tests/test_reduced_t_reference.py tests/test_nstar1535_charge_zero.py tests/test_nstar1535_reduced.py`. Expected: all pass. Then execute read-only report calculation:

```bash
PYTHONPATH=src python -c 'from pathlib import Path; from graal_theory.amplitudes.nstar1535_reduced import load_reduced_parameters; from graal_theory.amplitudes.nstar1535_charge_zero import load_charge_zero_parameters; from graal_theory.reduced_t_reference import load_fig1_reduced, compare_fig1_reduced, compare_fig1_charge_zero; r=Path("references"); p=load_reduced_parameters(r/"nstar1535_reduced_parameters.json",r/"sources.json"); z=load_charge_zero_parameters(r/"nstar1535_reduced_parameters.json",r/"sources.json",r/"nstar1535_charge_zero_extra.json"); pts=load_fig1_reduced(r/"p73_fig1_reduced.csv",r/"p73_fig1_reduced.json",Path("../tmp/pdfs/10.1103@PhysRevC.73.045209.pdf")); print("+1 thresholds",[round(m+b,9) for m,b in zip(p.meson_masses_gev,p.baryon_masses_gev)]); print("0 thresholds",[round(m+b,9) for m,b in zip(z.meson_masses_gev,z.baryon_masses_gev)]); [print(name,row) for name,rows in (("+1",compare_fig1_reduced(p,pts)),("0",compare_fig1_charge_zero(z,pts))) for row in rows]'
```

Copy actual outputs into report, marking `*` where `abs(residual) > reading_error`. Keep existing PDF and CSV SHA-256 strings unchanged.
- [ ] **Step 4: Update interpretation, then verify standalone suite.** Report both basis tables, max absolute residual and counts beyond the fixed `0.020` bound for real/imag components; do not call smaller residual a reproduction or evidence of historical basis choice. State signed comparison conditional on positive `eta N` phase, PDG 2024 mass policy, unprinted historical masses and unknown P73 Fig. 1 basis. State next bounded decision toward final fittable model: resolve any remaining source/convention gap, then specify full strong corrections separately; later native-bin fit needs covariance and nuisance separation. Run from `theory/`: `python -m pytest -q`. Expected: all standalone tests pass; if unrelated dirty-file tests fail, record exact failure and do not alter their files.
- [ ] **Step 5: Commit only Task 3 paths.** From root: `git add theory/src/graal_theory/reduced_t_reference.py theory/tests/test_reduced_t_reference.py theory/references/p73_fig1_reduced_comparison.md`; `git diff --cached --check`; `git commit -m "docs(theory): compare reduced charge bases with P73"`.

## Final verification and handoff

After all tasks: `git status --short` must show only pre-existing unrelated dirty paths; `git diff HEAD~3..HEAD --check` must pass; rerun `python -m pytest -q` from `theory/`. Independent reviewer checks exact P65 Table I transcription, source-linked mass, CG sign/convention statement, frozen `+1` grid, residual table arithmetic and absence of fit/Stage changes. Report outcome and unresolved scientific limits; do not claim model ready for fitting our data yet.
