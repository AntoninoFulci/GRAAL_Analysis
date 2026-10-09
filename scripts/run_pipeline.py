#!/usr/bin/env python3
"""Run the complete UV/VIS eta-pi0 analysis from pre-analysis files."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import fcntl
import importlib
import json
import os
import shlex
import subprocess
import time
from datetime import datetime, timezone
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
import shutil
import sys
import tempfile
import textwrap

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calibration.run_manifest import validate_manifest
from graal_common.physics.beam_profiles import get_beam_profile
from graal_common.physics.channels import CHANNEL_NAMES, get_channel
from scripts import artifact_manifest as cache
from scripts.artifact_manifest import validate_preanalysis
from graal_common.io.filesystem import atomic_output_directory
from observable_extraction.core.binning import PHI_BIN_CHOICES, phi_edges_rad


REPO_ROOT = Path(__file__).resolve().parents[1]
PROFILE_PATTERNS = {
    "uv": "pre_analisi_*uv*.root",
    "vis": "pre_analisi_*vis*.root",
}
RUNTIME_MODULES = (
    "ROOT",
    "numpy",
    "uproot",
    "awkward",
    "xgboost",
    "sklearn",
    "matplotlib",
)
UV_CHANNELS = tuple(CHANNEL_NAMES)
VIS_CHANNELS = (
    "eta_pi0",
    "pi0pi0",
    "3pi0",
    "eta_via_3pi0",
    "4pi0",
    "eta_pi0_via_3pi0",
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
    data_root: Path
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
        return self.output_root / "common/plots"

    @property
    def command_log(self) -> Path:
        return self.output_root / "pipeline_commands.log"

    def profile_root(self, profile: str) -> Path:
        if profile not in PROFILE_PATTERNS:
            raise PipelineError(f"unknown beam profile: {profile}")
        return self.output_root / profile

    def selected_dir(self, profile: str) -> Path:
        self.profile_root(profile)
        return self.data_root / "03_selected" / profile

    def mc_dir(self, profile: str) -> Path:
        self.profile_root(profile)
        return self.data_root / "04_mc" / profile

    def bdt_dir(self, profile: str) -> Path:
        self.profile_root(profile)
        return self.data_root / "05_bdt" / profile


@dataclass(frozen=True)
class PreflightResult:
    root_executable: str
    old_preanalysis_inputs: tuple[Path, ...] = ()


@dataclass(frozen=True)
class Stage:
    name: str
    argv: tuple[str, ...]


def mode_config(mode: str, repo_root: Path = REPO_ROOT) -> ModeConfig:
    repo_root = Path(repo_root).resolve()
    values = {
        "test_data": ("test_data/02_pre_analyzed", "results/test_data", 100_000),
        "production": (
            "data/02_pre_analyzed",
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
        else Path(output_override).expanduser().absolute()
    )
    return PipelinePaths(
        repo_root=config.repo_root,
        preanalysis_dir=config.preanalysis_dir,
        data_root=config.repo_root / ("data" if config.name == "production" else "test_data"),
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


def required_repository_files(paths: PipelinePaths) -> tuple[Path, ...]:
    generator_dir = paths.repo_root / "03_mc_simulation/generators"
    generators = tuple(
        generator_dir / f"generate_{name}_dataset.C"
        for name in (
            "eta_pi0",
            "pi0pi0",
            "3pi0",
            "eta_2pi0",
            "omega_pi0",
            "etaprime",
            "eta_via_3pi0",
            "4pi0",
            "eta_pi0_via_3pi0",
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
    preanalysis_validator: Callable[[Sequence[Path]], None] = validate_preanalysis,
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
    old_preanalysis_inputs: list[Path] = []
    now = datetime.now(timezone.utc).timestamp()
    for profile, pattern in PROFILE_PATTERNS.items():
        files = sorted(path for path in paths.preanalysis_dir.glob(pattern) if path.is_file())
        if not files:
            raise PipelineError(
                f"{profile.upper()} pre-analysis files not found: {pattern}"
            )
        try:
            preanalysis_validator(files)
        except Exception as exc:
            raise PipelineError(f"{profile.upper()} pre-analysis invalid: {exc}") from exc
        if config.name == "production":
            for path in files:
                if now - path.stat().st_mtime > 10 * 86400:
                    old_preanalysis_inputs.append(path)
    for path in required_repository_files(paths):
        if not path.is_file():
            raise PipelineError(f"required file not found: {path}")
    if paths.output_root.exists():
        if not paths.output_root.is_dir():
            raise PipelineError(
                f"output root is not a directory: {paths.output_root}"
            )
        if config.name == "production" and any(paths.output_root.iterdir()):
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
    return PreflightResult(root_executable, tuple(old_preanalysis_inputs))


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
        if '"' in text or "\\" in text or "\n" in text or "\r" in text:
            raise PipelineError(f"unsafe ROOT macro path: {text!r}")
    return (
        f'{macro}({events},{energy_min_gev:g},{energy_max_gev:g},'
        f'"{output}")'
    )


def _common_stages(python: str, paths: PipelinePaths) -> list[Stage]:
    return [
        Stage(
            "common:calibrate_flux",
            _argv(
                python,
                paths.repo_root / "06_calibration/build_strip_energy_flux.py",
                "--preanalysis-dir",
                paths.preanalysis_dir,
                "--manifest",
                paths.manifest,
                "--flux",
                paths.raw_flux,
                "--target",
                "P",
                "--output-dir",
                paths.calibrated_flux.parent,
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
    phi_bins: int,
) -> list[Stage]:
    profile = get_beam_profile(profile_name)
    root = paths.profile_root(profile_name)
    selected = paths.selected_dir(profile_name)
    mc_dir = paths.mc_dir(profile_name)
    bdt_dir = paths.bdt_dir(profile_name)
    model_dir = bdt_dir / "artifacts/stage1"
    chi2_reco = root / "reco/reco_eta_pi0_chi2.root"
    bdt_reco = root / "reco/reco_eta_pi0_bdt.root"
    asymmetry = root / "beam_asymmetry"
    stages = [
        Stage(
            f"{profile_name}:select",
            _argv(
                python,
                "-m",
                "event_selector.select_events",
                "--input-dir",
                paths.preanalysis_dir,
                "--output-dir",
                selected,
                "--pattern",
                PROFILE_PATTERNS[profile_name],
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
                    "-l",
                    "-b",
                    "-q",
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
                    python,
                    "-m",
                    "mc_simulation.mc_status",
                    "--data-dir",
                    mc_dir,
                    "--channels",
                    *channels,
                ),
            ),
            Stage(
                f"{profile_name}:beam_spectrum",
                _argv(
                    python,
                    "-m",
                    "bdt_training.beam_spectrum",
                    "--selected-dir",
                    selected,
                    "--profile",
                    profile_name,
                    "--output",
                    bdt_dir / "beam_spectrum.npz",
                ),
            ),
            Stage(
                f"{profile_name}:features",
                _argv(
                    python,
                    "-m",
                    "bdt_training.build_background_features",
                    "--mc-dir",
                    mc_dir,
                    "--signal-channel",
                    "eta_pi0",
                    "--background-channels",
                    *backgrounds,
                    "--beam-spectrum",
                    bdt_dir / "beam_spectrum.npz",
                    "--profile",
                    profile_name,
                    "--output",
                    bdt_dir / "features_stage1.npz",
                ),
            ),
            Stage(
                f"{profile_name}:train",
                _argv(
                    python,
                    "-m",
                    "bdt_training.train_bdt_stage1",
                    "--features",
                    bdt_dir / "features_stage1.npz",
                    "--hyperparams",
                    paths.hyperparams,
                    "--out-dir",
                    model_dir,
                ),
            ),
            Stage(
                f"{profile_name}:reconstruct_chi2",
                _argv(
                    python,
                    "-m",
                    "reconstruction.reconstruct_eta_pi0_chi2",
                    "--input-dir",
                    selected,
                    "--output-file",
                    chi2_reco,
                ),
            ),
            Stage(
                f"{profile_name}:reconstruct_bdt",
                _argv(
                    python,
                    "-m",
                    "reconstruction.reconstruct_eta_pi0_bdt",
                    "--input-dir",
                    selected,
                    "--output-file",
                    bdt_reco,
                    "--model-dir",
                    model_dir,
                    "--profile",
                    profile_name,
                ),
            ),
            Stage(
                f"{profile_name}:extract",
                _argv(
                    python,
                    paths.repo_root / "07_observable_extraction/beam_asymmetry.py",
                    "--raw",
                    chi2_reco,
                    "--raw-bdt",
                    bdt_reco,
                    "--raw-bdt-fit",
                    bdt_reco,
                    "--profile",
                    profile_name,
                    "--flux-file",
                    paths.calibrated_flux,
                    "--run-manifest",
                    paths.manifest,
                    "--output-dir",
                    asymmetry,
                    "--plots-dir",
                    root / "plots",
                    "--estimator",
                    "both",
                    "--phi-bins",
                    phi_bins,
                    "--bootstrap-replicas",
                    "0",
                ),
            ),
        ]
    )
    return stages


def build_pipeline_plan(
    config: ModeConfig,
    paths: PipelinePaths,
    preflight_result: PreflightResult,
    *,
    python_executable: str = sys.executable,
    phi_bins: int = 12,
) -> tuple[Stage, ...]:
    phi_edges_rad(phi_bins)
    stages = _common_stages(python_executable, paths)
    stages.extend(
        _profile_stages(
            "uv", UV_CHANNELS, config, paths, preflight_result, python_executable, phi_bins
        )
    )
    stages.extend(
        _profile_stages(
            "vis", VIS_CHANNELS, config, paths, preflight_result, python_executable, phi_bins
        )
    )
    stages.append(
        Stage(
            "campaign:plots",
            _argv(
                python_executable,
                "-m",
                "scripts.plot_campaign",
                "--campaign",
                paths.output_root,
                "--published-csv",
                paths.ajaka_reference,
            ),
        )
    )
    return tuple(stages)


def prepare_output_dirs(paths: PipelinePaths) -> None:
    paths.output_root.mkdir(parents=True, exist_ok=True)
    try:
        paths.command_log.touch(exist_ok=False)
    except FileExistsError as exc:
        raise PipelineError(
            f"output root already claimed by another pipeline: {paths.output_root}"
        ) from exc
    except OSError as exc:
        raise PipelineError(
            f"cannot claim output root {paths.output_root}: {exc}"
        ) from exc
    unexpected = tuple(
        path for path in paths.output_root.iterdir() if path != paths.command_log
    )
    if unexpected:
        paths.command_log.unlink()
        raise PipelineError(
            f"output root changed after preflight: {paths.output_root}"
        )
    for path in (
        paths.output_root / "common",
        paths.output_root / "uv/reco",
        paths.output_root / "vis/reco",
    ):
        path.mkdir(parents=True, exist_ok=True)


def validate_test_output(paths: PipelinePaths) -> None:
    expected_parent = (paths.repo_root / "results").resolve()
    if (paths.repo_root / "results").is_symlink():
        raise PipelineError("test output results parent must not be a symlink")
    if paths.output_root.parent.resolve() != expected_parent or paths.output_root.is_symlink() or not paths.output_root.name.startswith("test_") or len(paths.output_root.name) <= 5:
        raise PipelineError("test output must be results/test_<campaign>")


def validate_production_output(paths: PipelinePaths) -> None:
    results = paths.repo_root / "results"
    if (results.is_symlink() or paths.output_root.is_symlink() or
            paths.output_root.parent.resolve() != results.resolve() or
            paths.output_root.name.startswith("test_")):
        raise PipelineError("production output must be results/<campaign> without symlinked results paths")


@contextmanager
def pipeline_lock(repo_root: Path):
    lock_path = Path(repo_root) / "results/.pipeline.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise PipelineError(f"pipeline lock is held: {lock_path}") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def _log_stage(path: Path, stage: Stage, exit_code: int, duration: float) -> None:
    with path.open("a", encoding="utf-8") as stream:
        stream.write(
            f"{stage.name}\texit={exit_code}\tduration={duration:.3f}s\t"
            f"command={shlex.join(stage.argv)}\n"
        )


def _log_decision(path: Path, name: str, action: str, reason: str) -> None:
    line = f"{name}\t{action}\treason={reason}\n"
    print(line.strip())
    with path.open("a", encoding="utf-8") as stream:
        stream.write(line)


def run_cached_stages(
    stages: Sequence[Stage],
    paths: PipelinePaths,
    item: cache.CacheItem,
    destination: Path,
    validate: Callable[[Path], None],
    *,
    production: bool,
    force: bool = False,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> dict:
    """Run a cache unit against staging, then publish validated output."""
    if production and not force:
        reusable, reason = cache.cache_status(item, lambda: validate(destination))
        if reusable:
            _log_decision(paths.command_log, item.name, "SKIP", reason)
            return {"name": item.name, "action": "SKIP", "reason": reason, "manifest": str(item.manifest), "signature": item.signature}
    else:
        reason = "force" if force else "test data always rebuilds"
    _log_decision(paths.command_log, item.name, "RUN", reason)

    def execute_at(staged: Path) -> None:
        rewritten = tuple(
            Stage(stage.name, tuple(arg.replace(str(destination), str(staged)) for arg in stage.argv))
            for stage in stages
        )
        execute_plan(rewritten, paths, runner=runner)
        validate(staged)

    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.suffix == ".root":
            fd, temporary = tempfile.mkstemp(prefix=f".{destination.stem}.", suffix=".root", dir=destination.parent)
            os.close(fd)
            staged = Path(temporary)
            try:
                execute_at(staged)
                staged.replace(destination)
            finally:
                staged.unlink(missing_ok=True)
        else:
            with atomic_output_directory(destination) as staged:
                execute_at(staged)
        if production:
            cache.record_cache(item, lambda: validate(destination))
    except PipelineError:
        raise
    except Exception as exc:
        raise PipelineError(f"artifact {item.name} failed: {exc}") from exc
    return {"name": item.name, "action": "RUN", "reason": reason, "manifest": str(item.manifest) if production else None, "signature": item.signature if production else None}


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


def _source_files(paths: PipelinePaths, component: str) -> tuple[Path, ...]:
    shared = paths.repo_root / "00_common"
    own = paths.repo_root / component
    files = tuple(path for base in (shared, own) for path in base.rglob("*.py") if "tests" not in path.parts)
    if component == "03_mc_simulation":
        files += (*own.rglob("*.C"), *own.rglob("*.h"))
    return tuple(files)


def _revision(repo_root: Path) -> str:
    result = subprocess.run(
        ("git", "rev-parse", "HEAD"), cwd=repo_root, capture_output=True, text=True, check=False
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def _write_campaign_artifacts(paths: PipelinePaths, outcomes: list[dict]) -> None:
    preanalysis = {
        profile: cache.inventory(sorted(paths.preanalysis_dir.glob(pattern)))
        for profile, pattern in PROFILE_PATTERNS.items()
    }
    target = paths.output_root / "pipeline_artifacts.json"
    target.write_text(
        json.dumps({"source_revision": _revision(paths.repo_root), "preanalysis": preanalysis, "cache": outcomes}, indent=2) + "\n",
        encoding="utf-8",
    )


def execute_cached_plan(
    stages: Sequence[Stage],
    config: ModeConfig,
    paths: PipelinePaths,
    *,
    force_selected: bool = False,
    force_mc: bool = False,
    force_bdt: bool = False,
    runner: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> None:
    production = config.name == "production"
    outcomes: list[dict] = []
    stage_list = list(stages)
    index = 0
    while index < len(stage_list):
        stage = stage_list[index]
        parts = stage.name.split(":")
        profile = parts[0]
        if profile in PROFILE_PATTERNS and len(parts) >= 2 and parts[1] == "select":
            destination = paths.selected_dir(profile)
            inputs = tuple(sorted(paths.preanalysis_dir.glob(PROFILE_PATTERNS[profile])))
            item = cache.CacheItem(
                f"selected:{profile}", destination.parent / f"{profile}.manifest.json", (destination,),
                {"inputs": cache.inventory(inputs), "options": stage.argv, "source": cache.source_fingerprint(_source_files(paths, "02_event_selector"))},
            )
            outcome = run_cached_stages((stage,), paths, item, destination,
                                        lambda directory, source=inputs: cache.validate_selected(directory, source),
                                        production=production, force=force_selected, runner=runner)
        elif profile in PROFILE_PATTERNS and len(parts) == 3 and parts[1] == "generate":
            channel = parts[2]
            destination = paths.mc_dir(profile) / get_channel(channel).mc_filename
            item = cache.CacheItem(
                f"mc:{profile}:{channel}", destination.with_suffix(".manifest.json"), (destination,),
                {"options": stage.argv, "source": cache.source_fingerprint((
                    *tuple(path for path in (paths.repo_root / "00_common").rglob("*.py") if "tests" not in path.parts),
                    paths.repo_root / "03_mc_simulation/generators" / f"generate_{channel}_dataset.C",
                    *tuple((paths.repo_root / "03_mc_simulation/generators").rglob("*.h")),
                ))},
            )
            outcome = run_cached_stages((stage,), paths, item, destination,
                                        lambda path, name=channel: cache.validate_mc(path, name),
                                        production=production, force=force_mc, runner=runner)
        elif profile in PROFILE_PATTERNS and len(parts) >= 2 and parts[1] == "beam_spectrum":
            group = tuple(stage_list[index:index + 3])
            if [entry.name for entry in group] != [f"{profile}:beam_spectrum", f"{profile}:features", f"{profile}:train"]:
                raise PipelineError(f"incomplete {profile} BDT stage group")
            destination = paths.bdt_dir(profile)
            selected_identity = cache.inventory((paths.selected_dir(profile),))
            channels = UV_CHANNELS if profile == "uv" else VIS_CHANNELS
            mc_identity = cache.inventory(tuple(paths.mc_dir(profile) / get_channel(name).mc_filename for name in channels))
            item = cache.CacheItem(
                f"bdt:{profile}", destination.parent / f"{profile}.manifest.json", (destination,),
                {"selected": selected_identity, "mc": mc_identity, "options": [entry.argv for entry in group],
                 "hyperparams": cache.source_fingerprint((paths.hyperparams,)),
                 "source": cache.source_fingerprint(_source_files(paths, "04_bdt_training"))},
            )
            outcome = run_cached_stages(group, paths, item, destination,
                                        lambda directory, name=profile: cache.validate_bdt(directory, name),
                                        production=production, force=force_bdt, runner=runner)
            index += 2
        else:
            _log_decision(paths.command_log, stage.name, "RUN", "campaign stage" if production else "test data always rebuilds")
            execute_plan((stage,), paths, runner=runner)
            index += 1
            continue
        outcomes.append(outcome)
        if production:
            _write_campaign_artifacts(paths, outcomes)
        index += 1


def _replace_test_output(paths: PipelinePaths) -> None:
    validate_test_output(paths)
    if paths.output_root.exists():
        shutil.rmtree(paths.output_root)


def _use_color() -> bool:
    return (
        sys.stdout.isatty()
        and "NO_COLOR" not in os.environ
        and os.environ.get("TERM") != "dumb"
    )


def _print_table(title: str, rows: Sequence[tuple[str, str]], *, warning: bool = False) -> None:
    """Render a table within the current terminal width, including long paths."""
    columns = shutil.get_terminal_size(fallback=(80, 24)).columns
    color = _use_color()
    border_code = "\x1b[2;33m" if warning else "\x1b[2;36m"
    title_code = "\x1b[1;33m" if warning else "\x1b[1;36m"
    key_code = "\x1b[33m" if warning else "\x1b[36m"

    def paint(value: str, code: str) -> str:
        return f"{code}{value}\x1b[0m" if color and code else value

    def wrapped(value: str, width: int) -> list[str]:
        return textwrap.wrap(
            value, width=width, break_on_hyphens=False,
            drop_whitespace=False, replace_whitespace=False,
        ) or [""]

    print()
    for line in wrapped(title, max(columns, 1)):
        print(paint(line, title_code))
    if columns < 8:
        for label, value in rows:
            for line in wrapped(f"{label}: {value}", max(columns, 1)):
                print(paint(line, key_code))
        return
    if columns < 56:
        cell_width = columns - 4
        top = f"╭{'─' * (columns - 2)}╮"
        middle = f"├{'─' * (columns - 2)}┤"
        bottom = f"╰{'─' * (columns - 2)}╯"
        print(paint(top, border_code))
        for index, (label, value) in enumerate(rows):
            if index:
                print(paint(middle, border_code))
            for line in wrapped(label, cell_width):
                print(f"{paint('│', border_code)} {paint(f'{line:<{cell_width}}', key_code)} {paint('│', border_code)}")
            for line in wrapped(value, cell_width):
                print(f"{paint('│', border_code)} {line:<{cell_width}} {paint('│', border_code)}")
        print(paint(bottom, border_code), flush=True)
        return

    label_width = min(max(len("Campo"), *(len(label) for label, _ in rows)), max(5, (columns - 7) // 3))
    value_width = columns - label_width - 7
    top = f"╭{'─' * (label_width + 2)}┬{'─' * (value_width + 2)}╮"
    middle = f"├{'─' * (label_width + 2)}┼{'─' * (value_width + 2)}┤"
    bottom = f"╰{'─' * (label_width + 2)}┴{'─' * (value_width + 2)}╯"

    def print_row(label: str, value: str, *, header: bool = False) -> None:
        left_lines = wrapped(label, label_width)
        right_lines = wrapped(value, value_width)
        for index in range(max(len(left_lines), len(right_lines))):
            left = left_lines[index] if index < len(left_lines) else ""
            right = right_lines[index] if index < len(right_lines) else ""
            left_code = "\x1b[1m" if header else key_code
            right_code = "\x1b[1m" if header else ("\x1b[1;33m" if warning else "")
            print(
                f"{paint('│', border_code)} {paint(f'{left:<{label_width}}', left_code)} "
                f"{paint('│', border_code)} {paint(f'{right:<{value_width}}', right_code)} "
                f"{paint('│', border_code)}"
            )

    print(paint(top, border_code))
    print_row("Campo", "Valore", header=True)
    print(paint(middle, border_code))
    for label, value in rows:
        print_row(label, value)
    print(paint(bottom, border_code), flush=True)


def print_preflight_warnings(checked: PreflightResult) -> None:
    if checked.old_preanalysis_inputs:
        _print_table(
            f"Avvisi pre-analisi ({len(checked.old_preanalysis_inputs)})",
            [(f"{index:02d} · oltre 10 giorni", str(path))
             for index, path in enumerate(checked.old_preanalysis_inputs, 1)],
            warning=True,
        )


def print_run_summary(
    config: ModeConfig,
    paths: PipelinePaths,
    args: argparse.Namespace,
    stages: Sequence[Stage],
) -> None:
    """Show the validated campaign configuration before touching its outputs."""
    def relative(path: Path) -> str:
        return str(path.relative_to(config.repo_root))

    rows = [
        ("Modalità", config.name),
        ("Repository", str(config.repo_root)),
        ("Input h80", relative(paths.preanalysis_dir)),
        ("Risultati", relative(paths.output_root)),
        ("Flux input", relative(paths.raw_flux)),
        ("Run manifest", relative(paths.manifest)),
        ("Iperparametri BDT", relative(paths.hyperparams)),
        ("Riferimento AJAKA", relative(paths.ajaka_reference)),
        ("Eventi MC/canale", str(config.mc_events)),
    ]
    for profile, channels in (("uv", UV_CHANNELS), ("vis", VIS_CHANNELS)):
        energy_min, energy_max = get_beam_profile(profile).energy_range_gev
        rows.extend((
            (f"{profile.upper()} h80", ", ".join(
                path.name for path in sorted(paths.preanalysis_dir.glob(PROFILE_PATTERNS[profile]))
                if path.is_file()
            )),
            (f"{profile.upper()} energia", f"{energy_min:g}-{energy_max:g} GeV"),
            (f"{profile.upper()} canali MC", ", ".join(channels)),
            (f"{profile.upper()} selected", relative(paths.selected_dir(profile))),
            (f"{profile.upper()} MC", relative(paths.mc_dir(profile))),
            (f"{profile.upper()} BDT", relative(paths.bdt_dir(profile))),
        ))
    rows.extend((
        ("Estrazione", f"ratio + likelihood; phi bins {args.phi_bins}; bootstrap 0"),
        ("Plot", "UV, VIS e confronto combinato"),
    ))
    if config.name == "production":
        rows.extend((
            ("Cache", "selected, MC, BDT: riuso se validi entro 10 giorni; decisione RUN/SKIP durante esecuzione"),
            ("Forzatura", ", ".join(
                f"force-{name}={'sì' if getattr(args, f'force_{name}') else 'no'}"
                for name in ("selected", "mc", "bdt")
            )),
            ("Scrittura", "intermedi persistenti in data/; risultati in nuova campagna"),
        ))
    else:
        rows.extend((
            ("Cache", "disattivata; selected, MC e BDT sempre rigenerati"),
            ("Flag force", "ignorati in test_data"),
            ("Sovrascrittura", "intermedi in test_data/ e intera directory risultati indicata"),
        ))
    rows.append(("Stage previsti", str(len(stages))))
    rows.extend((f"{index:02d}", stage.name) for index, stage in enumerate(stages, 1))
    _print_table("Riepilogo pipeline", rows)


def confirm_run() -> bool:
    try:
        answer = input("Avviare la pipeline? [s/N]: ")
    except EOFError:
        return False
    return answer.strip().casefold() in {"s", "si", "sì", "y", "yes"}


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
    parser.add_argument("--force-selected", action="store_true", help="rebuild production selection")
    parser.add_argument("--force-mc", action="store_true", help="regenerate production MC")
    parser.add_argument("--force-bdt", action="store_true", help="retrain production BDT")
    parser.add_argument("--phi-bins", type=int, choices=PHI_BIN_CHOICES, default=12,
                        help="azimuth bins for UV/VIS ratio fits (default: 12)")
    return parser


def run(args: argparse.Namespace, *, repo_root: Path = REPO_ROOT) -> int:
    config = mode_config(args.mode, repo_root)
    paths = build_paths(config, args.output_dir)
    if config.name == "test_data":
        validate_test_output(paths)
    else:
        validate_production_output(paths)
    with pipeline_lock(config.repo_root):
        checked = preflight(config, paths)
        stages = build_pipeline_plan(config, paths, checked, phi_bins=args.phi_bins)
        print_run_summary(config, paths, args, stages)
        print_preflight_warnings(checked)
        if not confirm_run():
            print("Pipeline annullata.")
            return 0
        if config.name == "test_data":
            _replace_test_output(paths)
        prepare_output_dirs(paths)
        execute_cached_plan(
            stages, config, paths,
            force_selected=args.force_selected,
            force_mc=args.force_mc,
            force_bdt=args.force_bdt,
        )
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
