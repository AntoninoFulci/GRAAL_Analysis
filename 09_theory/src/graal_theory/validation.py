"""Source-linked checks for the Eq. 43 partial prediction."""

from __future__ import annotations

import csv
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import tempfile

import numpy as np
from numpy.typing import NDArray

from .observables import Histogram
from .kinematics import s_from_lab_photon_energy
from .models.eta_pi0_p import REQUIRED_TREE_PARAMETER_NAMES
from .phase_space import phase_space_volume_quad


@dataclass(frozen=True)
class ReferenceCurve:
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    relative_uncertainty: float = 0.0
    absolute_uncertainty: float = 0.0

    def __post_init__(self) -> None:
        x = np.asarray(self.x, dtype=np.float64)
        y = np.asarray(self.y, dtype=np.float64)
        if x.ndim != 1 or y.shape != x.shape or not len(x):
            raise ValueError("reference curve requires equal nonempty one-dimensional arrays")
        if not np.all(np.isfinite(x)) or not np.all(np.isfinite(y)) or np.any(y < 0):
            raise ValueError("reference curve contains nonfinite or negative values")
        if np.any(np.diff(x) <= 0):
            raise ValueError("reference abscissae must increase strictly")
        if not np.isfinite(self.relative_uncertainty) or self.relative_uncertainty < 0:
            raise ValueError("relative uncertainty must be finite and nonnegative")
        if not np.isfinite(self.absolute_uncertainty) or self.absolute_uncertainty < 0:
            raise ValueError("absolute uncertainty must be finite and nonnegative")
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)


@dataclass(frozen=True)
class CurveComparison:
    passed: bool
    compared_points: int
    model_relative_tolerance: float
    digitization_relative_uncertainty: float
    digitization_absolute_uncertainty: float
    maximum_relative_residual: float
    points: list[dict[str, float | bool]]


@dataclass(frozen=True)
class FactorTwoComparison:
    passed: bool
    ratio: float
    target_ratio: float
    model_relative_tolerance: float
    digitization_absolute_uncertainty: float
    relative_residual: float
    accepted_relative_residual: float


def _check_tolerance(value: float) -> None:
    if not np.isfinite(value) or value < 0:
        raise ValueError("relative tolerance must be finite and nonnegative")


def compare_curve(
    prediction: NDArray[np.float64], reference: ReferenceCurve, *, relative_tolerance: float = 0.20,
) -> CurveComparison:
    """Compare positive published points; keep model and reading errors separate."""
    _check_tolerance(relative_tolerance)
    prediction = np.asarray(prediction, dtype=np.float64)
    if prediction.shape != reference.y.shape or not np.all(np.isfinite(prediction)):
        raise ValueError("prediction must match reference shape and be finite")
    points: list[dict[str, float | bool]] = []
    for x, observed, calculated in zip(reference.x, reference.y, prediction):
        if observed == 0:
            points.append({"x": float(x), "reference": 0.0, "prediction": float(calculated), "compared": False})
            continue
        residual = abs(float(calculated - observed)) / float(observed)
        allowed = (
            relative_tolerance + reference.relative_uncertainty
            + reference.absolute_uncertainty / float(observed)
        )
        points.append({
            "x": float(x), "reference": float(observed), "prediction": float(calculated),
            "compared": True, "relative_residual": residual, "accepted_relative_residual": allowed,
            "passed": bool(residual <= allowed),
        })
    compared = [point for point in points if point["compared"]]
    if not compared:
        raise ValueError("reference curve has no positive comparison points")
    return CurveComparison(
        all(bool(point["passed"]) for point in compared), len(compared), relative_tolerance,
        reference.relative_uncertainty, reference.absolute_uncertainty,
        max(float(point["relative_residual"]) for point in compared), points,
    )


def validate_figure14_tree(histogram: Histogram, reference: ReferenceCurve) -> CurveComparison:
    edges = np.asarray(histogram.edges, dtype=np.float64)
    values = np.asarray(histogram.values, dtype=np.float64)
    if edges.ndim != 1 or len(edges) != len(values) + 1 or np.any(np.diff(edges) <= 0):
        raise ValueError("histogram requires increasing physical edges")
    active = reference.y > 0
    if np.any(reference.x[active] < edges[0]) or np.any(reference.x[active] > edges[-1]):
        raise ValueError("positive reference point outside physical histogram support")
    centers = (edges[:-1] + edges[1:]) / 2
    # Constant density from first/last center to physical edge; never extrapolate outside edges.
    prediction = np.interp(reference.x[active], centers, values)
    full_prediction = np.zeros_like(reference.y)
    full_prediction[active] = prediction
    return compare_curve(full_prediction, reference)


def compare_factor_two(
    partial: float, full: float, *, relative_tolerance: float = 0.20,
    digitization_absolute_uncertainty: float = 0.0,
) -> FactorTwoComparison:
    _check_tolerance(relative_tolerance)
    if not np.isfinite(partial) or partial < 0 or not np.isfinite(full) or full <= 0:
        raise ValueError("factor-two comparison requires finite nonnegative partial and positive full")
    if not np.isfinite(digitization_absolute_uncertainty) or digitization_absolute_uncertainty < 0:
        raise ValueError("digitization uncertainty must be finite and nonnegative")
    ratio = partial / full
    residual = abs(ratio - 0.5) / 0.5
    accepted = relative_tolerance + digitization_absolute_uncertainty / full
    return FactorTwoComparison(
        bool(residual <= accepted), ratio, 0.5, relative_tolerance,
        digitization_absolute_uncertainty, residual, accepted,
    )


def _load_rows(path: Path, fields: tuple[str, str]) -> tuple[NDArray[np.float64], NDArray[np.float64]]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != list(fields):
            raise ValueError(f"unexpected CSV columns in {path}")
        rows = list(reader)
    if not rows:
        raise ValueError(f"empty reference CSV: {path}")
    try:
        x = np.array([float(row[fields[0]]) for row in rows])
        y = np.array([float(row[fields[1]]) for row in rows])
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid numeric reference in {path}") from exc
    return x, y


def load_figure14_reference(root: Path, metadata: dict) -> ReferenceCurve:
    x, y = _load_rows(
        root / "figure14_eta_p_tree.csv", ("mass_gev", "dsigma_dmass_microbarn_per_gev"),
    )
    record = metadata["figure14_eta_p_tree"]
    return ReferenceCurve(x, y, record["relative_uncertainty"], record["absolute_uncertainty_microbarn_per_gev"])


def load_figure19_reference(root: Path) -> float:
    x, y = _load_rows(
        root / "figure19_total_1202.csv", ("photon_energy_gev", "total_cross_section_microbarn"),
    )
    if len(x) != 1 or not np.isclose(x[0], 1.202, rtol=0, atol=1e-10) or y[0] <= 0 or not np.isfinite(y[0]):
        raise ValueError("Figure 19 reference must contain one positive 1.202 GeV point")
    return float(y[0])


def _write_json(path: Path, value: object) -> None:
    with path.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def _bundle_histogram(arrays: dict[str, NDArray], name: str, index: int) -> Histogram:
    edges = np.asarray(arrays[f"{name}_edges_{index}"], dtype=np.float64)
    density = np.asarray(arrays[f"{name}_density_{index}"], dtype=np.float64)
    if edges.ndim != 1 or density.ndim != 1 or len(edges) != len(density) + 1:
        raise ValueError(f"malformed {name} histogram at energy index {index}")
    if not np.all(np.isfinite(edges)) or not np.all(np.isfinite(density)):
        raise ValueError(f"nonfinite {name} histogram at energy index {index}")
    return Histogram(edges, density)


def _check_observable_integrity(arrays: dict[str, NDArray], energies: NDArray[np.float64]) -> None:
    totals = np.asarray(arrays["partial_cross_section_microbarn"], dtype=np.float64)
    volumes = np.asarray(arrays["phase_space_volume_gev2"], dtype=np.float64)
    if totals.shape != energies.shape or np.any(~np.isfinite(totals)) or np.any(totals < 0):
        raise ValueError("bundle cross section must be finite, nonnegative, and match energy grid")
    if volumes.shape != energies.shape or np.any(~np.isfinite(volumes)) or np.any(volumes < 0):
        raise ValueError("bundle phase-space volume must be finite, nonnegative, and match energy grid")
    for index, total in enumerate(totals):
        for name in ("eta_p", "pi0_p", "eta_pi0"):
            histogram = _bundle_histogram(arrays, name, index)
            widths = np.diff(histogram.edges)
            if np.any(widths < 0) or np.any(histogram.values < 0):
                raise ValueError(f"{name} histogram contains negative widths or densities")
            integral = float(np.sum(histogram.values * widths))
            if not np.isclose(integral, total, rtol=1e-8, atol=1e-10):
                raise ValueError(f"{name} histogram integral disagrees with total cross section")


def _check_bundle_provenance(manifest: dict) -> None:
    parameters = manifest.get("parameters")
    sources = manifest.get("sources")
    if not isinstance(parameters, dict) or set(parameters) != REQUIRED_TREE_PARAMETER_NAMES:
        raise ValueError("bundle has incomplete parameter provenance")
    if not isinstance(sources, dict) or not sources:
        raise ValueError("bundle has no source registry")
    for name, entry in parameters.items():
        if not isinstance(entry, dict):
            raise ValueError(f"parameter {name} has malformed provenance")
        source_key = entry.get("source_key")
        source = sources.get(source_key)
        if not isinstance(source, dict):
            raise ValueError(f"parameter {name} references unknown source")
        identifier = source.get("doi") or source.get("arxiv")
        if not isinstance(identifier, str) or not identifier.strip() or identifier != entry.get("persistent_id"):
            raise ValueError(f"parameter {name} has invalid persistent identifier")
        if not isinstance(source.get("citation"), str) or not source["citation"].strip():
            raise ValueError(f"parameter {name} has no source citation")
        locator = entry.get("locator")
        if not isinstance(locator, str) or not locator.strip() or "://" in locator:
            raise ValueError(f"parameter {name} has missing or invalid source locator")
        if not isinstance(entry.get("unit"), str) or not entry["unit"].strip():
            raise ValueError(f"parameter {name} has no unit")


def _plot_validation(
    directory: Path, arrays: dict[str, NDArray], index_1200: int,
    reference: ReferenceCurve, full: float,
) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    names = (("eta_p", r"$M_{\eta p}$"), ("pi0_p", r"$M_{\pi^0 p}$"), ("eta_pi0", r"$M_{\eta\pi^0}$"))
    fig, axes = plt.subplots(1, 3, figsize=(13, 3.8))
    try:
        for axis, (name, xlabel) in zip(axes, names):
            histogram = _bundle_histogram(arrays, name, index_1200)
            axis.stairs(histogram.values, histogram.edges, label="Eq. 43 partial")
            if name == "eta_p":
                axis.plot(reference.x, reference.y, "k.", label="Figure 14 dotted tree")
            axis.set_xlabel(f"{xlabel} (GeV)")
            axis.set_ylabel(r"$d\sigma/dM$ ($\mu$b/GeV)")
            axis.legend(fontsize=8)
        fig.suptitle(r"$\gamma p\to\eta\pi^0 p$, $E_\gamma=1.200$ GeV: partial tree model")
        fig.tight_layout()
        fig.savefig(directory / "invariant_masses.pdf")
    finally:
        plt.close(fig)

    fig, axis = plt.subplots(figsize=(6.5, 4))
    try:
        energies = np.asarray(arrays["photon_energy_gev"], dtype=np.float64)
        partial = np.asarray(arrays["partial_cross_section_microbarn"], dtype=np.float64)
        axis.plot(energies, partial, "o-", label="Eq. 43 partial")
        axis.plot([1.202], [full], "ks", label="Figure 19 full (digitized)")
        axis.set_xlabel(r"$E_\gamma$ (GeV)")
        axis.set_ylabel(r"$\sigma$ ($\mu$b)")
        axis.legend()
        axis.set_title("Partial tree vs. full coherent model — different scope")
        fig.tight_layout()
        fig.savefig(directory / "total_cross_section.pdf")
    finally:
        plt.close(fig)


def validate_bundle(bundle_path: Path, reference_dir: Path) -> dict:
    """Validate stored predictions; write plots/report, then update manifest state."""
    bundle_path = Path(bundle_path)
    manifest_path = bundle_path / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("scope") != "partial:delta1700_eta_delta_tree_eq43" or manifest.get("schema_version") != 1:
        raise ValueError("bundle is not a supported Eq. 43 partial prediction")
    _check_bundle_provenance(manifest)
    with np.load(bundle_path / "results.npz", allow_pickle=False) as stored:
        arrays = {name: stored[name] for name in stored.files}
    energies = np.asarray(arrays["photon_energy_gev"], dtype=np.float64)
    if energies.ndim != 1 or not np.all(np.isfinite(energies)) or len(energies) != len(manifest["energy_grid_gev"]):
        raise ValueError("bundle has malformed energy grid")
    if not np.allclose(energies, manifest["energy_grid_gev"], atol=0, rtol=0):
        raise ValueError("bundle energy grid disagrees with manifest")

    def find_energy(value: float) -> int:
        indices = np.flatnonzero(np.isclose(energies, value, atol=1e-10, rtol=0))
        if len(indices) != 1:
            raise ValueError(f"validation requires exactly one {value:.3f} GeV prediction")
        return int(indices[0])

    index_1200, index_1202 = find_energy(1.200), find_energy(1.202)
    metadata = json.loads((reference_dir / "digitization.json").read_text(encoding="utf-8"))
    reference = load_figure14_reference(reference_dir, metadata)
    full = load_figure19_reference(reference_dir)
    curve = validate_figure14_tree(_bundle_histogram(arrays, "eta_p", index_1200), reference)
    _check_observable_integrity(arrays, energies)
    cross_sections = np.asarray(arrays["partial_cross_section_microbarn"], dtype=np.float64)
    volumes = np.asarray(arrays["phase_space_volume_gev2"], dtype=np.float64)
    factor = compare_factor_two(
        float(cross_sections[index_1202]), full,
        digitization_absolute_uncertainty=metadata["figure19_total_1202"]["absolute_uncertainty_microbarn"],
    )
    params = manifest["parameters"]
    masses = tuple(float(params[name]["value"]) for name in ("eta_mass", "pi0_mass", "proton_mass"))
    m_proton = masses[-1]
    phase_entries = []
    for energy, measured in zip(energies, volumes):
        if not np.isfinite(measured):
            raise ValueError("bundle contains nonfinite phase-space volume")
        sqrt_s = float(np.sqrt(s_from_lab_photon_energy(float(energy), m_proton)))
        expected = phase_space_volume_quad(sqrt_s, masses) if sqrt_s > sum(masses) else 0.0
        relative_difference = abs(float(measured) - expected) / expected if expected else (0.0 if measured == 0 else None)
        passed = bool(relative_difference is not None and relative_difference <= 0.005)
        phase_entries.append({
            "photon_energy_gev": float(energy), "sobol_volume_gev2": float(measured),
            "quadrature_volume_gev2": expected, "relative_difference": relative_difference,
            "relative_tolerance": 0.005, "passed": passed,
        })
    convergence = json.loads((bundle_path / "convergence.json").read_text(encoding="utf-8"))
    if not isinstance(convergence, list) or len(convergence) != len(energies):
        raise ValueError("bundle convergence report has wrong length")
    for energy, item in zip(energies, convergence):
        if not np.isclose(item["photon_energy_gev"], energy, atol=0, rtol=0) or not isinstance(item["passed"], bool):
            raise ValueError("bundle convergence report disagrees with energy grid")
    checks = {
        "figure14_tree": asdict(curve),
        "factor_two_1202": asdict(factor),
        "phase_space": {"passed": all(item["passed"] for item in phase_entries), "energies": phase_entries},
        "convergence": {"passed": all(item["passed"] for item in convergence), "energies": convergence},
    }
    status = "validated" if all(value["passed"] for value in checks.values()) else "failed"
    report = {"status": status, "scope": manifest["scope"], **checks}
    destination = bundle_path / "validation"
    destination.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".validation-", dir=bundle_path) as temporary:
        staged = Path(temporary)
        _plot_validation(staged, arrays, index_1200, reference, full)
        _write_json(staged / "comparison.json", report)
        for filename in ("invariant_masses.pdf", "total_cross_section.pdf", "comparison.json"):
            os.replace(staged / filename, destination / filename)
    manifest["validation_state"] = status
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=bundle_path, prefix=".manifest-", delete=False) as stream:
        temporary_manifest = Path(stream.name)
    try:
        _write_json(temporary_manifest, manifest)
        os.replace(temporary_manifest, manifest_path)
    finally:
        temporary_manifest.unlink(missing_ok=True)
    return report
