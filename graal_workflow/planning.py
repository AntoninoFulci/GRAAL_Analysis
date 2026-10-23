"""Construct the ordered UV/VIS stage commands."""
from __future__ import annotations

from pathlib import Path
import sys

from graal_common.physics.beam_profiles import get_beam_profile
from graal_common.physics.energy_binning import EnergyBinning
from graal_common.physics.channels import get_channel
from observable_extraction.core.binning import phi_edges_rad
from .models import ModeConfig, PipelineError, PipelinePaths, PreflightResult, Stage, PROFILE_PATTERNS, UV_CHANNELS, VIS_CHANNELS


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
    energy_binning: EnergyBinning | None = None,
) -> list[Stage]:
    profile = get_beam_profile(profile_name)
    grid = (energy_binning or EnergyBinning(profile.energy_edges_gev)).validate_profile(profile)
    channels = tuple(name for name in channels
                     if get_channel(name).production_threshold_gev < grid.energy_range_gev[1])
    if "eta_pi0" not in channels:
        raise PipelineError("energy range has no on-shell eta_pi0 MC support")
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
                        grid.energy_range_gev[0],
                        grid.energy_range_gev[1],
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
                    "--profile",
                    profile_name,
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
                    paths.repo_root / "08_observable_extraction/beam_asymmetry.py",
                    "--raw",
                    chi2_reco,
                    "--raw-bdt",
                    bdt_reco,
                    "--profile",
                    profile_name,
                    "--flux-file",
                    paths.calibrated_flux,
                    "--run-manifest",
                    paths.manifest,
                "--run-quality",
                paths.repo_root / "config/run_quality_exclusions.json",
                    "--by-period",
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
    if energy_binning is not None:
        energy_args = ("--energy-edges", *(str(edge) for edge in grid.edges_gev))
        consumers = {"beam_spectrum", "features", "reconstruct_chi2", "reconstruct_bdt", "extract"}
        stages = [Stage(stage.name, stage.argv + energy_args)
                  if stage.name.split(":")[-1] in consumers else stage for stage in stages]
    return stages


def build_pipeline_plan(
    config: ModeConfig,
    paths: PipelinePaths,
    preflight_result: PreflightResult,
    *,
    python_executable: str = sys.executable,
    phi_bins: int = 12,
    energy_binnings: dict[str, EnergyBinning] | None = None,
    best_binning: bool = False,
    flux_study: str = "off",
    flux_study_metadata: Path | None = None,
) -> tuple[Stage, ...]:
    if flux_study not in ("off", "audit", "study"):
        raise PipelineError(f"invalid flux study mode: {flux_study}")
    if flux_study == "off" and flux_study_metadata is not None:
        raise PipelineError("--flux-study-metadata requires --flux-study audit or study")
    phi_edges_rad(phi_bins)
    energy_binnings = energy_binnings or {}
    stages = _common_stages(python_executable, paths)
    if flux_study != "off":
        module = "audit_flux" if flux_study == "audit" else "study_missing_flux"
        command = _argv(python_executable, "-m", f"flux_studies.{module}",
                        "--manifest", paths.manifest, "--raw-flux", paths.raw_flux,
                        "--calibrated-flux", paths.calibrated_flux,
                        "--calibration-qa", paths.calibrated_flux.with_suffix(".qa.json"),
                        "--output-dir", paths.repo_root / "results_test/diagnostics" / paths.output_root.name / "missing_flux")
        if flux_study_metadata is not None:
            command += _argv("--run-metadata", flux_study_metadata)
        stages.append(Stage(f"common:flux_{flux_study}", command))
    stages.extend(
        _profile_stages(
            "uv", UV_CHANNELS, config, paths, preflight_result, python_executable, phi_bins, energy_binnings.get("uv")
        )
    )
    stages.extend(
        _profile_stages(
            "vis", VIS_CHANNELS, config, paths, preflight_result, python_executable, phi_bins, energy_binnings.get("vis")
        )
    )
    if best_binning:
        stages = [Stage(stage.name, (*stage.argv, "--best-binning"))
                  if stage.name.endswith(":extract") else stage for stage in stages]
    stages.append(
        Stage(
            "campaign:plots",
            _argv(
                python_executable,
                paths.repo_root / "scripts/plot_campaign.py",
                "--campaign",
                paths.output_root,
                "--published-csv",
                paths.ajaka_reference,
            ),
        )
    )
    return tuple(stages)
