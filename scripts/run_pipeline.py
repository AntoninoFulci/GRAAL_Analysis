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
from graal_common.physics.beam_profiles import get_beam_profile
from graal_common.physics.channels import CHANNEL_NAMES, get_channel


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


@dataclass(frozen=True)
class Stage:
    name: str
    argv: tuple[str, ...]


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
            raise PipelineError(
                f"output root is not a directory: {paths.output_root}"
            )
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
                "--output-dir",
                paths.output_root / "common",
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
                    "--estimator",
                    "both",
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
                python_executable,
                "-m",
                "observable_extraction.combine_profiles",
                "--uv-root",
                paths.profile_root("uv")
                / "beam_asymmetry/beam_asymmetry.root",
                "--vis-root",
                paths.profile_root("vis")
                / "beam_asymmetry/beam_asymmetry.root",
                "--published-csv",
                paths.ajaka_reference,
                "--output-dir",
                paths.combined_dir,
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
