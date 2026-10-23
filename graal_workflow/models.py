"""Workflow configuration and stage value types."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from graal_common.physics.channels import CHANNEL_NAMES

PROFILE_PATTERNS = {
    "uv": "pre_analisi_*uv*.root",
    "vis": "pre_analisi_*vis*.root",
}
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
    artifact_root: Path
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
        return self.artifact_root / "03_selected" / profile

    def mc_dir(self, profile: str) -> Path:
        self.profile_root(profile)
        return self.artifact_root / "04_mc" / profile

    def bdt_dir(self, profile: str) -> Path:
        self.profile_root(profile)
        return self.artifact_root / "05_bdt" / profile


@dataclass(frozen=True)
class PreflightResult:
    root_executable: str
    old_preanalysis_inputs: tuple[Path, ...] = ()


@dataclass(frozen=True)
class Stage:
    name: str
    argv: tuple[str, ...]


@dataclass(frozen=True)
class CacheItem:
    name: str
    manifest: Path
    outputs: tuple[Path, ...]
    signature: dict
