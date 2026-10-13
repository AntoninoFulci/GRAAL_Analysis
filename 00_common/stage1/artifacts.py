"""Dependency-free contract for stage-1 model artifacts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
from typing import Any, Mapping

from graal_common.physics.beam_profiles import get_beam_profile
from graal_common.physics.energy_binning import EnergyBinning


MODEL_FILE = "bdt_stage1.json"
THRESHOLD_FILE = "stage1_threshold.txt"
PROVENANCE_FILE = "stage1_provenance.json"
METRICS_FILE = "stage1_metrics.txt"

_REQUIRED_PROVENANCE_KEYS = (
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
_OPTIONAL_PROVENANCE_KEYS = (
    "beam_profile",
    "energy_min_gev",
    "energy_max_gev",
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
    beam_profile: str | None = None
    energy_min_gev: float | None = None
    energy_max_gev: float | None = None
    shared_training: dict[str, Any] | None = None

    @classmethod
    def from_json(cls, text: str) -> "Stage1Provenance":
        value = json.loads(text)
        if not isinstance(value, dict):
            raise ValueError("stage-1 provenance must be a JSON object")
        return cls._from_mapping(value)

    @classmethod
    def _from_mapping(cls, value: Mapping[str, Any]) -> "Stage1Provenance":
        required = set(_REQUIRED_PROVENANCE_KEYS)
        optional = set(_OPTIONAL_PROVENANCE_KEYS)
        actual = set(value)
        missing = required - actual
        unexpected = actual - required - optional - {"shared_training"}
        if missing:
            raise ValueError(f"missing keys: {', '.join(sorted(missing))}")
        if unexpected:
            raise ValueError(f"unexpected keys: {', '.join(sorted(unexpected))}")
        present_optional = actual & optional
        if present_optional and present_optional != optional:
            raise ValueError(
                "profile energy metadata must be complete or entirely absent"
            )

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

        beam_profile = None
        energy_min_gev = None
        energy_max_gev = None
        if present_optional:
            beam_profile = _string(value["beam_profile"], "beam_profile")
            energy_min_gev = _number(value["energy_min_gev"], "energy_min_gev")
            energy_max_gev = _number(value["energy_max_gev"], "energy_max_gev")
            if energy_max_gev <= energy_min_gev:
                raise ValueError("profile energy bounds must be increasing")
            profile = get_beam_profile(beam_profile)
            EnergyBinning((energy_min_gev, energy_max_gev)).validate_profile(profile)

        shared_training = None
        if "shared_training" in value:
            if present_optional:
                raise ValueError("single-profile and shared training metadata are mutually exclusive")
            shared_training = _shared_training(value["shared_training"])

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
            beam_profile=beam_profile,
            energy_min_gev=energy_min_gev,
            energy_max_gev=energy_max_gev,
            shared_training=shared_training,
        )

    def to_json(self) -> str:
        values = {name: getattr(self, name) for name in _REQUIRED_PROVENANCE_KEYS}
        profile_values = (
            self.beam_profile,
            self.energy_min_gev,
            self.energy_max_gev,
        )
        if any(value is not None for value in profile_values):
            if any(value is None for value in profile_values):
                raise ValueError(
                    "profile energy metadata must be complete or entirely absent"
                )
            values.update(
                beam_profile=self.beam_profile,
                energy_min_gev=self.energy_min_gev,
                energy_max_gev=self.energy_max_gev,
            )
        if self.shared_training is not None:
            values["shared_training"] = self.shared_training
        validated = self._from_mapping(values)
        output = {name: getattr(validated, name) for name in _REQUIRED_PROVENANCE_KEYS}
        if validated.beam_profile is not None:
            output.update(
                beam_profile=validated.beam_profile,
                energy_min_gev=validated.energy_min_gev,
                energy_max_gev=validated.energy_max_gev,
            )
        if validated.shared_training is not None:
            output["shared_training"] = validated.shared_training
        return json.dumps(output, indent=2) + "\n"


def _shared_training(value: Any) -> dict:
    """Versioned diagnostic contract, never a certificate of physics closure."""
    keys = {"schema_version", "supported_profiles", "profile_mixture", "dataset_sha256",
            "split_sha256", "training_seed", "threshold_policy", "validation_status"}
    if not isinstance(value, dict) or set(value) != keys:
        raise ValueError("shared_training has an incomplete or unsupported schema")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("unsupported shared_training schema_version")
    domains, mixture = value["supported_profiles"], value["profile_mixture"]
    if not isinstance(domains, dict) or set(domains) != {"uv", "vis"}:
        raise ValueError("shared model must declare UV and VIS coverage")
    if not isinstance(mixture, dict) or set(mixture) != set(domains):
        raise ValueError("profile mixture must match supported profiles")
    normalized = {}
    for name, bounds in domains.items():
        if not isinstance(bounds, (list, tuple)) or len(bounds) != 2:
            raise ValueError("shared profile coverage requires two energy bounds")
        low, high = (_number(v, "energy bound") for v in bounds)
        EnergyBinning((low, high)).validate_profile(get_beam_profile(name))
        normalized[name] = [low, high]
        if not 0 < _number(mixture[name], "profile mixture") < 1:
            raise ValueError("profile mixture must be positive and less than one")
    if not math.isclose(sum(mixture.values()), 1., rel_tol=0., abs_tol=1e-12):
        raise ValueError("profile mixture must sum to one")
    for field in ("dataset_sha256", "split_sha256"):
        digest = value[field]
        if not isinstance(digest, str) or len(digest) != 64 or any(c not in "0123456789abcdef" for c in digest):
            raise ValueError(f"{field} must be a SHA-256 digest")
    if type(value["training_seed"]) is not int or value["training_seed"] < 0:
        raise ValueError("training_seed must be a nonnegative integer")
    if value["threshold_policy"] != "weighted_validation_f1_single":
        raise ValueError("unsupported shared threshold policy")
    if value["validation_status"] != "diagnostic_only":
        raise ValueError("shared training does not certify physical validation")
    return {**value, "supported_profiles": normalized, "profile_mixture": dict(mixture)}


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
