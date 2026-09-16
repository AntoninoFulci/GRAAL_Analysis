"""Dependency-free contract for stage-1 model artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping


MODEL_FILE = "bdt_stage1.json"
THRESHOLD_FILE = "stage1_threshold.txt"
PROVENANCE_FILE = "stage1_provenance.json"
METRICS_FILE = "stage1_metrics.txt"

_PROVENANCE_KEYS = (
    "signal_channel",
    "hypothesis",
    "signal_prior",
    "beam_reweighted",
    "phase_space_sampling",
    "tagger_resolution_fwhm_gev",
    "tagger_resolution_sigma_gev",
    "detector_covariance_status",
    "feature_names",
)


@dataclass(frozen=True)
class Stage1ArtifactPaths:
    model: Path
    threshold: Path
    provenance: Path
    metrics: Path

    @classmethod
    def from_directory(cls, path: str | Path) -> "Stage1ArtifactPaths":
        directory = Path(path)
        return cls(
            model=directory / MODEL_FILE,
            threshold=directory / THRESHOLD_FILE,
            provenance=directory / PROVENANCE_FILE,
            metrics=directory / METRICS_FILE,
        )


@dataclass(frozen=True)
class Stage1Provenance:
    signal_channel: str
    hypothesis: str
    signal_prior: float | None
    beam_reweighted: bool | None
    phase_space_sampling: str
    tagger_resolution_fwhm_gev: float
    tagger_resolution_sigma_gev: float
    detector_covariance_status: str
    feature_names: tuple[str, ...]

    @classmethod
    def from_json(cls, text: str) -> "Stage1Provenance":
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("stage-1 provenance must be a JSON object")
        return cls._from_mapping(value)

    @classmethod
    def _from_mapping(cls, value: Mapping[str, Any]) -> "Stage1Provenance":
        expected = set(_PROVENANCE_KEYS)
        actual = set(value)
        missing = expected - actual
        unexpected = actual - expected
        if missing:
            raise ValueError(f"missing keys: {', '.join(sorted(missing))}")
        if unexpected:
            raise ValueError(f"unexpected keys: {', '.join(sorted(unexpected))}")

        signal_channel = _string(value["signal_channel"], "signal_channel")
        hypothesis = _string(value["hypothesis"], "hypothesis")
        signal_prior = _nullable_number(value["signal_prior"], "signal_prior")
        beam_reweighted = value["beam_reweighted"]
        if beam_reweighted is not None and not isinstance(beam_reweighted, bool):
            raise ValueError("beam_reweighted must be a boolean or null")
        phase_space_sampling = _string(
            value["phase_space_sampling"], "phase_space_sampling"
        )
        tagger_resolution_fwhm_gev = _number(
            value["tagger_resolution_fwhm_gev"], "tagger_resolution_fwhm_gev"
        )
        tagger_resolution_sigma_gev = _number(
            value["tagger_resolution_sigma_gev"], "tagger_resolution_sigma_gev"
        )
        detector_covariance_status = _string(
            value["detector_covariance_status"], "detector_covariance_status"
        )
        feature_names = value["feature_names"]
        if not isinstance(feature_names, (list, tuple)) or not all(
            isinstance(name, str) for name in feature_names
        ):
            raise ValueError("feature_names must be an array of strings")

        return cls(
            signal_channel=signal_channel,
            hypothesis=hypothesis,
            signal_prior=signal_prior,
            beam_reweighted=beam_reweighted,
            phase_space_sampling=phase_space_sampling,
            tagger_resolution_fwhm_gev=tagger_resolution_fwhm_gev,
            tagger_resolution_sigma_gev=tagger_resolution_sigma_gev,
            detector_covariance_status=detector_covariance_status,
            feature_names=tuple(feature_names),
        )

    def to_json(self) -> str:
        validated = self._from_mapping(
            {
                "signal_channel": self.signal_channel,
                "hypothesis": self.hypothesis,
                "signal_prior": self.signal_prior,
                "beam_reweighted": self.beam_reweighted,
                "phase_space_sampling": self.phase_space_sampling,
                "tagger_resolution_fwhm_gev": self.tagger_resolution_fwhm_gev,
                "tagger_resolution_sigma_gev": self.tagger_resolution_sigma_gev,
                "detector_covariance_status": self.detector_covariance_status,
                "feature_names": self.feature_names,
            }
        )
        return json.dumps(
            {
                "signal_channel": validated.signal_channel,
                "hypothesis": validated.hypothesis,
                "signal_prior": validated.signal_prior,
                "beam_reweighted": validated.beam_reweighted,
                "phase_space_sampling": validated.phase_space_sampling,
                "tagger_resolution_fwhm_gev": validated.tagger_resolution_fwhm_gev,
                "tagger_resolution_sigma_gev": validated.tagger_resolution_sigma_gev,
                "detector_covariance_status": validated.detector_covariance_status,
                "feature_names": list(validated.feature_names),
            },
            indent=2,
        ) + "\n"


def _string(value: Any, name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{name} must be a string")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _nullable_number(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a number or null")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite or null")
    return number
