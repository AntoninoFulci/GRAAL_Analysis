# VIS Beam-Asymmetry Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and locally execute a VIS-specific `eta pi0 p` chain over `0.9313--1.10 GeV`, then add its result as the first row of a five-row UV+VIS Figure 4.

**Architecture:** A shared immutable beam-profile registry supplies UV/VIS identity, Compton polarization, and energy edges to each existing stage. VIS Monte Carlo, BDT artifacts, reconstruction, and asymmetry output remain independent from UV; a final reader/compositor combines only extracted points. Existing UV defaults stay compatible, while every VIS command names profile `vis` explicitly and validates its artifacts.

**Tech Stack:** Python 3.10+, NumPy, SciPy, XGBoost, PyROOT/ROOT C++ macros, uproot, Matplotlib, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-vis-beam-asymmetry-design.md`

## Global Constraints

- VIS analysis range is exactly `0.9313 <= E_gamma <= 1.10 GeV`.
- UV energy edges remain exactly `1.10, 1.20, 1.30, 1.40, 1.50 GeV`.
- Final row order is VIS `0.9313--1.10`, then four existing UV rows.
- Final point x-coordinates are geometric mass-bin centers.
- Fit only bins containing at least 20 selected `POL1 + POL2` events; accept 20 and skip 19.
- Accept a run only when calibrated `POL1`, `POL2`, and `BREM` all exist exactly once.
- Drop events without valid `(run, strip)` exposure; never synthesize exposure.
- Train VIS BDT from dedicated VIS MC; never reuse UV booster as VIS model.
- Required VIS MC channels are `eta_pi0`, `pi0pi0`, `3pi0`, `eta_via_3pi0`, `4pi0`, and `eta_pi0_via_3pi0`.
- All new runtime artifacts live below `test_data/vis/` or `test_data/beam_asymmetry/uv_vis/`.
- Do not overwrite, move, or renumber existing UV artifacts or UV local energy bins.
- Bootstrap replicas remain zero. Do not add a new background correction, systematic study, or feasibility threshold.
- Preserve all existing dirty-worktree edits. Never revert unrelated changes. Inspect `git diff` before every commit and stage only files named by the current task.
- Some listed `07_observable_extraction` files already contain approved uncommitted UV work. Preserve that state and require its targeted regression tests to pass before committing overlapping files.

## Review Focus

1. Source files containing energies above `1.10 GeV` must produce no VIS reconstructed/asymmetry event outside the exact interval; Task 6 adds the reconstruction boundary test and Task 7 adds extraction boundary tests.
2. A calibrated run missing any one of `POL1`, `POL2`, or `BREM` must disappear atomically, while complete runs remain; Task 1 preserves and expands this ROOT exposure test for VIS.
3. Legacy provenance without profile metadata may run only through the UV compatibility path and must be rejected for VIS; Tasks 5 and 6 pin both cases.
4. VIS MC inventory must accept exactly the six requested channels, fail when one is absent, and ignore excluded above-threshold channels; Task 3 tests the subset-aware inventory.
5. A 19-event physical bin must return no fit, a 20-event two-polarization bin must fit, and a one-polarization bin must still skip safely; Task 7 tests both estimators.

---

### Task 1: Shared UV/VIS beam profiles and exposure routing

**Files:**
- Create: `00_common/physics/beam_profiles.py`
- Create: `00_common/tests/test_beam_profiles.py`
- Modify: `07_observable_extraction/calibration/flux_v2.py`
- Modify: `07_observable_extraction/tests/test_calibration_io.py`

**Interfaces:**
- Consumes: `linear_polarization_transfer()` and wavelength constants from `graal_common.physics.compton`.
- Produces: `BeamProfile`, `UV_PROFILE`, `VIS_PROFILE`, `BEAM_PROFILES`, and `get_beam_profile(name: str) -> BeamProfile`.
- Produces profile fields `name`, `target`, `beam_type`, `manifest_group`, `laser_wavelength_nm`, `energy_edges_gev`; property `energy_range_gev`; method `polarization(energy_gev: float) -> float`.

- [ ] **Step 1: Write profile registry tests**

```python
def test_vis_profile_is_exact_analysis_contract():
    profile = get_beam_profile("vis")
    assert profile.target == "P"
    assert profile.beam_type == "VIS"
    assert profile.manifest_group == "P_VIS"
    assert profile.laser_wavelength_nm == 514.0
    assert profile.energy_edges_gev == (0.9313, 1.10)
    assert profile.energy_range_gev == (0.9313, 1.10)


def test_unknown_profile_lists_valid_names():
    with pytest.raises(ValueError, match="uv, vis"):
        get_beam_profile("green")


def test_vis_polarization_uses_green_laser_transfer():
    expected = linear_polarization_transfer(1000.0, ELECTRON_ENERGY_MEV, 514.0)
    assert VIS_PROFILE.polarization(1.0) == pytest.approx(expected)
```

- [ ] **Step 2: Run profile tests and verify failure**

Run: `pytest -q 00_common/tests/test_beam_profiles.py`

Expected: collection/import failure because `beam_profiles.py` does not exist.

- [ ] **Step 3: Implement immutable profile registry**

```python
@dataclass(frozen=True)
class BeamProfile:
    name: str
    target: str
    beam_type: str
    manifest_group: str
    laser_wavelength_nm: float
    energy_edges_gev: tuple[float, ...]

    @property
    def energy_range_gev(self) -> tuple[float, float]:
        return self.energy_edges_gev[0], self.energy_edges_gev[-1]

    def polarization(self, energy_gev: float) -> float:
        return linear_polarization_transfer(
            energy_gev * 1000.0,
            ELECTRON_ENERGY_MEV,
            self.laser_wavelength_nm,
        )


UV_PROFILE = BeamProfile("uv", "P", "UV", "P_UV", 351.0,
                         (1.10, 1.20, 1.30, 1.40, 1.50))
VIS_PROFILE = BeamProfile("vis", "P", "VIS", "P_VIS", 514.0,
                          (0.9313, 1.10))
BEAM_PROFILES = {item.name: item for item in (UV_PROFILE, VIS_PROFILE)}
```

Validate in `BeamProfile.__post_init__` that the name/strings are non-empty,
wavelength is finite and positive, at least two edges exist, and all edges are
finite and strictly increasing. `get_beam_profile()` raises one explicit
`ValueError` naming `uv, vis`.

- [ ] **Step 4: Add VIS ROOT-exposure regression**

Extend `_write_flux_root()` fixture use with a VIS manifest and call:

```python
profile = get_beam_profile("vis")
exposures = load_exposures(
    root_path,
    manifest_path=manifest,
    polarization_model=profile.polarization,
    target=profile.target,
    beam_type=profile.beam_type,
    energy_range=profile.energy_range_gev,
)
assert {run for run, _ in exposures} == {1999}
assert all(0.9313 <= item.energy_gev <= 1.10 for item in exposures.values())
```

Fixture includes complete run 1999 and run 2071 without BREM. Assert warning
contains `skipped run 2071` and `missing BREM`.

- [ ] **Step 5: Make exposure error text profile-neutral**

Replace CSV fallback error `no selected proton/UV exposures in energy range`
with:

```python
raise ValueError(
    f"no selected {target}/{beam_type} exposures in energy range"
)
```

Keep current run-atomic ROOT loader behavior unchanged.

- [ ] **Step 6: Run focused tests**

Run: `pytest -q 00_common/tests/test_beam_profiles.py 07_observable_extraction/tests/test_calibration_io.py`

Expected: all pass, including existing incomplete-run tests.

- [ ] **Step 7: Commit**

```bash
git add 00_common/physics/beam_profiles.py \
        00_common/tests/test_beam_profiles.py \
        07_observable_extraction/calibration/flux_v2.py \
        07_observable_extraction/tests/test_calibration_io.py
git commit -m "feat: add UV and VIS beam profiles"
```

### Task 2: Select only requested VIS pre-analysis input

**Files:**
- Modify: `02_event_selector/select_events.py`
- Modify: `tests/test_event_selector.py`

**Interfaces:**
- Consumes: existing `run(input_dir, output_dir, threads=...)` selection logic.
- Produces: optional `pattern: str = "pre_*.root"` argument on `run()` and CLI `--pattern`; legacy calls retain current behavior.

- [ ] **Step 1: Write file-pattern isolation tests**

```python
def test_run_processes_only_requested_preanalysis_pattern(tmp_path, monkeypatch):
    input_dir = tmp_path / "pre"
    input_dir.mkdir()
    (input_dir / "pre_analisi_1998_uv.root").touch()
    (input_dir / "pre_analisi_1999_vis.root").touch()
    seen = []
    monkeypatch.setattr(selector, "_select_file",
                        lambda source, target: seen.append((source.name, target.name)))

    selector.run(input_dir, tmp_path / "selected", threads=1,
                 pattern="pre_analisi_1999_vis.root")

    assert seen == [("pre_analisi_1999_vis.root", "analisi_1999_vis.root")]


def test_run_rejects_pattern_with_directory_component(tmp_path):
    with pytest.raises(ValueError, match="basename glob"):
        selector.run(tmp_path, tmp_path / "out", pattern="other/pre_*.root")
```

- [ ] **Step 2: Run isolation tests and verify failure**

Run: `pytest -q tests/test_event_selector.py -k 'pattern or requested'`

Expected: failure because `run()` has no `pattern` argument.

- [ ] **Step 3: Implement basename-glob selection**

Add CLI option:

```python
p.add_argument(
    "--pattern",
    default="pre_*.root",
    help="basename glob for pre-analysis ROOT files",
)
```

Change signature and discovery:

```python
def run(input_dir: Path, output_dir: Path, *, threads: int = 1,
        pattern: str = "pre_*.root") -> None:
    if Path(pattern).name != pattern:
        raise ValueError("pattern must be a basename glob without directories")
    root_files = sorted(
        path for path in input_dir.glob(pattern)
        if path.is_file() and path.suffix == ".root" and path.name.startswith("pre_")
    )
```

Use the actual pattern in the empty-input error. Pass `args.pattern` from
`main()`.

- [ ] **Step 4: Run selector regressions**

Run: `pytest -q tests/test_event_selector.py`

Expected: all pass; default still processes both matching files.

- [ ] **Step 5: Commit**

```bash
git add 02_event_selector/select_events.py tests/test_event_selector.py
git commit -m "feat: select pre-analysis files by pattern"
```

### Task 3: Parameterize Monte Carlo energy windows and subset inventory

**Files:**
- Create: `03_mc_simulation/generators/beam_window.h`
- Modify: all nine `03_mc_simulation/generators/generate_*_dataset.C`
- Modify: `03_mc_simulation/mc_status.py`
- Modify: `03_mc_simulation/tests/test_generator_physics.py`
- Modify: `03_mc_simulation/tests/test_mc_status.py`

**Interfaces:**
- Consumes: each channel's locally calculated physical `threshold`.
- Produces: generator signature `(int Nevents=1000000, double requested_min_gev=-1.0, double requested_max_gev=1.75, const char *output_path=<legacy filename>)`.
- Produces: `ResolveBeamWindow(threshold, requested_min, requested_max)` returning validated lower/upper values.
- Produces: `status(data_dir, channels=CHANNEL_NAMES)` and CLI `--channels` for subset checks.

- [ ] **Step 1: Write source-contract and helper tests**

```python
@pytest.mark.parametrize("path", GENERATOR_FILES, ids=lambda path: path.stem)
def test_generators_accept_energy_window_and_output_path(path):
    source = path.read_text()
    assert "requested_min_gev" in source
    assert "requested_max_gev" in source
    assert "output_path" in source
    assert "ResolveBeamWindow" in source
    assert "rng.Uniform(beam_window.low, beam_window.high)" in source
```

Add ROOT-backed test using `generate_eta_pi0_dataset.C` with 200 events,
`0.95`, `1.00`, and a temporary output path. Read `beam_true.fE` with uproot
and assert every value is within `[0.95, 1.00)`.

- [ ] **Step 2: Write subset-status tests**

```python
VIS = ("eta_pi0", "pi0pi0", "3pi0", "eta_via_3pi0", "4pi0",
       "eta_pi0_via_3pi0")

def test_vis_subset_does_not_require_above_threshold_channels(tmp_path):
    for name in VIS:
        _make_mc(tmp_path, name)
    assert ms.all_present(ms.status(tmp_path, channels=VIS))


def test_vis_subset_fails_when_required_channel_is_missing(tmp_path):
    for name in VIS[:-1]:
        _make_mc(tmp_path, name)
    assert not ms.all_present(ms.status(tmp_path, channels=VIS))
```

- [ ] **Step 3: Run tests and verify failures**

Run: `pytest -q 03_mc_simulation/tests/test_generator_physics.py 03_mc_simulation/tests/test_mc_status.py`

Expected: source-contract failures and `status()` keyword failure.

- [ ] **Step 4: Implement shared C++ beam-window validation**

```cpp
struct BeamWindow {
    double low;
    double high;
};

inline BeamWindow ResolveBeamWindow(double threshold,
                                    double requested_min_gev,
                                    double requested_max_gev) {
    const double low = std::max(
        threshold,
        requested_min_gev < 0.0 ? threshold : requested_min_gev
    );
    if (!std::isfinite(low) || !std::isfinite(requested_max_gev)
        || requested_max_gev <= low) {
        throw std::invalid_argument("beam energy window is empty or invalid");
    }
    return {low, requested_max_gev};
}
```

Include `<algorithm>`, `<cmath>`, and `<stdexcept>` in `beam_window.h`.

- [ ] **Step 5: Update every generator without changing legacy calls**

For each macro, include `beam_window.h`, update function arguments, replace
hard-coded output filename with `output_path`, calculate:

```cpp
const BeamWindow beam_window = ResolveBeamWindow(
    threshold, requested_min_gev, requested_max_gev
);
```

and draw with:

```cpp
double Ebeam = rng.Uniform(beam_window.low, beam_window.high);
```

Keep each legacy default filename and `1.75 GeV` maximum unchanged.

- [ ] **Step 6: Implement channel-subset MC status**

Validate requested names through `get_channel()`, preserve caller order, and
add:

```python
parser.add_argument("--channels", nargs="+", choices=CHANNEL_NAMES,
                    default=CHANNEL_NAMES)
```

`main()` passes `args.channels` to `status()`; report/exit semantics remain
`0=complete`, `1=missing`, `2=internal error` for the requested subset.

- [ ] **Step 7: Run MC tests**

Run: `pytest -q 03_mc_simulation/tests/test_generator_physics.py 03_mc_simulation/tests/test_mc_status.py`

Expected: all pass; ROOT-backed tests skip only if ROOT executable is absent.

- [ ] **Step 8: Commit**

```bash
git add 03_mc_simulation/generators/beam_window.h \
        03_mc_simulation/generators/generate_*_dataset.C \
        03_mc_simulation/mc_status.py \
        03_mc_simulation/tests/test_generator_physics.py \
        03_mc_simulation/tests/test_mc_status.py
git commit -m "feat: generate MC in explicit beam windows"
```

### Task 4: Measure a profile-bounded VIS beam spectrum

**Files:**
- Modify: `04_bdt_training/beam_spectrum.py`
- Modify: `04_bdt_training/tests/test_beam_spectrum.py`

**Interfaces:**
- Consumes: `get_beam_profile()` from Task 1.
- Produces: CLI `--profile {uv,vis}`; absent profile preserves range `(0.5, 2.0)` and 150 bins.
- Produces: `default_bins_for_range(range_: tuple[float, float]) -> int`, returning 17 for VIS.

- [ ] **Step 1: Write profile-spectrum tests**

```python
def test_vis_profile_uses_exact_range_and_seventeen_bins():
    range_, bins = beam_spectrum.settings_for_profile("vis", bins=None)
    assert range_ == (0.9313, 1.10)
    assert bins == 17


def test_profile_spectrum_drops_source_energies_outside_vis():
    energies = np.array([0.90, 0.9313, 1.00, 1.10, 1.20])
    spectrum = from_energies(energies, bins=17, range_=(0.9313, 1.10))
    assert (spectrum.density * np.diff(spectrum.edges)).sum() == pytest.approx(1.0)
    assert spectrum.edges[[0, -1]].tolist() == pytest.approx([0.9313, 1.10])
```

Also assert parser default `profile is None` and explicit `--profile vis`.

- [ ] **Step 2: Run focused tests and verify failure**

Run: `pytest -q 04_bdt_training/tests/test_beam_spectrum.py`

Expected: missing profile settings functions/CLI.

- [ ] **Step 3: Implement profile settings**

```python
TARGET_BIN_WIDTH_GEV = 0.010

def default_bins_for_range(range_: tuple[float, float]) -> int:
    low, high = range_
    if not np.isfinite((low, high)).all() or high <= low:
        raise ValueError("beam-spectrum range must be finite and increasing")
    return int(np.ceil((high - low) / TARGET_BIN_WIDTH_GEV))

def settings_for_profile(profile_name: str | None,
                         bins: int | None) -> tuple[tuple[float, float], int]:
    if profile_name is None:
        return DEFAULT_RANGE, DEFAULT_BINS if bins is None else bins
    profile = get_beam_profile(profile_name)
    return profile.energy_range_gev, (
        default_bins_for_range(profile.energy_range_gev) if bins is None else bins
    )
```

Make `--bins` default `None`, add profile choices, and have `main()` pass
resolved range/bins to `measure()`.

- [ ] **Step 4: Run beam-spectrum tests**

Run: `pytest -q 04_bdt_training/tests/test_beam_spectrum.py`

Expected: all pass; legacy no-profile behavior still uses 150 bins.

- [ ] **Step 5: Commit**

```bash
git add 04_bdt_training/beam_spectrum.py \
        04_bdt_training/tests/test_beam_spectrum.py
git commit -m "feat: measure profile-specific beam spectra"
```

### Task 5: Carry profile identity through Stage-1 dataset and artifacts

**Files:**
- Modify: `04_bdt_training/dataset/stage1_dataset.py`
- Modify: `04_bdt_training/build_background_features.py`
- Modify: `04_bdt_training/train_bdt_stage1.py`
- Modify: `00_common/stage1/artifacts.py`
- Modify: `04_bdt_training/tests/test_stage1_dataset.py`
- Modify: `04_bdt_training/tests/test_build_background_features.py`
- Modify: `00_common/tests/test_stage1_artifacts.py`

**Interfaces:**
- Consumes: profile registry and `BeamSpectrum.edges`.
- Produces optional `beam_profile`, `energy_min_gev`, `energy_max_gev` fields in `Stage1DatasetMetadata` and `Stage1Provenance`.
- Produces `build_background_features --profile {uv,vis}`; VIS requires spectrum endpoints matching profile endpoints.
- Maintains loading of old NPZ/JSON artifacts without new keys.

- [ ] **Step 1: Write VIS dataset round-trip and partial-metadata rejection tests**

```python
metadata = Stage1DatasetMetadata(
    feature_names=tuple(FEATURE_NAMES_S1),
    signal_channel="eta_pi0",
    hypothesis="eta_pi0",
    signal_prior=0.5,
    beam_reweighted=True,
    beam_profile="vis",
    energy_min_gev=0.9313,
    energy_max_gev=1.10,
)
save_stage1_dataset(path, replace(_dataset(), metadata=metadata))
assert load_stage1_dataset(path).metadata == metadata

with pytest.raises(ValueError, match="profile energy metadata must be complete"):
    save_stage1_dataset(path, replace(dataset, metadata=replace(
        metadata, energy_max_gev=None)))

with pytest.raises(ValueError, match="both signal and background"):
    save_stage1_dataset(path, replace(dataset, y=np.ones(len(dataset.y))))
```

Keep old-format fixture test and assert all three new fields are `None`.

- [ ] **Step 2: Write artifact backward-compatibility tests**

```python
legacy = Stage1Provenance.from_json(LEGACY_JSON)
assert legacy.beam_profile is None

vis = replace(legacy, beam_profile="vis", energy_min_gev=0.9313,
              energy_max_gev=1.10)
assert Stage1Provenance.from_json(vis.to_json()) == vis
```

Reject unknown profile, one missing bound, non-finite bounds, and decreasing
bounds. Continue rejecting unknown JSON keys.

- [ ] **Step 3: Run dataset/artifact tests and verify failures**

Run: `pytest -q 00_common/tests/test_stage1_artifacts.py 04_bdt_training/tests/test_stage1_dataset.py`

Expected: constructor/key failures for new metadata.

- [ ] **Step 4: Extend NPZ metadata compatibly**

Add optional fields to dataclass. Loader reads them only when present. Saver
writes the three keys only when all three are present; when all are `None`, it
keeps the legacy eight-key schema. Any partial set raises:

```python
raise ValueError("profile energy metadata must be complete or entirely absent")
```

Validate profile name through `get_beam_profile()` and require stored bounds to
match that profile exactly within `1e-12`.

Extend `_validate_dataset()` to require labels to be exactly binary `0/1` and
to require both classes. This makes a one-class training input fail before
XGBoost rather than producing a meaningless model.

- [ ] **Step 5: Extend provenance JSON with optional keys**

Split required legacy keys from optional profile keys:

```python
_OPTIONAL_PROVENANCE_KEYS = (
    "beam_profile", "energy_min_gev", "energy_max_gev",
)
```

`from_json()` accepts absence of all optional keys but rejects partial
presence. `to_json()` writes optional keys only for profiled artifacts.

- [ ] **Step 6: Add builder profile validation**

Add CLI profile choice defaulting to `None`. After loading spectrum:

```python
profile = get_beam_profile(args.profile) if args.profile else None
if profile is not None:
    observed = (float(beam_target.edges[0]), float(beam_target.edges[-1]))
    if not np.allclose(observed, profile.energy_range_gev, atol=1e-12, rtol=0):
        raise ValueError(
            f"beam spectrum range {observed} does not match profile "
            f"{profile.name!r} range {profile.energy_range_gev}"
        )
```

Stamp profile name and bounds into saved metadata.

- [ ] **Step 7: Stamp dataset profile into trained model provenance**

Copy the three metadata fields when constructing `Stage1Provenance`; do not
infer them from output directory names.

- [ ] **Step 8: Test builder and trainer propagation**

Add a synthetic VIS spectrum fixture and assert profile-range mismatch fails
before channel loading. Train fake classifier from VIS NPZ and assert generated
JSON contains:

```json
{
  "beam_profile": "vis",
  "energy_min_gev": 0.9313,
  "energy_max_gev": 1.1
}
```

Run: `pytest -q 00_common/tests/test_stage1_artifacts.py 04_bdt_training/tests/test_stage1_dataset.py 04_bdt_training/tests/test_build_background_features.py`

Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add 00_common/stage1/artifacts.py \
        00_common/tests/test_stage1_artifacts.py \
        04_bdt_training/dataset/stage1_dataset.py \
        04_bdt_training/build_background_features.py \
        04_bdt_training/train_bdt_stage1.py \
        04_bdt_training/tests/test_stage1_dataset.py \
        04_bdt_training/tests/test_build_background_features.py
git commit -m "feat: stamp beam profile on Stage-1 artifacts"
```

### Task 6: Enforce profile compatibility and energy range in reconstruction

**Files:**
- Modify: `05_reconstruction/runtime/stage1_gate.py`
- Modify: `05_reconstruction/runtime/reco_core.py`
- Modify: `05_reconstruction/reconstruct_eta_pi0_bdt.py`
- Modify: `05_reconstruction/tests/test_stage1_gate.py`
- Modify: `05_reconstruction/tests/test_reco_core.py`
- Modify: `05_reconstruction/tests/test_cli_options.py`
- Modify: `05_reconstruction/tests/test_cli_contracts.py`

**Interfaces:**
- Consumes: profiled `Stage1Provenance` and `BeamProfile`.
- Produces: `Stage1Gate.check_profile(expected: BeamProfile) -> None`.
- Produces: optional `RecoConfig.energy_range_gev`; events outside it never reach BDT gate.
- Produces: BDT CLI `--profile {uv,vis}`; absent option preserves legacy behavior.

- [ ] **Step 1: Write profile compatibility tests**

```python
def test_legacy_model_is_rejected_for_vis():
    gate = Stage1Gate(FakeModel(0.9), 0.5, beam_profile=None)
    with pytest.raises(ValueError, match="legacy.*VIS"):
        gate.check_profile(VIS_PROFILE)


def test_legacy_model_remains_accepted_for_uv():
    gate = Stage1Gate(FakeModel(0.9), 0.5, beam_profile=None)
    gate.check_profile(UV_PROFILE)


def test_profiled_model_requires_exact_energy_bounds():
    gate = Stage1Gate(FakeModel(0.9), 0.5, beam_profile="vis",
                      energy_range_gev=(0.95, 1.10))
    with pytest.raises(ValueError, match="energy range"):
        gate.check_profile(VIS_PROFILE)
```

- [ ] **Step 2: Write pre-gate energy-filter test**

Give fake chain one event at `0.9312`, one at `0.9313`, one at `1.10`, and one
at `1.1001`. Use gate recording scored rows. Assert only exact-boundary events
reach `scores_many()` and output.

- [ ] **Step 3: Run reconstruction tests and verify failures**

Run: `pytest -q 05_reconstruction/tests/test_stage1_gate.py 05_reconstruction/tests/test_reco_core.py 05_reconstruction/tests/test_cli_options.py 05_reconstruction/tests/test_cli_contracts.py`

Expected: missing profile methods/config fields.

- [ ] **Step 4: Extend gate identity and compatibility check**

Store optional profile/range from provenance on `Stage1Gate`. Implement:

```python
def check_profile(self, expected: BeamProfile) -> None:
    if self.beam_profile is None:
        if expected.name == "uv":
            return
        raise ValueError("legacy Stage-1 model has no profile metadata and cannot gate VIS")
    if self.beam_profile != expected.name:
        raise ValueError(
            f"Stage-1 model profile {self.beam_profile!r} does not match "
            f"requested profile {expected.name!r}"
        )
    if self.energy_range_gev != expected.energy_range_gev:
        raise ValueError(
            f"Stage-1 model energy range {self.energy_range_gev} does not match "
            f"requested range {expected.energy_range_gev}"
        )
```

Do not infer profile from model path.

- [ ] **Step 5: Filter energy before buffering or BDT scoring**

Add `energy_range_gev: tuple[float, float] | None = None` to `RecoConfig`,
validate it once at function start, and in event loop add:

```python
if cfg.energy_range_gev is not None:
    low, high = cfg.energy_range_gev
    energy = float(chain.beam.E())
    if energy < low or energy > high:
        n_outside_energy += 1
        continue
```

Print `Skipped (outside beam profile): N` in summary.

- [ ] **Step 6: Add BDT CLI profile option**

Parse `--profile` with registry choices and default `None`. For explicit
profile, call `gate.check_profile(profile)` before reconstruction and assign
`cfg.energy_range_gev = profile.energy_range_gev`.

- [ ] **Step 7: Run reconstruction tests**

Run: `pytest -q 05_reconstruction/tests`

Expected: all pass, including existing BDT/chi-square equivalence tests.

- [ ] **Step 8: Commit**

```bash
git add 05_reconstruction/runtime/stage1_gate.py \
        05_reconstruction/runtime/reco_core.py \
        05_reconstruction/reconstruct_eta_pi0_bdt.py \
        05_reconstruction/tests/test_stage1_gate.py \
        05_reconstruction/tests/test_reco_core.py \
        05_reconstruction/tests/test_cli_options.py \
        05_reconstruction/tests/test_cli_contracts.py
git commit -m "feat: enforce beam profile during reconstruction"
```

### Task 7: Make asymmetry extraction profile-driven with 20-event gate

**Files:**
- Modify: `07_observable_extraction/core/binning.py`
- Modify: `07_observable_extraction/io/reconstructed_events.py`
- Modify: `07_observable_extraction/core/ratio_fit.py`
- Modify: `07_observable_extraction/core/conditional_likelihood.py`
- Modify: `07_observable_extraction/beam_asymmetry.py`
- Modify: `07_observable_extraction/tests/test_binning.py`
- Modify: `07_observable_extraction/tests/test_reconstructed_events.py`
- Modify: `07_observable_extraction/tests/test_ratio_fit.py`
- Modify: `07_observable_extraction/tests/test_conditional_likelihood.py`
- Modify: `07_observable_extraction/tests/test_beam_asymmetry_cli.py`

**Interfaces:**
- Consumes: `BeamProfile.energy_edges_gev`, exposure profile fields, reconstructed VIS file.
- Produces explicit `energy_edges` argument on energy binning and both grid extractors, with UV default for compatibility.
- Produces `min_events: int = 20` on both grid extractors.
- Produces observable CLI `--profile {uv,vis}`, default `uv`.

- [ ] **Step 1: Write generic energy-edge tests**

```python
def test_vis_energy_bin_includes_both_outer_edges():
    edges = np.array([0.9313, 1.10])
    assert energy_bin_index(0.9313, edges) == 0
    assert energy_bin_index(1.10, edges) == 0
    assert energy_bin_index(0.9312, edges) is None
    assert energy_bin_index(1.1001, edges) is None
```

- [ ] **Step 2: Write 19/20 event tests for ratio and likelihood grids**

Parameterize estimator tests with 19 and 20 events split across POL1/POL2.
For the 20-event ratio fixture, use five distinct phi-bin centers with two
POL1 and two POL2 events at each center so the fit has nonzero Poisson errors.
Use VIS energy `1.0`, a mass in first Ajaka bin, and valid exposure. Assert no
result for 19 and exactly one result for 20. Add a 20-event all-POL1 case and
assert no result.

- [ ] **Step 3: Write reconstructed-event VIS cut test**

Call `select_sigma_events(..., energy_range=(0.9313, 1.10))` on events at four
boundary-adjacent energies. Assert only exact boundaries survive after valid
exposure filtering.

- [ ] **Step 4: Run focused tests and verify failures**

Run: `pytest -q 07_observable_extraction/tests/test_binning.py 07_observable_extraction/tests/test_reconstructed_events.py 07_observable_extraction/tests/test_ratio_fit.py 07_observable_extraction/tests/test_conditional_likelihood.py`

Expected: signature failures and current likelihood acceptance of sub-20 bins.

- [ ] **Step 5: Parameterize binning and reconstructed selection**

Keep `ENERGY_EDGES_GEV` as UV compatibility alias. Change:

```python
def energy_bin_index(energy_gev: float,
                     energy_edges: np.ndarray = ENERGY_EDGES_GEV) -> int | None:
    return bin_index(energy_gev, energy_edges)
```

Add required keyword `energy_range` to `_select_by_polarization()` and optional
UV default to public selectors. Use inclusive outer boundaries.

- [ ] **Step 6: Parameterize ratio/likelihood grids and apply common count gate**

Both extractors convert/validate `energy_edges`, loop over those edges, and
compute:

```python
selected = energy_mask & mass_mask & np.isin(polarization, (1, 2))
if np.count_nonzero(selected) < min_events:
    continue
if not np.any(polarization[selected] == 1) or not np.any(polarization[selected] == 2):
    continue
```

Ratio histograms use the already filtered `selected` mask. Exposure bin lookup
passes the same `energy_edges` to `energy_bin_index()`.

- [ ] **Step 7: Route profile through observable orchestration**

Add CLI profile. In `run()`:

```python
profile = get_beam_profile(args.profile)
energy_edges = np.asarray(profile.energy_edges_gev, dtype=np.float64)
exposures = load_exposures(
    args.flux_file,
    manifest_path=args.run_manifest,
    run_numbers=np.unique(all_nominal_events.run_number),
    polarization_model=profile.polarization,
    target=profile.target,
    beam_type=profile.beam_type,
    energy_range=profile.energy_range_gev,
)
events = select_sigma_events(
    all_nominal_events, exposures,
    energy_range=profile.energy_range_gev,
    drop_missing=True,
)
```

Thread `energy_edges` through `_extract_sample()`, background helpers,
bootstrap callbacks, multiplicity callbacks, ROOT payload, and provenance.
Use `profile=<name>` in provenance. Keep bootstrap default zero.

- [ ] **Step 8: Assert VIS CLI routing**

Extend CLI test monkeypatches to capture profile-derived arguments. Assert VIS
uses beam type `VIS`, exact interval, VIS polarization callable, and ROOT
payload energy edges `[0.9313, 1.10]`.

- [ ] **Step 9: Run extraction tests**

Run: `pytest -q 07_observable_extraction/tests/test_binning.py 07_observable_extraction/tests/test_reconstructed_events.py 07_observable_extraction/tests/test_ratio_fit.py 07_observable_extraction/tests/test_conditional_likelihood.py 07_observable_extraction/tests/test_beam_asymmetry_cli.py`

Expected: all pass, including 19/20 boundary and current UV regressions.

- [ ] **Step 10: Commit**

```bash
git add 07_observable_extraction/core/binning.py \
        07_observable_extraction/io/reconstructed_events.py \
        07_observable_extraction/core/ratio_fit.py \
        07_observable_extraction/core/conditional_likelihood.py \
        07_observable_extraction/beam_asymmetry.py \
        07_observable_extraction/tests/test_binning.py \
        07_observable_extraction/tests/test_reconstructed_events.py \
        07_observable_extraction/tests/test_ratio_fit.py \
        07_observable_extraction/tests/test_conditional_likelihood.py \
        07_observable_extraction/tests/test_beam_asymmetry_cli.py
git commit -m "feat: extract asymmetries by beam profile"
```

### Task 8: Build profile-aware ROOT reader and five-row figures

**Files:**
- Create: `07_observable_extraction/io/root_input.py`
- Create: `07_observable_extraction/combine_profiles.py`
- Create: `07_observable_extraction/tests/test_root_input.py`
- Create: `07_observable_extraction/tests/test_combine_profiles.py`
- Modify: `07_observable_extraction/plotting/figure4.py`
- Modify: `07_observable_extraction/plotting/diagnostics.py`
- Modify: `07_observable_extraction/beam_asymmetry.py`
- Modify: `07_observable_extraction/tests/test_figure4.py`
- Modify: `07_observable_extraction/tests/test_diagnostics.py`

**Interfaces:**
- Consumes: UV and VIS `beam_asymmetry.root` files and Ajaka CSV.
- Produces: `read_output_points(path: Path) -> tuple[OutputPoint, ...]`.
- Produces: `EnergyRow(profile: str, energy_bin: int, low_gev: float, high_gev: float)`.
- Produces generic plotting functions accepting `Mapping[str, Sequence[OutputPoint]]` and ordered rows.
- Produces CLI `python -m observable_extraction.combine_profiles`.

- [ ] **Step 1: Write ROOT round-trip reader test**

Write synthetic payload with both ratio and likelihood points using existing
`write_root_output()`, then:

```python
actual = read_output_points(output)
assert actual == payload.points
```

Also test missing `sigma_points` and malformed/missing ID mapping fail with
path-specific `RuntimeError`.

- [ ] **Step 2: Implement ROOT point reader**

Parse `id_mapping` lines into reverse maps, rebuild `FitDiagnostics`,
`SigmaPoint`, and `OutputPoint` from every tree row, and close ROOT file in a
`finally` block. Use stored `mass_mean_gev` for data contract but plotting will
use geometric `mass_low/high` center.

- [ ] **Step 3: Write five-row layout tests**

```python
rows = combined_energy_rows()
assert [(r.profile, r.energy_bin) for r in rows] == [
    ("vis", 0), ("uv", 0), ("uv", 1), ("uv", 2), ("uv", 3),
]
figure, axes = build_profile_figure4(
    {"vis": vis_points, "uv": uv_points}, rows,
)
assert axes.shape == (5, 3)
assert axes[0, 0].get_ylabel().endswith("0.9313\\leq E_\\gamma\\leq 1.10$ GeV")
```

Inspect plotted data and assert this analysis uses
`0.5 * (mass_low_gev + mass_high_gev)`, not `mass_mean_gev`.

- [ ] **Step 4: Write Ajaka routing test**

Supply one published point with UV `energy_bin=0`. Assert it appears in
combined row 1, never VIS row 0. Preserve existing four-row comparison test.

- [ ] **Step 5: Generalize Figure 4 without breaking UV API**

Implement generic renderer around ordered `EnergyRow` objects. Existing
`build_figure4(points)` wraps it with four UV rows and returns same 4x3 axes.
Single-profile extraction passes rows derived from active profile; VIS produces
1x3 local figure. Combined plot uses five rows.

- [ ] **Step 6: Replace flat comparison/diagnostics with physical grids**

Add grid writers that select by `(profile, energy_bin, pair)`:

- estimator comparison: ratio and likelihood points with asymmetric errors;
- fit diagnostics: ratio only, mass-bin center on x, p-value on left axis,
  `chi2/ndf` on right axis, blank panel text when no fit exists.

Keep existing writer names as UV wrappers where tests/public callers depend on
them. Ensure synthetic likelihood values `p=1, ndf=0` never enter fit
diagnostics.

- [ ] **Step 7: Implement combined CLI**

Parser arguments:

```text
--uv-root       test_data/beam_asymmetry/beam_asymmetry.root
--vis-root      test_data/vis/beam_asymmetry/beam_asymmetry.root
--published-csv test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv
--output-dir    test_data/beam_asymmetry/uv_vis
```

Read points, build fixed combined rows from registry, and write exactly:

```text
figure4_experimental.pdf
figure4_comparison_ajaka2008.pdf
comparison_estimators.pdf
fit_diagnostics.pdf
```

Fail if either ROOT file has no points for its profile.

- [ ] **Step 8: Route local extraction plots through active profile rows**

Update `beam_asymmetry.py` writer calls so UV remains 4x3 and VIS local output
is 1x3. `comparison_estimators.pdf` groups estimators by physical panel;
`fit_diagnostics.pdf` passes ratio points only.

- [ ] **Step 9: Run plotting and I/O tests**

Run: `pytest -q 07_observable_extraction/tests/test_root_input.py 07_observable_extraction/tests/test_figure4.py 07_observable_extraction/tests/test_diagnostics.py 07_observable_extraction/tests/test_combine_profiles.py 07_observable_extraction/tests/test_root_output.py`

Expected: all pass; UV legacy layout remains 4x3, combined layout is 5x3.

- [ ] **Step 10: Commit**

```bash
git add 07_observable_extraction/io/root_input.py \
        07_observable_extraction/combine_profiles.py \
        07_observable_extraction/plotting/figure4.py \
        07_observable_extraction/plotting/diagnostics.py \
        07_observable_extraction/beam_asymmetry.py \
        07_observable_extraction/tests/test_root_input.py \
        07_observable_extraction/tests/test_figure4.py \
        07_observable_extraction/tests/test_diagnostics.py \
        07_observable_extraction/tests/test_combine_profiles.py
git commit -m "feat: compose five-row UV VIS asymmetry figures"
```

### Task 9: Document exact local VIS runbook and verify codebase

**Files:**
- Create: `docs/runbooks/vis-local-analysis.md`

**Interfaces:**
- Consumes: all CLIs completed in Tasks 1--8.
- Produces: copyable local commands and explicit review checkpoints; no new runtime abstraction or edits to existing dirty wiki files.

- [ ] **Step 1: Write runbook with fixed paths and six-channel list**

Document these commands, each from repository root:

```bash
mkdir -p test_data/vis/mc test_data/vis/bdt

python -m event_selector.select_events \
  --input-dir test_data/pre_analyzed \
  --output-dir test_data/vis/selected \
  --pattern pre_analisi_1999_vis.root

python -m mc_simulation.mc_status \
  --data-dir test_data/vis/mc \
  --channels eta_pi0 pi0pi0 3pi0 eta_via_3pi0 4pi0 eta_pi0_via_3pi0

python -m bdt_training.beam_spectrum \
  --selected-dir test_data/vis/selected \
  --profile vis \
  --output test_data/vis/bdt/beam_spectrum.npz

python -m bdt_training.build_background_features \
  --mc-dir test_data/vis/mc \
  --signal-channel eta_pi0 \
  --background-channels pi0pi0 3pi0 eta_via_3pi0 4pi0 eta_pi0_via_3pi0 \
  --beam-spectrum test_data/vis/bdt/beam_spectrum.npz \
  --profile vis \
  --output test_data/vis/bdt/features_stage1.npz

python -m bdt_training.train_bdt_stage1 \
  --features test_data/vis/bdt/features_stage1.npz \
  --hyperparams 04_bdt_training/artifacts/stage1/best_hyperparams.json \
  --out-dir test_data/vis/bdt/artifacts/stage1

python -m reconstruction.reconstruct_eta_pi0_bdt \
  --input-dir test_data/vis/selected \
  --output-file test_data/vis/reco/reco_eta_pi0_bdt.root \
  --model-dir test_data/vis/bdt/artifacts/stage1 \
  --profile vis

python 07_observable_extraction/beam_asymmetry.py \
  --raw-bdt test_data/vis/reco/reco_eta_pi0_bdt.root \
  --profile vis \
  --flux-file data/00_external/flux_calibrated.root \
  --run-manifest config/run_manifest.csv \
  --output-dir test_data/vis/beam_asymmetry \
  --estimator both \
  --bootstrap-replicas 0

python -m observable_extraction.combine_profiles \
  --uv-root test_data/beam_asymmetry/beam_asymmetry.root \
  --vis-root test_data/vis/beam_asymmetry/beam_asymmetry.root \
  --published-csv test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv \
  --output-dir test_data/beam_asymmetry/uv_vis
```

Insert these commands between selection and `mc_status`:

```bash
root -l -b -q '03_mc_simulation/generators/generate_eta_pi0_dataset.C(1000000,0.9313,1.10,"test_data/vis/mc/eta_pi0_mc.root")'
root -l -b -q '03_mc_simulation/generators/generate_pi0pi0_dataset.C(1000000,0.9313,1.10,"test_data/vis/mc/pi0pi0_mc.root")'
root -l -b -q '03_mc_simulation/generators/generate_3pi0_dataset.C(1000000,0.9313,1.10,"test_data/vis/mc/3pi0_mc.root")'
root -l -b -q '03_mc_simulation/generators/generate_eta_via_3pi0_dataset.C(1000000,0.9313,1.10,"test_data/vis/mc/eta_via_3pi0_mc.root")'
root -l -b -q '03_mc_simulation/generators/generate_4pi0_dataset.C(1000000,0.9313,1.10,"test_data/vis/mc/4pi0_mc.root")'
root -l -b -q '03_mc_simulation/generators/generate_eta_pi0_via_3pi0_dataset.C(1000000,0.9313,1.10,"test_data/vis/mc/eta_pi0_via_3pi0_mc.root")'
```

State that above-threshold channels are deliberately absent.

- [ ] **Step 2: Document review checkpoints**

After selection: entry count and filename. After MC: six files and truth beam
window. After training: survival/ESS/AUC/threshold. After reconstruction:
entries and exact observed energy bounds. After extraction: skipped run/event
counts and populated bins. After combination: visual inspection of all four
PDFs.

- [ ] **Step 3: Run full automated suite**

Run: `pytest -q`

Expected: all tests pass; baseline was 609 tests before VIS additions.

- [ ] **Step 4: Check formatting and accidental changes**

Run:

```bash
git diff --check
git status --short
```

Expected: no whitespace errors; `theory/` edits and other pre-existing user
changes remain untouched.

- [ ] **Step 5: Commit documentation**

```bash
git add docs/runbooks/vis-local-analysis.md
git commit -m "docs: add local VIS analysis runbook"
```

### Task 10: Execute local VIS chain and inspect each checkpoint

**Files:**
- Create runtime artifacts only under `test_data/vis/`
- Create combined PDFs only under `test_data/beam_asymmetry/uv_vis/`
- Do not commit generated ROOT, NPZ, JSON model, PNG, or PDF artifacts unless repository policy already tracks the exact destination.

**Interfaces:**
- Consumes: commands in `docs/runbooks/vis-local-analysis.md`.
- Produces: local selected data, six-channel VIS MC, VIS BDT, VIS reconstruction, VIS asymmetries, and four combined review PDFs.

- [ ] **Step 1: Run VIS-only event selection**

Run selector command from runbook. Verify:

```bash
python -c 'import ROOT; p="test_data/vis/selected/analisi_1999_vis.root"; f=ROOT.TFile.Open(p); print(f.Get("h85").GetEntries()); f.Close()'
```

Expected: tree `h85`; no UV selected file in `test_data/vis/selected/`.

- [ ] **Step 2: Generate and inventory six VIS MC channels**

Run six ROOT commands, then subset `mc_status`. Expected status: `6/6`
present. Stop on generator or inventory failure; do not replace a missing
channel with broad-range MC.

- [ ] **Step 3: Measure spectrum and build training dataset**

Run spectrum and feature-builder commands. Inspect NPZ metadata:

```bash
python -c 'import numpy as np; p="test_data/vis/bdt/features_stage1.npz"; d=np.load(p); print(d["beam_profile"].item(), d["energy_min_gev"].item(), d["energy_max_gev"].item(), d["X"].shape, np.isfinite(d["w"]).all())'
```

Expected: `vis 0.9313 1.1`, two-dimensional features, finite weights.

- [ ] **Step 4: Train VIS BDT and review basic diagnostics**

Run trainer. Verify artifact directory contains model, threshold, provenance,
metrics, ROC, score distribution, and feature importance. Record AUC,
threshold, per-channel survival, zero weights, and ESS without imposing a new
pass/fail threshold.

- [ ] **Step 5: Reconstruct VIS sample and verify range**

Run reconstruction. Inspect tree with PyROOT/uproot and assert every stored
beam energy is within `[0.9313, 1.10]`. Record total input, profile-skipped,
BDT-rejected, physics-cut, and written counts.

- [ ] **Step 6: Extract VIS asymmetries**

Run extraction. Confirm warning reports run 2071 skipped for missing BREM and
reports any dropped invalid-exposure events. Verify ROOT binning vector is
exactly `[0.9313, 1.10]`; inspect counts to confirm no emitted point has fewer
than 20 total events.

- [ ] **Step 7: Compose and render five-row output**

Run combined CLI. Render PDFs for visual inspection:

```bash
mkdir -p /tmp/graal-vis-pdf-review
pdftoppm -png -r 120 \
  test_data/beam_asymmetry/uv_vis/figure4_comparison_ajaka2008.pdf \
  /tmp/graal-vis-pdf-review/figure4
```

Expected: five rows, three columns, VIS first, Ajaka points only in UV rows,
geometric bin-center alignment, readable legends, empty inaccessible bins.

- [ ] **Step 8: Re-run full tests after runtime exercise**

Run: `pytest -q`

Expected: all pass. Runtime artifacts do not alter source-test results.

- [ ] **Step 9: Report local results and stop before farm execution**

Report artifact paths, event counts, skipped runs/exposures, BDT metrics, fitted
bin count, and visual issues. Farm commands are prepared only after user
reviews local PDFs; do not launch farm processing in this task.
