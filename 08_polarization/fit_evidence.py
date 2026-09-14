"""Strict serialization and independent validation of immutable S4 evidence."""

from __future__ import annotations

import csv
from dataclasses import dataclass, fields
import json
import math
from pathlib import Path, PurePosixPath
from typing import Mapping, Sequence

import numpy as np
import scipy
from scipy.special import xlogy

from analysis_config import AnalysisConfig, load_analysis_config
from azimuth_counts import (
    AZIMUTH_COUNT_FIELDS,
    AzimuthCountRow,
    AzimuthCountTable,
    CountAuthority,
    ExpectedRecoGrid,
    _authority_fingerprint,
    load_count_authority,
    _reload_count_authority,
    _validate_table_for_publication,
    write_azimuth_counts,
)
from contracts import (
    COMMIT_PATTERN,
    SHA256_PATTERN,
    PolarizationContractError,
    canonical_relative_file,
    load_json,
    sha256_file,
)
from phi_response import ResponseKey
from response_uncertainty import ResponseModeRefit, ResponsePropagationResult
from sigma_fit import (
    JointSigmaFitResult,
    _row_order as _fit_row_order,
    _sigma_bin_key,
    canonical_count_row_key,
)


FIT_EVIDENCE_FILENAMES = frozenset(
    {"azimuth_counts_v1.csv", "sigma_fit_v1.csv", "sigma_fit_qa.json"}
)
FIT_FIELDS = (
    "schema_version", "analysis_version", "fit_release_id", "bin_index",
    "bin_key", "sigma", "bootstrap_stat_uncertainty",
    "hessian_stat_uncertainty", "log_yield", "bootstrap_variance",
    "hessian_variance", "response_variance",
)
_FIT_PARENT = "results/physics/polarization_fits"
_QA_KEYS = frozenset(
    {
        "schema_version", "analysis_version", "fit_release_id",
        "producer_commit", "valid", "blocked_reasons", "bin_set_id",
        "counts", "fit", "authorities", "optimizer", "bootstrap",
        "nominal_fit", "response_propagation",
    }
)
_AUTHORITY_KEYS = frozenset(
    {
        "config", "gate0_handoff", "n2_inventory", "n2_source_kind",
        "acceptance_release_id", "acceptance_qa", "phi_response",
        "phi_response_schema", "phi_response_schema_approval_id",
        "state_mapping", "flux", "compton_sources",
    }
)
_FILE_KEYS = frozenset({"path", "sha256"})


@dataclass(frozen=True)
class FitEvidence:
    directory: Path
    counts: AzimuthCountTable
    nominal_fit: JointSigmaFitResult
    statistical_covariance: np.ndarray
    response_propagation: ResponsePropagationResult
    bootstrap_sigma_vectors: np.ndarray
    successful_replica_ids: tuple[int, ...]
    failed_replica_ids: tuple[int, ...]
    qa: Mapping[str, object]


def _readonly(raw: object) -> np.ndarray:
    array = np.asarray(raw, dtype=float)
    return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape)


def _finite(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PolarizationContractError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise PolarizationContractError(f"{label} must be finite")
    return result


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise PolarizationContractError(f"{label} must be an integer >= {minimum}")
    return value


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise PolarizationContractError(f"{label} must be a non-empty string")
    return value


def _release_id(value: object) -> str:
    result = _text(value, "S4 fit_release_id")
    if (
        result != result.strip()
        or "\\" in result
        or PurePosixPath(result).parts != (result,)
        or result in {".", ".."}
    ):
        raise PolarizationContractError(
            "S4 fit release ID must be one canonical path component"
        )
    return result


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise PolarizationContractError(f"{label} must be lowercase SHA-256")
    return value


def _json_array(raw: object, label: str, *, ndim: int) -> np.ndarray:
    try:
        value = np.asarray(raw, dtype=float)
    except (TypeError, ValueError) as exc:
        raise PolarizationContractError(f"{label} must be numeric") from exc
    if value.ndim != ndim or not np.all(np.isfinite(value)):
        raise PolarizationContractError(f"{label} must be a finite rank-{ndim} array")
    return value


def _psd(raw: object, dimension: int, label: str) -> np.ndarray:
    value = _json_array(raw, label, ndim=2)
    if value.shape != (dimension, dimension):
        raise PolarizationContractError(f"{label} shape is invalid")
    scale = float(np.max(np.abs(value))) if value.size else 0.0
    tolerance = 64.0 * np.finfo(float).eps * dimension * scale
    if not np.allclose(value, value.T, rtol=0.0, atol=tolerance):
        raise PolarizationContractError(f"{label} must be symmetric")
    value = (value + value.T) / 2.0
    if dimension and np.linalg.eigvalsh(value)[0] < -tolerance:
        raise PolarizationContractError(f"{label} must be positive semidefinite")
    return _readonly(value)


def _file_record(root: Path, path: Path) -> dict[str, str]:
    relative = path.resolve(strict=True).relative_to(root.resolve(strict=True)).as_posix()
    canonical_relative_file(root, relative, "S4 authority")
    return {"path": relative, "sha256": sha256_file(path)}


def _validate_file_record(root: Path, raw: object, label: str) -> tuple[str, Path, str]:
    if not isinstance(raw, Mapping) or set(raw) != _FILE_KEYS:
        raise PolarizationContractError(f"{label} file record is invalid")
    digest = _digest(raw.get("sha256"), f"{label} SHA-256")
    relative, path = canonical_relative_file(root, raw.get("path"), label)
    if sha256_file(path) != digest:
        raise PolarizationContractError(f"{label} SHA-256 mismatch")
    return relative, path, digest


def _authority_payload(authority: CountAuthority) -> dict[str, object]:
    root = authority.repository_root
    acceptance = {item.path.name: item for item in authority.acceptance_files}
    return {
        "config": _file_record(root, authority.config_file.path),
        "gate0_handoff": _file_record(root, authority.gate0_handoff_file.path),
        "n2_inventory": _file_record(root, authority.n2_inventory_file.path),
        "n2_source_kind": "N2_metadata_reconstruction",
        "acceptance_release_id": authority.config.acceptance_release_id,
        "acceptance_qa": _file_record(root, acceptance["acceptance_qa.json"].path),
        "phi_response": _file_record(
            root, acceptance["acceptance_phi_response_v1.csv"].path
        ),
        "phi_response_schema": _file_record(root, authority.n3_schema_file.path),
        "phi_response_schema_approval_id": authority.config.phi_response_schema_approval_id,
        "state_mapping": _file_record(root, authority.state_mapping_file.path),
        "flux": _file_record(root, authority.flux_file.path),
        "compton_sources": [
            {
                "source_period": item.source_period,
                **_file_record(root, item.file.path),
            }
            for item in sorted(
                authority.compton_files, key=lambda source: source.source_period
            )
        ],
    }


def _fit_payload(result: JointSigmaFitResult) -> dict[str, object]:
    return {
        "bin_keys": list(result.bin_keys),
        "nuisance_keys": list(result.nuisance_keys),
        "row_keys": list(result.row_keys),
        "sigma": result.sigma.tolist(),
        "log_yield": result.log_yield.tolist(),
        "hessian_covariance": result.hessian_covariance.tolist(),
        "expected": result.expected.tolist(),
        "residuals": result.residuals.tolist(),
        "deviance_contributions": result.deviance_contributions.tolist(),
        "deviance": result.deviance,
        "ndof": result.ndof,
        "converged": result.converged,
        "rank": result.rank,
        "replica_id": result.replica_id,
    }


def _response_payload(result: ResponsePropagationResult) -> dict[str, object]:
    return {
        "covariance": result.covariance.tolist(),
        "retained_modes": list(result.retained_modes),
        "refits": [
            {
                "mode_id": item.mode_id,
                "eigenvalue": item.eigenvalue,
                "step": item.step,
                "scheme": item.scheme,
                "derivative": item.derivative.tolist(),
                "lower_sigma": None if item.lower_sigma is None else item.lower_sigma.tolist(),
                "upper_sigma": None if item.upper_sigma is None else item.upper_sigma.tolist(),
            }
            for item in result.refits
        ],
        "valid": result.valid,
    }


def write_fit_evidence(
    directory: Path,
    *,
    authority: CountAuthority,
    counts: AzimuthCountTable,
    nominal: JointSigmaFitResult,
    statistical_covariance: np.ndarray,
    bootstrap_sigma_vectors: np.ndarray,
    successful_replica_ids: Sequence[int],
    failed_replica_ids: Sequence[int],
    response_propagation: ResponsePropagationResult,
    producer_commit: str,
) -> None:
    """Write canonical S4 bytes into an already-owned empty staging directory."""
    if type(authority) is not CountAuthority:
        raise PolarizationContractError("S4 evidence requires authenticated CountAuthority")
    fresh = _reload_count_authority(authority)
    if _authority_fingerprint(fresh) != _authority_fingerprint(authority):
        raise PolarizationContractError("S4 authority changed before serialization")
    _validate_table_for_publication(counts, fresh)
    if COMMIT_PATTERN.fullmatch(producer_commit or "") is None:
        raise PolarizationContractError("producer_commit must be a Git hash")
    target = Path(directory)
    if not target.is_dir() or target.is_symlink() or any(target.iterdir()):
        raise PolarizationContractError("S4 staging directory must be empty and non-symlink")
    dimension = len(nominal.bin_keys)
    stat = _psd(statistical_covariance, dimension, "bootstrap covariance")
    response = _psd(response_propagation.covariance, dimension, "response covariance")
    hessian = _psd(nominal.hessian_covariance, dimension, "Hessian covariance")
    if not nominal.converged or nominal.replica_id != 0 or not response_propagation.valid:
        raise PolarizationContractError("S4 evidence requires valid nominal and response results")
    successful = tuple(successful_replica_ids)
    failed = tuple(failed_replica_ids)
    vectors = _json_array(
        bootstrap_sigma_vectors, "bootstrap Sigma vectors", ndim=2
    )
    if vectors.shape != (len(successful), dimension):
        raise PolarizationContractError(
            "bootstrap Sigma vectors disagree with successful replicas"
        )

    counts_path = target / "azimuth_counts_v1.csv"
    counts_sha = write_azimuth_counts(counts, counts_path, authority=fresh)
    fit_path = target / "sigma_fit_v1.csv"
    with fit_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIT_FIELDS, lineterminator="\n")
        writer.writeheader()
        for index, key in enumerate(nominal.bin_keys):
            writer.writerow(
                {
                    "schema_version": 1,
                    "analysis_version": fresh.config.analysis_version,
                    "fit_release_id": fresh.fit_release_id,
                    "bin_index": index,
                    "bin_key": key,
                    "sigma": format(float(nominal.sigma[index]), ".17g"),
                    "bootstrap_stat_uncertainty": format(float(np.sqrt(stat[index, index])), ".17g"),
                    "hessian_stat_uncertainty": format(float(np.sqrt(hessian[index, index])), ".17g"),
                    "log_yield": format(float(nominal.log_yield[index]), ".17g"),
                    "bootstrap_variance": format(float(stat[index, index]), ".17g"),
                    "hessian_variance": format(float(hessian[index, index]), ".17g"),
                    "response_variance": format(float(response[index, index]), ".17g"),
                }
            )
    fit_sha = sha256_file(fit_path)
    optimizer = {
        "name": "L-BFGS-B",
        "implementation": "scipy.optimize.minimize",
        "sigma_bounds": [-1.0, 1.0],
        "log_yield_bounds": [-30.0, 30.0],
        "initialization": "deterministic_least_squares_v1",
        "scipy_version": scipy.__version__,
        "options": {"ftol": 1e-12, "gtol": 1e-8, "maxiter": 2000},
        "response_finite_difference_relative_step": fresh.config.response_validation.finite_difference_relative_step,
        "response_finite_difference_absolute_step": fresh.config.response_validation.finite_difference_absolute_step,
        "replay_absolute_tolerance": fresh.config.response_validation.replay_absolute_tolerance,
        "replay_relative_tolerance": fresh.config.response_validation.replay_relative_tolerance,
    }
    bootstrap = {
        "algorithm_version": fresh.config.bootstrap.algorithm_version,
        "seed": fresh.config.bootstrap.seed,
        "configured_replicas": fresh.config.bootstrap.replicas,
        "successful_replica_ids": list(successful),
        "failed_replica_ids": list(failed),
        "statistical_covariance": stat.tolist(),
        "sigma_vectors": vectors.tolist(),
        "hessian_diagonal_ratio": (np.diag(hessian) / np.diag(stat)).tolist(),
    }
    qa = {
        "schema_version": 1,
        "analysis_version": fresh.config.analysis_version,
        "fit_release_id": fresh.fit_release_id,
        "producer_commit": producer_commit,
        "valid": True,
        "blocked_reasons": [],
        "bin_set_id": fresh.bin_set_id,
        "counts": {"path": "azimuth_counts_v1.csv", "sha256": counts_sha},
        "fit": {"path": "sigma_fit_v1.csv", "sha256": fit_sha},
        "authorities": _authority_payload(fresh),
        "optimizer": optimizer,
        "bootstrap": bootstrap,
        "nominal_fit": _fit_payload(nominal),
        "response_propagation": _response_payload(response_propagation),
    }
    (target / "sigma_fit_qa.json").write_text(
        json.dumps(qa, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def _parse_counts(path: Path) -> AzimuthCountTable:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != AZIMUTH_COUNT_FIELDS:
            raise PolarizationContractError("S4 counts CSV columns are not canonical")
        parsed = []
        for number, raw in enumerate(reader, start=2):
            values: dict[str, object] = {}
            for field in fields(AzimuthCountRow):
                value = raw[field.name]
                if field.name in {"schema_version", "replica_id", "reco_mass_bin", "reco_phi_bin", "observed_count"}:
                    try:
                        values[field.name] = int(value)
                    except ValueError as exc:
                        raise PolarizationContractError(f"S4 count row {number} integer is invalid") from exc
                elif field.name in {
                    "Egamma_low", "Egamma_high", "cos_theta_low", "cos_theta_high",
                    "reco_mass_low_gev", "reco_mass_high_gev", "reco_phi_low",
                    "reco_phi_high", "exposure", "beam_polarization",
                    "beam_polarization_variance",
                }:
                    try:
                        values[field.name] = float(value)
                    except ValueError as exc:
                        raise PolarizationContractError(f"S4 count row {number} numeric value is invalid") from exc
                else:
                    values[field.name] = value
            parsed.append(AzimuthCountRow(**values))
    if not parsed:
        raise PolarizationContractError("S4 counts CSV is empty")
    rows = tuple(parsed)
    replicas = tuple(sorted({row.replica_id for row in rows}))
    groups: dict[tuple[object, ...], list[AzimuthCountRow]] = {}
    for row in rows:
        key = (
            row.analysis_version, row.fit_release_id, row.bin_set_id,
            row.channel, row.target, row.beam_group, row.source_period,
            row.Egamma_low, row.Egamma_high, row.cos_theta_low,
            row.cos_theta_high, row.observable, row.selection_id, row.orientation,
        )
        groups.setdefault(key, []).append(row)
    expected = []
    for group, members in groups.items():
        first = members[0]
        mass_edges = tuple(
            [next(row.reco_mass_low_gev for row in members if row.reco_mass_bin == i)
             for i in range(max(row.reco_mass_bin for row in members) + 1)]
            + [next(row.reco_mass_high_gev for row in members if row.reco_mass_bin == max(item.reco_mass_bin for item in members))]
        )
        phi_edges = tuple(
            [next(row.reco_phi_low for row in members if row.reco_phi_bin == i)
             for i in range(max(row.reco_phi_bin for row in members) + 1)]
            + [next(row.reco_phi_high for row in members if row.reco_phi_bin == max(item.reco_phi_bin for item in members))]
        )
        key = ResponseKey(
            first.channel, first.target, first.beam_group, first.Egamma_low,
            first.Egamma_high, first.cos_theta_low, first.cos_theta_high,
            first.observable, first.selection_id,
        )
        expected.append(
            ExpectedRecoGrid(
                first.analysis_version, first.fit_release_id, first.bin_set_id,
                key, first.source_period, first.orientation, mass_edges, phi_edges,
            )
        )
    expected.sort(key=lambda item: (
        1,
        item.analysis_version,
        item.fit_release_id,
        item.bin_set_id,
        item.response_key.channel,
        item.response_key.target,
        item.response_key.beam_group,
        item.source_period,
        item.response_key.Egamma_low,
        item.response_key.Egamma_high,
        item.response_key.cos_theta_low,
        item.response_key.cos_theta_high,
        item.response_key.observable,
        item.response_key.selection_id,
        item.orientation,
    ))
    return AzimuthCountTable(rows, tuple(expected), replicas)


def _validate_fit_payload(raw: object) -> JointSigmaFitResult:
    required = {
        "bin_keys", "nuisance_keys", "row_keys", "sigma", "log_yield",
        "hessian_covariance", "expected", "residuals", "deviance_contributions",
        "deviance", "ndof", "converged", "rank", "replica_id",
    }
    if not isinstance(raw, Mapping) or set(raw) != required:
        raise PolarizationContractError("S4 nominal fit record is invalid")
    bin_keys = tuple(raw["bin_keys"]) if isinstance(raw["bin_keys"], list) else ()
    nuisance = tuple(raw["nuisance_keys"]) if isinstance(raw["nuisance_keys"], list) else ()
    row_keys = tuple(raw["row_keys"]) if isinstance(raw["row_keys"], list) else ()
    if not bin_keys or len(set(bin_keys)) != len(bin_keys) or any(not isinstance(x, str) or not x for x in (*bin_keys, *nuisance, *row_keys)):
        raise PolarizationContractError("S4 nominal fit keys are invalid")
    dimension = len(bin_keys)
    sigma = _json_array(raw["sigma"], "S4 Sigma", ndim=1)
    log_yield = _json_array(raw["log_yield"], "S4 nuisance", ndim=1)
    expected = _json_array(raw["expected"], "S4 expected counts", ndim=1)
    residuals = _json_array(raw["residuals"], "S4 residuals", ndim=1)
    contributions = _json_array(raw["deviance_contributions"], "S4 deviance", ndim=1)
    if sigma.shape != (dimension,) or log_yield.shape != (dimension,) or len(nuisance) != dimension or expected.shape != residuals.shape or expected.shape != contributions.shape or len(row_keys) != expected.size:
        raise PolarizationContractError("S4 nominal fit array alignment is invalid")
    covariance = _psd(raw["hessian_covariance"], dimension, "S4 Hessian covariance")
    deviance = _finite(raw["deviance"], "S4 deviance")
    if not math.isclose(deviance, float(np.sum(contributions)), rel_tol=1e-12, abs_tol=1e-12):
        raise PolarizationContractError("S4 deviance does not equal contributions")
    if raw["converged"] is not True or raw["replica_id"] != 0:
        raise PolarizationContractError("S4 nominal fit is not converged nominal result")
    return JointSigmaFitResult(
        bin_keys, nuisance, row_keys, _readonly(sigma), _readonly(log_yield),
        covariance, _readonly(expected), _readonly(residuals),
        _readonly(contributions), deviance, _integer(raw["ndof"], "S4 ndof", minimum=1),
        True, _integer(raw["rank"], "S4 rank", minimum=1), 0,
    )


def _validate_response_payload(raw: object, dimension: int) -> ResponsePropagationResult:
    if not isinstance(raw, Mapping) or set(raw) != {"covariance", "retained_modes", "refits", "valid"} or raw["valid"] is not True:
        raise PolarizationContractError("S4 response propagation record is invalid")
    covariance = _psd(raw["covariance"], dimension, "S4 response covariance")
    modes = tuple(raw["retained_modes"]) if isinstance(raw["retained_modes"], list) else ()
    records = raw["refits"] if isinstance(raw["refits"], list) else None
    if records is None or len(records) != len(modes) or len(set(modes)) != len(modes):
        raise PolarizationContractError("S4 retained response modes are invalid")
    refits = []
    for index, item in enumerate(records):
        required = {"mode_id", "eigenvalue", "step", "scheme", "derivative", "lower_sigma", "upper_sigma"}
        if not isinstance(item, Mapping) or set(item) != required or item.get("mode_id") != modes[index] or item.get("scheme") not in {"central", "forward", "backward"}:
            raise PolarizationContractError("S4 response refit record is invalid")
        derivative = _json_array(item["derivative"], "response derivative", ndim=1)
        if derivative.shape != (dimension,):
            raise PolarizationContractError("S4 response derivative shape is invalid")
        endpoints = []
        for label in ("lower_sigma", "upper_sigma"):
            value = item[label]
            if value is None:
                endpoints.append(None)
            else:
                array = _json_array(value, f"response {label}", ndim=1)
                if array.shape != (dimension,):
                    raise PolarizationContractError("S4 response endpoint shape is invalid")
                endpoints.append(_readonly(array))
        refits.append(ResponseModeRefit(
            modes[index], _finite(item["eigenvalue"], "response eigenvalue"),
            _finite(item["step"], "response step"), item["scheme"],
            _readonly(derivative), endpoints[0], endpoints[1],
        ))
    return ResponsePropagationResult(covariance, modes, tuple(refits), True)


def validate_fit_evidence(
    directory: Path,
    root: Path,
    *,
    config: AnalysisConfig,
    _allow_staging: bool = False,
) -> FitEvidence:
    """Independently parse and bind one exact S4 triplet."""
    repository = Path(root).resolve(strict=True)
    candidate = Path(directory)
    if candidate.is_symlink() or not candidate.is_dir():
        raise PolarizationContractError("S4 evidence directory must be regular and non-symlink")
    resolved = candidate.resolve(strict=True)
    try:
        relative = resolved.relative_to(repository).as_posix()
    except ValueError as exc:
        raise PolarizationContractError("S4 evidence must stay inside repository") from exc
    if not _allow_staging:
        expected = f"{_FIT_PARENT}/{resolved.name}"
        if relative != expected:
            raise PolarizationContractError("S4 evidence directory is not canonical")
    if {item.name for item in resolved.iterdir()} != FIT_EVIDENCE_FILENAMES or any(item.is_symlink() or not item.is_file() for item in resolved.iterdir()):
        raise PolarizationContractError("S4 evidence directory must contain exact triplet")
    qa = load_json(resolved / "sigma_fit_qa.json")
    if set(qa) != _QA_KEYS or qa.get("schema_version") != 1 or qa.get("analysis_version") != "polarization-v1" or qa.get("valid") is not True or qa.get("blocked_reasons") != []:
        raise PolarizationContractError("S4 QA top-level contract is invalid")
    release_id = _release_id(qa.get("fit_release_id"))
    if not _allow_staging and release_id != resolved.name:
        raise PolarizationContractError("S4 directory and fit_release_id disagree")
    if COMMIT_PATTERN.fullmatch(str(qa.get("producer_commit", ""))) is None:
        raise PolarizationContractError("S4 producer_commit is invalid")
    for key, filename in (("counts", "azimuth_counts_v1.csv"), ("fit", "sigma_fit_v1.csv")):
        record = qa.get(key)
        if not isinstance(record, Mapping) or set(record) != _FILE_KEYS or record.get("path") != filename or sha256_file(resolved / filename) != _digest(record.get("sha256"), f"S4 {key} SHA-256"):
            raise PolarizationContractError(f"S4 {key} record is invalid")
    authorities = qa.get("authorities")
    if not isinstance(authorities, Mapping) or set(authorities) != _AUTHORITY_KEYS or authorities.get("n2_source_kind") != "N2_metadata_reconstruction" or str(authorities.get("n2_source_kind", "")).startswith("N4"):
        raise PolarizationContractError("S4 requires N2 metadata reconstruction provenance")
    config_relative, config_path, config_sha = _validate_file_record(repository, authorities["config"], "S4 config")
    loaded_config = load_analysis_config(config_path, repository, require_approved=True)
    if loaded_config != config or config.analysis_version != qa["analysis_version"]:
        raise PolarizationContractError("S4 config authority disagrees with requested config")
    authority_records = {}
    for key in ("gate0_handoff", "n2_inventory", "acceptance_qa", "phi_response", "phi_response_schema", "state_mapping", "flux"):
        authority_records[key] = _validate_file_record(
            repository, authorities[key], f"S4 {key}"
        )
    if authorities.get("acceptance_release_id") != config.acceptance_release_id or authorities.get("phi_response_schema_approval_id") != config.phi_response_schema_approval_id:
        raise PolarizationContractError("S4 N3 authority identity disagrees with config")
    compton = authorities.get("compton_sources")
    if not isinstance(compton, list) or not compton:
        raise PolarizationContractError("S4 Compton authority list is invalid")
    periods = []
    for record in compton:
        if not isinstance(record, Mapping) or set(record) != {"source_period", "path", "sha256"}:
            raise PolarizationContractError("S4 Compton authority record is invalid")
        periods.append(_text(record["source_period"], "S4 source_period"))
        _validate_file_record(repository, {"path": record["path"], "sha256": record["sha256"]}, "S4 Compton source")
    if periods != sorted(periods) or len(set(periods)) != len(periods):
        raise PolarizationContractError("S4 Compton authorities are not canonical")
    n2_inventory = load_json(authority_records["n2_inventory"][1])
    if n2_inventory.get("artifact_kind") != "n2_metadata_reconstruction":
        raise PolarizationContractError(
            "S4 requires authenticated N2 metadata reconstruction inventory"
        )
    fresh_authority = load_count_authority(
        repository_root=repository,
        config_path=config_relative,
        gate0_handoff_path=authority_records["gate0_handoff"][0],
        n2_inventory_path=authority_records["n2_inventory"][0],
        acceptance_handoff_path=authority_records["acceptance_qa"][0],
        fit_release_id=release_id,
        bin_set_id=_text(qa.get("bin_set_id"), "S4 bin_set_id"),
    )
    if _authority_payload(fresh_authority) != authorities:
        raise PolarizationContractError(
            "S4 serialized authorities disagree with authenticated source graph"
        )
    counts = _parse_counts(resolved / "azimuth_counts_v1.csv")
    _validate_table_for_publication(counts, fresh_authority)
    if {row.fit_release_id for row in counts.rows} != {release_id} or {row.analysis_version for row in counts.rows} != {qa["analysis_version"]} or {row.config_sha256 for row in counts.rows} != {config_sha}:
        raise PolarizationContractError("S4 counts provenance disagrees with QA")
    nominal = _validate_fit_payload(qa.get("nominal_fit"))
    expected_bin_keys = tuple(
        _sigma_bin_key(key, mass_bin)
        for key in fresh_authority.response.keys
        for mass_bin in range(len(fresh_authority.response.mass_edges[key]) - 1)
    )
    if nominal.bin_keys != expected_bin_keys:
        raise PolarizationContractError("S4 nominal bin keys are not canonical")
    bootstrap = qa.get("bootstrap")
    expected_bootstrap_keys = {"algorithm_version", "seed", "configured_replicas", "successful_replica_ids", "failed_replica_ids", "statistical_covariance", "sigma_vectors", "hessian_diagonal_ratio"}
    if not isinstance(bootstrap, Mapping) or set(bootstrap) != expected_bootstrap_keys or bootstrap.get("algorithm_version") != config.bootstrap.algorithm_version or bootstrap.get("seed") != config.bootstrap.seed or bootstrap.get("configured_replicas") != config.bootstrap.replicas:
        raise PolarizationContractError("S4 bootstrap authority is invalid")
    successful = tuple(bootstrap["successful_replica_ids"]) if isinstance(bootstrap["successful_replica_ids"], list) else ()
    failed = tuple(bootstrap["failed_replica_ids"]) if isinstance(bootstrap["failed_replica_ids"], list) else ()
    if (
        any(type(item) is not int for item in (*successful, *failed))
        or successful != tuple(sorted(successful))
        or failed != tuple(sorted(failed))
        or set((*successful, *failed)) != set(range(1, config.bootstrap.replicas + 1))
        or set(successful) & set(failed)
        or len(failed) / config.bootstrap.replicas > config.bootstrap.maximum_failed_fraction
        or len(successful) <= len(nominal.bin_keys)
    ):
        raise PolarizationContractError("S4 bootstrap replica coverage is invalid")
    stat = _psd(bootstrap["statistical_covariance"], len(nominal.bin_keys), "S4 statistical covariance")
    if np.any(np.diag(stat) <= 0.0) or np.linalg.matrix_rank(stat) != len(nominal.bin_keys):
        raise PolarizationContractError("S4 statistical covariance has insufficient rank")
    vectors = _json_array(
        bootstrap["sigma_vectors"], "S4 bootstrap Sigma vectors", ndim=2
    )
    if vectors.shape != (len(successful), len(nominal.bin_keys)):
        raise PolarizationContractError("S4 bootstrap Sigma vectors are misaligned")
    replay_stat = np.atleast_2d(np.cov(vectors, rowvar=False, ddof=1))
    if not np.allclose(
        replay_stat,
        stat,
        rtol=config.response_validation.replay_relative_tolerance,
        atol=config.response_validation.replay_absolute_tolerance,
    ):
        raise PolarizationContractError(
            "S4 statistical covariance disagrees with bootstrap Sigma vectors"
        )
    ratio = _json_array(bootstrap["hessian_diagonal_ratio"], "S4 Hessian ratio", ndim=1)
    expected_ratio = np.diag(nominal.hessian_covariance) / np.diag(stat)
    if (
        ratio.shape != expected_ratio.shape
        or not np.allclose(ratio, expected_ratio, rtol=1e-12, atol=1e-12)
        or np.any(ratio < config.bootstrap.hessian_diagonal_ratio_min)
        or np.any(ratio > config.bootstrap.hessian_diagonal_ratio_max)
    ):
        raise PolarizationContractError("S4 Hessian/bootstrap diagnostic disagrees")
    response = _validate_response_payload(qa.get("response_propagation"), len(nominal.bin_keys))
    reconstructed_response = np.zeros_like(response.covariance)
    for refit in response.refits:
        if refit.eigenvalue <= 0.0 or refit.step <= 0.0:
            raise PolarizationContractError("S4 response refit scale is invalid")
        if (
            (refit.scheme == "central" and (refit.lower_sigma is None or refit.upper_sigma is None))
            or (refit.scheme == "forward" and (refit.lower_sigma is not None or refit.upper_sigma is None))
            or (refit.scheme == "backward" and (refit.lower_sigma is None or refit.upper_sigma is not None))
        ):
            raise PolarizationContractError("S4 response refit endpoints disagree with scheme")
        reconstructed_response += refit.eigenvalue * np.outer(
            refit.derivative, refit.derivative
        )
    response_tolerance = config.response_validation.replay_absolute_tolerance
    response_relative = config.response_validation.replay_relative_tolerance
    if not np.allclose(
        reconstructed_response,
        response.covariance,
        rtol=response_relative,
        atol=response_tolerance,
    ):
        raise PolarizationContractError("S4 response covariance disagrees with retained modes")
    nominal_rows = tuple(
        sorted(
            (row for row in counts.rows if row.replica_id == 0),
            key=_fit_row_order,
        )
    )
    if nominal.row_keys != tuple(canonical_count_row_key(row) for row in nominal_rows):
        raise PolarizationContractError("S4 nominal row keys disagree with counts")
    observed = np.asarray([row.observed_count for row in nominal_rows], dtype=float)
    if (
        nominal.expected.size != observed.size
        or np.any(nominal.expected <= 0.0)
        or nominal.ndof != observed.size - 2 * len(nominal.bin_keys)
        or nominal.rank != 2 * len(nominal.bin_keys)
        or nominal.nuisance_keys
        != tuple(f"{key}|log_yield" for key in nominal.bin_keys)
    ):
        raise PolarizationContractError("S4 nominal fit dimensions disagree with model")
    residuals = (observed - nominal.expected) / np.sqrt(nominal.expected)
    contributions = 2.0 * (
        xlogy(observed, observed / nominal.expected)
        - (observed - nominal.expected)
    )
    replay_atol = config.response_validation.replay_absolute_tolerance
    replay_rtol = config.response_validation.replay_relative_tolerance
    if not np.allclose(nominal.residuals, residuals, rtol=replay_rtol, atol=replay_atol) or not np.allclose(nominal.deviance_contributions, contributions, rtol=replay_rtol, atol=replay_atol):
        raise PolarizationContractError("S4 nominal residual/deviance evidence disagrees with counts")
    optimizer = qa.get("optimizer")
    if optimizer != {
        "name": "L-BFGS-B",
        "implementation": "scipy.optimize.minimize",
        "sigma_bounds": [-1.0, 1.0],
        "log_yield_bounds": [-30.0, 30.0],
        "initialization": "deterministic_least_squares_v1",
        "scipy_version": scipy.__version__,
        "options": {"ftol": 1e-12, "gtol": 1e-8, "maxiter": 2000},
        "response_finite_difference_relative_step": config.response_validation.finite_difference_relative_step,
        "response_finite_difference_absolute_step": config.response_validation.finite_difference_absolute_step,
        "replay_absolute_tolerance": config.response_validation.replay_absolute_tolerance,
        "replay_relative_tolerance": config.response_validation.replay_relative_tolerance,
    }:
        raise PolarizationContractError("S4 optimizer record is invalid")
    with (resolved / "sigma_fit_v1.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if tuple(reader.fieldnames or ()) != FIT_FIELDS:
            raise PolarizationContractError("S4 fit CSV columns are not canonical")
        fit_rows = list(reader)
    if len(fit_rows) != len(nominal.bin_keys):
        raise PolarizationContractError("S4 fit CSV row count is invalid")
    for index, row in enumerate(fit_rows):
        expected_values = (
            int(row["schema_version"]) == 1,
            row["analysis_version"] == qa["analysis_version"],
            row["fit_release_id"] == release_id,
            int(row["bin_index"]) == index,
            row["bin_key"] == nominal.bin_keys[index],
            _finite(float(row["sigma"]), "fit Sigma") == nominal.sigma[index],
            _finite(float(row["bootstrap_variance"]), "fit bootstrap variance") == stat[index, index],
            _finite(float(row["hessian_variance"]), "fit Hessian variance") == nominal.hessian_covariance[index, index],
            _finite(float(row["response_variance"]), "fit response variance") == response.covariance[index, index],
            _finite(float(row["log_yield"]), "fit nuisance") == nominal.log_yield[index],
        )
        if not all(expected_values) or not math.isclose(float(row["bootstrap_stat_uncertainty"]), math.sqrt(stat[index, index]), rel_tol=1e-15, abs_tol=0.0) or not math.isclose(float(row["hessian_stat_uncertainty"]), math.sqrt(nominal.hessian_covariance[index, index]), rel_tol=1e-15, abs_tol=0.0):
            raise PolarizationContractError("S4 fit CSV disagrees with QA arrays")
    return FitEvidence(
        resolved,
        counts,
        nominal,
        stat,
        response,
        _readonly(vectors),
        successful,
        failed,
        qa,
    )
