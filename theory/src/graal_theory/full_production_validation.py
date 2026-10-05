"""Independent PRC73 stroke audits and coherent-production baseline reports.

Published kernel strokes that are narrower than a whole-family API are
unresolved, never compared to the family's coherent sum. Source uncertainty,
the 20% reconstruction allowance and numerical resolution error stay separate.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import asdict, dataclass, field, replace
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from types import MappingProxyType
from typing import Mapping

import numpy as np
from numpy.typing import NDArray

from .models.eta_pi0_p_full import EtaPi0PFullModel, FAMILY_NAMES, _polarization


PDF_SHA256 = "19a2fbce10ed8201a29bdfbcfb9f3690a280d943c1e83db01aa1b2057d20eccb"
_CSV = "p73_full_production_curves.csv"
_JSON = "p73_full_production_curves.json"
_STATUSES = ("compatible", "discrepant", "unresolved", "masked_nonconverged")
_MAPPINGS = {
    "fig12_contact": (12, "dotted", "chiral_contact"),
    "fig12_external": (12, "dash_dot", "external_pi0"),
    "fig12_internal": (12, "solid", "internal_pi0"),
    "fig12_k_sigma": (12, "double_dash_dot", "k_sigma_star_rescattering"),
    "fig13_delta1700": (13, "dotted", "explicit_resonances"),
    "fig13_nstar1520": (13, "solid", "explicit_resonances"),
    "fig13_delta_kr": (13, "dash_dot", "explicit_resonances"),
    "fig13_sigma_kr": (13, "double_dash_dot", "k_sigma_star_rescattering"),
    "fig14_eta_delta": (14, "dash_dot", "eta_delta_rescattering"),
    "fig14_tree": (14, "dotted", "eq43_tree"),
    "fig14_full": (14, "solid", "full"),
    "fig14_reduced": (14, "dashed", "reduced"),
    "fig19_full": (19, "solid", "full"),
}
_UNRESOLVED = frozenset(("fig12_k_sigma", "fig13_delta1700", "fig13_nstar1520",
    "fig13_delta_kr", "fig13_sigma_kr", "fig14_reduced"))


def _array(value, *, dtype=float, label="curve") -> NDArray:
    try:
        raw = np.asarray(value)
        if raw.ndim != 1 or not len(raw):
            raise ValueError("requires a nonempty one-dimensional array")
        if dtype is bool:
            if raw.dtype.kind != "b":
                raise ValueError("requires boolean convergence flags without truth-value casting")
        else:
            mixed_bool = (not isinstance(value, np.ndarray)
                and any(isinstance(item, (bool, np.bool_))
                        for item in np.asarray(value, dtype=object).flat))
            if raw.dtype.kind not in "iuf" or mixed_bool:
                raise ValueError("requires real numeric values without booleans, strings or complex casts")
        with np.errstate(over="raise", invalid="raise"):
            array = np.array(raw, dtype=dtype, copy=True)
    except (ValueError, TypeError, OverflowError, FloatingPointError) as exc:
        raise ValueError(f"{label}: {exc}") from exc
    array.setflags(write=False)
    return array


def _x(value, *, label="abscissae") -> NDArray:
    array = _array(value, label=label)
    if not np.all(np.isfinite(array)) or np.any(np.diff(array) <= 0):
        raise ValueError(f"{label} must be finite and increase strictly, without duplicate points")
    return array


@dataclass(frozen=True)
class ReferenceCurve:
    figure: int
    curve: str
    family: str
    photon_energy_gev: float | None
    observable: str
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    reading_error: NDArray[np.float64]
    unresolved: bool = False
    ambiguity_note: str = ""

    def __post_init__(self):
        x, y, error = (_x(self.x, label="reference.x"), _array(self.y, label="reference.y"),
                       _array(self.reading_error, label="reference.reading_error"))
        if y.shape != x.shape or error.shape != x.shape:
            raise ValueError("reference arrays must have equal shape")
        if not np.all(np.isfinite(y)) or np.any(y < 0):
            raise ValueError("reference values must be finite and nonnegative")
        if not np.all(np.isfinite(error)) or np.any(error < 0):
            raise ValueError("reading uncertainty must be finite and nonnegative")
        if not isinstance(self.unresolved, bool) or (self.unresolved and not self.ambiguity_note.strip()):
            raise ValueError("unresolved reference requires an explicit ambiguity note")
        if (self.figure not in (12, 13, 14, 19) or self.observable not in ("eta_p", "total")
                or not self.curve or not self.family):
            raise ValueError("reference requires figure, curve, family and physical observable")
        if self.photon_energy_gev is not None and (
                not np.isfinite(self.photon_energy_gev) or self.photon_energy_gev <= 0):
            raise ValueError("source photon energy must be finite and positive")
        for name, value in (("x", x), ("y", y), ("reading_error", error)):
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class PredictionCurve:
    x: NDArray[np.float64]
    y: NDArray[np.float64]
    numerical_error: NDArray[np.float64]
    converged: NDArray[np.bool_]
    reason: str = ""

    def __post_init__(self):
        values = (_x(self.x, label="prediction.x"), _array(self.y, label="prediction.y"),
                  _array(self.numerical_error, label="prediction.numerical_error"),
                  _array(self.converged, dtype=bool, label="prediction.converged"))
        if any(value.shape != values[0].shape for value in values):
            raise ValueError("prediction arrays must have equal shape")
        if np.any(np.isfinite(values[2]) & (values[2] < 0)):
            raise ValueError("prediction.numerical_error: finite numerical uncertainty must be nonnegative")
        for name, value in zip(("x", "y", "numerical_error", "converged"), values):
            object.__setattr__(self, name, value)


@dataclass(frozen=True)
class FullProductionValidation:
    points: list[dict]
    counts: dict[str, int]
    total: int


def _filename(root: Path, value: object) -> Path:
    if not isinstance(value, str) or not value or Path(value).name != value:
        raise ValueError("reference filename must be a local basename, without path traversal")
    return root / value


def _csv_rows(path: Path, columns: list[str]) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        if reader.fieldnames != columns:
            raise ValueError(f"unexpected CSV columns in {path.name}")
        rows = list(reader)
    if not rows or any(set(row) != set(columns) or None in row.values() for row in rows):
        raise ValueError(f"empty or malformed reference CSV {path.name}")
    return rows


def load_full_production_reference(reference_dir: Path) -> Mapping[str, ReferenceCurve]:
    """Load closed source records, including filename links to existing readings."""
    root = Path(reference_dir)
    metadata = json.loads((root / _JSON).read_text(encoding="utf-8"))
    if metadata.get("pdf_sha256") != PDF_SHA256:
        raise ValueError("primary-source PDF hash does not match the audited source")
    if metadata.get("schema_version") != 1 or set(metadata.get("curves", {})) != set(_MAPPINGS):
        raise ValueError("reference requires the complete source curve inventory")
    if not metadata.get("reading_method") or metadata.get("doi") != "10.1103/PhysRevC.73.045209":
        raise ValueError("reference requires an independent reading method and source DOI")
    if metadata.get("units") != {"x_gev": "GeV", "eta_p": "microbarn/GeV", "total": "microbarn"}:
        raise ValueError("reference requires the exact GeV/microbarn scientific unit registry")
    rows = _csv_rows(root / _CSV, ["figure", "curve", "x_gev", "y", "reading_error"])
    groups = {key: [] for key in _MAPPINGS}
    for row in rows:
        key = row["curve"]
        if key not in groups or key in ("fig14_tree", "fig19_full"):
            raise ValueError("unknown curve or duplicated filename-linked points in reference CSV")
        if row["figure"] != str(_MAPPINGS[key][0]):
            raise ValueError("CSV figure does not match the source curve mapping")
        groups[key].append(row)
    result = {}
    fields = {"figure", "curve", "line_style", "family", "photon_energy_gev",
              "observable", "unresolved", "ambiguity_note", "source"}
    for key, record in metadata["curves"].items():
        if set(record) != fields:
            raise ValueError(f"curve {key} requires closed source metadata fields")
        if (record["figure"], record["line_style"], record["family"]) != _MAPPINGS[key]:
            raise ValueError(f"curve {key}: figure/family/line mapping disagrees with the caption")
        if key in _UNRESOLVED and record["unresolved"] is not True:
            raise ValueError(f"curve {key}: unresolved source-to-API mapping must be preserved")
        expected_energy = None if key == "fig19_full" else 1.2
        if record["photon_energy_gev"] != expected_energy:
            raise ValueError(f"curve {key}: source photon energy disagrees with caption")
        expected_observable = "total" if key == "fig19_full" else "eta_p"
        if record["observable"] != expected_observable:
            raise ValueError(f"curve {key}: observable must be {expected_observable!r} for this published quantity")
        figure = metadata.get("figures", {}).get(str(record["figure"]), {})
        if (figure.get("printed_page") != f"045209-{figure.get('page_in_pdf')}"
                or not figure.get("axis_calibration") or not figure.get("ambiguity_notes")):
            raise ValueError(f"curve {key}: missing page/axis/ambiguity source audit")
        source = record["source"]
        path = _filename(root, source.get("filename"))
        if key in ("fig14_tree", "fig19_full"):
            required_filename = "figure14_eta_p_tree.csv" if key == "fig14_tree" else "figure19_total_1202.csv"
            if path.name != required_filename:
                raise ValueError(f"curve {key} must reuse {required_filename}")
            linked = _csv_rows(path, source["columns"])
            audit = json.loads(_filename(root, source["metadata_filename"]).read_text())[source["metadata_record"]]
            x = [float(row[source["columns"][0]]) for row in linked]
            y = np.array([float(row[source["columns"][1]]) for row in linked])
            absolute_key = ("absolute_uncertainty_microbarn_per_gev" if key == "fig14_tree"
                            else "absolute_uncertainty_microbarn")
            error = audit[absolute_key] + audit["relative_uncertainty"] * np.abs(y)
        else:
            if path.name != _CSV or set(source) != {"filename"}:
                raise ValueError(f"curve {key}: unexpected source filename or metadata")
            x = [float(row["x_gev"]) for row in groups[key]]
            y = [float(row["y"]) for row in groups[key]]
            error = [float(row["reading_error"]) for row in groups[key]]
        result[key] = ReferenceCurve(**{name: record[name] for name in fields - {"line_style", "source"}},
                                     x=x, y=y, reading_error=error)
    return MappingProxyType(result)


def _sample_prediction(prediction: PredictionCurve, x: float) -> tuple[float | None, float | None, str]:
    """Interpolate only one adjacent pair; a masked endpoint blocks the segment."""
    exact = np.flatnonzero(np.isclose(prediction.x, x, rtol=0, atol=1e-12))
    if len(exact):
        indices = exact[:1]
    else:
        right = int(np.searchsorted(prediction.x, x))
        indices = np.array([right-1, right])
    if (not np.all(np.isfinite(prediction.y[indices]))
            or not np.all(np.isfinite(prediction.numerical_error[indices]))):
        return None, None, prediction.reason or "nonfinite prediction or numerical error"
    if not np.all(prediction.converged[indices]):
        return None, None, prediction.reason or "numerical convergence gate failed; masked segment"
    if len(indices) == 1:
        return float(prediction.y[indices[0]]), float(prediction.numerical_error[indices[0]]), ""
    return (float(np.interp(x, prediction.x[indices], prediction.y[indices])),
            float(np.interp(x, prediction.x[indices], prediction.numerical_error[indices])), "")


def compare_full_production(prediction: Mapping[str, PredictionCurve],
                            references: Mapping[str, ReferenceCurve]) -> FullProductionValidation:
    """Compare overlapping domains, retaining ambiguity and numerical-mask identity."""
    if set(prediction) - set(references):
        raise ValueError("prediction contains unknown reference curve")
    points = []
    for key, reference in references.items():
        calculated = prediction.get(key)
        for x, y, reading in zip(reference.x, reference.y, reference.reading_error):
            if calculated is not None and (x < calculated.x[0] or x > calculated.x[-1]):
                continue
            observed = float(y)
            point = {"reference_id": key, "curve": reference.curve, "family": reference.family,
                "figure": reference.figure, "photon_energy_gev": (
                    float(x) if reference.observable == "total" else reference.photon_energy_gev),
                "observable": reference.observable, "x_gev": float(x), "reference": observed,
                "reading_error": float(reading), "prediction": None, "numerical_error": None,
                "residual": None, "tolerance": None}
            if reference.unresolved:
                status, reason = "unresolved", reference.ambiguity_note
            elif calculated is None:
                status, reason = "unresolved", "missing prediction for source curve"
            else:
                value, error, reason = _sample_prediction(calculated, float(x))
                if reason:
                    status = "masked_nonconverged"
                else:
                    residual = abs(value-observed)
                    tolerance = float(reading) + error + (0.20*abs(observed) if observed else 0.)
                    status = "compatible" if residual <= tolerance else "discrepant"
                    point.update(prediction=value, numerical_error=error, residual=residual, tolerance=tolerance)
            points.append({**point, "status": status, "reason": reason})
    counts = {status: sum(point["status"] == status for point in points) for status in _STATUSES}
    return FullProductionValidation(points, counts, len(points))


def _validate_report(result: FullProductionValidation, metadata: Mapping) -> None:
    actual = {status: sum(point.get("status") == status for point in result.points) for status in _STATUSES}
    if actual != result.counts or sum(actual.values()) != result.total or result.total != len(result.points):
        raise ValueError("report status counts must sum to the complete point total")
    required = {"model", "command", "config", "git_commit", "parameter_file_sha256", "pdf_sha256", "conventions"}
    if not required <= metadata.keys() or metadata["pdf_sha256"] != PDF_SHA256:
        raise ValueError("report requires complete model/config/source provenance and exact PDF hash")
    if not all(isinstance(metadata[key], str) and metadata[key].strip() for key in ("model", "command", "git_commit")):
        raise ValueError("report requires nonempty model, command and git commit")
    commit = metadata["git_commit"]
    if len(commit) != 40 or any(character not in "0123456789abcdef" for character in commit):
        raise ValueError("report requires the complete git commit hash")
    hashes = metadata["parameter_file_sha256"]
    if not isinstance(hashes, dict) or not hashes or any(
            not isinstance(value, str) or len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
            for value in hashes.values()):
        raise ValueError("report requires parameter file SHA256 hashes")
    if not isinstance(metadata["config"], dict) or not {"sobol_powers", "bins", "quadrature"} <= metadata["config"].keys():
        raise ValueError("report requires Sobol powers, bins and quadrature configuration")
    from .amplitudes.production_loops import QuadratureSettings
    from .observables import HistogramSpec
    from .phase_space import SobolConfig

    config = metadata["config"]
    try:
        powers = config["sobol_powers"]
        if not isinstance(powers, list) or len(powers) != 2 or powers[1] != powers[0]+1:
            raise ValueError("requires consecutive Sobol powers")
        for power in powers:
            SobolConfig(power)
        HistogramSpec(config["bins"])
        if set(config["quadrature"]) != {"q_order", "angle_order", "relative_tolerance", "absolute_tolerance"}:
            raise ValueError("requires complete quadrature settings")
        QuadratureSettings(**config["quadrature"])
    except (TypeError, KeyError, ValueError) as exc:
        raise ValueError(f"invalid report numerical configuration: {exc}") from exc
    if (not isinstance(metadata["conventions"], list) or not metadata["conventions"]
            or not all(isinstance(item, str) and item.strip() for item in metadata["conventions"])):
        raise ValueError("report requires an explicit convention list")


def write_full_production_report(output_dir: Path, result: FullProductionValidation,
                                 metadata: Mapping) -> tuple[Path, Path]:
    """Validate/serialize both artifacts before fsync and sibling atomic replacement."""
    _validate_report(result, metadata)
    payload = json.dumps({"metadata": dict(metadata), **asdict(result)}, indent=2, allow_nan=False)+"\n"
    lines = ["# PRC73 coherent-production validation", "", f"Model: {metadata['model']}",
        f"Git commit: {metadata['git_commit']}", f"PDF SHA256: {metadata['pdf_sha256']}", "",
        f"Total overlapping reference points: {result.total}", "",
        *[f"- {status}: {result.counts[status]}" for status in _STATUSES], "",
        "| Reference | Family | Figure | E_gamma (GeV) | x (GeV) | Status | Reason |",
        "|---|---|---:|---:|---:|---|---|"]
    for point in result.points:
        lines.append(f"| {point['reference_id']} | {point['family']} | {point['figure']} | "
            f"{point['photon_energy_gev']} | {point['x_gev']} | {point['status']} | {point['reason']} |")
    lines.extend(["", "## Reproduction metadata", "", "```json",
                  json.dumps(dict(metadata), indent=2, allow_nan=False), "```", ""])
    texts = (payload, "\n".join(lines))
    directory = Path(output_dir)
    directory.mkdir(parents=True, exist_ok=True)
    destinations = tuple(directory / f"full_production_validation.{extension}" for extension in ("json", "md"))
    temporary = []
    try:
        for destination, contents in zip(destinations, texts):
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=directory,
                    prefix=f".{destination.name}.", suffix=".tmp", delete=False) as stream:
                temporary.append(Path(stream.name))
                stream.write(contents)
                stream.flush()
                os.fsync(stream.fileno())
        for source, destination in zip(temporary, destinations):
            source.replace(destination)
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
    return destinations


@dataclass(frozen=True)
class _SelectedModel:
    """Private validation-only whole-family adapter for the observable integrator."""

    model: object
    families: tuple[str, ...]

    @property
    def parameters(self):
        return self.model.parameters

    @property
    def masses(self):
        return self.model.masses

    def matrix_element_squared(self, sample):
        return self.model.selected_matrix_element_squared(sample, self.families)


def _histogram_prediction(low, high, reference: ReferenceCurve) -> PredictionCurve:
    if low.photon_energy_gev != high.photon_energy_gev or high.sobol_config.power != low.sobol_config.power+1:
        raise ValueError("baseline convergence requires consecutive Sobol powers at the same energy")
    a, b = low.histograms[reference.observable], high.histograms[reference.observable]
    if not np.array_equal(a.edges, b.edges):
        raise ValueError("baseline histograms require identical physical edges")
    error = np.abs(b.values-a.values)
    change = np.divide(error, np.abs(b.values), out=np.full_like(error, np.inf), where=b.values != 0)
    change[(a.values == 0) & (b.values == 0)] = 0.
    total_error = abs(high.partial_cross_section_microbarn-low.partial_cross_section_microbarn)
    total = high.partial_cross_section_microbarn
    total_ok = total_error < .01*abs(total) if total else total_error == 0
    converged = (change < .03) & total_ok
    centers = (a.edges[:-1]+a.edges[1:])/2
    # Extend first/last densities only to the physical edges, never outside.
    return PredictionCurve(np.r_[a.edges[0], centers, a.edges[-1]],
        np.r_[b.values[0], b.values, b.values[-1]], np.r_[error[0], error, error[-1]],
        np.r_[converged[0], converged, converged[-1]],
        "consecutive Sobol gate failed: total <1% and adjacent populated bins <3% required")


@dataclass(frozen=True)
class _CachedModel(EtaPi0PFullModel):
    """Run-local event memoization; inherited physical and diagnostic APIs unchanged.

    Parameters are immutable and local to this instance. Every uncached family
    delegates to the original dispatch, and all seven are still added before
    squaring. Nested Sobol prefixes can reuse identical amplitudes without
    repeating expensive direct checked quadrature. No interpolation is used.
    """

    _cache: dict = field(default_factory=dict, init=False, repr=False, compare=False)

    @property
    def evaluated_event_families(self):
        return len(self._cache)

    def _families(self, sample, polarization, names):
        self._validate_sample(sample)
        epsilon = _polarization(polarization)
        result = {}
        for name in names:
            keys = [(name, epsilon.tobytes(), sample.initial[i].tobytes(), sample.momenta[i].tobytes())
                    for i in range(len(sample.momenta))]
            missing = [i for i, key in enumerate(keys) if key not in self._cache]
            if missing:
                subset = replace(sample, initial=sample.initial[missing], momenta=sample.momenta[missing],
                    weights_gev2=sample.weights_gev2[missing], s12_gev2=sample.s12_gev2[missing])
                values = super()._families(subset, polarization, (name,))[name]
                for index, value in zip(missing, values):
                    self._cache[keys[index]] = value.copy()
            matrix = np.stack([self._cache[key] for key in keys])
            matrix.setflags(write=False)
            result[name] = matrix
        return MappingProxyType(result)


def _failed_prediction(reference: ReferenceCurve, reason: str) -> PredictionCurve:
    return PredictionCurve(reference.x, np.full_like(reference.x, np.nan),
        np.zeros_like(reference.x), np.zeros_like(reference.x, dtype=bool), reason)


def _prediction_record(prediction) -> dict:
    return {"photon_energy_gev": prediction.photon_energy_gev,
        "cross_section_microbarn": prediction.partial_cross_section_microbarn,
        "sample_size": prediction.sample_size, "sobol": asdict(prediction.sobol_config),
        "histograms": {name: {"edges": histogram.edges.tolist(), "density": histogram.values.tolist()}
                       for name, histogram in prediction.histograms.items()}}


def _baseline_conventions(parameters) -> list[str]:
    """Record conventions from the parameter record used by the calculation."""
    return [
        "All seven complex spin families sum coherently before spin and photon averages.",
        "Selected diagnostic adapters restrict only whole families and preserve inseparable gauge partners.",
        "Reconstructed full N*(1535) uses final-fit subtractions, pion correction and sourced modern masses.",
        "Quoted g_eta=1.7-1.4i and g_K=3.3+0.7i; Butler decuplet phases; empirical 1.15 correction.",
        "Lambda=1.4 GeV first-loop cutoff; direct +i0 checked quadrature with principal continuation.",
        f"Pion monopole form-factor cutoff Lambda_pi={parameters.production.pion_form_factor_cutoff_gev:g} GeV.",
        "No tuning to source curves; 20% source-relative allowance plus reading and numerical errors.",
        "Reduced coherent closure is unavailable; reduced source stroke stays unresolved.",
        "Individual resonance and split Sigma* strokes are unresolved; whole-family outputs are diagnostics only."]


def generate_baseline(reference_dir: Path, pdf_path: Path, output_dir: Path, *,
                      low_power: int = 4, bins: int = 8, quadrature=None,
                      command: str) -> tuple[Path, Path]:
    """Evaluate available source-energy observables without parameter tuning.

    Invalid direct quadrature is retained with its diagnostic error. Individual
    kernel and missing reduced-model comparisons stay unresolved; whole-family
    diagnostics are recorded separately rather than substituted for their data.
    """
    from .amplitudes.production_loops import QuadratureSettings
    from .observables import HistogramSpec, predict_energy
    from .phase_space import SobolConfig

    pdf_hash = hashlib.sha256(Path(pdf_path).read_bytes()).hexdigest()
    if pdf_hash != PDF_SHA256:
        raise ValueError("baseline primary-source PDF hash mismatch")
    root = Path(reference_dir)
    references = load_full_production_reference(root)
    controls = quadrature if quadrature is not None else QuadratureSettings()
    original = EtaPi0PFullModel.from_files(root)
    model = _CachedModel(replace(original.parameters,
        production=replace(original.parameters.production, quadrature=controls)))
    configurations = (SobolConfig(low_power), SobolConfig(low_power+1))
    histogram_spec = HistogramSpec(bins)
    predictions, diagnostics, failures = {}, {}, {}
    available = {}
    # Every producible isolated family at the source energy, including families
    # with unresolved individual-kernel mappings. Their baselines are distinct.
    for energy, family in [(1.2, family) for family in FAMILY_NAMES] + [(1.2, "full"), (1.202, "full")]:
        identity = f"{family}@{energy:.3f}"
        print(f"Evaluating real {identity}, Sobol {low_power}/{low_power+1}", flush=True)
        evaluator = model if family == "full" else _SelectedModel(model, (family,))
        pair, error = [], ""
        for config in configurations:
            try:
                calculated = predict_energy(energy, evaluator, config, histogram_spec)
                pair.append(calculated)
            except (ValueError, FloatingPointError, OverflowError) as exc:
                error = f"{identity}, Sobol power={config.power}: {exc}"
                failures[identity] = error
                print(f"Masked diagnostic: {error}", flush=True)
                break
        diagnostics[identity] = {"family": family, "photon_energy_gev": energy,
            "predictions": [_prediction_record(item) for item in pair], "failure_reason": error}
        available[(energy, family)] = (pair, error)
    for key, reference in references.items():
        if reference.unresolved:
            continue
        energy = reference.photon_energy_gev if reference.observable != "total" else float(reference.x[0])
        pair, error = available[(energy, reference.family)]
        if error:
            predictions[key] = _failed_prediction(reference, error)
        elif reference.observable == "eta_p":
            predictions[key] = _histogram_prediction(*pair, reference)
        else:
            low, high = (item.partial_cross_section_microbarn for item in pair)
            difference = abs(high-low)
            converged = difference < .01*abs(high) if high else difference == 0
            predictions[key] = PredictionCurve(reference.x, np.array([high]),
                np.array([difference]), np.array([converged]),
                "consecutive Sobol total cross-section gate failed (<1% required)" if not converged else "")
    parameter_files = ("central_parameters.json", "nstar1535_reduced_parameters.json",
        "nstar1535_final_subtractions.json", "nstar1535_vmd_masses.json", "eta_pi0_p_full_parameters.json",
        "nstar1535_charge_zero_extra.json", "sources.json")
    try:
        commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                                text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("baseline cannot capture git commit") from exc
    metadata = {"model": "EtaPi0PFullModel (run-local exact event cache)", "command": command,
        "working_directory": str(Path.cwd()), "python_version": sys.version,
        "config": {"sobol_powers": [low_power, low_power+1], "scramble": False, "seed": None,
            "bins": bins, "quadrature": asdict(controls), "source_energies_gev": [1.2, 1.202],
            "convergence_total_relative_limit": .01, "convergence_bin_relative_limit": .03},
        "git_commit": commit, "parameter_file_sha256": {
            name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in parameter_files},
        "pdf_sha256": pdf_hash, "reference_file_sha256": {
            name: hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
            (_CSV, _JSON, "figure14_eta_p_tree.csv", "figure19_total_1202.csv", "digitization.json")},
        "conventions": _baseline_conventions(model.parameters),
        "diagnostics": diagnostics, "numerical_failures": failures,
        "cached_event_family_polarization_count": model.evaluated_event_families,
        "step6_incomplete": ["Source-faithful reduced coherent model API is unavailable.",
            "Individual Fig.13 kernels and Fig.12 Eqs.40-41 are not separate whole-family diagnostics."],
        "digitization": json.loads((root/_JSON).read_text(encoding="utf-8"))}
    result = compare_full_production(predictions, references)
    paths = write_full_production_report(output_dir, result, metadata)
    print(json.dumps({"counts": result.counts, "total": result.total,
                      "reports": [str(path) for path in paths]}, allow_nan=False), flush=True)
    return paths


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--low-power", type=int, default=4)
    parser.add_argument("--bins", type=int, default=8)
    parser.add_argument("--q-order", type=int, default=64)
    parser.add_argument("--angle-order", type=int, default=48)
    parser.add_argument("--relative-tolerance", type=float, default=1e-5)
    parser.add_argument("--absolute-tolerance", type=float, default=1e-10)
    args = parser.parse_args(argv)
    from .amplitudes.production_loops import QuadratureSettings

    generate_baseline(args.reference_dir, args.pdf, args.output_dir,
        low_power=args.low_power, bins=args.bins,
        quadrature=QuadratureSettings(args.q_order, args.angle_order,
                                      args.relative_tolerance, args.absolute_tolerance),
        command=(f"PYTHONPATH={shlex.quote(os.environ['PYTHONPATH'])} " if "PYTHONPATH" in os.environ else "")
            + shlex.join(["python", "-m", "graal_theory.full_production_validation",
                          *(sys.argv[1:] if argv is None else argv)]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
