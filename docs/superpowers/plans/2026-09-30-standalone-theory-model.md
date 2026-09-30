# Standalone Chiral-Unitary Theory Model Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated Python package that calculates the central-value tree-level \(\Delta^*(1700)\rightarrow\eta\Delta(1232)\rightarrow\eta\pi^0p\) prediction, its partial total cross section, and three invariant-mass spectra, then validates the published \(M_{\eta p}\) contribution in Figure 14 of Döring et al.

**Architecture:** `theory/` is a standalone `src`-layout package with no imports from, or edits to, the existing analysis stages. A generic Lorentz-invariant three-body Sobol sampler feeds a reaction-specific spin amplitude; observables, convergence checks, serialization, and source-linked regression validation remain separate. The first release implements the Figure 11/Eq. 43 tree term only and labels every result as partial.

**Tech Stack:** Python 3.10+, NumPy, SciPy (`scipy.stats.qmc` and integration), Matplotlib, pytest, JSON, CSV, NPZ.

**Spec:** `docs/superpowers/specs/2026-09-30-standalone-theory-model-design.md`

## Global Constraints

- Keep `theory/` autonomous; do not modify root `pyproject.toml`, `07_observable_extraction/`, wiki pages, or pipeline numbering.
- Use GeV, natural units \(\hbar=c=1\), metric \(+---\), `float64`, and `complex128` internally.
- Use central parameters only; every physical value requires an exact source locator before validated execution.
- Use reproducible Sobol samples with powers of two and no implicit global random state.
- Treat the Eq. 43 result as a partial prediction; do not label it as the full Figure 19 cross section.
- Keep generated `theory/outputs/` artifacts unversioned; version source metadata, configuration, tests, and digitized targets.
- Do not tune parameters against experimental data or digitized theory curves.

## Review Focus

- Missing, blank, or malformed source metadata must prevent a parameter set from becoming validated; Task 1 pins this with loader tests.
- Energies at or below the exact three-body threshold must return a physical zero prediction without invoking Sobol generation; Task 6 pins this behavior.
- Negative Källén values caused only by roundoff at a boundary must clamp to zero, while genuinely nonphysical inputs must fail; Tasks 2 and 3 pin both cases.
- Sobol powers outside the supported range, or scrambled sequences without an explicit seed, must fail deterministically; Task 3 pins configuration validation.
- Nonfinite amplitudes must fail with energy and event index instead of contaminating integrals or histograms; Task 6 pins contextual failure reporting.

---

## Locked File Map

| File | Responsibility |
|---|---|
| `theory/pyproject.toml` | Standalone package metadata, dependencies, pytest settings, CLI entry point |
| `theory/.gitignore` | Ignore generated runs while retaining directory marker |
| `theory/README.md` | Supported calculation, commands, source and limitation summary |
| `theory/src/graal_theory/sources.py` | Source and physical-parameter provenance contracts |
| `theory/src/graal_theory/constants.py` | Unit conversions shared by observable calculations |
| `theory/src/graal_theory/particles.py` | Immutable particle/resonance records |
| `theory/src/graal_theory/kinematics.py` | Lorentz operations, thresholds, boosts, Källén function |
| `theory/src/graal_theory/phase_space.py` | Reproducible three-body Sobol mapping and invariant weights |
| `theory/src/graal_theory/spin.py` | Pauli matrices, spin-transition operators, polarization vectors |
| `theory/src/graal_theory/amplitudes/propagators.py` | Energy-dependent widths and resonance propagators |
| `theory/src/graal_theory/amplitudes/delta1700.py` | Eq. 39 production vertex and Eq. 43 tree amplitude |
| `theory/src/graal_theory/models/eta_pi0_p.py` | Reaction masses, central parameters, spin average, normalization |
| `theory/src/graal_theory/observables.py` | Partial cross section and invariant-mass histograms |
| `theory/src/graal_theory/convergence.py` | \(2^N\) versus \(2^{N+1}\) acceptance checks |
| `theory/src/graal_theory/run_output.py` | Atomic NPZ/JSON output bundle |
| `theory/src/graal_theory/validation.py` | Reference-curve loading and scientific acceptance reports |
| `theory/src/graal_theory/cli.py` | `predict` and `validate` commands |
| `theory/references/sources.json` | DOI/arXiv/page/equation registry |
| `theory/references/central_parameters.json` | Source-linked central values only |
| `theory/references/figure14_eta_p_tree.csv` | Digitized dotted tree-level curve from Figure 14 |
| `theory/references/figure19_total_1202.csv` | Digitized full result at 1.202 GeV for factor-of-two check |
| `theory/references/digitization.json` | Axis calibration and digitization uncertainty |
| `theory/tests/` | Independent ROOT-free unit, property, convergence, and regression tests |

### Task 1: Bootstrap Standalone Package and Provenance Gate

**Files:**
- Create: `theory/pyproject.toml`
- Create: `theory/.gitignore`
- Create: `theory/README.md`
- Create: `theory/src/graal_theory/__init__.py`
- Create: `theory/src/graal_theory/sources.py`
- Create: `theory/references/sources.json`
- Create: `theory/tests/test_sources.py`

**Interfaces:**
- Consumes: supplied PDFs under `tmp/pdfs/` and the four exact bibliographic records listed below.
- Produces: `SourceRef`, `PhysicalParameter`, `load_source_registry()`, and `validate_parameter_sources()`.

- [ ] **Step 1: Record exact source inventory**

Create `theory/references/sources.json` with these keys and identifiers:

```json
{
  "doering_2006_prc": {
    "doi": "10.1103/PhysRevC.73.045209",
    "citation": "M. Döring, E. Oset, D. Strottman, Physical Review C 73, 045209 (2006)"
  },
  "doering_2006_plb": {
    "doi": "10.1016/j.physletb.2006.06.022",
    "citation": "M. Döring, E. Oset, D. Strottman, Physics Letters B 639, 59-67 (2006)"
  },
  "nacher_2001": {
    "doi": "10.1016/S0375-9474(01)01110-1",
    "arxiv": "nucl-th/0012065",
    "citation": "J. C. Nacher et al., Nuclear Physics A 695, 295-327 (2001)"
  },
  "sarkar_2005": {
    "doi": "10.1016/j.nuclphysa.2005.01.006",
    "arxiv": "nucl-th/0407025",
    "citation": "S. Sarkar, E. Oset, M. J. Vicente Vacas, Nuclear Physics A 750, 294-323 (2005)"
  }
}
```

Retrieve the two dependency preprints into `tmp/pdfs/` during execution if absent. Keep them unversioned. Use the arXiv identifiers above rather than searching by title.

- [ ] **Step 2: Write failing provenance tests**

```python
def test_parameter_requires_nonempty_locator():
    source = SourceRef("doering_2006_prc", "10.1103/PhysRevC.73.045209", "")
    with pytest.raises(ValueError, match="locator"):
        PhysicalParameter("m_delta", 1.232, "GeV", source)


def test_registry_rejects_missing_doi_and_arxiv(tmp_path):
    path = tmp_path / "sources.json"
    path.write_text('{"bad": {"citation": "unresolvable"}}')
    with pytest.raises(ValueError, match="identifier"):
        load_source_registry(path)
```

- [ ] **Step 3: Run tests and confirm expected failure**

Run: `cd theory && python -m pytest tests/test_sources.py -q`

Expected: collection fails because `graal_theory.sources` does not exist.

- [ ] **Step 4: Create isolated packaging configuration**

Use this package contract in `theory/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=64"]
build-backend = "setuptools.build_meta"

[project]
name = "graal-theory"
version = "0.1.0"
requires-python = ">=3.10"
dependencies = ["numpy>=1.24", "scipy>=1.10", "matplotlib>=3.7"]

[project.optional-dependencies]
test = ["pytest>=7.4"]

[project.scripts]
graal-theory = "graal_theory.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
addopts = "--import-mode=importlib"
testpaths = ["tests"]
```

Ignore `outputs/*` locally while retaining `outputs/.gitkeep`.

- [ ] **Step 5: Implement provenance value objects and loader**

```python
@dataclass(frozen=True)
class SourceRef:
    citation_key: str
    persistent_id: str
    locator: str

    def __post_init__(self) -> None:
        if not self.citation_key.strip() or not self.persistent_id.strip():
            raise ValueError("source requires citation key and persistent identifier")


@dataclass(frozen=True)
class PhysicalParameter:
    name: str
    value: float | complex
    unit: str
    source: SourceRef

    def __post_init__(self) -> None:
        numeric = complex(self.value)
        if not self.name.strip():
            raise ValueError("parameter name must be nonempty")
        if not np.isfinite(numeric.real) or not np.isfinite(numeric.imag):
            raise ValueError(f"parameter {self.name!r} must be finite")
        if not self.unit.strip():
            raise ValueError(f"parameter {self.name!r} requires a unit")
        if not self.source.locator.strip() or "://" in self.source.locator:
            raise ValueError(f"parameter {self.name!r} requires a source locator")
```

Implement the dataclasses above together with these closed validators, not
permissive deserializers:

```python
def load_source_registry(path: Path) -> dict[str, dict[str, str]]:
    records = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(records, dict) or not records:
        raise ValueError("source registry must be a nonempty object")
    for key, record in records.items():
        if not isinstance(key, str) or not key.strip():
            raise ValueError("source keys must be nonempty strings")
        if not isinstance(record, dict):
            raise ValueError(f"source {key!r} must be an object")
        if not str(record.get("citation", "")).strip():
            raise ValueError(f"source {key!r} has no citation")
        identifiers = [record.get("doi"), record.get("arxiv")]
        if not any(isinstance(value, str) and value.strip() for value in identifiers):
            raise ValueError(f"source {key!r} has no persistent identifier")
    return records


def validate_parameter_sources(
    parameters: Mapping[str, PhysicalParameter],
) -> None:
    for key, parameter in parameters.items():
        if key != parameter.name:
            raise ValueError(f"parameter key/name mismatch: {key!r}")
        if not parameter.unit.strip() or not parameter.source.locator.strip():
            raise ValueError(f"parameter {key!r} has incomplete provenance")
```

Reject blank keys, values, units, locators, citations, and source records without DOI or arXiv ID. Do not accept URLs as substitutes for equation/page locators.

- [ ] **Step 6: Run focused package tests**

Run: `cd theory && python -m pytest tests/test_sources.py -q`

Expected: all tests pass.

- [ ] **Step 7: Commit Task 1**

```bash
git add theory/pyproject.toml theory/.gitignore theory/README.md theory/src theory/references/sources.json theory/tests/test_sources.py
git commit -m "feat(theory): add standalone provenance-aware package"
```

### Task 2: Add Relativistic Kinematics and Particle Contracts

**Files:**
- Create: `theory/src/graal_theory/constants.py`
- Create: `theory/src/graal_theory/particles.py`
- Create: `theory/src/graal_theory/kinematics.py`
- Create: `theory/tests/test_particles.py`
- Create: `theory/tests/test_kinematics.py`

**Interfaces:**
- Consumes: `SourceRef` from Task 1.
- Produces: `Particle`, `kallen()`, `mass_squared()`, `invariant_mass()`, `boost()`, `two_body_momentum()`, `s_from_lab_photon_energy()`, `cm_photon_momentum()`, and `validate_final_state()`.

- [ ] **Step 1: Write failing particle and invariant tests**

```python
def test_particle_rejects_nonphysical_mass():
    with pytest.raises(ValueError, match="mass_gev"):
        Particle("bad", 0.0, 0.0, SOURCE)


def test_lab_photon_energy_maps_to_invariant_s():
    assert s_from_lab_photon_energy(1.2, 0.9382720813) == pytest.approx(
        0.9382720813**2 + 2 * 0.9382720813 * 1.2
    )


def test_roundoff_negative_kallen_clamps_but_physical_negative_fails():
    assert kallen(4.0, 1.0, 1.0, atol=1e-14) == pytest.approx(0.0)
    with pytest.raises(ValueError, match="nonphysical"):
        kallen(3.0, 1.0, 1.0, atol=1e-14)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd theory && python -m pytest tests/test_particles.py tests/test_kinematics.py -q`

Expected: FAIL because modules do not exist.

- [ ] **Step 3: Implement immutable particles and vectorized Lorentz helpers**

Use four-vectors ordered `(E, px, py, pz)` and last-axis size `4`:

```python
@dataclass(frozen=True)
class Particle:
    name: str
    mass_gev: float
    width_gev: float
    source: SourceRef


def mass_squared(p: NDArray[np.float64]) -> NDArray[np.float64]:
    p = np.asarray(p, dtype=np.float64)
    return p[..., 0] ** 2 - np.sum(p[..., 1:] ** 2, axis=-1)


def invariant_mass(p: NDArray[np.float64]) -> NDArray[np.float64]:
    m2 = mass_squared(p)
    if np.any(m2 < -1e-12):
        raise ValueError("four-vector has nonphysical negative mass squared")
    return np.sqrt(np.maximum(m2, 0.0))


def two_body_momentum(parent_mass: float, m1: float, m2: float) -> float:
    root = kallen(parent_mass**2, m1**2, m2**2, atol=1e-14)
    return np.sqrt(root) / (2.0 * parent_mass)


def cm_photon_momentum(sqrt_s: float, target_mass: float) -> NDArray[np.float64]:
    if sqrt_s <= target_mass:
        raise ValueError("sqrt_s must exceed target mass")
    magnitude = (sqrt_s**2 - target_mass**2) / (2.0 * sqrt_s)
    return np.array([0.0, 0.0, magnitude], dtype=np.float64)
```

Implement `boost()` from
`E' = gamma * (E - beta·p)` and
`p' = p + ((gamma - 1)(beta·p)/beta² - gamma*E) beta`, with an identity fast path for `beta² == 0`.

`constants.py` defines `GEV2_TO_MICROBARN = 389.3793721` and no reaction-specific masses.

`boost()` must reject `|beta| >= 1`. `invariant_mass()` clamps only residuals within its explicit absolute tolerance.

- [ ] **Step 4: Add conservation/property tests**

```python
def test_boost_preserves_mass_squared():
    p = np.array([2.0, 0.3, -0.2, 1.0])
    boosted = boost(p, np.array([0.1, -0.05, 0.2]))
    assert mass_squared(boosted) == pytest.approx(mass_squared(p), abs=1e-13)


def test_cm_real_photon_energy_equals_momentum_norm():
    sqrt_s = np.sqrt(s_from_lab_photon_energy(1.2, 0.9382720813))
    momentum = cm_photon_momentum(sqrt_s, 0.9382720813)
    expected_energy = (sqrt_s**2 - 0.9382720813**2) / (2.0 * sqrt_s)
    assert np.linalg.norm(momentum) == pytest.approx(expected_energy)


def test_validate_final_state_reports_event_index():
    initial = np.array([[2.0, 0.0, 0.0, 0.0]])
    final = np.zeros((1, 3, 4))
    with pytest.raises(ValueError, match="event 0"):
        validate_final_state(initial, final, (0.5, 0.5, 0.5), atol=1e-12)
```

- [ ] **Step 5: Run focused tests**

Run: `cd theory && python -m pytest tests/test_particles.py tests/test_kinematics.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit Task 2**

```bash
git add theory/src/graal_theory/constants.py theory/src/graal_theory/particles.py theory/src/graal_theory/kinematics.py theory/tests/test_particles.py theory/tests/test_kinematics.py
git commit -m "feat(theory): add relativistic kinematics"
```

### Task 3: Implement Reproducible Three-Body Sobol Phase Space

**Files:**
- Create: `theory/src/graal_theory/phase_space.py`
- Create: `theory/tests/test_phase_space.py`

**Interfaces:**
- Consumes: Task 2 Lorentz helpers.
- Produces: `SobolConfig`, `ThreeBodySample`, `sample_three_body()`, and `phase_space_volume_quad()`.

- [ ] **Step 1: Write failing configuration and conservation tests**

```python
def test_scrambled_sobol_requires_seed():
    with pytest.raises(ValueError, match="seed"):
        SobolConfig(power=10, scramble=True, seed=None)


def test_power_must_be_supported():
    with pytest.raises(ValueError, match="power"):
        SobolConfig(power=3)


def test_three_body_sample_is_reproducible_and_conserved():
    cfg = SobolConfig(power=10, scramble=False, seed=None)
    first = sample_three_body(2.0, (0.547862, 0.1349768, 0.9382721), cfg)
    second = sample_three_body(2.0, (0.547862, 0.1349768, 0.9382721), cfg)
    np.testing.assert_array_equal(first.momenta, second.momenta)
    np.testing.assert_array_equal(first.weights_gev2, second.weights_gev2)
    validate_final_state(first.initial, first.momenta, first.masses, atol=1e-12)
```

- [ ] **Step 2: Run tests and verify failure**

Run: `cd theory && python -m pytest tests/test_phase_space.py -q`

Expected: FAIL because phase-space API does not exist.

- [ ] **Step 3: Implement sequential two-body factorization**

Map five Sobol coordinates to \(s_{12}\), two parent-frame angles, and two pair-rest-frame angles. Use

\[
d\Phi_3=\frac{ds_{12}}{2\pi}\,d\Phi_2(P;q_3,Q)\,d\Phi_2(Q;q_1,q_2)
\]

and return a per-point integration weight

\[
w=\Delta s_{12}\frac{p_3p_1^*}{32\pi^3\sqrt{s}\sqrt{s_{12}}}.
\]

Define exact data contracts:

```python
@dataclass(frozen=True)
class SobolConfig:
    power: int
    scramble: bool = False
    seed: int | None = None


@dataclass(frozen=True)
class ThreeBodySample:
    initial: NDArray[np.float64]       # (n, 4)
    momenta: NDArray[np.float64]       # (n, 3, 4)
    weights_gev2: NDArray[np.float64]  # (n,)
    masses: tuple[float, float, float]
    s12_gev2: NDArray[np.float64]
    config: SobolConfig
```

Support powers 4 through 24. Reject `sqrt_s <= sum(masses)` with `BelowThresholdError`; Task 6 owns conversion of that physical condition to a zero prediction.

- [ ] **Step 4: Add independent phase-space-volume check**

Implement a SciPy quadrature reference using

\[
\Phi_3=\int_{s_{12}^{min}}^{s_{12}^{max}}
\frac{\lambda^{1/2}(s,s_{12},m_3^2)\lambda^{1/2}(s_{12},m_1^2,m_2^2)}
{128\pi^3s\,s_{12}}\,ds_{12}.
\]

```python
def test_sobol_phase_space_matches_quadrature():
    masses = (0.547862, 0.1349768, 0.9382721)
    sample = sample_three_body(2.0, masses, SobolConfig(power=16))
    expected = phase_space_volume_quad(2.0, masses)
    assert sample.weights_gev2.mean() == pytest.approx(expected, rel=5e-3)
```

- [ ] **Step 5: Run phase-space and kinematics tests**

Run: `cd theory && python -m pytest tests/test_phase_space.py tests/test_kinematics.py -q`

Expected: all tests pass, including the 0.5% analytic gate.

- [ ] **Step 6: Commit Task 3**

```bash
git add theory/src/graal_theory/phase_space.py theory/tests/test_phase_space.py
git commit -m "feat(theory): add Sobol three-body phase space"
```

### Task 4: Add Spin Algebra and Resonance Propagators

**Files:**
- Create: `theory/src/graal_theory/spin.py`
- Create: `theory/src/graal_theory/amplitudes/__init__.py`
- Create: `theory/src/graal_theory/amplitudes/propagators.py`
- Create: `theory/tests/test_spin.py`
- Create: `theory/tests/test_propagators.py`

**Interfaces:**
- Consumes: Task 2 `two_body_momentum()`.
- Produces: `PAULI`, `TRANSITION`, `transverse_polarizations()`, `p_wave_width()`, `breit_wigner()`, and `delta1700_width()`.

- [ ] **Step 1: Write failing spin-identity tests**

```python
def test_transition_operators_satisfy_spin_identity():
    for i in range(3):
        for j in range(3):
            expected = (2.0 / 3.0) * (i == j) * np.eye(2, dtype=complex)
            expected -= (1j / 3.0) * sum(
                LEVI_CIVITA[i, j, k] * PAULI[k] for k in range(3)
            )
            np.testing.assert_allclose(
                TRANSITION[i] @ TRANSITION[j].conj().T,
                expected,
                atol=1e-14,
            )
```

- [ ] **Step 2: Implement explicit spin matrices**

Use the normalized \(2\times4\) transition matrices satisfying
\(S_iS_j^\dagger=(2\delta_{ij}-i\epsilon_{ijk}\sigma_k)/3\):

```python
TRANSITION = np.array([
    [[-np.sqrt(3), 0, 1, 0], [0, -1, 0, np.sqrt(3)]],
    [[-1j*np.sqrt(3), 0, -1j, 0], [0, -1j, 0, -1j*np.sqrt(3)]],
    [[0, 2, 0, 0], [0, 0, 2, 0]],
], dtype=np.complex128) / np.sqrt(6)
```

`transverse_polarizations(k_hat)` must return two orthonormal real vectors perpendicular to `k_hat` and use a stable alternate reference axis when `k_hat` is parallel to `z`.

- [ ] **Step 3: Write failing width and pole tests**

```python
def test_p_wave_width_is_zero_below_decay_threshold():
    assert p_wave_width(1.0, pole_mass=1.232, pole_width=0.117,
                        daughter_masses=(0.9382721, 0.1349768)) == 0.0


def test_breit_wigner_at_pole_is_purely_negative_imaginary():
    value = breit_wigner(1.7, pole_mass=1.7, width=0.3)
    assert value.real == pytest.approx(0.0, abs=1e-15)
    assert value.imag == pytest.approx(-2.0 / 0.3)
```

- [ ] **Step 4: Implement propagators with source-compatible callables**

```python
def breit_wigner(energy_gev: ArrayLike, pole_mass: float,
                 width: ArrayLike) -> NDArray[np.complex128]:
    energy = np.asarray(energy_gev, dtype=np.float64)
    gamma = np.asarray(width, dtype=np.float64)
    if np.any(gamma < 0.0):
        raise ValueError("width must be nonnegative")
    return 1.0 / (energy - pole_mass + 0.5j * gamma)

def p_wave_width(energy_gev: ArrayLike, pole_mass: float,
                 pole_width: float,
                 daughter_masses: tuple[float, float]) -> NDArray[np.float64]:
    energy = np.asarray(energy_gev, dtype=np.float64)
    q0 = two_body_momentum(pole_mass, *daughter_masses)
    q = np.array([
        two_body_momentum(value, *daughter_masses)
        if value > sum(daughter_masses) else 0.0
        for value in energy.reshape(-1)
    ]).reshape(energy.shape)
    return pole_width * (q / q0) ** 3 * pole_mass / energy
```

Define an immutable `Delta1700WidthParameters` containing pole mass, total
width, branching fractions, `g_rho`, `f_rho`, and the source-linked `A_s` and
`A_d` partial amplitudes. `delta1700_width()` sums the three explicit Eq. 37
components after checking that branching fractions are within `[0, 1]`.

Implement Eq. 36–37 from `doering_2006_prc`, including the \(N\pi\), \(N\rho\), and \(\Delta\pi\) components. Use SciPy quadrature for the two convolutions. Verify all branching fractions and partial-wave amplitudes against `nacher_2001` before entering them in the central parameter file. At the pole, the three partial components must sum to the recorded central total width.

- [ ] **Step 5: Add threshold, continuity, and pole-width tests**

```python
def test_delta1700_components_sum_to_pole_width(central_width_parameters):
    parts = central_width_parameters.components_at_pole()
    assert sum(parts.values()) == pytest.approx(
        central_width_parameters.total_width_gev, rel=1e-10
    )
```

Also test continuity on both sides of each physical threshold and rejection of negative widths or branching fractions outside `[0, 1]`.

- [ ] **Step 6: Run focused tests**

Run: `cd theory && python -m pytest tests/test_spin.py tests/test_propagators.py -q`

Expected: all tests pass.

- [ ] **Step 7: Commit Task 4**

```bash
git add theory/src/graal_theory/spin.py theory/src/graal_theory/amplitudes theory/tests/test_spin.py theory/tests/test_propagators.py
git commit -m "feat(theory): add spin algebra and resonance propagators"
```

### Task 5: Implement Source-Complete Central Parameters and Eq. 43 Tree Amplitude

**Files:**
- Create: `theory/references/central_parameters.json`
- Create: `theory/src/graal_theory/amplitudes/delta1700.py`
- Create: `theory/src/graal_theory/models/__init__.py`
- Create: `theory/src/graal_theory/models/eta_pi0_p.py`
- Create: `theory/tests/test_delta1700_amplitude.py`
- Create: `theory/tests/test_eta_pi0_p_model.py`

**Interfaces:**
- Consumes: Tasks 1–4 contracts and source papers `doering_2006_prc`, `nacher_2001`, and `sarkar_2005`.
- Produces: `Delta1700Parameters`, `load_central_parameters()`, `delta1700_eta_delta_vertex()`, `tree_amplitude()`, and `EtaPi0PModel.matrix_element_squared()`.

- [ ] **Step 1: Build closed parameter inventory from exact equations**

Record every value needed by Eqs. 36, 39, 43, and 44. Each JSON entry must have `value`, `unit`, `source_key`, and `locator`. Complex values use objects such as `{ "real": 1.7, "imag": -1.4 }`. The inventory must include:

- \(m_p,m_{\pi^0},m_\eta,m_\Delta,\Gamma_\Delta,m_{\Delta^*}\);
- electromagnetic \(e\), \(m_\pi\), and \(f_{\Delta N\pi}\);
- \(g_\eta=1.7-i1.4\) from `doering_2006_prc`, page 10, discussion following Eq. 37, traced to `sarkar_2005`;
- \(g'_1,g'_2\) for the \(\gamma p\Delta^*\) vertex from `nacher_2001`;
- all partial-width inputs required by Eq. 37.

The loader must compare this exact required-name set with the JSON keys and report missing and unexpected names separately.

- [ ] **Step 2: Write failing parameter-completeness tests**

```python
def test_central_parameter_file_is_closed_and_source_complete():
    parameters = load_central_parameters(PARAMETER_FILE, SOURCE_FILE)
    assert set(parameters) == REQUIRED_TREE_PARAMETER_NAMES
    validate_parameter_sources(parameters)


def test_missing_electromagnetic_coupling_is_named(tmp_path):
    broken = write_parameters_without(tmp_path, "g1_prime")
    with pytest.raises(ValueError, match="g1_prime"):
        load_central_parameters(broken, SOURCE_FILE)
```

- [ ] **Step 3: Implement Eq. 39 as a vectorized spin matrix**

Use initial photon momentum along `+z` in the center-of-mass frame. For each event and transverse polarization, calculate

\[
t^{(3)}_{\eta\Delta^+p}=-\sqrt{\frac23}\,g_\eta
\frac{f_{\Delta N\pi}}{m_\pi}G_{\Delta^*}(\sqrt{s})
(\mathbf S\!\cdot\!\mathbf p_\pi)\,V_{\gamma p\Delta^*},
\]

with the complete electromagnetic bracket from Eq. 39. Return shape `(events, 2, 2)` for nucleon final and initial spin.

```python
def delta1700_eta_delta_vertex(
    sqrt_s: float,
    photon_three_momentum: NDArray[np.float64],
    pion_three_momentum: NDArray[np.float64],
    polarization: NDArray[np.float64],
    parameters: Delta1700Parameters,
) -> NDArray[np.complex128]:
    k = np.asarray(photon_three_momentum, dtype=np.float64)
    p_pi = np.asarray(pion_three_momentum, dtype=np.float64)
    epsilon = np.asarray(polarization, dtype=np.float64)
    s_dot_p = np.einsum("aij,na->nij", TRANSITION, p_pi)
    sdag_dot_k = np.einsum("aij,a->ji", TRANSITION.conj(), k)
    sdag_dot_epsilon = np.einsum("aij,a->ji", TRANSITION.conj(), epsilon)
    sigma_cross_k_dot_epsilon = sum(
        epsilon[i] * LEVI_CIVITA[i, j, ell] * PAULI[j] * k[ell]
        for i in range(3)
        for j in range(3)
        for ell in range(3)
    )
    magnetic = (
        -1j * parameters.g1_prime / (2.0 * parameters.proton_mass_gev)
        * (sdag_dot_k @ sigma_cross_k_dot_epsilon)
    )
    electric_scalar = (
        parameters.g1_prime
        * (
            np.linalg.norm(k)
            + np.dot(k, k) / (2.0 * parameters.proton_mass_gev)
        )
        + parameters.g2_prime * sqrt_s * np.linalg.norm(k)
    )
    electromagnetic = magnetic - sdag_dot_epsilon * electric_scalar
    gamma = delta1700_width(sqrt_s, parameters.width_parameters)
    g_delta_star = breit_wigner(
        sqrt_s, parameters.delta1700_mass_gev, gamma
    )
    scalar = (
        -np.sqrt(2.0 / 3.0)
        * parameters.g_eta_delta
        * parameters.f_delta_n_pi
        / parameters.pion_reference_mass_gev
        * g_delta_star
    )
    return scalar * np.einsum("nij,jk->nik", s_dot_p, electromagnetic)
```

Here `np.linalg.norm(k)` is (k^0=|\mathbf{k}|) for the real incoming
photon in the center-of-mass frame. The two terms named `magnetic` and
`electric_scalar` are, including signs and factors of (i), the two terms in
the square bracket of Eq. 39. Validate all input shapes before the contractions:
`k` and `epsilon` are `(3,)`, while `p_pi` is `(events, 3)`.

Construct the spin matrix with `np.einsum` contractions over the explicit
`TRANSITION` and `PAULI` arrays. Calculate the two electromagnetic terms
inside the Eq. 39 bracket separately, add them coherently, left-multiply by
`S·p_pi`, and multiply by the scalar
`-sqrt(2/3) * g_eta_delta * f_delta_n_pi / m_pi * G_delta_star`.

- [ ] **Step 4: Implement Eq. 43 and Eq. 44**

Calculate \(z'=M_{\pi^0p}\) directly from final four-vectors and multiply the production vertex by the energy-dependent \(\Delta(1232)\) propagator:

```python
def tree_amplitude(
    sample: ThreeBodySample,
    polarization: NDArray[np.float64],
    parameters: Delta1700Parameters,
) -> NDArray[np.complex128]:
    p_eta, p_pi0, p_proton = np.moveaxis(sample.momenta, 1, 0)
    z_prime = invariant_mass(p_pi0 + p_proton)
    gamma_delta = p_wave_width(
        z_prime,
        pole_mass=parameters.delta_mass_gev,
        pole_width=parameters.delta_width_gev,
        daughter_masses=(
            parameters.proton_mass_gev,
            parameters.pi0_mass_gev,
        ),
    )
    g_delta = breit_wigner(
        z_prime,
        pole_mass=parameters.delta_mass_gev,
        width=gamma_delta,
    )
    production = delta1700_eta_delta_vertex(
        sqrt_s=float(sample.initial[0, 0]),
        photon_three_momentum=cm_photon_momentum(
            float(sample.initial[0, 0]), parameters.proton_mass_gev
        ),
        pion_three_momentum=p_pi0[:, 1:],
        polarization=polarization,
        parameters=parameters,
    )
    return production * g_delta[:, None, None]
```

Use Task 2's `cm_photon_momentum()` so incoming-beam kinematics remains outside
the parameter object. `p_eta` remains deliberately unused in Eq. 43; retaining
its explicit unpacking makes final-state ordering auditable.

Do not add the Eq. 39 rescattering term or any other Figure 14 component in this task.

- [ ] **Step 5: Add algebraic and basis-invariance tests**

```python
def test_zero_eta_delta_coupling_gives_zero_amplitude(sample, parameters):
    zeroed = replace(parameters, g_eta_delta=0j)
    assert np.all(tree_amplitude(sample, EX, zeroed) == 0j)


def test_unpolarized_result_is_invariant_under_transverse_basis_rotation(
    sample, model
):
    ex, ey = transverse_polarizations(np.array([0.0, 0.0, 1.0]))
    angle = 0.37
    rotated = (
        np.cos(angle) * ex + np.sin(angle) * ey,
        -np.sin(angle) * ex + np.cos(angle) * ey,
    )
    np.testing.assert_allclose(
        model.matrix_element_squared(sample, polarizations=(ex, ey)),
        model.matrix_element_squared(sample, polarizations=rotated),
        rtol=1e-12,
        atol=1e-14,
    )
```

`matrix_element_squared()` averages over two initial proton spins and two photon polarizations and sums final proton spin using `trace(A @ A.conj().T) / 4`.

- [ ] **Step 6: Run amplitude/model tests**

Run: `cd theory && python -m pytest tests/test_delta1700_amplitude.py tests/test_eta_pi0_p_model.py -q`

Expected: all tests pass with finite nonnegative squared amplitudes.

- [ ] **Step 7: Commit Task 5**

```bash
git add theory/references/central_parameters.json theory/src/graal_theory/amplitudes/delta1700.py theory/src/graal_theory/models theory/tests/test_delta1700_amplitude.py theory/tests/test_eta_pi0_p_model.py
git commit -m "feat(theory): add delta1700 tree amplitude"
```

### Task 6: Integrate Partial Cross Sections, Spectra, and Convergence

**Files:**
- Create: `theory/src/graal_theory/observables.py`
- Create: `theory/src/graal_theory/convergence.py`
- Create: `theory/tests/test_observables.py`
- Create: `theory/tests/test_convergence.py`

**Interfaces:**
- Consumes: `EtaPi0PModel`, `ThreeBodySample`, and `SobolConfig`.
- Produces: `HistogramSpec`, `Prediction`, `predict_energy()`, `predict_grid()`, `ConvergenceReport`, and `compare_resolutions()`.

- [ ] **Step 1: Write failing threshold, normalization, and histogram tests**

```python
def test_below_threshold_returns_zero_without_sampling(monkeypatch, model):
    monkeypatch.setattr("graal_theory.observables.sample_three_body",
                        lambda *args, **kwargs: pytest.fail("sampler called"))
    result = predict_energy(0.90, model, SobolConfig(power=8), HISTOGRAMS)
    assert result.partial_cross_section_microbarn == 0.0
    assert all(np.all(hist.values == 0.0) for hist in result.histograms.values())


def test_histogram_integrals_equal_partial_cross_section(constant_model):
    result = predict_energy(1.2, constant_model, SobolConfig(power=15), HISTOGRAMS)
    for histogram in result.histograms.values():
        assert np.sum(histogram.values * np.diff(histogram.edges)) == pytest.approx(
            result.partial_cross_section_microbarn, rel=5e-3
        )
```

- [ ] **Step 2: Implement paper-normalized observable integration**

Use the invariant phase-space sample and initial flux \(2(s-m_p^2)\). Because the paper's nonrelativistic baryon normalization differs from invariant relativistic normalization, apply the explicit \(4M_pM_f\) factor obtained by matching Eq. 45:

\[
\sigma_{partial}=389.3793721\,\mu\mathrm b\,\mathrm{GeV}^2
\times\frac{4M_pM_f}{2(s-M_p^2)}
\left\langle w\,\overline{|T|^2}\right\rangle.
\]

```python
@dataclass(frozen=True)
class Prediction:
    photon_energy_gev: float
    partial_cross_section_microbarn: float
    histograms: dict[str, Histogram]
    sobol_config: SobolConfig
    sample_size: int
```

Histogram keys are exactly `eta_p`, `pi0_p`, and `eta_pi0`; values are densities in `microbarn/GeV`.

- [ ] **Step 3: Fail contextually on nonfinite amplitudes**

Before integration, locate all nonfinite values. Raise:

```text
nonfinite matrix element at E_gamma=<value> GeV, event=<index>
```

Add a test model that injects `np.nan` at event 7 and assert both fields appear in the error.

- [ ] **Step 4: Implement convergence comparison**

```python
@dataclass(frozen=True)
class ConvergenceReport:
    cross_section_relative_change: float
    max_populated_bin_relative_change: float
    passed: bool
    excluded_edge_bins: dict[str, list[int]]
```

Pass when cross-section change is `< 0.01` and populated-bin change is `< 0.03`. An edge bin may be excluded only when both resolutions predict less than `1e-6` microbarn in that bin; record every exclusion.

- [ ] **Step 5: Add nested-resolution tests**

Use a constant matrix element and compare powers 12 and 13. Assert the high-resolution sample starts with the same Sobol points as the low-resolution sample and the convergence report passes.

- [ ] **Step 6: Run observables/convergence tests**

Run: `cd theory && python -m pytest tests/test_observables.py tests/test_convergence.py -q`

Expected: all tests pass.

- [ ] **Step 7: Commit Task 6**

```bash
git add theory/src/graal_theory/observables.py theory/src/graal_theory/convergence.py theory/tests/test_observables.py theory/tests/test_convergence.py
git commit -m "feat(theory): integrate partial observables"
```

### Task 7: Add Atomic Run Bundles and CLI

**Files:**
- Create: `theory/src/graal_theory/run_output.py`
- Create: `theory/src/graal_theory/cli.py`
- Create: `theory/tests/test_run_output.py`
- Create: `theory/tests/test_cli.py`
- Create: `theory/outputs/.gitkeep`

**Interfaces:**
- Consumes: predictions and convergence reports from Task 6.
- Produces: `write_run_bundle()`, CLI `predict`, and a stable `results.npz`/`manifest.json`/`convergence.json` schema.

- [ ] **Step 1: Write failing atomic-output test**

```python
def test_failed_bundle_write_preserves_existing_destination(tmp_path, monkeypatch):
    destination = tmp_path / "run"
    destination.mkdir()
    (destination / "sentinel").write_text("old")
    monkeypatch.setattr(np, "savez_compressed", lambda *a, **k: (_ for _ in ()).throw(OSError("boom")))
    with pytest.raises(OSError, match="boom"):
        write_run_bundle(destination, BUNDLE)
    assert (destination / "sentinel").read_text() == "old"
```

- [ ] **Step 2: Implement closed manifest schema and atomic replacement**

Write into a sibling temporary directory and fsync JSON/NPZ files. For a new
destination, atomically rename the temporary directory into place. With
`--replace`, first rename the existing destination to a sibling backup, rename
the completed temporary directory into place, then remove the backup; if the
second rename fails, restore the backup before raising. Manifest keys are
exactly:

```python
MANIFEST_KEYS = {
    "schema_version", "model", "scope", "code_revision", "parameters",
    "sources", "energy_grid_gev", "sobol", "normalization",
    "configuration_sha256", "validation_state",
}
```

Set `scope` to `"partial:delta1700_eta_delta_tree_eq43"`. A dirty or unavailable Git state is recorded, not hidden.

- [ ] **Step 3: Write failing CLI test**

```python
def test_predict_cli_writes_partial_bundle(tmp_path):
    result = subprocess.run([
        sys.executable, "-m", "graal_theory.cli", "predict",
        "--energy", "1.2", "--sobol-power", "8",
        "--output", str(tmp_path / "run"),
    ], text=True, capture_output=True)
    assert result.returncode == 0, result.stderr
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    assert manifest["scope"] == "partial:delta1700_eta_delta_tree_eq43"
```

- [ ] **Step 4: Implement CLI argument validation**

Commands:

```text
graal-theory predict --energy 1.2 --energy 1.202 --sobol-power 15 --output outputs/e1200
graal-theory predict --energy-min 1.1 --energy-max 1.5 --energy-step 0.1 --sobol-power 15 --output outputs/grid
```

Allow `--energy` to repeat. Reject simultaneous repeated `--energy` values and grid arguments, incomplete grids, nonpositive steps, duplicate energies, overwrite without `--replace`, and invalid Sobol powers. Print a one-line summary containing `partial` so output cannot be mistaken for a complete prediction.

- [ ] **Step 5: Run output and CLI tests**

Run: `cd theory && python -m pytest tests/test_run_output.py tests/test_cli.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit Task 7**

```bash
git add theory/src/graal_theory/run_output.py theory/src/graal_theory/cli.py theory/tests/test_run_output.py theory/tests/test_cli.py theory/outputs/.gitkeep
git commit -m "feat(theory): add atomic prediction bundles"
```

### Task 8: Digitize Published Targets and Add Scientific Validation

**Files:**
- Create: `theory/references/figure14_eta_p_tree.csv`
- Create: `theory/references/figure19_total_1202.csv`
- Create: `theory/references/digitization.json`
- Create: `theory/src/graal_theory/validation.py`
- Create: `theory/tests/test_validation.py`
- Create: `theory/tests/test_reference_regression.py`
- Modify: `theory/src/graal_theory/cli.py`

**Interfaces:**
- Consumes: Task 6 predictions and Task 7 bundles.
- Produces: `ReferenceCurve`, `ValidationResult`, `validate_figure14_tree()`, `validate_factor_two()`, validation PDFs, and CLI `validate`.

- [ ] **Step 1: Digitize fixed source targets without fitting**

From `doering_2006_prc`:

- digitize the dotted tree-level curve in Figure 14 at \(E_\gamma=1.2\) GeV over its displayed \(M_{\eta p}\) range;
- use 10 MeV mass spacing, preserving endpoints and zero-valued displayed points;
- digitize the full Figure 19 curve at \(E_\gamma=1.202\) GeV for the factor-of-two comparison;
- record plot bounds, pixel-to-axis calibration, extraction date, operator, and estimated digitization uncertainty in `digitization.json`.

CSV schemas:

```text
# figure14_eta_p_tree.csv
mass_gev,dsigma_dmass_microbarn_per_gev

# figure19_total_1202.csv
photon_energy_gev,total_cross_section_microbarn
```

Do not rescale digitized values to improve agreement.

- [ ] **Step 2: Write failing validation tests**

```python
def test_curve_validation_rejects_twenty_one_percent_shift():
    reference = ReferenceCurve(X, Y, relative_uncertainty=0.0)
    prediction = Y * 1.21
    result = compare_curve(prediction, reference, relative_tolerance=0.20)
    assert not result.passed


def test_factor_two_validation_uses_partial_over_full_ratio():
    result = compare_factor_two(partial=0.50, full=1.00,
                                relative_tolerance=0.20)
    assert result.passed
    assert result.ratio == pytest.approx(0.5)
```

- [ ] **Step 3: Implement interpolation and acceptance logic**

Interpolate predictions onto reference mass points without extrapolation. Compare only points whose digitized central value is greater than zero. Combine the 20% model tolerance and recorded digitization uncertainty linearly, keeping both fields separate in JSON. Report per-point residuals and the maximum accepted residual.

- [ ] **Step 4: Generate validation plots and JSON**

Use Matplotlib's noninteractive `Agg` backend. Produce:

- `validation/invariant_masses.pdf`, showing generated \(M_{\eta p}\) density and Figure 14 dotted-line points;
- `validation/total_cross_section.pdf`, clearly labeling the generated curve as `Eq. 43 partial` and the digitized point as `Figure 19 full`;
- `validation/comparison.json`, with separate `figure14_tree`, `factor_two_1202`, `phase_space`, and `convergence` verdicts.

Overall status is `validated` only when every applicable verdict passes.

- [ ] **Step 5: Add CLI validation command**

```text
graal-theory validate --bundle outputs/e1200
```

Exit `0` only for `validated`; exit `2` for a completed but failed scientific comparison; exit `1` for malformed input or runtime failure.

- [ ] **Step 6: Run validation tests and explicit regression**

Run: `cd theory && python -m pytest tests/test_validation.py -q`

Expected: unit tests pass.

Run: `cd theory && python -m pytest tests/test_reference_regression.py -q`

Expected: Figure 14 tree and factor-of-two validations pass at configured Sobol resolution. If either fails, preserve diagnostics and stop; do not relax tolerances or retune parameters.

- [ ] **Step 7: Commit Task 8**

```bash
git add theory/references/figure14_eta_p_tree.csv theory/references/figure19_total_1202.csv theory/references/digitization.json theory/src/graal_theory/validation.py theory/src/graal_theory/cli.py theory/tests/test_validation.py theory/tests/test_reference_regression.py
git commit -m "test(theory): validate delta1700 prediction"
```

### Task 9: Document Reproduction Workflow and Run Final Verification

**Files:**
- Modify: `theory/README.md`
- Create: `theory/references/parameter_provenance.md`
- Create: `theory/references/model_scope.md`
- Test: entire `theory/tests/` suite

**Interfaces:**
- Consumes: all previous tasks.
- Produces: reproducible user workflow, equation-to-code map, explicit supported-scope statement, and final verification evidence.

- [ ] **Step 1: Document exact setup and execution commands**

README must contain:

```bash
cd theory
python -m pip install -e '.[test]'
graal-theory predict --energy 1.2 --energy 1.202 --sobol-power 15 --output outputs/e1200
graal-theory validate --bundle outputs/e1200
python -m pytest -q
```

State prominently that output is tree-level Eq. 43 partial theory, not full Figure 19, not beam asymmetry, and not integrated with Stage 07.

- [ ] **Step 2: Add equation-to-code provenance table**

`parameter_provenance.md` maps every central parameter and formula to source key, page, equation/table, JSON key, and responsible function. Minimum formula rows: Eqs. 36, 37, 39, 43, 44, 45, and 46 of `doering_2006_prc`.

- [ ] **Step 3: Add supported-scope document**

`model_scope.md` lists:

- included: Figure 11 tree mechanism, Eq. 43, central values, unpolarized partial observables;
- excluded: Eq. 39 inserted into rescattering Eq. 26, other Figure 14 curves, coherent sum, uncertainty band, Figure 19 reproduction, beam asymmetry, experimental overlay.

- [ ] **Step 4: Run complete standalone suite**

Run: `cd theory && python -m pytest -q`

Expected: all tests pass.

- [ ] **Step 5: Run clean end-to-end calculation**

Run:

```bash
cd theory
run_dir="outputs/final-e1200"
graal-theory predict --energy 1.2 --energy 1.202 --sobol-power 16 --output "$run_dir" --replace
graal-theory validate --bundle "$run_dir"
```

Expected: validation exits `0`; manifest scope is `partial:delta1700_eta_delta_tree_eq43`; comparison status is `validated`; all four output artifacts exist.

- [ ] **Step 6: Verify isolation from existing project**

Run from repository root:

```bash
git diff --name-only HEAD~1 -- . ':!theory' ':!docs/superpowers/plans/2026-09-30-standalone-theory-model.md'
```

Expected: no output. Also run existing focused packaging test without installing theory into the root package:

```bash
python -m pytest tests/test_packaging.py -q
```

Expected: existing package tests pass unchanged.

- [ ] **Step 7: Commit Task 9**

```bash
git add theory/README.md theory/references/parameter_provenance.md theory/references/model_scope.md
git commit -m "docs(theory): document standalone reproduction"
```

## Final Review Gate

After Task 9, review the entire branch against the design specification with special attention to:

1. source completeness and exact equation conventions;
2. spin-transition ordering and polarization averaging;
3. phase-space and baryon-normalization factors;
4. distinction between partial Eq. 43 output and full Figure 19 theory;
5. absence of changes or imports involving existing pipeline stages.

No work on beam asymmetry, additional amplitudes, stage renumbering, or Figure 4 overlays begins under this plan.
