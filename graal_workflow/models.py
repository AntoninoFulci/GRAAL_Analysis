"""Workflow configuration and stage value types."""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
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
    run_quality: Path | None = None

    @property
    def quality_path(self) -> Path:
        return self.run_quality or self.repo_root / "config/support/run_quality_exclusions.json"

    @property
    def calibrated_flux(self) -> Path:
        return self.output_root / "root/common/flux_calibrated.root"

    @property
    def combined_dir(self) -> Path:
        return self.output_root / "plots/common"

    @property
    def command_log(self) -> Path:
        return self.output_root / "metadata/pipeline_commands.log"

    def profile_root(self, profile: str) -> Path:
        if profile not in PROFILE_PATTERNS:
            raise PipelineError(f"unknown beam profile: {profile}")
        return self.output_root / "root" / profile

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
    kind: str = "command"
    profile: str | None = None
    channel: str | None = None
    seed_key: str = ""


@dataclass(frozen=True)
class ArtifactGroup:
    """An indivisible cache publication unit, declared by the planner."""

    kind: Literal["selected", "mc", "bdt"]
    profile: str
    stages: tuple[Stage, ...]
    destination: Path
    channel: str | None = None
    energy_range: tuple[float, float] | None = None
    force: bool | None = None
    inputs: tuple[Path, ...] = ()

    def __post_init__(self) -> None:
        expected = {"selected": ("select",), "mc": ("generate",),
                    "bdt": ("beam_spectrum", "features", "train")}
        if self.kind not in expected:
            raise PipelineError(f"unknown artifact group kind: {self.kind}")
        label = "BDT" if self.kind == "bdt" else self.kind
        if tuple(stage.kind for stage in self.stages) != expected[self.kind]:
            raise PipelineError(f"incomplete {self.profile} {label} stage group")
        if self.profile not in PROFILE_PATTERNS or any(stage.profile != self.profile for stage in self.stages):
            raise PipelineError(f"inconsistent profile in {label} stage group")
        if self.kind == "mc":
            if not self.channel or any(stage.channel != self.channel or not stage.seed_key for stage in self.stages):
                raise PipelineError("MC stage group requires matching channel and explicit seed_key")
        elif self.channel is not None or any(stage.channel is not None for stage in self.stages):
            raise PipelineError(f"unexpected channel in {label} stage group")
        if self.energy_range is not None:
            low, high = self.energy_range
            if not low < high:
                raise PipelineError(f"invalid energy range in {label} stage group")


PipelinePlan = tuple[Stage | ArtifactGroup, ...]


def flatten_stages(plan: Sequence[Stage | ArtifactGroup]) -> tuple[Stage, ...]:
    """Expose command order for dispatch, source inventory, and presentation."""
    return tuple(stage for entry in plan
                 for stage in (entry.stages if isinstance(entry, ArtifactGroup) else (entry,)))


@dataclass(frozen=True)
class CacheItem:
    name: str
    manifest: Path
    outputs: tuple[Path, ...]
    signature: dict
