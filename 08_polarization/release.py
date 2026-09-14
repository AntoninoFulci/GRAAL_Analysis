"""Read-only validation of Sigma release and publication-bin mappings."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

import numpy as np

from acceptance_handoff import validate_acceptance_handoff
from analysis_config import AnalysisConfig, load_analysis_config
from compton import load_period_curves
from contracts import (
    COMMIT_PATTERN,
    SHA256_PATTERN,
    PolarizationContractError,
    _resolved_regular_file,
    load_json,
    sha256_file,
    validate_gate0_handoff,
)
from figure4_config import load_figure4_config
from fit_evidence import FitEvidence, validate_fit_evidence
from reco_inventory import load_gate0_run_numbers, load_reco_inventory
from state_mapping import load_state_mapping


CSV_FIELDS = (
    "analysis_version", "bin_key", "channel", "target", "beam_group",
    "Egamma_low", "Egamma_high", "cos_theta_low", "cos_theta_high",
    "observable", "selection_id", "mass_low_gev", "mass_high_gev", "sigma",
    "stat_uncertainty", "systematic_components_json", "validity_mask",
    "fit_id", "input_sha256", "config_sha256", "event_count",
    "fit_deviance", "fit_ndof",
)
ACCEPTANCE_KEY_FIELDS = (
    "analysis_version", "channel", "target", "beam_group", "Egamma_low",
    "Egamma_high", "cos_theta_low", "cos_theta_high", "observable",
    "selection_id",
)
ACCEPTANCE_FIELDS = ACCEPTANCE_KEY_FIELDS + (
    "n_generated", "n_thrown_in_bin", "n_reconstructed_selected",
    "acceptance", "acceptance_stat_uncertainty", "validity_mask",
    "input_sha256", "config_sha256",
)
NPZ_FIELDS = frozenset(
    {
        "bin_keys",
        "stat_covariance",
        "systematic_covariance",
        "covariance",
        "schema_version",
    }
)
OBSERVABLES = frozenset({"p_pi0", "p_eta", "eta_pi0"})


@dataclass(frozen=True)
class SigmaRelease:
    bin_keys: tuple[str, ...]
    total_covariance: np.ndarray
    qa: Mapping[str, object]
    repository_root: Path
    qa_sha256: str


@dataclass(frozen=True)
class _SigmaRows:
    bin_keys: tuple[str, ...]
    sigma: np.ndarray
    stat_uncertainties: np.ndarray
    systematic_uncertainties: np.ndarray
    analysis_version: str
    input_sha256: str
    config_sha256: str
    event_counts: np.ndarray
    deviance_per_ndof: np.ndarray
    systematic_names: frozenset[str]
    systematic_components: tuple[Mapping[str, float], ...]
    acceptance_keys: frozenset[tuple[object, ...]]


def _positive_float(raw: str, label: str) -> float:
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise PolarizationContractError(f"{label} must be numeric") from exc
    if not np.isfinite(value) or value <= 0.0:
        raise PolarizationContractError(f"{label} must be finite and positive")
    return value


def _acceptance_key(row: Mapping[str, str], label: str) -> tuple[object, ...]:
    text_values = []
    for field in (
        "analysis_version", "channel", "target", "beam_group", "observable",
        "selection_id",
    ):
        value = row.get(field)
        if not isinstance(value, str) or not value.strip():
            raise PolarizationContractError(f"{label} requires non-empty {field}")
        text_values.append(value)
    try:
        energy_low = float(row["Egamma_low"])
        energy_high = float(row["Egamma_high"])
        cos_low = float(row["cos_theta_low"])
        cos_high = float(row["cos_theta_high"])
    except (KeyError, TypeError, ValueError) as exc:
        raise PolarizationContractError(f"{label} has invalid physical bin edges") from exc
    if (
        not all(np.isfinite(value) for value in (energy_low, energy_high, cos_low, cos_high))
        or energy_low <= 0.0
        or energy_high <= energy_low
        or not -1.0 <= cos_low < cos_high <= 1.0
    ):
        raise PolarizationContractError(f"{label} has invalid physical bin edges")
    analysis, channel, target, beam_group, observable, selection = text_values
    return (
        analysis, channel, target, beam_group, energy_low, energy_high,
        cos_low, cos_high, observable, selection,
    )


def _read_sigma_csv(path: Path) -> _SigmaRows:
    try:
        handle = path.open(newline="", encoding="utf-8")
    except OSError as exc:
        raise PolarizationContractError(f"cannot read Sigma CSV: {path}") from exc
    keys = []
    sigma_values = []
    uncertainties = []
    systematic_uncertainties = []
    fit_ids = set()
    analysis_versions = set()
    input_digests = set()
    config_digests = set()
    event_counts = []
    deviance_per_ndof = []
    systematic_name_sets = []
    systematic_components = []
    acceptance_keys = set()
    with handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != CSV_FIELDS:
            raise PolarizationContractError("Sigma CSV has wrong columns or column order")
        for row_number, row in enumerate(reader, start=2):
            key = row["bin_key"]
            if not key or key in keys:
                raise PolarizationContractError("Sigma bin_keys must be non-empty and unique")
            if row["observable"] not in OBSERVABLES:
                raise PolarizationContractError(
                    f"Sigma row {row_number} has unknown observable"
                )
            acceptance_keys.add(_acceptance_key(row, f"Sigma row {row_number}"))
            energy_low = _positive_float(row["Egamma_low"], "Egamma_low")
            energy_high = _positive_float(row["Egamma_high"], "Egamma_high")
            mass_low = _positive_float(row["mass_low_gev"], "mass_low_gev")
            mass_high = _positive_float(row["mass_high_gev"], "mass_high_gev")
            if energy_high <= energy_low or mass_high <= mass_low:
                raise PolarizationContractError("Sigma bins must have positive width")
            try:
                sigma = float(row["sigma"])
                deviance = float(row["fit_deviance"])
                ndof = int(row["fit_ndof"])
                event_count = int(row["event_count"])
            except (TypeError, ValueError) as exc:
                raise PolarizationContractError(
                    f"Sigma row {row_number} has invalid fit values"
                ) from exc
            uncertainty = _positive_float(
                row["stat_uncertainty"], "stat_uncertainty"
            )
            if not np.isfinite(sigma) or not -1.0 <= sigma <= 1.0:
                raise PolarizationContractError("released Sigma must lie in [-1, 1]")
            if not np.isfinite(deviance) or deviance < 0.0 or ndof <= 0:
                raise PolarizationContractError("released fit QA must be finite and valid")
            if event_count <= 0:
                raise PolarizationContractError("released event_count must be positive")
            if row["validity_mask"] != "valid":
                raise PolarizationContractError("Sigma release cannot contain invalid rows")
            if not row["analysis_version"]:
                raise PolarizationContractError("Sigma rows require analysis_version")
            analysis_versions.add(row["analysis_version"])
            fit_id = row["fit_id"]
            if not fit_id or fit_id in fit_ids:
                raise PolarizationContractError("Sigma fit_id values must be unique")
            fit_ids.add(fit_id)
            for digest_name in ("input_sha256", "config_sha256"):
                if SHA256_PATTERN.fullmatch(row[digest_name]) is None:
                    raise PolarizationContractError(
                        f"Sigma {digest_name} must be lowercase SHA-256"
                    )
            input_digests.add(row["input_sha256"])
            config_digests.add(row["config_sha256"])
            try:
                components = json.loads(row["systematic_components_json"])
            except json.JSONDecodeError as exc:
                raise PolarizationContractError(
                    "systematic_components_json must be valid JSON"
                ) from exc
            if not isinstance(components, dict) or not components:
                raise PolarizationContractError(
                    "systematic_components_json must be a non-empty object"
                )
            values = []
            for name, raw_value in components.items():
                if not isinstance(name, str) or not name:
                    raise PolarizationContractError("systematic component names must be non-empty")
                if isinstance(raw_value, bool) or not isinstance(raw_value, (int, float)):
                    raise PolarizationContractError("systematic components must be numeric")
                value = float(raw_value)
                if not np.isfinite(value) or value < 0.0:
                    raise PolarizationContractError(
                        "systematic components must be finite and non-negative"
                    )
                values.append(value)
            systematic_name_sets.append(frozenset(components))
            systematic_components.append(
                {name: float(value) for name, value in components.items()}
            )
            keys.append(key)
            sigma_values.append(sigma)
            uncertainties.append(uncertainty)
            systematic_uncertainties.append(float(np.linalg.norm(values)))
            event_counts.append(event_count)
            deviance_per_ndof.append(deviance / ndof)
    if not keys:
        raise PolarizationContractError("Sigma release contains no bins")
    if len(analysis_versions) != 1 or len(input_digests) != 1 or len(config_digests) != 1:
        raise PolarizationContractError(
            "Sigma rows must share analysis_version, input_sha256, and config_sha256"
        )
    if len(set(systematic_name_sets)) != 1:
        raise PolarizationContractError(
            "Sigma rows must declare the same systematic components"
        )
    return _SigmaRows(
        tuple(keys),
        np.asarray(sigma_values, dtype=float),
        np.asarray(uncertainties, dtype=float),
        np.asarray(systematic_uncertainties, dtype=float),
        analysis_versions.pop(),
        input_digests.pop(),
        config_digests.pop(),
        np.asarray(event_counts, dtype=int),
        np.asarray(deviance_per_ndof, dtype=float),
        systematic_name_sets[0],
        tuple(systematic_components),
        frozenset(acceptance_keys),
    )


def _readonly(raw: object) -> np.ndarray:
    array = np.asarray(raw, dtype=float)
    return np.frombuffer(array.tobytes(), dtype=array.dtype).reshape(array.shape)


def _deep_freeze(raw: object) -> object:
    if isinstance(raw, Mapping):
        return MappingProxyType(
            {key: _deep_freeze(value) for key, value in raw.items()}
        )
    if isinstance(raw, (list, tuple)):
        return tuple(_deep_freeze(value) for value in raw)
    return raw


def _covariance(raw, size: int, label: str) -> np.ndarray:
    matrix = np.asarray(raw, dtype=float)
    if matrix.shape != (size, size) or not np.all(np.isfinite(matrix)):
        raise PolarizationContractError(
            f"{label} covariance must be finite with shape {(size, size)}"
        )
    if not np.allclose(matrix, matrix.T, rtol=1e-12, atol=1e-14):
        raise PolarizationContractError(f"{label} covariance must be symmetric")
    scale = max(1.0, float(np.max(np.abs(matrix))))
    if float(np.min(np.linalg.eigvalsh(matrix))) < -1e-12 * scale:
        raise PolarizationContractError(
            f"{label} covariance must be positive semidefinite"
        )
    return matrix


def _required_digest(payload: Mapping[str, object], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or SHA256_PATTERN.fullmatch(value) is None:
        raise PolarizationContractError(f"QA {key} must be lowercase SHA-256")
    return value


def _finite_number(payload: Mapping[str, object], key: str, label: str) -> float:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PolarizationContractError(f"{label} {key} must be numeric")
    number = float(value)
    if not np.isfinite(number):
        raise PolarizationContractError(f"{label} {key} must be finite")
    return number


def _validate_file_record(
    record: object,
    repository_root: Path,
    label: str,
    *,
    canonical_path: str | None = None,
) -> tuple[Path, str]:
    if not isinstance(record, Mapping):
        raise PolarizationContractError(f"QA {label} must be a file record")
    raw_path = record.get("path")
    if canonical_path is not None and raw_path != canonical_path:
        raise PolarizationContractError(f"QA {label} path must be {canonical_path}")
    path = _resolved_regular_file(repository_root, raw_path, f"QA {label}")
    digest = record.get("sha256")
    if not isinstance(digest, str) or SHA256_PATTERN.fullmatch(digest) is None:
        raise PolarizationContractError(f"QA {label} requires lowercase SHA-256")
    if sha256_file(path) != digest:
        raise PolarizationContractError(f"QA {label} SHA-256 mismatch")
    return path, digest


def _input_digest(records: list[tuple[str, str]]) -> str:
    encoded = json.dumps(records, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _validate_acceptance_csv(
    path: Path, required_keys: frozenset[tuple[object, ...]]
) -> tuple[str, str]:
    try:
        handle = path.open(newline="", encoding="utf-8")
    except OSError as exc:
        raise PolarizationContractError(f"cannot read acceptance CSV: {path}") from exc
    valid_keys = set()
    seen_keys = set()
    input_digests = set()
    config_digests = set()
    with handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != ACCEPTANCE_FIELDS:
            raise PolarizationContractError("acceptance CSV has wrong N1 handoff columns")
        for row_number, row in enumerate(reader, start=2):
            key = _acceptance_key(row, f"acceptance row {row_number}")
            if key in seen_keys:
                raise PolarizationContractError("acceptance physical keys must be unique")
            seen_keys.add(key)
            try:
                n_generated = int(row["n_generated"])
                n_thrown = int(row["n_thrown_in_bin"])
                n_reconstructed = int(row["n_reconstructed_selected"])
            except (TypeError, ValueError) as exc:
                raise PolarizationContractError(
                    f"acceptance row {row_number} has non-numeric denominators"
                ) from exc
            if (
                min(n_generated, n_thrown, n_reconstructed) < 0
                or n_reconstructed > n_thrown
                or n_thrown > n_generated
            ):
                raise PolarizationContractError(
                    f"acceptance row {row_number} has inconsistent denominators"
                )
            mask = row["validity_mask"]
            if mask not in {"valid", "invalid"}:
                raise PolarizationContractError(
                    f"acceptance row {row_number} has unknown validity_mask"
                )
            if mask == "valid":
                try:
                    acceptance = float(row["acceptance"])
                    uncertainty = float(row["acceptance_stat_uncertainty"])
                except (TypeError, ValueError) as exc:
                    raise PolarizationContractError(
                        f"acceptance row {row_number} has non-numeric values"
                    ) from exc
                if (
                    n_thrown == 0
                    or not np.isfinite(acceptance)
                    or not 0.0 < acceptance <= 1.0
                    or not np.isfinite(uncertainty)
                    or uncertainty < 0.0
                    or not np.isclose(
                        acceptance, n_reconstructed / n_thrown,
                        rtol=1e-10, atol=1e-14,
                    )
                ):
                    raise PolarizationContractError(
                        f"acceptance row {row_number} has invalid values"
                    )
                valid_keys.add(key)
            else:
                for field in ("acceptance", "acceptance_stat_uncertainty"):
                    raw = row[field]
                    if raw == "":
                        continue
                    try:
                        value = float(raw)
                    except (TypeError, ValueError) as exc:
                        raise PolarizationContractError(
                            f"masked acceptance row {row_number} has invalid {field}"
                        ) from exc
                    if not np.isfinite(value) or value < 0.0:
                        raise PolarizationContractError(
                            f"masked acceptance row {row_number} has invalid {field}"
                        )
            if any(
                SHA256_PATTERN.fullmatch(row[name]) is None
                for name in ("input_sha256", "config_sha256")
            ):
                raise PolarizationContractError(
                    f"acceptance row {row_number} has invalid provenance hash"
                )
            input_digests.add(row["input_sha256"])
            config_digests.add(row["config_sha256"])
    missing = set(required_keys) - valid_keys
    if missing:
        raise PolarizationContractError(
            f"acceptance handoff lacks valid rows for {len(missing)} Sigma bins"
        )
    if len(input_digests) != 1 or len(config_digests) != 1:
        raise PolarizationContractError(
            "acceptance rows must share input_sha256 and config_sha256"
        )
    return input_digests.pop(), config_digests.pop()


def _validate_inputs(
    qa: Mapping[str, object], repository_root: Path,
    required_acceptance_keys: frozenset[tuple[object, ...]],
) -> tuple[str, str, str, str, dict[str, object]]:
    inputs = qa.get("inputs")
    required = {
        "config", "gate0_handoff", "acceptance_csv",
        "acceptance_phi_response_csv", "acceptance_qa",
        "reconstruction_inventory", "state_mapping_sources", "compton_sources",
    }
    if not isinstance(inputs, Mapping) or set(inputs) != required:
        raise PolarizationContractError("polarization QA has incomplete input records")
    config_path, config_digest = _validate_file_record(
        inputs["config"], repository_root, "config",
        canonical_path="config/physics/polarization_v1.json",
    )
    analysis_config = load_analysis_config(
        config_path, repository_root, require_approved=True
    )
    gate0_path, gate0_digest = _validate_file_record(
        inputs["gate0_handoff"], repository_root, "gate0_handoff",
        canonical_path="results/observable_runs/HANDOFF.json",
    )
    validate_gate0_handoff(gate0_path, repository_root)
    acceptance_csv, acceptance_csv_digest = _validate_file_record(
        inputs["acceptance_csv"], repository_root, "acceptance_csv",
    )
    acceptance_response, acceptance_response_digest = _validate_file_record(
        inputs["acceptance_phi_response_csv"], repository_root,
        "acceptance_phi_response_csv",
    )
    acceptance_qa_path, acceptance_qa_digest = _validate_file_record(
        inputs["acceptance_qa"], repository_root, "acceptance_qa",
    )
    reconstruction_path, reconstruction_digest = _validate_file_record(
        inputs["reconstruction_inventory"], repository_root,
        "reconstruction_inventory",
    )
    handoff = validate_acceptance_handoff(
        acceptance_qa_path.parent,
        repository_root,
        config=analysis_config,
        expected_gate0_sha256=gate0_digest,
    )
    if (
        acceptance_csv != handoff.acceptance_csv
        or acceptance_response != handoff.phi_response_csv
        or acceptance_qa_path != handoff.qa_json
        or acceptance_csv_digest != handoff.acceptance_sha256
        or acceptance_response_digest != handoff.phi_response_sha256
        or acceptance_qa_digest != handoff.qa_sha256
    ):
        raise PolarizationContractError(
            "acceptance input records disagree with immutable handoff"
        )
    if reconstruction_digest != handoff.n2_reconstruction_sha256:
        raise PolarizationContractError(
            "acceptance handoff is bound to a different N2 reconstruction"
        )
    acceptance_qa = handoff.qa
    acceptance_input_digest, acceptance_config_digest = _validate_acceptance_csv(
        acceptance_csv, required_acceptance_keys
    )
    if (
        acceptance_qa.get("input_sha256") != acceptance_input_digest
        or acceptance_qa.get("config_sha256") != acceptance_config_digest
    ):
        raise PolarizationContractError(
            "acceptance row provenance hashes disagree with acceptance QA"
        )
    digest_records = [
        ("gate0_handoff", gate0_digest),
        ("acceptance_csv", acceptance_csv_digest),
        ("acceptance_phi_response_csv", acceptance_response_digest),
        ("acceptance_qa", acceptance_qa_digest),
        ("reconstruction_inventory", reconstruction_digest),
    ]
    for collection_name in ("state_mapping_sources", "compton_sources"):
        collection = inputs[collection_name]
        if not isinstance(collection, list) or not collection:
            raise PolarizationContractError(f"QA {collection_name} must be non-empty")
        for index, record in enumerate(collection):
            _, digest = _validate_file_record(
                record, repository_root, f"{collection_name}[{index}]"
            )
            digest_records.append((collection_name, digest))
    config = load_json(config_path)
    acceptance_config = config.get("acceptance")
    expected_acceptance_directory = handoff.directory.relative_to(
        Path(repository_root).resolve()
    ).as_posix()
    if (
        not isinstance(acceptance_config, Mapping)
        or acceptance_config.get("status") != "approved"
        or acceptance_config.get("release_id") != handoff.release_id
        or acceptance_config.get("handoff_directory")
        != expected_acceptance_directory
    ):
        raise PolarizationContractError(
            "acceptance handoff disagrees with approved canonical config"
        )
    phi_response_reviewers = acceptance_config.get(
        "phi_response_schema_reviewers"
    )
    normalized_phi_response_reviewers = {
        reviewer.strip()
        for reviewer in phi_response_reviewers or []
        if isinstance(reviewer, str) and reviewer.strip()
    }
    phi_response_approval_id = acceptance_config.get(
        "phi_response_schema_approval_id"
    )
    if (
        acceptance_config.get("phi_response_schema_status") != "approved"
        or not isinstance(phi_response_approval_id, str)
        or not phi_response_approval_id.strip()
        or len(normalized_phi_response_reviewers) < 2
    ):
        raise PolarizationContractError(
            "phi-response schema approval requires id and two reviewers"
        )
    if phi_response_approval_id != handoff.phi_response_schema_approval_id:
        raise PolarizationContractError(
            "acceptance QA phi-response schema approval ID disagrees with config"
        )
    load_state_mapping(config_path, repository_root)
    load_period_curves(config_path, repository_root)
    layout = load_figure4_config(config_path)
    state_section = config.get("state_mapping")
    configured_state = state_section.get("source") if isinstance(state_section, Mapping) else None
    expected_state = [] if configured_state is None else [
        {"path": configured_state.get("path"), "sha256": configured_state.get("sha256")}
    ]
    if inputs["state_mapping_sources"] != expected_state:
        raise PolarizationContractError(
            "state mapping source records disagree with canonical config"
        )
    compton_section = config.get("compton_polarization")
    periods = compton_section.get("periods") if isinstance(compton_section, Mapping) else None
    if not isinstance(periods, list):
        raise PolarizationContractError("canonical config lacks Compton periods")
    expected_compton = []
    for period in periods:
        source = period.get("source") if isinstance(period, Mapping) else None
        if not isinstance(source, Mapping):
            raise PolarizationContractError("canonical config has invalid Compton source")
        expected_compton.append(
            {"path": source.get("path"), "sha256": source.get("sha256")}
        )
    if inputs["compton_sources"] != expected_compton:
        raise PolarizationContractError(
            "Compton source records disagree with canonical config"
        )
    gate0_runs = load_gate0_run_numbers(
        repository_root / "results/observable_runs/run_manifest_observables.csv",
        target=layout.target,
    )
    load_reco_inventory(
        reconstruction_path,
        repository_root,
        expected_handoff_sha256=gate0_digest,
        expected_tree=layout.tree,
        expected_vectors=layout.vectors,
        expected_run_numbers=gate0_runs,
    )
    return (
        config_digest,
        gate0_digest,
        _input_digest(digest_records),
        acceptance_response_digest,
        config,
    )


def _replay_fit_evidence(
    qa: Mapping[str, object],
    repository_root: Path,
    *,
    config_path: Path,
) -> tuple[FitEvidence, AnalysisConfig]:
    pin = qa.get("fit_evidence")
    required = {"fit_release_id", "path", "qa_sha256"}
    if not isinstance(pin, Mapping) or set(pin) != required:
        raise PolarizationContractError(
            "polarization QA must pin one exact S4 evidence triplet"
        )
    release_id = pin.get("fit_release_id")
    if not isinstance(release_id, str) or not release_id:
        raise PolarizationContractError("S4 fit_release_id is invalid")
    expected_path = f"results/physics/polarization_fits/{release_id}"
    if pin.get("path") != expected_path:
        raise PolarizationContractError("S4 evidence path is not canonical")
    expected_qa_sha256 = _required_digest(pin, "qa_sha256")
    directory = repository_root / expected_path
    config = load_analysis_config(
        config_path, repository_root, require_approved=True
    )
    evidence = validate_fit_evidence(
        directory, repository_root, config=config
    )
    if evidence.qa.get("fit_release_id") != release_id:
        raise PolarizationContractError("S4 fit_release_id disagrees with pin")
    actual_qa_sha256 = sha256_file(directory / "sigma_fit_qa.json")
    if actual_qa_sha256 != expected_qa_sha256:
        raise PolarizationContractError("S4 evidence QA SHA-256 mismatch")
    return evidence, config


def _validate_replayed_release(
    qa: Mapping[str, object],
    rows: _SigmaRows,
    statistical: np.ndarray,
    systematic: np.ndarray,
    evidence: FitEvidence,
    config: AnalysisConfig,
) -> None:
    atol = config.response_validation.replay_absolute_tolerance
    rtol = config.response_validation.replay_relative_tolerance
    nominal = evidence.nominal_fit
    if rows.bin_keys != nominal.bin_keys:
        raise PolarizationContractError("S6 bin order disagrees with replayed S4")
    if not np.allclose(rows.sigma, nominal.sigma, rtol=rtol, atol=atol):
        raise PolarizationContractError("S6 Sigma disagrees with replayed S4")
    release_qa = evidence.qa.get("release_qa")
    if (
        not isinstance(release_qa, Mapping)
        or tuple(release_qa.get("event_counts", ()))
        != tuple(int(value) for value in rows.event_counts)
        or not np.allclose(
            rows.deviance_per_ndof,
            nominal.deviance / nominal.ndof,
            rtol=rtol,
            atol=atol,
        )
    ):
        raise PolarizationContractError(
            "S6 event/deviance values disagree with replayed S4"
        )
    if not np.allclose(
        statistical,
        evidence.statistical_covariance,
        rtol=rtol,
        atol=atol,
    ):
        raise PolarizationContractError(
            "S6 statistical covariance disagrees with replayed S4"
        )
    raw_covariances = qa.get("systematic_covariances")
    if not isinstance(raw_covariances, Mapping) or set(raw_covariances) != set(
        rows.systematic_names
    ):
        raise PolarizationContractError(
            "S6 named systematic covariances disagree with CSV"
        )
    named = {
        name: _covariance(raw, len(rows.bin_keys), f"systematic {name}")
        for name, raw in raw_covariances.items()
    }
    response_name = "acceptance_response_statistics"
    if response_name not in named or not np.allclose(
        named[response_name],
        evidence.response_propagation.covariance,
        rtol=rtol,
        atol=atol,
    ):
        raise PolarizationContractError(
            "S6 acceptance_response_statistics disagrees with replayed response covariance"
        )
    pin = qa["fit_evidence"]
    response_sources = [
        source
        for source in qa["systematic_sources"]
        if source.get("name") == response_name
    ]
    if len(response_sources) != 1 or response_sources[0] != {
        "name": response_name,
        "path": f"{pin['path']}/sigma_fit_qa.json",
        "sha256": pin["qa_sha256"],
    }:
        raise PolarizationContractError(
            "S6 acceptance_response_statistics source must be pinned S4 QA"
        )
    recomputed_systematic = np.zeros_like(systematic)
    for matrix in named.values():
        recomputed_systematic += matrix
    if not np.allclose(
        systematic, recomputed_systematic, rtol=rtol, atol=atol
    ):
        raise PolarizationContractError(
            "S6 systematic covariance disagrees with named source sum"
        )
    for index, components in enumerate(rows.systematic_components):
        for name, matrix in named.items():
            if not np.isclose(
                components[name],
                np.sqrt(matrix[index, index]),
                rtol=rtol,
                atol=atol,
            ):
                raise PolarizationContractError(
                    "S6 CSV systematic component disagrees with named covariance"
                )


def _validate_qa(
    qa: dict[str, object], csv_path: Path, npz_path: Path,
    repository_root: Path, rows: _SigmaRows,
    statistical: np.ndarray, systematic: np.ndarray,
) -> FitEvidence:
    if qa.get("schema_version") != 1 or qa.get("valid") is not True:
        raise PolarizationContractError("polarization QA must be schema v1 and valid")
    if not isinstance(qa.get("analysis_version"), str) or not qa["analysis_version"]:
        raise PolarizationContractError("polarization QA requires analysis_version")
    if qa["analysis_version"] != rows.analysis_version:
        raise PolarizationContractError("QA analysis_version disagrees with Sigma CSV")
    commit = qa.get("producer_commit")
    if not isinstance(commit, str) or COMMIT_PATTERN.fullmatch(commit) is None:
        raise PolarizationContractError("polarization QA requires producer Git hash")
    files = qa.get("files")
    if not isinstance(files, Mapping) or set(files) != {
        "sigma_v1.csv", "sigma_covariance.npz"
    }:
        raise PolarizationContractError("polarization QA must cross-hash release files")
    expected = {
        "sigma_v1.csv": sha256_file(csv_path),
        "sigma_covariance.npz": sha256_file(npz_path),
    }
    for name, actual in expected.items():
        digest = files.get(name)
        if not isinstance(digest, str) or digest != actual:
            raise PolarizationContractError(f"polarization QA hash mismatch for {name}")
    fit_qa = qa.get("fit_qa")
    closure = qa.get("closure")
    if not isinstance(fit_qa, Mapping) or fit_qa.get("valid") is not True:
        raise PolarizationContractError("fit QA is not valid")
    if (
        not isinstance(closure, Mapping)
        or closure.get("valid") is not True
        or closure.get("sign_check_passed") is not True
    ):
        raise PolarizationContractError("closure/sign QA is not valid")
    for key in (
        "config_sha256", "gate0_handoff_sha256", "acceptance_qa_sha256"
    ):
        _required_digest(qa, key)
    (
        config_digest,
        gate0_digest,
        input_digest,
        acceptance_response_digest,
        config,
    ) = _validate_inputs(
        qa, repository_root, rows.acceptance_keys
    )
    if (
        fit_qa.get("acceptance_phi_response_sha256")
        != acceptance_response_digest
        or fit_qa.get("response_application") != "forward_folded"
    ):
        raise PolarizationContractError(
            "fit QA does not prove approved phi-response usage"
        )
    if qa["config_sha256"] != config_digest or rows.config_sha256 != config_digest:
        raise PolarizationContractError("config SHA-256 disagrees with actual config")
    if qa["gate0_handoff_sha256"] != gate0_digest:
        raise PolarizationContractError("Gate 0 SHA-256 disagrees with actual HANDOFF")
    acceptance_record = qa["inputs"]["acceptance_qa"]
    if qa["acceptance_qa_sha256"] != acceptance_record["sha256"]:
        raise PolarizationContractError("acceptance QA SHA-256 disagrees with actual input")
    if qa.get("input_sha256") != input_digest or rows.input_sha256 != input_digest:
        raise PolarizationContractError("input SHA-256 disagrees with actual inputs")
    thresholds = qa.get("qa_thresholds")
    configured_thresholds = config.get("release_qa_thresholds")
    if (
        not isinstance(configured_thresholds, Mapping)
        or configured_thresholds.get("status") != "approved"
        or dict(configured_thresholds) != thresholds
    ):
        raise PolarizationContractError(
            "release QA threshold policy must equal approved canonical config"
        )
    if not isinstance(thresholds, Mapping) or thresholds.get("status") != "approved":
        raise PolarizationContractError("release QA thresholds are not approved")
    threshold_reviewers = thresholds.get("reviewers")
    normalized_reviewers = {
        value.strip()
        for value in threshold_reviewers or []
        if isinstance(value, str) and value.strip()
    }
    if (
        not isinstance(thresholds.get("approval_id"), str)
        or not thresholds["approval_id"]
        or len(normalized_reviewers) < 2
    ):
        raise PolarizationContractError(
            "release QA threshold approval requires id and two reviewers"
        )
    minimum_events = _finite_number(
        thresholds, "minimum_events_per_bin", "QA threshold"
    )
    maximum_deviance = _finite_number(
        thresholds, "maximum_deviance_per_ndof", "QA threshold"
    )
    maximum_bias = _finite_number(
        thresholds, "closure_bias_absolute_max", "QA threshold"
    )
    maximum_pull_mean = _finite_number(
        thresholds, "closure_pull_mean_absolute_max", "QA threshold"
    )
    pull_width_tolerance = _finite_number(
        thresholds, "closure_pull_width_tolerance", "QA threshold"
    )
    minimum_systematics = _finite_number(
        thresholds, "minimum_systematic_sources", "QA threshold"
    )
    if (
        minimum_events <= 0
        or not minimum_events.is_integer()
        or maximum_deviance <= 0
        or maximum_bias < 0
        or maximum_pull_mean < 0
        or pull_width_tolerance < 0
        or minimum_systematics < 1
        or not minimum_systematics.is_integer()
    ):
        raise PolarizationContractError("release QA thresholds have invalid ranges")
    if thresholds.get("systematic_combination_policy") != (
        "independent_sources_quadrature"
    ):
        raise PolarizationContractError(
            "systematic combination policy must declare independent-source quadrature"
        )
    if np.any(rows.event_counts < int(minimum_events)):
        raise PolarizationContractError("Sigma bin fails minimum event threshold")
    if np.any(rows.deviance_per_ndof > maximum_deviance):
        raise PolarizationContractError("Sigma bin fails deviance/ndof threshold")
    closure_bias = _finite_number(closure, "bias", "closure")
    closure_pull_mean = _finite_number(closure, "pull_mean", "closure")
    closure_pull_width = _finite_number(closure, "pull_width", "closure")
    if abs(closure_bias) > maximum_bias:
        raise PolarizationContractError("closure bias exceeds approved threshold")
    if abs(closure_pull_mean) > maximum_pull_mean:
        raise PolarizationContractError("closure pull mean exceeds approved threshold")
    if abs(closure_pull_width - 1.0) > pull_width_tolerance:
        raise PolarizationContractError("closure pull width exceeds approved tolerance")
    systematics = qa.get("systematic_sources")
    if not isinstance(systematics, list) or not systematics:
        raise PolarizationContractError("QA requires systematic_sources")
    names = set()
    for source in systematics:
        if not isinstance(source, Mapping):
            raise PolarizationContractError("systematic source must be an object")
        name = source.get("name")
        if not isinstance(name, str) or not name or name in names:
            raise PolarizationContractError("systematic source names must be unique")
        names.add(name)
        _validate_file_record(
            source, repository_root, f"systematic source {name}"
        )
    if names != set(rows.systematic_names):
        raise PolarizationContractError(
            "systematic source names disagree with Sigma CSV components"
        )
    if len(names) < int(minimum_systematics):
        raise PolarizationContractError(
            "systematic source count fails approved threshold"
        )
    config_path, _ = _validate_file_record(
        qa["inputs"]["config"], repository_root, "config",
        canonical_path="config/physics/polarization_v1.json",
    )
    evidence, analysis_config = _replay_fit_evidence(
        qa, repository_root, config_path=config_path
    )
    _validate_replayed_release(
        qa,
        rows,
        statistical,
        systematic,
        evidence,
        analysis_config,
    )
    return evidence


def validate_sigma_release(
    results_dir: Path,
    repository_root: Path,
    *,
    replay_fit: bool = True,
) -> SigmaRelease:
    """Validate immutable S6 CSV, covariance archive, and QA cross-hashes."""
    if replay_fit is not True:
        raise PolarizationContractError("S6 validation cannot disable S4 replay")
    repository = Path(repository_root).resolve()
    canonical = repository / "results/physics/polarization"
    try:
        root = Path(results_dir).resolve(strict=True)
    except FileNotFoundError as exc:
        raise PolarizationContractError("canonical Sigma release directory is missing") from exc
    if root != canonical:
        raise PolarizationContractError(
            "Sigma release must use canonical results/physics/polarization directory"
        )
    required_files = {
        "sigma_v1.csv", "sigma_covariance.npz", "polarization_qa.json"
    }
    try:
        entries = {entry.name for entry in root.iterdir()}
    except OSError as exc:
        raise PolarizationContractError("cannot inspect Sigma release directory") from exc
    if entries != required_files:
        raise PolarizationContractError(
            "Sigma release directory must contain exactly three handoff files"
        )
    csv_path = _resolved_regular_file(
        repository, "results/physics/polarization/sigma_v1.csv", "Sigma CSV"
    )
    npz_path = _resolved_regular_file(
        repository,
        "results/physics/polarization/sigma_covariance.npz",
        "Sigma covariance",
    )
    qa_path = _resolved_regular_file(
        repository,
        "results/physics/polarization/polarization_qa.json",
        "polarization QA",
    )
    rows = _read_sigma_csv(csv_path)
    keys = rows.bin_keys
    try:
        with np.load(npz_path, allow_pickle=False) as archive:
            if set(archive.files) != NPZ_FIELDS:
                raise PolarizationContractError("Sigma covariance NPZ has wrong arrays")
            schema_version = np.asarray(archive["schema_version"])
            if schema_version.shape != () or schema_version.item() != 1:
                raise PolarizationContractError(
                    "Sigma covariance NPZ schema_version must be scalar 1"
                )
            npz_keys = tuple(str(value) for value in archive["bin_keys"].tolist())
            if npz_keys != keys:
                raise PolarizationContractError("covariance bin_keys order disagrees with CSV")
            statistical = _covariance(
                archive["stat_covariance"], len(keys), "statistical"
            )
            systematic = _covariance(
                archive["systematic_covariance"], len(keys), "systematic"
            )
            total = _covariance(archive["covariance"], len(keys), "total")
    except PolarizationContractError:
        raise
    except (OSError, ValueError, KeyError) as exc:
        raise PolarizationContractError(f"cannot read covariance NPZ: {npz_path}") from exc
    if not np.allclose(
        np.diag(statistical), rows.stat_uncertainties**2, rtol=1e-10, atol=1e-14
    ):
        raise PolarizationContractError(
            "statistical covariance diagonal disagrees with CSV uncertainties"
        )
    if not np.allclose(
        np.diag(systematic),
        rows.systematic_uncertainties**2,
        rtol=1e-10,
        atol=1e-14,
    ):
        raise PolarizationContractError(
            "systematic covariance diagonal disagrees with CSV components"
        )
    if not np.allclose(total, statistical + systematic, rtol=1e-10, atol=1e-14):
        raise PolarizationContractError(
            "total covariance must equal statistical plus systematic covariance"
        )
    qa = load_json(qa_path)
    _validate_qa(
        qa, csv_path, npz_path, repository, rows, statistical, systematic
    )
    return SigmaRelease(
        keys, _readonly(total), _deep_freeze(qa), repository, sha256_file(qa_path)
    )


def validate_aggregation_mapping(
    mapping: Mapping[str, object], paper: str, release: SigmaRelease
) -> None:
    """Validate proposed P1/P2 aggregation without authorizing publication."""
    if mapping.get("schema_version") != 1 or mapping.get("paper") != paper:
        raise PolarizationContractError("publication mapping schema/paper mismatch")
    source_keys = mapping.get("source_bin_keys")
    if not isinstance(source_keys, list) or tuple(source_keys) != release.bin_keys:
        raise PolarizationContractError(
            "publication source_bin_keys must equal Sigma release order"
        )
    aggregate_keys = mapping.get("aggregate_bin_keys")
    if (
        not isinstance(aggregate_keys, list)
        or not aggregate_keys
        or any(not isinstance(key, str) or not key for key in aggregate_keys)
        or len(set(aggregate_keys)) != len(aggregate_keys)
    ):
        raise PolarizationContractError("aggregate_bin_keys must be unique and non-empty")
    try:
        weights = np.asarray(mapping.get("weights"), dtype=float)
    except (TypeError, ValueError) as exc:
        raise PolarizationContractError("publication weights must be numeric") from exc
    expected_shape = (len(aggregate_keys), len(release.bin_keys))
    if (
        weights.shape != expected_shape
        or not np.all(np.isfinite(weights))
        or np.any(weights < 0.0)
        or not np.allclose(np.sum(weights, axis=1), 1.0, rtol=0.0, atol=1e-12)
    ):
        raise PolarizationContractError(
            "publication weights must be finite, non-negative, aligned, and row-normalized"
        )
    if np.any(np.count_nonzero(weights, axis=0) > 1):
        raise PolarizationContractError(
            "elementary Sigma bins cannot feed multiple aggregate bins"
        )
    aggregate_covariance = _covariance(
        mapping.get("aggregate_covariance"), len(aggregate_keys), "aggregate"
    )
    propagated = weights @ release.total_covariance @ weights.T
    if not np.allclose(
        aggregate_covariance, propagated, rtol=1e-10, atol=1e-14
    ):
        raise PolarizationContractError(
            "aggregate covariance must equal W C W^T"
        )


def validate_publication_mapping(
    path: Path, paper: str, release: SigmaRelease
) -> None:
    """Validate aggregation, then fail closed until joint P0 output is defined."""
    mapping = load_json(path)
    validate_aggregation_mapping(mapping, paper, release)
    raise PolarizationContractError(
        "shared P0 release artifact interface is not implemented and jointly approved"
    )
