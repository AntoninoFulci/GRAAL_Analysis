"""Strict reader for the joint mass/azimuth N3 response authority."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import math
from pathlib import Path
import re
from types import MappingProxyType
from typing import Mapping, NamedTuple

import numpy as np

from analysis_config import (
    AnalysisConfig, RESPONSE_SCHEMA_APPROVAL_ID, RESPONSE_SCHEMA_PATH,
    ResponseValidationConfig,
)
from contracts import (
    PolarizationContractError, SHA256_PATTERN, canonical_relative_file,
    load_json, sha256_file,
)
from figure4_analysis import physical_mass_edges


RESPONSE_FIELDS = tuple("""
schema_version analysis_version acceptance_release_id channel target beam_group
Egamma_low Egamma_high cos_theta_low cos_theta_high observable selection_id
orientation true_mass_bin true_mass_low_gev true_mass_high_gev true_phi_bin
true_phi_low true_phi_high reco_mass_bin reco_mass_low_gev reco_mass_high_gev
reco_phi_bin reco_phi_low reco_phi_high n_generated_true sumw_generated_true
sumw2_generated_true n_selected_migration sumw_selected_migration
sumw2_selected_migration response_probability response_stat_uncertainty
validity_mask input_sha256 config_sha256
""".split())
ORIENTATIONS = ("parallel", "perpendicular")
CHANNELS = ("eta_pi0",)
VALIDITY_MASKS = (
    "valid", "invalid_zero_generated", "invalid_low_effective_statistics",
    "invalid_nonphysical_weights", "invalid_incomplete_coverage",
)
PARTICLE_MASSES_GEV = {"proton": .938272, "eta": .547862, "pi0": .134977}
EDGE_ATOL = 1e-12
_INTEGER = re.compile(r"^[0-9]+$")
_INTEGER_FIELDS = (
    "schema_version", "true_mass_bin", "true_phi_bin", "reco_mass_bin",
    "reco_phi_bin", "n_generated_true", "n_selected_migration",
)
_NUMERIC_FIELDS = (
    "Egamma_low", "Egamma_high", "cos_theta_low", "cos_theta_high",
    "true_mass_low_gev", "true_mass_high_gev", "true_phi_low", "true_phi_high",
    "reco_mass_low_gev", "reco_mass_high_gev", "reco_phi_low", "reco_phi_high",
    "sumw_generated_true", "sumw2_generated_true", "sumw_selected_migration",
    "sumw2_selected_migration", "response_probability", "response_stat_uncertainty",
)


class ResponseKey(NamedTuple):
    channel: str
    target: str
    beam_group: str
    Egamma_low: float
    Egamma_high: float
    cos_theta_low: float
    cos_theta_high: float
    observable: str
    selection_id: str


class TrueCellKey(NamedTuple):
    key: ResponseKey
    orientation: str
    true_cell: int


@dataclass(frozen=True)
class PhiResponse:
    keys: tuple[ResponseKey, ...]
    matrices: Mapping[tuple[ResponseKey, str], np.ndarray]
    covariance_by_true_cell: Mapping[TrueCellKey, np.ndarray]
    validity: Mapping[TrueCellKey, str]
    source_sha256: str
    input_sha256: str
    config_sha256: str
    mass_edges: Mapping[ResponseKey, tuple[float, ...]]
    phi_edges: Mapping[ResponseKey, tuple[float, ...]]

    def matrix(self, key: ResponseKey, orientation: str) -> np.ndarray:
        """Return R[reconstructed, true], flattened mass-major then phi-major."""
        try:
            return self.matrices[key, orientation]
        except KeyError as exc:
            raise PolarizationContractError("response key/orientation is not present") from exc

    def covariance_blocks(self, key: ResponseKey, orientation: str) -> tuple[np.ndarray, ...]:
        """Return covariance across reconstructed cells, in true-cell order."""
        size = self.matrix(key, orientation).shape[1]
        return tuple(self.covariance_by_true_cell[TrueCellKey(key, orientation, i)]
                     for i in range(size))


def _authority(repository_root: Path, config: AnalysisConfig, release_id: str) -> None:
    if config.status != "approved":
        raise PolarizationContractError("response requires approved canonical config")
    if not release_id or config.acceptance_release_id != release_id:
        raise PolarizationContractError("response release does not match canonical config")
    if (config.phi_response_schema_path != RESPONSE_SCHEMA_PATH
            or config.phi_response_schema_approval_id != RESPONSE_SCHEMA_APPROVAL_ID):
        raise PolarizationContractError("response schema authority path or approval ID mismatch")
    _, schema_path = canonical_relative_file(repository_root, config.phi_response_schema_path, "response schema")
    if sha256_file(schema_path) != config.phi_response_schema_sha256:
        raise PolarizationContractError("response schema SHA-256 mismatch")
    schema = load_json(schema_path)
    if (type(schema.get("schema_version")) is not int or schema["schema_version"] != 1
            or schema.get("schema_id") != "graal.acceptance_phi_response.v1"
            or schema.get("approval_id") != RESPONSE_SCHEMA_APPROVAL_ID
            or schema.get("columns") != list(RESPONSE_FIELDS)
            or schema.get("channels") != list(CHANNELS)
            or schema.get("orientations") != list(ORIENTATIONS)
            or schema.get("validity_masks") != list(VALIDITY_MASKS)
            or schema.get("angle_convention") != {
                "observable": "reaction_plane_phi",
                "period_radians": "pi",
                "range_radians": [0, "pi"],
                "interval": "[0, pi)",
                "reference_axis_lab": [1, 0, 0],
                "reaction_momentum": "proton",
                "degenerate_plane_policy": "reject_publication",
                "tolerance_authority": "approved canonical config angle.tolerance",
            }
            or schema.get("acceptance_qa_contract") != {
                "field": "response_period_coverage",
                "record_keys": [
                    "beam_group", "covered_source_periods", "coverage_valid",
                    "detector_conditions_sha256", "mc_config_sha256",
                    "selection_sha256",
                ],
                "coverage": "exactly one record per response beam_group",
                "periods": "non-empty unique canonical source periods in ascending order",
                "validity": "coverage_valid must be true for a releasable N3 handoff",
                "hashes": "lowercase SHA-256 identities for detector conditions, MC configuration, and selection",
            }):
        raise PolarizationContractError("unsupported response schema authority")
    for name, value in vars(config.response_validation).items():
        if (isinstance(value, bool) or not isinstance(value, (float, int))
                or not math.isfinite(value) or value < 0):
            raise PolarizationContractError(f"response validation {name} must be finite and nonnegative")
    for name in (
        "minimum_generated_effective_events_per_true_phi",
        "finite_difference_relative_step", "finite_difference_absolute_step",
    ):
        if getattr(config.response_validation, name) <= 0:
            raise PolarizationContractError(f"response validation {name} must be positive")


def _parse_row(raw: dict[str, str], config: AnalysisConfig, release_id: str) -> dict:
    if set(raw) != set(RESPONSE_FIELDS) or any(value is None for value in raw.values()):
        raise PolarizationContractError("response row must contain exactly the schema columns")
    row = dict(raw)
    for field, value in raw.items():
        if not value or value.strip() != value:
            raise PolarizationContractError(f"response {field} must be non-empty and canonical")
    for field in _INTEGER_FIELDS:
        if _INTEGER.fullmatch(raw[field]) is None:
            raise PolarizationContractError(f"response {field} must be a nonnegative integer")
        row[field] = int(raw[field])
    for field in _NUMERIC_FIELDS:
        try:
            value = float(raw[field])
        except ValueError as exc:
            raise PolarizationContractError(f"response {field} must be numeric") from exc
        if not math.isfinite(value):
            raise PolarizationContractError(f"response {field} must be finite")
        row[field] = value
        if (field.startswith("sumw") or field.startswith("response_")) and value < 0:
            raise PolarizationContractError(f"response {field} must be nonnegative")
    if row["schema_version"] != 1 or row["analysis_version"] != config.analysis_version:
        raise PolarizationContractError("response schema/analysis version mismatch")
    if row["acceptance_release_id"] != release_id:
        raise PolarizationContractError("response release ID mismatch")
    if row["channel"] != CHANNELS[0]:
        raise PolarizationContractError("response channel must be canonical eta_pi0")
    if row["orientation"] not in ORIENTATIONS or row["validity_mask"] not in VALIDITY_MASKS:
        raise PolarizationContractError("response orientation or validity mask is invalid")
    for field in ("input_sha256", "config_sha256"):
        if SHA256_PATTERN.fullmatch(row[field]) is None:
            raise PolarizationContractError(f"response {field} must be lowercase SHA-256")
    for low, high in (
        ("Egamma_low", "Egamma_high"), ("cos_theta_low", "cos_theta_high"),
        ("true_mass_low_gev", "true_mass_high_gev"), ("reco_mass_low_gev", "reco_mass_high_gev"),
        ("true_phi_low", "true_phi_high"), ("reco_phi_low", "reco_phi_high"),
    ):
        if row[low] >= row[high]:
            raise PolarizationContractError("response bin edges must be strictly ordered")
    energy_bins = tuple(zip(config.figure4_energy_edges_gev, config.figure4_energy_edges_gev[1:]))
    if (row["Egamma_low"], row["Egamma_high"]) not in energy_bins:
        raise PolarizationContractError("response energy bin disagrees with approved config")
    if row["target"] != config.figure4_target or not -1 <= row["cos_theta_low"] < row["cos_theta_high"] <= 1:
        raise PolarizationContractError("response target or angular bin disagrees with physical config")
    if row["response_probability"] > 1.0:
        raise PolarizationContractError("response probability must lie in [0,1]")
    return row


def _axis(rows: list[dict], prefix: str, kind: str, count: int) -> tuple[float, ...]:
    suffix = "_gev" if kind == "mass" else ""
    bins = {}
    for row in rows:
        index = row[f"{prefix}_{kind}_bin"]
        bounds = (row[f"{prefix}_{kind}_low{suffix}"], row[f"{prefix}_{kind}_high{suffix}"])
        if index in bins and bins[index] != bounds:
            raise PolarizationContractError("response axes have inconsistent bin edges")
        bins[index] = bounds
    if set(bins) != set(range(count)):
        raise PolarizationContractError("response requires a complete Cartesian grid with contiguous indices")
    for i in range(count - 1):
        if not math.isclose(bins[i][1], bins[i + 1][0], rel_tol=0, abs_tol=EDGE_ATOL):
            raise PolarizationContractError("response partition has gaps or overlaps")
    return (bins[0][0], *(bins[i][1] for i in range(count)))


def _covariance(rows: list[dict], validation: ResponseValidationConfig) -> tuple[np.ndarray, np.ndarray, str]:
    masks = {row["validity_mask"] for row in rows}
    if len(masks) != 1:
        raise PolarizationContractError("response true-cell block has mixed validity masks")
    mask = masks.pop()
    generated = {(row["n_generated_true"], row["sumw_generated_true"], row["sumw2_generated_true"]) for row in rows}
    if len(generated) != 1:
        raise PolarizationContractError("response generated values must repeat identically")
    n, g, g2 = generated.pop()
    p = np.array([row["response_probability"] for row in rows])
    uncertainty = np.array([row["response_stat_uncertainty"] for row in rows])
    if g == 0 or g2 == 0:
        if mask == "valid" or np.any(p != 0) or np.any(uncertainty != 0):
            raise PolarizationContractError("undefined normalization requires an invalid block with zero probability and uncertainty")
        return p, np.zeros((len(rows), len(rows))), mask
    if sum(row["n_selected_migration"] for row in rows) > n:
        raise PolarizationContractError("selected counts exceed generated count")
    selected = np.array([row["sumw_selected_migration"] for row in rows])
    selected2 = np.array([row["sumw2_selected_migration"] for row in rows])
    tolerance = validation.probability_absolute_tolerance
    if not np.allclose(p, selected / g, rtol=0, atol=tolerance):
        raise PolarizationContractError("response probability does not equal selected/generated weight")
    if float(np.sum(selected / g)) > 1 + tolerance or float(np.sum(p)) > 1 + tolerance:
        raise PolarizationContractError("response selected weights/probabilities exceed generated normalization")
    # Compare square roots of N_eff=G**2/G2 to keep finite diagnostics from
    # overflowing merely while deciding whether their threshold is satisfied.
    low_statistics = g / math.sqrt(g2) < math.sqrt(validation.minimum_generated_effective_events_per_true_phi)
    if mask == "valid" and low_statistics:
        raise PolarizationContractError("valid response has low effective generated statistics")
    if mask == "invalid_zero_generated":
        raise PolarizationContractError("zero-generated mask contradicts defined normalization")
    if mask == "invalid_low_effective_statistics" and not low_statistics:
        raise PolarizationContractError("low-statistics mask contradicts effective generated statistics")
    # Divide weight moments before combining to avoid overflowing G**2.
    normalized_g2 = (g2 / g) / g
    normalized_s2 = (selected2 / g) / g
    covariance = (np.outer(p, p) * normalized_g2
                  - np.outer(normalized_s2, p) - np.outer(p, normalized_s2)
                  + np.diag(normalized_s2))
    eigen_tolerance = validation.covariance_eigenvalue_absolute_tolerance
    if not np.all(np.isfinite(covariance)):
        raise PolarizationContractError("response covariance must be finite")
    if np.any(np.diag(covariance) < -eigen_tolerance):
        raise PolarizationContractError("response covariance has a materially negative variance")
    if not np.allclose(covariance, covariance.T, rtol=0, atol=eigen_tolerance):
        raise PolarizationContractError("response covariance must be symmetric")
    if np.linalg.eigvalsh(covariance)[0] < -eigen_tolerance:
        raise PolarizationContractError("response covariance has a materially negative eigenvalue")
    if not np.allclose(uncertainty, np.sqrt(np.maximum(np.diag(covariance), 0)),
                       rtol=validation.uncertainty_relative_tolerance,
                       atol=validation.uncertainty_absolute_tolerance):
        raise PolarizationContractError("response statistical uncertainty disagrees with weighted covariance")
    return p, covariance, mask


def _readonly(array: np.ndarray) -> np.ndarray:
    # An immutable bytes backing also prevents callers re-enabling WRITEABLE.
    return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape)


def load_phi_response(path: Path, *, repository_root: Path, config: AnalysisConfig,
                      expected_release_id: str) -> PhiResponse:
    """Validate exact CSV bytes and reconstruct complete pooled N3 matrices.

    CSV producer/input hashes are checked for consistency here; the handoff
    reader binds them to the independently anchored acceptance QA publication.
    Invalid blocks are retained, and callers must reject them for release.
    """
    _authority(repository_root, config, expected_release_id)
    path = Path(path)
    if path.is_absolute():
        try:
            relative = path.relative_to(Path(repository_root).resolve()).as_posix()
        except ValueError as exc:
            raise PolarizationContractError("response path is outside repository") from exc
    else:
        relative = path.as_posix()
    _, path = canonical_relative_file(repository_root, relative, "response CSV")
    source_digest = sha256_file(path)
    groups = {}
    previous = None
    hashes = set()
    try:
        with path.open(newline="", encoding="utf-8") as stream:
            reader = csv.DictReader(stream, strict=True)
            if reader.fieldnames != list(RESPONSE_FIELDS):
                raise PolarizationContractError("response CSV requires exact ordered schema columns")
            for raw in reader:
                row = _parse_row(raw, config, expected_release_id)
                key = ResponseKey(*(row[field] for field in ResponseKey._fields))
                ordering = (key, row["orientation"], row["true_mass_bin"], row["true_phi_bin"],
                            row["reco_mass_bin"], row["reco_phi_bin"])
                if previous is not None and ordering <= previous:
                    raise PolarizationContractError("response rows must be unique and in canonical ascending order")
                previous = ordering
                groups.setdefault((key, row["orientation"]), []).append(row)
                hashes.add((row["input_sha256"], row["config_sha256"]))
    except (OSError, UnicodeError, csv.Error) as exc:
        raise PolarizationContractError(f"cannot read response CSV: {exc}") from exc
    if not groups:
        raise PolarizationContractError("response CSV requires a complete Cartesian grid")
    if len(hashes) != 1:
        raise PolarizationContractError("response input/config hashes must be consistent across file")
    if sha256_file(path) != source_digest:
        raise PolarizationContractError("response CSV changed during validation")
    keys = tuple(sorted({key for key, _ in groups}))
    matrices, covariance, validity, mass_edges, phi_edges = {}, {}, {}, {}, {}
    m, p = config.figure4_mass_bins, config.figure4_phi_bins
    size = m * p
    for key in keys:
        expected_mass = physical_mass_edges(key.Egamma_high, bins=m, masses_gev=PARTICLE_MASSES_GEV)
        if key.observable not in expected_mass:
            raise PolarizationContractError("response observable has no approved mass binning")
        for orientation in ORIENTATIONS:
            if (key, orientation) not in groups:
                raise PolarizationContractError("response requires both mandatory orientations")
            rows = groups[key, orientation]
            if len(rows) != size ** 2:
                raise PolarizationContractError("response requires a complete Cartesian grid including zero cells")
            for kind, count in (("mass", m), ("phi", p)):
                true = _axis(rows, "true", kind, count)
                reco = _axis(rows, "reco", kind, count)
                if not np.allclose(true, reco, rtol=0, atol=EDGE_ATOL):
                    raise PolarizationContractError("true/reconstructed response axes must be equal")
                if kind == "mass":
                    if not np.allclose(true, expected_mass[key.observable], rtol=0, atol=EDGE_ATOL):
                        raise PolarizationContractError("response mass edges disagree with approved fit binning")
                    if key in mass_edges and not np.allclose(
                        mass_edges[key], true, rtol=0, atol=EDGE_ATOL
                    ):
                        raise PolarizationContractError(
                            "response orientations must share equal mass axes"
                        )
                    mass_edges[key] = true
                else:
                    if not math.isclose(true[0], 0, abs_tol=EDGE_ATOL, rel_tol=0) or not math.isclose(true[-1], math.pi, abs_tol=EDGE_ATOL, rel_tol=0):
                        raise PolarizationContractError("response phi axes must cover [0,pi) without wrap")
                    if key in phi_edges and not np.allclose(phi_edges[key], true, rtol=0, atol=EDGE_ATOL):
                        raise PolarizationContractError("response orientations must share equal phi axes")
                    phi_edges[key] = true
            matrix = np.empty((size, size))
            for i in range(size):
                probability, block, mask = _covariance(rows[i * size:(i + 1) * size], config.response_validation)
                matrix[:, i] = probability
                cell = TrueCellKey(key, orientation, i)
                covariance[cell] = _readonly(block)
                validity[cell] = mask
            matrices[key, orientation] = _readonly(matrix)
    input_digest, config_digest = hashes.pop()
    return PhiResponse(keys, MappingProxyType(matrices), MappingProxyType(covariance),
                       MappingProxyType(validity), source_digest, input_digest, config_digest,
                       MappingProxyType(mass_edges), MappingProxyType(phi_edges))
