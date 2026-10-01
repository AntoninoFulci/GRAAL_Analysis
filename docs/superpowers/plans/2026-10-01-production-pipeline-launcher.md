# Production Pipeline Launcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one small Python launcher that runs the existing analysis from pre-analysis ROOT files through independent UV/VIS models and asymmetries, then produces the combined Ajaka plots in `test_data` or `production` mode.

**Architecture:** `scripts/run_pipeline.py` owns immutable mode configuration, lightweight preflight, an inspectable ordered list of subprocess commands, and sequential execution with a command log. Existing stage entry points continue to own physics and artifact validation; calibration runs once, profile-dependent work remains isolated below `<output>/{uv,vis}`, and only Stage-07 outputs meet in `<output>/combined`.

**Tech Stack:** Python 3.10+, `argparse`, `dataclasses`, `pathlib`, `subprocess`, CERN ROOT/PyROOT, existing GRAAL Python packages, pytest.

**Spec:** `docs/superpowers/specs/2026-10-01-production-pipeline-launcher-design.md`

## Global Constraints

- Support exactly `test_data` and `production` execution modes.
- Start from `pre_analisi_*.root` files containing `h80`; raw `h70` processing stays outside the launcher.
- Use `test_data/pre_analyzed` with `100000` attempted MC events per channel in `test_data` mode.
- Use `data/02_pre_analyzed/pre_analisi` with `1000000` attempted MC events per channel in `production` mode.
- Validate the checked-in manifest and calibrate flux once before profile branches.
- Keep UV and VIS selection, MC, beam spectrum, feature dataset, Stage-1 model, reconstruction, and extraction artifacts separate.
- Train both profile models from scratch with `04_bdt_training/artifacts/stage1/best_hyperparams.json`; do not run grid search.
- Use estimator `both`, bootstrap replicas `0`, and no sideband correction.
- Combine only final Stage-07 point products.
- Refuse nonempty output roots; never delete existing results.
- Preserve existing warning policy; warnings do not fail the launcher when child exit status is zero.
- Add no resume, scheduler, queue, container, structured telemetry, disk threshold, or raw-data pre-analysis.
- Use argument arrays with `shell=False`; never construct shell command strings for execution.
- Do not modify `theory/` files or revert concurrent theory/calibration work.

## Review Focus

- PyROOT imports but `root` executable is missing: preflight must fail before creating output. Covered in Task 2.
- Only one beam profile has matching pre-analysis files: preflight must identify the missing profile, not start a partial campaign. Covered in Task 2.
- Output root already contains any file: preflight must refuse it without deleting or replacing content. Covered in Task 2.
- Repository or output paths contain spaces or ROOT-string metacharacters: argument boundaries must survive spaces, while quote/newline paths must fail explicitly. Covered in Task 3.
- A middle child command exits nonzero: later UV/VIS/combine commands must not run, and the failing exit must appear in the command log. Covered in Task 4.

---

### Task 1: Version Ajaka reference and fix combined-plot defaults

**Files:**
- Create: `07_observable_extraction/references/ajaka2008_figure4_digitized.csv`
- Modify: `.gitignore`
- Modify: `07_observable_extraction/combine_profiles.py:27-50`
- Modify: `07_observable_extraction/tests/test_combine_profiles.py:13-26`
- Test: `07_observable_extraction/tests/test_combine_profiles.py`

**Interfaces:**
- Consumes: existing 58-line digitization at `test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv`, SHA-256 `aab73cc23c54f137eb46f37949911af83f266c50ef5e7f4ae6d33a9b68bedfa7`.
- Produces: `AJAKA_REFERENCE: Path`, production defaults for `build_parser()`, and a tracked canonical CSV available in a clean clone.
- Compatibility: keep the old `test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv` tracked temporarily because current theory tests consume it and theory files are outside this task. Both copies must have the same SHA-256.

- [ ] **Step 1: Write failing default and reference-integrity tests**

Replace the existing default-layout test and add an integrity test:

```python
import hashlib


def test_combined_cli_defaults_use_production_layout():
    args = combine_profiles.build_parser().parse_args([])

    assert args.uv_root == Path(
        "results/production/uv/beam_asymmetry/beam_asymmetry.root"
    )
    assert args.vis_root == Path(
        "results/production/vis/beam_asymmetry/beam_asymmetry.root"
    )
    assert args.published_csv == combine_profiles.AJAKA_REFERENCE
    assert args.output_dir == Path("results/production/combined")


def test_ajaka_reference_is_versioned_and_compatibility_copy_matches():
    canonical = combine_profiles.AJAKA_REFERENCE
    compatibility = (
        Path(__file__).parents[2]
        / "test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv"
    )
    expected = "aab73cc23c54f137eb46f37949911af83f266c50ef5e7f4ae6d33a9b68bedfa7"

    assert canonical.is_file()
    assert compatibility.is_file()
    assert hashlib.sha256(canonical.read_bytes()).hexdigest() == expected
    assert hashlib.sha256(compatibility.read_bytes()).hexdigest() == expected
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
pytest 07_observable_extraction/tests/test_combine_profiles.py::test_combined_cli_defaults_use_production_layout 07_observable_extraction/tests/test_combine_profiles.py::test_ajaka_reference_is_versioned_and_compatibility_copy_matches -v
```

Expected: first test fails on `test_data` defaults; second fails because canonical Stage-07 reference does not exist.

- [ ] **Step 3: Add canonical data and production defaults**

Use `apply_patch` to add a byte-for-byte copy of the existing CSV at the
canonical path. Preserve header and all 57 data rows. Add narrow `.gitignore`
exceptions so the compatibility CSV is tracked without exposing other test
artifacts:

```gitignore
!/test_data/
/test_data/*
!/test_data/beam_asymmetry/
/test_data/beam_asymmetry/*
!/test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv
```

Define defaults near imports in `combine_profiles.py`:

```python
AJAKA_REFERENCE = (
    Path(__file__).resolve().parent
    / "references"
    / "ajaka2008_figure4_digitized.csv"
)
PRODUCTION_ROOT = Path("results/production")
```

Update parser defaults:

```python
default=PRODUCTION_ROOT / "uv/beam_asymmetry/beam_asymmetry.root"
default=PRODUCTION_ROOT / "vis/beam_asymmetry/beam_asymmetry.root"
default=AJAKA_REFERENCE
default=PRODUCTION_ROOT / "combined"
```

- [ ] **Step 4: Run targeted tests**

Run:

```bash
pytest 07_observable_extraction/tests/test_combine_profiles.py -q
```

Expected: all combined-profile tests pass.

- [ ] **Step 5: Commit reference ownership change**

Stage only files owned by this task, including ignored compatibility CSV with
`git add -f`:

```bash
git add .gitignore 07_observable_extraction/combine_profiles.py 07_observable_extraction/tests/test_combine_profiles.py 07_observable_extraction/references/ajaka2008_figure4_digitized.csv
git add -f test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv
git commit -m "fix(observables): version Ajaka reference"
```

### Task 2: Add mode configuration, paths, and lightweight preflight

**Files:**
- Create: `scripts/run_pipeline.py`
- Create: `tests/test_run_pipeline.py`

**Interfaces:**
- Produces: `PipelineError`, `ModeConfig`, `PipelinePaths`, `PreflightResult`, `mode_config()`, `build_paths()`, and `preflight()`.
- `mode_config(mode: str, repo_root: Path) -> ModeConfig` resolves only fixed mode inputs and MC counts.
- `build_paths(config: ModeConfig, output_override: Path | None) -> PipelinePaths` owns every shared/profile/final artifact path.
- `preflight(config: ModeConfig, paths: PipelinePaths, ...) -> PreflightResult` performs read-only validation and returns resolved `root_executable`.
- Later tasks consume these exact types and signatures.

- [ ] **Step 1: Write failing configuration tests**

Create `tests/test_run_pipeline.py` with imports and mode assertions:

```python
from pathlib import Path

import pytest

from scripts import run_pipeline


def test_mode_config_uses_exact_test_and_production_inputs(tmp_path):
    test = run_pipeline.mode_config("test_data", tmp_path)
    production = run_pipeline.mode_config("production", tmp_path)

    assert test.preanalysis_dir == tmp_path / "test_data/pre_analyzed"
    assert test.default_output == tmp_path / "results/test_data"
    assert test.mc_events == 100_000
    assert production.preanalysis_dir == (
        tmp_path / "data/02_pre_analyzed/pre_analisi"
    )
    assert production.default_output == tmp_path / "results/production"
    assert production.mc_events == 1_000_000


def test_unknown_mode_is_rejected(tmp_path):
    with pytest.raises(run_pipeline.PipelineError, match="unknown mode"):
        run_pipeline.mode_config("farm", tmp_path)


def test_output_override_replaces_only_output_root(tmp_path):
    config = run_pipeline.mode_config("production", tmp_path)
    paths = run_pipeline.build_paths(config, tmp_path / "campaign 01")

    assert paths.output_root == tmp_path / "campaign 01"
    assert paths.preanalysis_dir == config.preanalysis_dir
    assert paths.calibrated_flux == (
        tmp_path / "campaign 01/common/flux_calibrated.root"
    )
    assert paths.profile_root("uv") == tmp_path / "campaign 01/uv"
    assert paths.profile_root("vis") == tmp_path / "campaign 01/vis"
```

- [ ] **Step 2: Run configuration tests to verify import failure**

Run:

```bash
pytest tests/test_run_pipeline.py -v
```

Expected: collection fails because `scripts.run_pipeline` does not exist.

- [ ] **Step 3: Implement immutable configuration and layout**

Create `scripts/run_pipeline.py` with these public definitions:

```python
#!/usr/bin/env python3
"""Run the complete UV/VIS eta-pi0 analysis from pre-analysis files."""

from __future__ import annotations

import importlib
import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
import shutil
import sys

from calibration.run_manifest import validate_manifest


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATTERNS = {
    "uv": "pre_analisi_*uv*.root",
    "vis": "pre_analisi_*vis*.root",
}
RUNTIME_MODULES = (
    "ROOT", "numpy", "uproot", "awkward", "xgboost", "sklearn", "matplotlib"
)


class PipelineError(RuntimeError):
    """A launcher-level configuration or execution failure."""


@dataclass(frozen=True)
class ModeConfig:
    name: str
    repo_root: Path
    preanalysis_dir: Path
    default_output: Path
    mc_events: int


@dataclass(frozen=True)
class PipelinePaths:
    repo_root: Path
    preanalysis_dir: Path
    output_root: Path
    manifest: Path
    raw_flux: Path
    hyperparams: Path
    ajaka_reference: Path

    @property
    def calibrated_flux(self) -> Path:
        return self.output_root / "common/flux_calibrated.root"

    @property
    def combined_dir(self) -> Path:
        return self.output_root / "combined"

    @property
    def command_log(self) -> Path:
        return self.output_root / "pipeline_commands.log"

    def profile_root(self, profile: str) -> Path:
        if profile not in PROFILE_PATTERNS:
            raise PipelineError(f"unknown beam profile: {profile}")
        return self.output_root / profile


@dataclass(frozen=True)
class PreflightResult:
    root_executable: str


def mode_config(mode: str, repo_root: Path = REPO_ROOT) -> ModeConfig:
    repo_root = Path(repo_root).resolve()
    values = {
        "test_data": ("test_data/pre_analyzed", "results/test_data", 100_000),
        "production": (
            "data/02_pre_analyzed/pre_analisi",
            "results/production",
            1_000_000,
        ),
    }
    try:
        preanalysis, output, events = values[mode]
    except KeyError:
        raise PipelineError(f"unknown mode: {mode}") from None
    return ModeConfig(
        name=mode,
        repo_root=repo_root,
        preanalysis_dir=repo_root / preanalysis,
        default_output=repo_root / output,
        mc_events=events,
    )


def build_paths(
    config: ModeConfig, output_override: Path | None = None
) -> PipelinePaths:
    output = (
        config.default_output
        if output_override is None
        else Path(output_override).expanduser().resolve()
    )
    return PipelinePaths(
        repo_root=config.repo_root,
        preanalysis_dir=config.preanalysis_dir,
        output_root=output,
        manifest=config.repo_root / "config/run_manifest.csv",
        raw_flux=config.repo_root / "data/00_external/flux.root",
        hyperparams=(
            config.repo_root
            / "04_bdt_training/artifacts/stage1/best_hyperparams.json"
        ),
        ajaka_reference=(
            config.repo_root
            / "07_observable_extraction/references/ajaka2008_figure4_digitized.csv"
        ),
    )
```

- [ ] **Step 4: Run configuration tests to verify green**

Run:

```bash
pytest tests/test_run_pipeline.py -q
```

Expected: three tests pass.

- [ ] **Step 5: Add failing preflight tests**

Add helpers and focused cases to `tests/test_run_pipeline.py`:

```python
def _touch(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch()


def _valid_preflight_tree(tmp_path: Path):
    config = run_pipeline.mode_config("test_data", tmp_path)
    paths = run_pipeline.build_paths(config)
    for path in run_pipeline.required_repository_files(paths):
        _touch(path)
    _touch(paths.preanalysis_dir / "pre_analisi_1998_uv.root")
    _touch(paths.preanalysis_dir / "pre_analisi_1999_vis.root")
    return config, paths


def _imports(_name: str):
    return object()


def test_preflight_rejects_old_python(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    with pytest.raises(run_pipeline.PipelineError, match="Python 3.10"):
        run_pipeline.preflight(
            config,
            paths,
            import_module=_imports,
            which=lambda _name: "/usr/bin/root",
            manifest_validator=lambda _path: (),
            python_version=(3, 9),
        )


def test_preflight_rejects_missing_root_executable(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    with pytest.raises(run_pipeline.PipelineError, match="root executable"):
        run_pipeline.preflight(
            config,
            paths,
            import_module=_imports,
            which=lambda _name: None,
            manifest_validator=lambda _path: (),
        )
    assert not paths.output_root.exists()


def test_preflight_rejects_pyroot_import_failure(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)

    def fail_root(name: str):
        if name == "ROOT":
            raise ImportError("ABI mismatch")
        return object()

    with pytest.raises(run_pipeline.PipelineError, match="cannot import ROOT"):
        run_pipeline.preflight(
            config,
            paths,
            import_module=fail_root,
            which=lambda _name: "/usr/bin/root",
            manifest_validator=lambda _path: (),
        )


def test_preflight_rejects_missing_vis_input(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    (paths.preanalysis_dir / "pre_analisi_1999_vis.root").unlink()

    with pytest.raises(run_pipeline.PipelineError, match="VIS.*pre-analysis"):
        run_pipeline.preflight(
            config,
            paths,
            import_module=_imports,
            which=lambda _name: "/usr/bin/root",
            manifest_validator=lambda _path: (),
        )


def test_preflight_rejects_nonempty_output_without_removing_it(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    sentinel = paths.output_root / "keep.txt"
    _touch(sentinel)

    with pytest.raises(run_pipeline.PipelineError, match="not empty"):
        run_pipeline.preflight(
            config,
            paths,
            import_module=_imports,
            which=lambda _name: "/usr/bin/root",
            manifest_validator=lambda _path: (),
        )
    assert sentinel.is_file()


def test_preflight_accepts_complete_minimal_inputs(tmp_path):
    config, paths = _valid_preflight_tree(tmp_path)
    result = run_pipeline.preflight(
        config,
        paths,
        import_module=_imports,
        which=lambda _name: "/opt/root/bin/root",
        manifest_validator=lambda _path: (),
    )
    assert result == run_pipeline.PreflightResult("/opt/root/bin/root")
    assert not paths.output_root.exists()
```

- [ ] **Step 6: Run preflight tests to verify failure**

Run:

```bash
pytest tests/test_run_pipeline.py -q
```

Expected: failures report missing `required_repository_files` and `preflight`.

- [ ] **Step 7: Implement read-only preflight**

Add exact required-file ownership and checks:

```python
def required_repository_files(paths: PipelinePaths) -> tuple[Path, ...]:
    generator_dir = paths.repo_root / "03_mc_simulation/generators"
    generators = tuple(
        generator_dir / f"generate_{name}_dataset.C"
        for name in (
            "eta_pi0", "pi0pi0", "3pi0", "eta_2pi0", "omega_pi0",
            "etaprime", "eta_via_3pi0", "4pi0", "eta_pi0_via_3pi0",
        )
    )
    return (
        paths.manifest,
        paths.raw_flux,
        paths.hyperparams,
        paths.ajaka_reference,
        paths.repo_root / "06_calibration/build_strip_energy_flux.py",
        paths.repo_root / "07_observable_extraction/beam_asymmetry.py",
        *generators,
    )


def _writable_ancestor(path: Path) -> Path:
    candidate = path
    while not candidate.exists() and candidate != candidate.parent:
        candidate = candidate.parent
    return candidate


def preflight(
    config: ModeConfig,
    paths: PipelinePaths,
    *,
    import_module: Callable[[str], object] = importlib.import_module,
    which: Callable[[str], str | None] = shutil.which,
    manifest_validator: Callable[[Path], object] = validate_manifest,
    python_version: tuple[int, int] = sys.version_info[:2],
) -> PreflightResult:
    if python_version < (3, 10):
        raise PipelineError(
            f"Python 3.10 or newer is required, got {python_version[0]}."
            f"{python_version[1]}"
        )
    if config.mc_events <= 0:
        raise PipelineError("MC event count must be positive")
    if not paths.preanalysis_dir.is_dir():
        raise PipelineError(
            f"pre-analysis directory not found: {paths.preanalysis_dir}"
        )
    for profile, pattern in PROFILE_PATTERNS.items():
        if not any(path.is_file() for path in paths.preanalysis_dir.glob(pattern)):
            raise PipelineError(
                f"{profile.upper()} pre-analysis files not found: {pattern}"
            )
    for path in required_repository_files(paths):
        if not path.is_file():
            raise PipelineError(f"required file not found: {path}")
    if paths.output_root.exists():
        if not paths.output_root.is_dir():
            raise PipelineError(f"output root is not a directory: {paths.output_root}")
        if any(paths.output_root.iterdir()):
            raise PipelineError(f"output root is not empty: {paths.output_root}")
    writable = _writable_ancestor(paths.output_root)
    if not writable.is_dir() or not os.access(writable, os.W_OK):
        raise PipelineError(f"output parent is not writable: {writable}")
    for name in RUNTIME_MODULES:
        try:
            import_module(name)
        except Exception as exc:
            raise PipelineError(f"cannot import {name}: {exc}") from exc
    root_executable = which("root")
    if root_executable is None:
        raise PipelineError("root executable not found on PATH")
    try:
        manifest_validator(paths.manifest)
    except Exception as exc:
        raise PipelineError(f"invalid run manifest: {exc}") from exc
    return PreflightResult(root_executable)
```

The function must not call `mkdir`, touch logs, or mutate any input/output.

- [ ] **Step 8: Run Task-2 tests**

Run:

```bash
pytest tests/test_run_pipeline.py -q
```

Expected: all configuration and preflight tests pass.

- [ ] **Step 9: Commit launcher foundation**

```bash
git add scripts/run_pipeline.py tests/test_run_pipeline.py
git commit -m "feat(pipeline): add modes and preflight"
```

### Task 3: Build exact common, UV, VIS, and combine command plan

**Files:**
- Modify: `scripts/run_pipeline.py`
- Modify: `tests/test_run_pipeline.py`

**Interfaces:**
- Consumes: `ModeConfig`, `PipelinePaths`, `PreflightResult`, `PROFILE_PATTERNS` from Task 2; `get_beam_profile()` and channel registry.
- Produces: immutable `Stage(name: str, argv: tuple[str, ...])`, `build_pipeline_plan()`, and `prepare_output_dirs()`.
- `build_pipeline_plan(config, paths, preflight_result, python_executable=sys.executable) -> tuple[Stage, ...]` is pure: no directories, processes, or logs.
- `prepare_output_dirs(paths) -> None` is the only pre-execution directory creator.

- [ ] **Step 1: Write failing plan-shape tests**

Add imports `sys` and these assertions:

```python
def _plan(tmp_path: Path, mode: str = "test_data"):
    config = run_pipeline.mode_config(mode, tmp_path)
    paths = run_pipeline.build_paths(config, tmp_path / "out with spaces")
    result = run_pipeline.PreflightResult("/opt/root/bin/root")
    stages = run_pipeline.build_pipeline_plan(
        config, paths, result, python_executable="/venv/bin/python"
    )
    return config, paths, stages


def _stage(stages, name: str):
    return next(item for item in stages if item.name == name)


def test_plan_calibrates_once_then_runs_uv_vis_and_combines(tmp_path):
    _config, paths, stages = _plan(tmp_path)

    assert stages[0].name == "common:calibrate_flux"
    assert stages[-1].name == "combined:plots"
    assert sum(stage.name == "common:calibrate_flux" for stage in stages) == 1
    assert sum(stage.name.endswith(":extract") for stage in stages) == 2
    assert _stage(stages, "uv:extract").argv[-2:] == (
        "--bootstrap-replicas", "0"
    )
    assert str(paths.calibrated_flux) in _stage(stages, "uv:extract").argv
    assert str(paths.calibrated_flux) in _stage(stages, "vis:extract").argv
    assert stages.index(_stage(stages, "uv:extract")) < stages.index(
        _stage(stages, "vis:select")
    )


def test_plan_uses_exact_profile_patterns_channels_and_energy_ranges(tmp_path):
    config, paths, stages = _plan(tmp_path)

    uv_select = _stage(stages, "uv:select")
    vis_select = _stage(stages, "vis:select")
    assert uv_select.argv[-2:] == ("--pattern", "pre_analisi_*uv*.root")
    assert vis_select.argv[-2:] == ("--pattern", "pre_analisi_*vis*.root")

    uv_generators = [s for s in stages if s.name.startswith("uv:generate:")]
    vis_generators = [s for s in stages if s.name.startswith("vis:generate:")]
    assert [s.name.removeprefix("uv:generate:") for s in uv_generators] == list(
        run_pipeline.UV_CHANNELS
    )
    assert [s.name.removeprefix("vis:generate:") for s in vis_generators] == list(
        run_pipeline.VIS_CHANNELS
    )
    assert len(uv_generators) == 9
    assert len(vis_generators) == 6
    assert f"({config.mc_events},1.1,1.5," in uv_generators[0].argv[-1]
    assert f"({config.mc_events},0.9313,1.1," in vis_generators[0].argv[-1]


def test_plan_trains_and_reconstructs_with_profile_local_artifacts(tmp_path):
    _config, paths, stages = _plan(tmp_path)

    for profile in ("uv", "vis"):
        root = paths.profile_root(profile)
        train = _stage(stages, f"{profile}:train")
        bdt = _stage(stages, f"{profile}:reconstruct_bdt")
        extract = _stage(stages, f"{profile}:extract")
        model_dir = root / "bdt/artifacts/stage1"
        reco = root / "reco/reco_eta_pi0_bdt.root"
        assert str(model_dir) in train.argv
        assert str(model_dir) in bdt.argv
        assert ("--profile", profile) == bdt.argv[-2:]
        assert extract.argv.count(str(reco)) == 2
        assert str(root / "reco/reco_eta_pi0_chi2.root") in extract.argv


def test_root_macro_argument_preserves_spaces_and_rejects_metacharacters(tmp_path):
    macro = tmp_path / "generator folder/generate_eta_pi0_dataset.C"
    output = tmp_path / "output folder/eta_pi0_mc.root"
    call = run_pipeline.root_macro_call(macro, 100, 1.1, 1.5, output)
    assert str(macro) in call
    assert f'"{output}"' in call

    with pytest.raises(run_pipeline.PipelineError, match="ROOT macro path"):
        run_pipeline.root_macro_call(macro, 100, 1.1, 1.5, Path('bad"name.root'))
    with pytest.raises(run_pipeline.PipelineError, match="ROOT macro path"):
        run_pipeline.root_macro_call(macro, 100, 1.1, 1.5, Path("bad\nname.root"))
```

- [ ] **Step 2: Run plan tests to verify missing symbols**

Run:

```bash
pytest tests/test_run_pipeline.py -q
```

Expected: failures identify `Stage`, `UV_CHANNELS`, `VIS_CHANNELS`,
`root_macro_call`, and `build_pipeline_plan` as missing.

- [ ] **Step 3: Add stage model, channel ownership, and safe ROOT call builder**

Add imports and definitions:

```python
from graal_common.physics.beam_profiles import get_beam_profile
from graal_common.physics.channels import CHANNEL_NAMES, get_channel


UV_CHANNELS = tuple(CHANNEL_NAMES)
VIS_CHANNELS = (
    "eta_pi0",
    "pi0pi0",
    "3pi0",
    "eta_via_3pi0",
    "4pi0",
    "eta_pi0_via_3pi0",
)


@dataclass(frozen=True)
class Stage:
    name: str
    argv: tuple[str, ...]


def _argv(*values: object) -> tuple[str, ...]:
    return tuple(str(value) for value in values)


def root_macro_call(
    macro: Path,
    events: int,
    energy_min_gev: float,
    energy_max_gev: float,
    output: Path,
) -> str:
    for value in (macro, output):
        text = str(value)
        if '"' in text or "\n" in text or "\r" in text:
            raise PipelineError(f"unsafe ROOT macro path: {text!r}")
    return (
        f'{macro}({events},{energy_min_gev:g},{energy_max_gev:g},'
        f'"{output}")'
    )
```

- [ ] **Step 4: Implement common and per-profile plan builders**

Use small private builders, not one monolithic literal:

```python
def _common_stages(python: str, paths: PipelinePaths) -> list[Stage]:
    return [
        Stage(
            "common:calibrate_flux",
            _argv(
                python,
                paths.repo_root / "06_calibration/build_strip_energy_flux.py",
                "--preanalysis-dir", paths.preanalysis_dir,
                "--manifest", paths.manifest,
                "--flux", paths.raw_flux,
                "--output", paths.calibrated_flux,
            ),
        )
    ]


def _profile_stages(
    profile_name: str,
    channels: tuple[str, ...],
    config: ModeConfig,
    paths: PipelinePaths,
    preflight_result: PreflightResult,
    python: str,
) -> list[Stage]:
    profile = get_beam_profile(profile_name)
    root = paths.profile_root(profile_name)
    selected = root / "selected"
    mc_dir = root / "mc"
    bdt_dir = root / "bdt"
    model_dir = bdt_dir / "artifacts/stage1"
    chi2_reco = root / "reco/reco_eta_pi0_chi2.root"
    bdt_reco = root / "reco/reco_eta_pi0_bdt.root"
    asymmetry = root / "beam_asymmetry"
    stages = [
        Stage(
            f"{profile_name}:select",
            _argv(
                python, "-m", "event_selector.select_events",
                "--input-dir", paths.preanalysis_dir,
                "--output-dir", selected,
                "--pattern", PROFILE_PATTERNS[profile_name],
            ),
        )
    ]
    for channel_name in channels:
        channel = get_channel(channel_name)
        macro = (
            paths.repo_root
            / "03_mc_simulation/generators"
            / f"generate_{channel_name}_dataset.C"
        )
        stages.append(
            Stage(
                f"{profile_name}:generate:{channel_name}",
                _argv(
                    preflight_result.root_executable,
                    "-l", "-b", "-q",
                    root_macro_call(
                        macro,
                        config.mc_events,
                        profile.energy_range_gev[0],
                        profile.energy_range_gev[1],
                        mc_dir / channel.mc_filename,
                    ),
                ),
            )
        )
    backgrounds = tuple(name for name in channels if name != "eta_pi0")
    stages.extend(
        [
            Stage(
                f"{profile_name}:mc_status",
                _argv(
                    python, "-m", "mc_simulation.mc_status",
                    "--data-dir", mc_dir,
                    "--channels", *channels,
                ),
            ),
            Stage(
                f"{profile_name}:beam_spectrum",
                _argv(
                    python, "-m", "bdt_training.beam_spectrum",
                    "--selected-dir", selected,
                    "--profile", profile_name,
                    "--output", bdt_dir / "beam_spectrum.npz",
                ),
            ),
            Stage(
                f"{profile_name}:features",
                _argv(
                    python, "-m", "bdt_training.build_background_features",
                    "--mc-dir", mc_dir,
                    "--signal-channel", "eta_pi0",
                    "--background-channels", *backgrounds,
                    "--beam-spectrum", bdt_dir / "beam_spectrum.npz",
                    "--profile", profile_name,
                    "--output", bdt_dir / "features_stage1.npz",
                ),
            ),
            Stage(
                f"{profile_name}:train",
                _argv(
                    python, "-m", "bdt_training.train_bdt_stage1",
                    "--features", bdt_dir / "features_stage1.npz",
                    "--hyperparams", paths.hyperparams,
                    "--out-dir", model_dir,
                ),
            ),
            Stage(
                f"{profile_name}:reconstruct_chi2",
                _argv(
                    python, "-m", "reconstruction.reconstruct_eta_pi0_chi2",
                    "--input-dir", selected,
                    "--output-file", chi2_reco,
                ),
            ),
            Stage(
                f"{profile_name}:reconstruct_bdt",
                _argv(
                    python, "-m", "reconstruction.reconstruct_eta_pi0_bdt",
                    "--input-dir", selected,
                    "--output-file", bdt_reco,
                    "--model-dir", model_dir,
                    "--profile", profile_name,
                ),
            ),
            Stage(
                f"{profile_name}:extract",
                _argv(
                    python,
                    paths.repo_root / "07_observable_extraction/beam_asymmetry.py",
                    "--raw", chi2_reco,
                    "--raw-bdt", bdt_reco,
                    "--raw-bdt-fit", bdt_reco,
                    "--profile", profile_name,
                    "--flux-file", paths.calibrated_flux,
                    "--run-manifest", paths.manifest,
                    "--output-dir", asymmetry,
                    "--estimator", "both",
                    "--bootstrap-replicas", "0",
                ),
            ),
        ]
    )
    return stages
```

- [ ] **Step 5: Implement final composition and full pure plan**

```python
def build_pipeline_plan(
    config: ModeConfig,
    paths: PipelinePaths,
    preflight_result: PreflightResult,
    *,
    python_executable: str = sys.executable,
) -> tuple[Stage, ...]:
    stages = _common_stages(python_executable, paths)
    stages.extend(
        _profile_stages(
            "uv", UV_CHANNELS, config, paths, preflight_result, python_executable
        )
    )
    stages.extend(
        _profile_stages(
            "vis", VIS_CHANNELS, config, paths, preflight_result, python_executable
        )
    )
    stages.append(
        Stage(
            "combined:plots",
            _argv(
                python_executable, "-m", "observable_extraction.combine_profiles",
                "--uv-root",
                paths.profile_root("uv") / "beam_asymmetry/beam_asymmetry.root",
                "--vis-root",
                paths.profile_root("vis") / "beam_asymmetry/beam_asymmetry.root",
                "--published-csv", paths.ajaka_reference,
                "--output-dir", paths.combined_dir,
            ),
        )
    )
    return tuple(stages)


def prepare_output_dirs(paths: PipelinePaths) -> None:
    for path in (
        paths.output_root / "common",
        paths.profile_root("uv") / "mc",
        paths.profile_root("vis") / "mc",
    ):
        path.mkdir(parents=True, exist_ok=True)
```

Only MC directories need early creation; existing Python stages create their
own parent directories. Creating common directory also provides command-log
parent.

- [ ] **Step 6: Run plan tests and inspect one command list**

Run:

```bash
pytest tests/test_run_pipeline.py -q
python -c 'from pathlib import Path; from scripts.run_pipeline import *; c=mode_config("test_data", Path.cwd()); p=build_paths(c, Path("/tmp/graal plan")); r=PreflightResult("root"); print("\n".join(f"{s.name}: {s.argv}" for s in build_pipeline_plan(c,p,r)))'
```

Expected: tests pass; printed order is one calibration, complete UV chain,
complete VIS chain, then combined plots. Paths with spaces remain single tuple
items.

- [ ] **Step 7: Commit deterministic plan construction**

```bash
git add scripts/run_pipeline.py tests/test_run_pipeline.py
git commit -m "feat(pipeline): plan UV and VIS stages"
```

### Task 4: Execute sequentially, log commands, and expose CLI

**Files:**
- Modify: `scripts/run_pipeline.py`
- Modify: `tests/test_run_pipeline.py`

**Interfaces:**
- Consumes: `preflight()`, `prepare_output_dirs()`, and `build_pipeline_plan()`.
- Produces: `execute_plan()`, `build_parser()`, `run()`, and `main()`.
- `execute_plan(stages, paths, runner=subprocess.run, monotonic=time.monotonic) -> None` runs with `cwd=paths.repo_root`, `shell=False`, and inherited stdout/stderr.
- CLI returns `0` after all stages, `1` for launcher/child failures, and `130` for keyboard interruption.

- [ ] **Step 1: Write failing executor tests**

Add imports `subprocess` and tests:

```python
def test_executor_stops_after_failure_and_logs_exit(tmp_path):
    config = run_pipeline.mode_config("test_data", tmp_path)
    paths = run_pipeline.build_paths(config, tmp_path / "out")
    run_pipeline.prepare_output_dirs(paths)
    stages = (
        run_pipeline.Stage("one", ("tool", "one")),
        run_pipeline.Stage("two", ("tool", "two")),
        run_pipeline.Stage("three", ("tool", "three")),
    )
    calls = []

    def runner(argv, *, cwd, check, shell):
        calls.append((tuple(argv), cwd, check, shell))
        code = 7 if argv[-1] == "two" else 0
        return subprocess.CompletedProcess(argv, code)

    ticks = iter((10.0, 12.5, 20.0, 24.0))
    with pytest.raises(run_pipeline.PipelineError, match="two.*exit 7"):
        run_pipeline.execute_plan(
            stages,
            paths,
            runner=runner,
            monotonic=lambda: next(ticks),
        )

    assert [call[0][-1] for call in calls] == ["one", "two"]
    assert all(call[1] == paths.repo_root for call in calls)
    assert all(call[2:] == (False, False) for call in calls)
    log = paths.command_log.read_text()
    assert "one" in log and "exit=0" in log and "duration=2.500s" in log
    assert "two" in log and "exit=7" in log and "duration=4.000s" in log
    assert "three" not in log


def test_executor_shell_quotes_display_only(tmp_path, capsys):
    config = run_pipeline.mode_config("test_data", tmp_path)
    paths = run_pipeline.build_paths(config, tmp_path / "out")
    run_pipeline.prepare_output_dirs(paths)
    stage = run_pipeline.Stage("spaced", ("tool", "path with spaces"))
    seen = []

    def runner(argv, **kwargs):
        seen.append((tuple(argv), kwargs))
        return subprocess.CompletedProcess(argv, 0)

    run_pipeline.execute_plan(
        (stage,), paths, runner=runner, monotonic=iter((0.0, 1.0)).__next__
    )

    assert seen[0][0] == ("tool", "path with spaces")
    assert "'path with spaces'" in capsys.readouterr().out
```

- [ ] **Step 2: Run executor tests to verify missing function**

Run:

```bash
pytest tests/test_run_pipeline.py -q
```

Expected: executor tests fail because `execute_plan` is missing.

- [ ] **Step 3: Implement sequential executor and command log**

Add imports and implementation:

```python
import shlex
import subprocess
import time
from collections.abc import Sequence


def _log_stage(path: Path, stage: Stage, exit_code: int, duration: float) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            f"{stage.name}\texit={exit_code}\tduration={duration:.3f}s\t"
            f"command={shlex.join(stage.argv)}\n"
        )


def execute_plan(
    stages: Sequence[Stage],
    paths: PipelinePaths,
    *,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    monotonic: Callable[[], float] = time.monotonic,
) -> None:
    for index, stage in enumerate(stages, start=1):
        print(f"\n[{index}/{len(stages)}] {stage.name}")
        print(f"$ {shlex.join(stage.argv)}")
        started = monotonic()
        result = runner(
            stage.argv,
            cwd=paths.repo_root,
            check=False,
            shell=False,
        )
        duration = monotonic() - started
        _log_stage(paths.command_log, stage, result.returncode, duration)
        print(f"[{stage.name}] exit={result.returncode} duration={duration:.1f}s")
        if result.returncode != 0:
            raise PipelineError(
                f"stage {stage.name} failed with exit {result.returncode}"
            )
```

- [ ] **Step 4: Add failing CLI contract tests**

```python
def test_parser_accepts_only_two_modes():
    parser = run_pipeline.build_parser()
    assert parser.parse_args(["--mode", "test_data"]).mode == "test_data"
    assert parser.parse_args(["--mode", "production"]).mode == "production"
    with pytest.raises(SystemExit):
        parser.parse_args(["--mode", "farm"])


def test_run_calls_preflight_prepare_plan_and_execute_in_order(tmp_path, monkeypatch):
    events = []
    result = run_pipeline.PreflightResult("root")
    monkeypatch.setattr(
        run_pipeline,
        "preflight",
        lambda config, paths: events.append(("preflight", config.name)) or result,
    )
    monkeypatch.setattr(
        run_pipeline,
        "prepare_output_dirs",
        lambda paths: events.append(("prepare", paths.output_root)),
    )
    monkeypatch.setattr(
        run_pipeline,
        "build_pipeline_plan",
        lambda config, paths, preflight_result: (
            events.append(("plan", preflight_result.root_executable))
            or (run_pipeline.Stage("only", ("true",)),)
        ),
    )
    monkeypatch.setattr(
        run_pipeline,
        "execute_plan",
        lambda stages, paths: events.append(("execute", stages[0].name)),
    )

    code = run_pipeline.run(
        run_pipeline.build_parser().parse_args(
            ["--mode", "test_data", "--output-dir", str(tmp_path / "chosen")]
        ),
        repo_root=tmp_path,
    )

    assert code == 0
    assert events == [
        ("preflight", "test_data"),
        ("prepare", tmp_path / "chosen"),
        ("plan", "root"),
        ("execute", "only"),
    ]


def test_main_reports_pipeline_error_without_traceback(monkeypatch, capsys):
    monkeypatch.setattr(
        run_pipeline,
        "run",
        lambda _args: (_ for _ in ()).throw(run_pipeline.PipelineError("broken")),
    )
    assert run_pipeline.main(["--mode", "test_data"]) == 1
    assert capsys.readouterr().err.strip() == "ERROR: broken"
```

- [ ] **Step 5: Run CLI tests to verify missing parser/run/main**

Run:

```bash
pytest tests/test_run_pipeline.py -q
```

Expected: new tests fail on missing public CLI functions.

- [ ] **Step 6: Implement parser, orchestration, and error boundary**

Add `argparse` and final entry point:

```python
import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", required=True, choices=("test_data", "production")
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        help="empty or absent campaign output root",
    )
    return parser


def run(args: argparse.Namespace, *, repo_root: Path = REPO_ROOT) -> int:
    config = mode_config(args.mode, repo_root)
    paths = build_paths(config, args.output_dir)
    checked = preflight(config, paths)
    prepare_output_dirs(paths)
    stages = build_pipeline_plan(config, paths, checked)
    execute_plan(stages, paths)
    print(f"\nPipeline complete: {paths.output_root}")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    try:
        return run(build_parser().parse_args(argv))
    except KeyboardInterrupt:
        print("ERROR: pipeline interrupted", file=sys.stderr)
        return 130
    except PipelineError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 7: Run launcher tests and CLI help**

Run:

```bash
pytest tests/test_run_pipeline.py -q
python scripts/run_pipeline.py --help
```

Expected: all launcher tests pass; help shows required `--mode
{test_data,production}` and optional `--output-dir`.

- [ ] **Step 8: Commit executable launcher**

```bash
git add scripts/run_pipeline.py tests/test_run_pipeline.py
git commit -m "feat(pipeline): execute full analysis"
```

### Task 5: Correct runtime guidance and document server workflow

**Files:**
- Modify: `05_reconstruction/runtime/stage1_gate.py:62-67`
- Modify: `05_reconstruction/tests/test_stage1_gate.py:99-106`
- Modify: `README.md:25-64`
- Create: `docs/runbooks/full-pipeline.md`
- Modify: `docs/runbooks/vis-local-analysis.md:125-140`
- Modify: `wiki/workflow.md:1-110`
- Modify: `wiki/commands-and-configuration.md:1-120`
- Modify: `wiki/data-and-artifacts.md`
- Modify: `wiki/known-limitations.md:7-21`
- Modify: `wiki/07-observable-extraction.md`
- Modify: `tests/test_wiki.py`
- Modify: `tests/test_run_pipeline.py`

**Interfaces:**
- Consumes: final CLI and output layout from Tasks 2-4.
- Produces: one server runbook, consistent top-level/wiki navigation, accurate Stage 06-to-07 handoff, and actionable missing-model error text.
- Does not modify any `theory/` source, test, README, or reference.

- [ ] **Step 1: Pin missing-model guidance and documentation consistency**

Extend `test_load_raises_when_the_model_is_missing`:

```python
def test_load_raises_when_the_model_is_missing(tmp_path):
    with pytest.raises(FileNotFoundError) as caught:
        Stage1Gate.load(tmp_path)

    message = str(caught.value)
    assert "bdt_stage1.json" in message
    assert "scripts/run_pipeline.py" in message
    assert "run_pipeline.sh" not in message
```

Add documentation assertions to `tests/test_run_pipeline.py`:

```python
def test_pipeline_documentation_names_current_launcher_and_handoff():
    root = Path(__file__).parents[1]
    required = (
        root / "README.md",
        root / "docs/runbooks/full-pipeline.md",
        root / "wiki/workflow.md",
        root / "wiki/commands-and-configuration.md",
        root / "wiki/data-and-artifacts.md",
        root / "wiki/known-limitations.md",
        root / "wiki/07-observable-extraction.md",
    )
    for path in required:
        text = path.read_text(encoding="utf-8")
        assert "scripts/run_pipeline.py" in text, path
    corpus = "\n".join(path.read_text(encoding="utf-8") for path in required)
    assert "adapter pending" not in corpus.lower()
    assert "still expects a legacy exposure CSV" not in corpus
    assert "run_pipeline.sh" not in corpus
```

Add `"full-pipeline.md"` to any explicit runbook/page inventory if repository
tests maintain one. Do not weaken existing link or section checks.

- [ ] **Step 2: Run focused tests to verify failure**

Run:

```bash
pytest 05_reconstruction/tests/test_stage1_gate.py::test_load_raises_when_the_model_is_missing tests/test_run_pipeline.py::test_pipeline_documentation_names_current_launcher_and_handoff tests/test_wiki.py -q
```

Expected: missing-model test finds obsolete shell script; full runbook assertion
fails because file does not exist.

- [ ] **Step 3: Fix missing-model message**

Change only guidance text:

```python
raise FileNotFoundError(
    f"stage-1 model not found: {artifacts.model}. "
    "Run scripts/run_pipeline.py to train profile-specific models, or use "
    "reconstruct_eta_pi0_chi2.py for analysis without the BDT gate."
)
```

- [ ] **Step 4: Write full pipeline runbook**

Create `docs/runbooks/full-pipeline.md` with these exact sections and concrete
commands:

```markdown
# Full UV/VIS pipeline

## Scope

Starts from `pre_analisi_*.root` files containing `h80`. Runs shared flux
calibration, isolated UV/VIS training and reconstruction, separate asymmetry
extraction, then final plot composition. Raw `h70`, resume, grid search,
bootstrap, and sideband correction are outside version one.

## Server setup

```bash
./scripts/setup.sh --mode farm \
  --python /path/to/pyroot-compatible-python \
  --raw-target /path/to/graal_data \
  --pre-target /path/to/pre_analysis
source .venv/bin/activate
```

`--raw-target` remains required by current setup although launcher begins from
pre-analysis. Server needs no queue service or administrator-only daemon.

## Test-data campaign

```bash
python scripts/run_pipeline.py --mode test_data
```

Reads one local UV and one local VIS period, generates 100000 attempted MC
events per required channel, and writes `results/test_data/`.

## Production campaign

```bash
python scripts/run_pipeline.py --mode production
```

Reads all matching UV/VIS pre-analysis periods, generates 1000000 attempted MC
events per required channel, and writes `results/production/`.

## Alternate output root

```bash
python scripts/run_pipeline.py --mode production \
  --output-dir /data/graal/results/campaign-01
```

Destination must be absent or empty. Launcher never deletes previous results.

## Output layout

```text
results/<mode>/
|-- common/
|   `-- flux_calibrated.root
|-- uv/
|   |-- selected/
|   |-- mc/
|   |-- bdt/
|   |   |-- beam_spectrum.npz
|   |   |-- features_stage1.npz
|   |   `-- artifacts/stage1/
|   |-- reco/
|   |   |-- reco_eta_pi0_chi2.root
|   |   `-- reco_eta_pi0_bdt.root
|   `-- beam_asymmetry/
|-- vis/
|   |-- selected/
|   |-- mc/
|   |-- bdt/
|   |   |-- beam_spectrum.npz
|   |   |-- features_stage1.npz
|   |   `-- artifacts/stage1/
|   |-- reco/
|   |   |-- reco_eta_pi0_chi2.root
|   |   `-- reco_eta_pi0_bdt.root
|   `-- beam_asymmetry/
|-- combined/
|   |-- figure4_experimental.pdf
|   |-- figure4_comparison_ajaka2008.pdf
|   |-- comparison_estimators.pdf
|   `-- fit_diagnostics.pdf
`-- pipeline_commands.log
```

## Failure behavior

Preflight checks runtime and required inputs without creating output. Pipeline
stops on first nonzero child exit. Existing warnings remain warnings. Earlier
completed artifacts remain for diagnosis but are not resume checkpoints.

## Acceptance checks

Run `pytest -q`, inspect command log, confirm both Stage-07 ROOT files carry
matching profile metadata/energy edges, and inspect all four combined PDFs.
```

- [ ] **Step 5: Reconcile README and wiki**

Make these factual edits:

- `README.md`: add launcher commands after setup; retain individual stage
  commands as advanced/manual operation.
- `wiki/workflow.md`: replace “no central pipeline runner” with “one sequential
  v1 launcher, no DAG/scheduler/resume”; state Stage 07 consumes calibrated
  ROOT now.
- `wiki/commands-and-configuration.md`: add launcher row and options; keep
  stage matrix.
- `wiki/data-and-artifacts.md`: add `results/{test_data,production}` layout and
  tracked canonical Ajaka reference.
- `wiki/known-limitations.md`: retain no scheduler/resume/freshness claims but
  remove claim that all stages require manual invocation.
- `wiki/07-observable-extraction.md`: identify common calibrated flux input and
  profile-local outputs.
- `docs/runbooks/vis-local-analysis.md`: point combined command at canonical
  Stage-07 CSV and production-neutral explicit output paths.

Do not edit generated graphify output or theory documentation.

- [ ] **Step 6: Run documentation and targeted runtime tests**

Run:

```bash
pytest tests/test_run_pipeline.py 05_reconstruction/tests/test_stage1_gate.py 07_observable_extraction/tests/test_combine_profiles.py tests/test_wiki.py tests/test_repository_layout.py -q
```

Expected: all targeted tests pass.

- [ ] **Step 7: Run full repository verification**

Run:

```bash
MPLCONFIGDIR=/tmp/graal-mpl XDG_CACHE_HOME=/tmp/graal-cache pytest -q
```

Expected: zero failures. Record exact pass count and duration; do not reuse the
pre-implementation `682 passed` result as evidence.

- [ ] **Step 8: Run read-only production preflight and command-plan smoke**

Do not launch production stages locally. Execute preflight against available
production links only when present; otherwise print plan from pure builder:

```bash
python -c 'from pathlib import Path; from scripts.run_pipeline import *; c=mode_config("production", Path.cwd()); p=build_paths(c); r=PreflightResult("root"); s=build_pipeline_plan(c,p,r); print(len(s)); print(s[0].name, s[-1].name)'
```

Expected: `33`, then `common:calibrate_flux combined:plots`.

- [ ] **Step 9: Run real test-data acceptance campaign**

Use absent/empty temporary output outside versioned paths:

```bash
python scripts/run_pipeline.py --mode test_data \
  --output-dir /tmp/graal-pipeline-test-data
```

Expected:

- exit `0`;
- command log has 33 successful stage records;
- common calibrated ROOT exists;
- UV and VIS model/provenance/threshold bundles exist independently;
- UV and VIS reconstruction and asymmetry ROOT files exist;
- combined directory contains exactly four PDFs;
- known exposure/run warnings may appear but do not stop execution.

If `/tmp/graal-pipeline-test-data` already contains data, choose a new explicit
temporary path; do not remove it automatically.

- [ ] **Step 10: Commit documentation and guidance**

Stage only owned files; inspect `git diff --cached --name-only` before commit so
concurrent theory/calibration edits remain outside it:

```bash
git add 05_reconstruction/runtime/stage1_gate.py 05_reconstruction/tests/test_stage1_gate.py README.md docs/runbooks/full-pipeline.md docs/runbooks/vis-local-analysis.md wiki/workflow.md wiki/commands-and-configuration.md wiki/data-and-artifacts.md wiki/known-limitations.md wiki/07-observable-extraction.md tests/test_wiki.py tests/test_run_pipeline.py
git commit -m "docs: document full pipeline launcher"
```

## Final verification checklist

- [ ] Re-read spec and map every requirement to Tasks 1-5.
- [ ] Confirm `git diff --check` returns no output.
- [ ] Confirm no `theory/` file appears in launcher commits.
- [ ] Confirm no unrelated dirty calibration file appears in launcher commits.
- [ ] Confirm `git status --short` distinguishes pre-existing concurrent work
  from launcher changes.
- [ ] Confirm fresh full-suite output reports zero failures.
- [ ] Confirm real `test_data` campaign exit status and 33 log entries.
- [ ] Inspect `results` produced under temporary acceptance path, not repository
  `test_data` inputs.
- [ ] Report known warnings without claiming they were resolved.
