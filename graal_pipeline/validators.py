from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any, Iterable

import numpy as np

from .model import ValidationResult


def _result(name: str, reasons: Iterable[str] = (), *, level: str = "fast") -> ValidationResult:
    collected = tuple(reasons)
    return ValidationResult(not collected, name, collected, level)


def _root_module():
    import ROOT

    return ROOT


def validate_root_tree(
    path: str | Path,
    tree_name: str,
    required_branches: Iterable[str],
    *,
    require_entries: bool = True,
    validator: str = "root_tree",
    root_module: Any | None = None,
) -> ValidationResult:
    candidate = Path(path)
    if not candidate.is_file():
        return _result(validator, (f"missing ROOT file: {candidate}",))
    root = root_module or _root_module()
    try:
        source = root.TFile.Open(str(candidate), "READ")
    except OSError:
        source = None
    if not source or source.IsZombie():
        if source:
            source.Close()
        return _result(validator, (f"ROOT file is zombie or unreadable: {candidate}",))
    try:
        tree = source.Get(tree_name)
        if not tree or not tree.InheritsFrom("TTree"):
            return _result(validator, (f"missing TTree {tree_name!r} in {candidate}",))
        branches = {branch.GetName() for branch in tree.GetListOfBranches()}
        missing = sorted(set(required_branches) - branches)
        if missing:
            return _result(
                validator,
                (f"{candidate}:{tree_name}: missing branches: {', '.join(missing)}",),
            )
        if require_entries and int(tree.GetEntries()) <= 0:
            return _result(validator, (f"{candidate}:{tree_name}: tree is empty",))
        return _result(validator)
    finally:
        source.Close()


_DETECTOR_BRANCHES = (
    "gammas",
    "fcharged_theta",
    "RunNumber",
    "Polarization",
    "Xstrip",
)


def _validate_root_directory(
    directory: str | Path,
    *,
    pattern: str,
    tree_name: str,
    required_branches: Iterable[str],
    expected_files: Iterable[str] | None,
    validator: str,
) -> ValidationResult:
    root = Path(directory)
    if not root.is_dir():
        return _result(validator, (f"missing directory: {root}",))
    if expected_files is not None:
        missing = sorted(name for name in expected_files if not (root / name).is_file())
        if missing:
            return _result(validator, (f"missing expected files: {', '.join(missing)}",))
    files = sorted(root.glob(pattern))
    if not files:
        return _result(validator, (f"no files matching {pattern!r} in {root}",))
    reasons: list[str] = []
    for path in files:
        checked = validate_root_tree(
            path,
            tree_name,
            required_branches,
            validator=validator,
        )
        reasons.extend(checked.reasons)
    return _result(validator, reasons)


def validate_preanalysis_directory(directory: str | Path) -> ValidationResult:
    return _validate_root_directory(
        directory,
        pattern="pre_*.root",
        tree_name="h80",
        required_branches=_DETECTOR_BRANCHES,
        expected_files=None,
        validator="preanalysis",
    )


def validate_selected_directory(
    directory: str | Path, *, expected_files: Iterable[str] | None = None
) -> ValidationResult:
    return _validate_root_directory(
        directory,
        pattern="*.root",
        tree_name="h85",
        required_branches=_DETECTOR_BRANCHES,
        expected_files=expected_files,
        validator="event_selection",
    )


def validate_mc_file(
    path: str | Path,
    *,
    required_branches: Iterable[str] = ("beam", "proton"),
) -> ValidationResult:
    return validate_root_tree(
        path,
        "mc",
        required_branches,
        validator="monte_carlo",
    )


def validate_feature_dataset(
    path: str | Path, expected_signal_channel: str, expected_hypothesis: str
) -> ValidationResult:
    from bdt_training.dataset.stage1_dataset import load_stage1_dataset

    try:
        dataset = load_stage1_dataset(path)
    except Exception as exc:
        return _result("stage1_features", (f"invalid Stage-1 dataset: {exc}",))
    if dataset.metadata.signal_channel != expected_signal_channel:
        return _result(
            "stage1_features",
            (
                "signal channel mismatch: expected "
                f"{expected_signal_channel}, found {dataset.metadata.signal_channel}",
            ),
        )
    if dataset.metadata.hypothesis != expected_hypothesis:
        return _result(
            "stage1_features",
            (
                f"hypothesis mismatch: expected {expected_hypothesis}, "
                f"found {dataset.metadata.hypothesis}",
            ),
        )
    return _result("stage1_features")


def validate_model_bundle(
    directory: str | Path,
    expected_signal_channel: str,
    expected_hypothesis: str,
) -> ValidationResult:
    from graal_common.stage1.artifacts import Stage1ArtifactPaths, Stage1Provenance

    artifacts = Stage1ArtifactPaths.from_directory(directory)
    missing = [
        path.name
        for path in (
            artifacts.model,
            artifacts.threshold,
            artifacts.provenance,
            artifacts.metrics,
        )
        if not path.is_file()
    ]
    if missing:
        return _result("stage1_model", (f"missing model artifacts: {', '.join(missing)}",))
    try:
        model = json.loads(artifacts.model.read_text())
        if not isinstance(model, dict) or not model:
            raise ValueError("model JSON must be a non-empty object")
        threshold = float(artifacts.threshold.read_text().strip())
        if not math.isfinite(threshold):
            raise ValueError("threshold must be finite")
        provenance = Stage1Provenance.from_json(artifacts.provenance.read_text())
    except Exception as exc:
        return _result("stage1_model", (f"invalid model bundle: {exc}",))
    if (
        provenance.signal_channel != expected_signal_channel
        or provenance.hypothesis != expected_hypothesis
    ):
        return _result(
            "stage1_model",
            (
                "model provenance mismatch: expected "
                f"signal={expected_signal_channel}, hypothesis={expected_hypothesis}; "
                f"found signal={provenance.signal_channel}, "
                f"hypothesis={provenance.hypothesis}",
            ),
        )
    return _result("stage1_model")


def validate_calibration_directory(
    directory: str | Path,
    *,
    required_selected_keys: set[tuple[int, int]] | None = None,
) -> ValidationResult:
    from graal_common.calibration.strip_energy_flux import (
        FLUX_SCHEMA_VERSION,
        STRIP_EXPOSURE_FIELDS,
    )

    root = Path(directory)
    qa_path = root / "strip_energy_flux_qa.json"
    exposure_path = root / "flux_by_run_strip.csv"
    missing = [path.name for path in (qa_path, exposure_path) if not path.is_file()]
    if missing:
        return _result("flux_calibration", (f"missing calibration artifacts: {', '.join(missing)}",))
    try:
        qa = json.loads(qa_path.read_text())
        if qa.get("schema_version") != FLUX_SCHEMA_VERSION:
            raise ValueError(
                f"QA schema {qa.get('schema_version')} != {FLUX_SCHEMA_VERSION}"
            )
        if qa.get("valid") is not True or qa.get("errors"):
            raise ValueError(f"QA reports invalid calibration: {qa.get('errors', [])}")
        with exposure_path.open(newline="") as stream:
            reader = csv.DictReader(stream)
            if tuple(reader.fieldnames or ()) != STRIP_EXPOSURE_FIELDS:
                raise ValueError("flux exposure columns do not match schema v2")
            rows = list(reader)
        if not rows:
            raise ValueError("flux exposure table is empty")
        keys: set[tuple[int, int]] = set()
        for row in rows:
            if int(row["schema_version"]) != FLUX_SCHEMA_VERSION:
                raise ValueError("flux exposure row has wrong schema version")
            keys.add((int(row["run_number"]), int(row["xstrip"])))
    except Exception as exc:
        return _result("flux_calibration", (f"invalid calibration: {exc}",))
    required = required_selected_keys or set()
    absent = sorted(required - keys)
    if absent:
        return _result(
            "flux_calibration",
            (f"missing selected run/strip exposure: {absent}",),
        )
    return _result("flux_calibration")


_RECONSTRUCTION_BRANCHES = {
    "RunNumber",
    "Polarization",
    "Xstrip",
    "beam",
    "eta",
    "pi0",
    "proton",
    "missing",
    "eta_mass",
    "pi0_mass",
    "n_photons_input",
}


def validate_reconstruction_file(
    path: str | Path,
    tree_name: str,
    *,
    require_bdt: bool = False,
    require_fit: bool = False,
) -> ValidationResult:
    required = set(_RECONSTRUCTION_BRANCHES)
    if require_bdt:
        required.add("bdt_score")
    if require_fit:
        required.update(
            {
                "eta_fit",
                "pi0_fit",
                "proton_fit",
                "fit_chi2",
                "fit_ndf",
                "fit_converged",
            }
        )
    contract = validate_root_tree(
        path, tree_name, required, validator="reconstruction"
    )
    if not contract.valid:
        return contract
    root = _root_module()
    source = root.TFile.Open(str(path), "READ")
    try:
        tree = source.Get(tree_name)
        limit = min(int(tree.GetEntries()), 100)
        for index in range(limit):
            tree.GetEntry(index)
            values = [float(tree.eta_mass), float(tree.pi0_mass), float(tree.Xstrip)]
            if require_bdt:
                values.append(float(tree.bdt_score))
            if not all(math.isfinite(value) for value in values):
                return _result(
                    "reconstruction", (f"non-finite value at entry {index}",)
                )
            if int(tree.n_photons_input) < 0:
                return _result(
                    "reconstruction", (f"negative photon count at entry {index}",)
                )
    finally:
        source.Close()
    return _result("reconstruction")


_BEAM_PDFS = (
    "figure4_experimental.pdf",
    "comparison_reconstruction_samples.pdf",
    "comparison_estimators.pdf",
    "fit_diagnostics.pdf",
    "systematic_summary.pdf",
    "false_asymmetry_controls.pdf",
    "photon_multiplicity.pdf",
)


def validate_beam_asymmetry_directory(
    directory: str | Path,
    *,
    expected_energy_edges: Iterable[float],
) -> ValidationResult:
    root_dir = Path(directory)
    root_path = root_dir / "beam_asymmetry.root"
    contract = validate_root_tree(
        root_path,
        "sigma_points",
        ("sigma", "fit_converged", "energy_bin"),
        validator="beam_asymmetry",
    )
    if not contract.valid:
        return contract
    root = _root_module()
    source = root.TFile.Open(str(root_path), "READ")
    try:
        tree = source.Get("sigma_points")
        edges = source.Get("binning/energy_edges")
        covariance = source.Get("covariance/total")
        if not edges:
            return _result("beam_asymmetry", ("missing binning/energy_edges",))
        if not covariance:
            return _result("beam_asymmetry", ("missing covariance/total",))
        actual_edges = tuple(float(edges[index]) for index in range(edges.GetNrows()))
        expected = tuple(float(value) for value in expected_energy_edges)
        if len(actual_edges) != len(expected) or not np.allclose(
            actual_edges, expected, rtol=0.0, atol=1e-12
        ):
            return _result(
                "beam_asymmetry",
                (f"energy edges do not match: expected {expected}, found {actual_edges}",),
            )
        entries = int(tree.GetEntries())
        if int(covariance.GetNbinsX()) != entries or int(covariance.GetNbinsY()) != entries:
            return _result(
                "beam_asymmetry",
                ("covariance/total dimensions do not match sigma_points",),
            )
        for index in range(entries):
            tree.GetEntry(index)
            if int(tree.fit_converged) not in {0, 1}:
                return _result(
                    "beam_asymmetry", (f"invalid fit status at entry {index}",)
                )
            if not math.isfinite(float(tree.sigma)):
                return _result(
                    "beam_asymmetry", (f"non-finite sigma at entry {index}",)
                )
    finally:
        source.Close()

    missing_pdfs = [
        name
        for name in _BEAM_PDFS
        if not (root_dir / name).is_file() or (root_dir / name).stat().st_size == 0
    ]
    if missing_pdfs:
        return _result(
            "beam_asymmetry",
            (f"missing or empty PDF products: {', '.join(missing_pdfs)}",),
        )
    return _result("beam_asymmetry")
