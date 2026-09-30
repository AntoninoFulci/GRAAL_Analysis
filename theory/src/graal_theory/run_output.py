"""Durable, replaceable bundles for standalone partial predictions."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

import numpy as np

from .constants import GEV2_TO_MICROBARN
from .convergence import ConvergenceReport
from .models.eta_pi0_p import EtaPi0PModel
from .observables import Prediction


MANIFEST_KEYS = {
    "schema_version", "model", "scope", "code_revision", "parameters",
    "sources", "energy_grid_gev", "sobol", "normalization",
    "configuration_sha256", "validation_state",
}


@dataclass(frozen=True)
class RunBundle:
    model: EtaPi0PModel
    predictions: tuple[Prediction, ...]
    convergence: tuple[ConvergenceReport, ...]
    source_registry: Mapping[str, Mapping[str, str]]

    def __post_init__(self) -> None:
        if not self.predictions or len(self.predictions) != len(self.convergence):
            raise ValueError("bundle requires one convergence report per prediction")
        energies = [item.photon_energy_gev for item in self.predictions]
        if len(set(energies)) != len(energies):
            raise ValueError("bundle photon energies must be unique")


def _git_revision(project_root: Path) -> dict[str, str | bool | None]:
    try:
        commit = subprocess.run(
            ["git", "rev-parse", "HEAD"], cwd=project_root,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        status = subprocess.run(
            ["git", "status", "--porcelain"], cwd=project_root,
            capture_output=True, text=True, check=True,
        ).stdout.strip()
        return {"commit": commit, "dirty": bool(status)}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def _physical_parameters(model: EtaPi0PModel) -> dict[str, dict]:
    result = {}
    for name, parameter in model.parameters.provenance.items():
        value = parameter.value
        serialized = {"real": value.real, "imag": value.imag} if isinstance(value, complex) else value
        result[name] = {
            "value": serialized,
            "unit": parameter.unit,
            "source_key": parameter.source.citation_key,
            "persistent_id": parameter.source.persistent_id,
            "locator": parameter.source.locator,
        }
    return result


def _manifest(bundle: RunBundle, project_root: Path) -> dict:
    predictions = bundle.predictions
    parameters = _physical_parameters(bundle.model)
    normalization = {
        "equation": "Doring PRC 73 (2006), Eq. 45",
        "initial_flux": "2*(s-m_proton^2)",
        "baryon_factor": "4*m_initial*m_final",
        "initial_spin_and_photon_average": 0.25,
        "gev_minus_two_to_microbarn": GEV2_TO_MICROBARN,
    }
    configuration = {
        "parameters": parameters,
        "energy_grid_gev": [p.photon_energy_gev for p in predictions],
        "sobol": [vars(p.sobol_config) for p in predictions],
        "histogram_bins": len(predictions[0].histograms["eta_p"].values),
        "normalization": normalization,
    }
    digest = hashlib.sha256(
        json.dumps(configuration, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()
    manifest = {
        "schema_version": 1,
        "model": "gamma p -> eta pi0 p",
        "scope": "partial:delta1700_eta_delta_tree_eq43",
        "code_revision": _git_revision(project_root),
        "parameters": parameters,
        "sources": dict(bundle.source_registry),
        "energy_grid_gev": configuration["energy_grid_gev"],
        "sobol": configuration["sobol"],
        "normalization": normalization,
        "configuration_sha256": digest,
        "validation_state": "pending",
    }
    assert set(manifest) == MANIFEST_KEYS
    return manifest


def _arrays(bundle: RunBundle) -> dict[str, np.ndarray]:
    arrays = {
        "photon_energy_gev": np.array([p.photon_energy_gev for p in bundle.predictions]),
        "partial_cross_section_microbarn": np.array([
            p.partial_cross_section_microbarn for p in bundle.predictions
        ]),
        "phase_space_volume_gev2": np.array([
            p.phase_space_volume_gev2 for p in bundle.predictions
        ]),
    }
    for index, prediction in enumerate(bundle.predictions):
        for name, histogram in prediction.histograms.items():
            arrays[f"{name}_edges_{index}"] = histogram.edges
            arrays[f"{name}_density_{index}"] = histogram.values
    return arrays


def _convergence_json(bundle: RunBundle) -> list[dict]:
    reports = []
    for prediction, report in zip(bundle.predictions, bundle.convergence):
        reports.append({
            "photon_energy_gev": prediction.photon_energy_gev,
            "low_power": prediction.sobol_config.power - 1,
            "high_power": prediction.sobol_config.power,
            "cross_section_relative_change": report.cross_section_relative_change,
            "max_populated_bin_relative_change": report.max_populated_bin_relative_change,
            "passed": report.passed,
            "excluded_edge_bins": report.excluded_edge_bins,
        })
    return reports


def _write_json(path: Path, value: object) -> None:
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def write_run_bundle(destination: Path, bundle: RunBundle, *, replace: bool = False) -> None:
    destination = Path(destination)
    if destination.exists():
        if not replace:
            raise FileExistsError(f"output already exists: {destination}")
        if not destination.is_dir():
            raise ValueError("existing output must be a directory")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{destination.name}.tmp-", dir=destination.parent))
    backup: Path | None = None
    try:
        project_root = Path(__file__).resolve().parents[3]
        _write_json(temp / "manifest.json", _manifest(bundle, project_root))
        _write_json(temp / "convergence.json", _convergence_json(bundle))
        result_path = temp / "results.npz"
        np.savez_compressed(result_path, **_arrays(bundle))
        with result_path.open("rb") as stream:
            os.fsync(stream.fileno())
        if destination.exists():
            backup = destination.parent / f".{destination.name}.backup-{uuid.uuid4().hex}"
            os.replace(destination, backup)
        try:
            os.replace(temp, destination)
        except OSError:
            if backup is not None:
                os.replace(backup, destination)
                backup = None
            raise
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
    finally:
        if temp.exists():
            shutil.rmtree(temp)
