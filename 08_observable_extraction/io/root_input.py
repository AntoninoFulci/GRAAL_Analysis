"""Read public beam-asymmetry points back from ROOT output files."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import math
import json

import numpy as np
from pathlib import Path

import ROOT

from graal_common.physics.channels import M_ETA, M_PI0
from observable_extraction.core.models import FitDiagnostics, SigmaPoint
from observable_extraction.core.binning import PHI_EDGES_RAD, PHI_BIN_DIVISORS, phi_bin_divisor
from observable_extraction.io.root_output import OutputPoint, ordered_point_keys, point_key_label
from observable_extraction.core.systematics import validate_covariance


@contextmanager
def _open_output(path):
    """Keep every detached ROOT reader within the same file lifetime contract."""
    source = ROOT.TFile.Open(str(path), "READ")
    if not source or source.IsZombie():
        raise RuntimeError(f"cannot open beam-asymmetry ROOT file: {path}")
    try:
        yield source
    finally:
        source.Close()


@dataclass(frozen=True)
class CandleContract:
    """Selection definition and counts stored for a candle extraction."""

    eta_center_gev: float
    pi0_center_gev: float
    mass_half_width_gev: float
    geometry: str
    core_logic: str
    tail_logic: str
    boundary: str
    baseline_event_count: int
    full_core_event_count: int
    tail_event_count: int
    balanced_core_event_count: int
    excluded_nonfinite_event_count: int
    balance_method: str
    balance_seed: int
    mass_source: str


@dataclass(frozen=True)
class RootOutputContract:
    """Profile identity and energy/azimuth binning stored in one ROOT output."""

    profile: str | None
    energy_edges_gev: tuple[float, ...]
    phi_edges_rad: tuple[float, ...] = tuple(PHI_EDGES_RAD)
    phi_bin_divisor: float | None = 1.0
    explicit_energy_grid: bool = False
    best_binning: bool = False
    candle: CandleContract | None = None


def _provenance_values(text: str) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator:
            values.setdefault(key.strip(), []).append(value.strip())
    return values


def _parse_candle_contract(
    values: dict[str, list[str]], path: Path
) -> CandleContract | None:
    candle_keys = {key for key in values if key.startswith("candle_")}
    if not candle_keys:
        return None
    required = {
        "candle_enabled",
        "candle_eta_center_gev",
        "candle_pi0_center_gev",
        "candle_mass_half_width_gev",
        "candle_geometry",
        "candle_core_logic",
        "candle_tail_logic",
        "candle_boundary",
        "candle_baseline_event_count",
        "candle_full_core_event_count",
        "candle_tail_event_count",
        "candle_balanced_core_event_count",
        "candle_excluded_nonfinite_event_count",
        "candle_balance_method",
        "candle_balance_seed",
        "candle_mass_source",
    }
    try:
        if candle_keys != required:
            raise ValueError("incomplete or unknown candle fields")

        def one(name: str) -> str:
            entries = values.get(name, [])
            if len(entries) != 1 or not entries[0]:
                raise ValueError(f"invalid {name}")
            return entries[0]

        if one("candle_enabled") != "true":
            raise ValueError("candle must be explicitly enabled")
        eta_center = float(one("candle_eta_center_gev"))
        pi0_center = float(one("candle_pi0_center_gev"))
        width = float(one("candle_mass_half_width_gev"))
        baseline_count = int(one("candle_baseline_event_count"))
        full_core_count = int(one("candle_full_core_event_count"))
        tail_count = int(one("candle_tail_event_count"))
        balanced_core_count = int(one("candle_balanced_core_event_count"))
        excluded_nonfinite_count = int(
            one("candle_excluded_nonfinite_event_count")
        )
        balance_seed = int(one("candle_balance_seed"))
        if not math.isclose(
            eta_center, M_ETA, rel_tol=0.0, abs_tol=1e-12
        ) or not math.isclose(
            pi0_center, M_PI0, rel_tol=0.0, abs_tol=1e-12
        ):
            raise ValueError("candidate-mass centers do not match shared constants")
        if not math.isfinite(width) or width <= 0.0:
            raise ValueError("invalid candle width")
        if baseline_count <= 0 or full_core_count <= 0 or tail_count <= 0:
            raise ValueError("candle counts must be positive")
        if excluded_nonfinite_count < 0:
            raise ValueError("excluded non-finite count must be non-negative")
        if full_core_count + tail_count + excluded_nonfinite_count != baseline_count:
            raise ValueError("candle region counts do not match baseline")
        if balanced_core_count != tail_count or full_core_count < tail_count:
            raise ValueError("candle samples are not balanceable and equal")
        if balance_seed < 0:
            raise ValueError("invalid candle balance seed")
        semantics = {
            "candle_geometry": "rectangular",
            "candle_core_logic": "and",
            "candle_tail_logic": "or_complement",
            "candle_boundary": "inclusive",
            "candle_balance_method": "random_without_replacement",
            "candle_mass_source": "raw_pre_fit",
        }
        if any(one(name) != expected for name, expected in semantics.items()):
            raise ValueError("invalid candle selection semantics")
        return CandleContract(
            eta_center_gev=eta_center,
            pi0_center_gev=pi0_center,
            mass_half_width_gev=width,
            geometry=one("candle_geometry"),
            core_logic=one("candle_core_logic"),
            tail_logic=one("candle_tail_logic"),
            boundary=one("candle_boundary"),
            baseline_event_count=baseline_count,
            full_core_event_count=full_core_count,
            tail_event_count=tail_count,
            balanced_core_event_count=balanced_core_count,
            excluded_nonfinite_event_count=excluded_nonfinite_count,
            balance_method=one("candle_balance_method"),
            balance_seed=balance_seed,
            mass_source=one("candle_mass_source"),
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{path}: invalid candle provenance") from exc


def _id_maps(text: str, path: Path) -> dict[str, dict[int, str]]:
    maps: dict[str, dict[int, str]] = {
        "sample": {},
        "estimator": {},
        "pair": {},
    }
    try:
        for line in text.splitlines():
            kind, raw_id, name = line.split(maxsplit=2)
            if kind not in maps or not name:
                raise ValueError
            identifier = int(raw_id)
            if identifier in maps[kind]:
                raise ValueError
            maps[kind][identifier] = name
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"{path}: malformed id_mapping") from exc
    if any(not values for values in maps.values()):
        raise RuntimeError(f"{path}: malformed id_mapping")
    return maps


def _mapped(
    maps: dict[str, dict[int, str]], kind: str, identifier: int, path: Path
) -> str:
    try:
        return maps[kind][identifier]
    except KeyError as exc:
        raise RuntimeError(
            f"{path}: id_mapping has no {kind} id {identifier}"
        ) from exc


def _optional_finite(value: float) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def read_output_contract(path: Path) -> RootOutputContract:
    """Read profile metadata and energy edges needed for safe composition."""
    path = Path(path)
    with _open_output(path) as source:
        vector = source.Get("binning/energy_edges")
        if not vector or not hasattr(vector, "GetNrows"):
            raise RuntimeError(f"{path}: missing binning/energy_edges")
        edges = tuple(float(vector[index]) for index in range(vector.GetNrows()))
        if (
            len(edges) < 2
            or not all(math.isfinite(edge) for edge in edges)
            or any(high <= low for low, high in zip(edges[:-1], edges[1:]))
        ):
            raise RuntimeError(f"{path}: invalid binning/energy_edges")

        provenance = source.Get("provenance")
        profile = None
        divisor_values = []
        explicit_energy_grid = False
        provenance_text = ""
        if provenance:
            if not provenance.InheritsFrom("TNamed"):
                raise RuntimeError(f"{path}: malformed provenance")
            provenance_text = provenance.GetTitle()
            profile_values = [
                line.partition("=")[2].strip()
                for line in provenance_text.splitlines()
                if line.startswith("profile=")
            ]
            if len(profile_values) > 1 or (
                profile_values and not profile_values[0]
            ):
                raise RuntimeError(f"{path}: malformed profile provenance")
            if profile_values:
                profile = profile_values[0]
            divisor_values = [
                line.partition("=")[2].strip()
                for line in provenance_text.splitlines()
                if line.startswith("phi_bin_divisor=")
            ]
        if provenance:
            declarations = [line.partition("=")[2] for line in provenance_text.splitlines()
                            if line.startswith("energy_edges_gev=")]
            if declarations:
                try:
                    if len(declarations) != 1 or profile is None:
                        raise ValueError("grid requires unique declaration and beam profile")
                    from graal_common.physics.energy_binning import EnergyBinning
                    from graal_common.physics.beam_profiles import get_beam_profile
                    declared = EnergyBinning(json.loads(declarations[0])).validate_profile(get_beam_profile(profile))
                    if declared.edges_gev != edges:
                        raise ValueError("energy edges disagree with provenance")
                    explicit_energy_grid = True
                except (TypeError, ValueError) as exc:
                    raise RuntimeError(f"{path}: invalid energy grid provenance: {exc}") from exc
        vector = source.Get("binning/phi_edges")
        # Legacy Stage-07 outputs enforced exactly 12 phi bins.
        phi_edges = tuple(PHI_EDGES_RAD)
        if vector:
            if not hasattr(vector, "GetNrows"):
                raise RuntimeError(f"{path}: invalid binning/phi_edges")
            phi_edges = tuple(float(vector[index]) for index in range(vector.GetNrows()))
            if (
                len(phi_edges) < 2
                or not all(math.isfinite(edge) for edge in phi_edges)
                or any(high <= low for low, high in zip(phi_edges[:-1], phi_edges[1:]))
            ):
                raise RuntimeError(f"{path}: invalid binning/phi_edges")
        # Absent metadata identifies older, uncorrected center-fit outputs.
        divisor = 1.0
        best_binning = "phi_bins=best-binning" in provenance_text.splitlines()
        if best_binning:
            if divisor_values != ["per_point"]:
                raise RuntimeError(f"{path}: best-binning requires per-point phi_bin_divisor")
            divisor = None
            # Verify per-point correction metadata before allowing composition.
            read_output_points(path)
        elif divisor_values:
            try:
                if len(divisor_values) != 1:
                    raise ValueError("duplicate divisor")
                divisor = float(divisor_values[0])
                if not math.isfinite(divisor) or not math.isclose(
                    divisor, phi_bin_divisor(phi_edges), rel_tol=0.0, abs_tol=1e-12
                ):
                    raise ValueError("divisor does not match phi edges")
            except ValueError as exc:
                raise RuntimeError(f"{path}: invalid phi_bin_divisor provenance") from exc
        return RootOutputContract(
            profile=profile, energy_edges_gev=edges,
            phi_edges_rad=phi_edges, phi_bin_divisor=divisor, explicit_energy_grid=explicit_energy_grid,
            best_binning=best_binning,
            candle=_parse_candle_contract(_provenance_values(provenance_text), path),
        )


def read_output_points(path: Path) -> tuple[OutputPoint, ...]:
    """Rebuild immutable output-point contracts from one ROOT result file."""
    path = Path(path)
    with _open_output(path) as source:
        provenance = source.Get("provenance")
        best_binning = bool(provenance and "phi_bins=best-binning" in provenance.GetTitle().splitlines())
        tree = source.Get("sigma_points")
        if not tree or not tree.InheritsFrom("TTree"):
            raise RuntimeError(f"{path}: missing sigma_points TTree")
        if tree.GetEntries() == 0:
            metadata = source.Get("extraction_metadata")
            if metadata and json.loads(metadata.GetTitle()).get("status") == "not_estimable":
                return ()
            raise RuntimeError(f"{path}: empty sigma_points without non-estimable status")
        mapping = source.Get("id_mapping")
        if not mapping or not mapping.InheritsFrom("TNamed"):
            raise RuntimeError(f"{path}: missing id_mapping")
        maps = _id_maps(mapping.GetTitle(), path)

        kinds_object = source.Get("point_uncertainty_kinds")
        kinds = json.loads(kinds_object.GetTitle()) if kinds_object else None
        if kinds is not None and len(kinds) != tree.GetEntries():
            raise RuntimeError(f"{path}: uncertainty kinds dimension mismatch")
        points = []
        for row in tree:
            diagnostics = FitDiagnostics(
                converged=bool(row.fit_converged),
                chi2=float(row.fit_chi2),
                ndf=int(row.fit_ndf),
                p_value=float(row.fit_p_value),
                used_fallback=bool(row.used_fallback),
                c0=_optional_finite(row.c0),
                s2=_optional_finite(row.s2),
            )
            point = SigmaPoint(
                pair=_mapped(maps, "pair", int(row.pair_id), path),
                energy_bin=int(row.energy_bin),
                mass_bin=int(row.mass_bin),
                energy_low_gev=float(row.energy_low_gev),
                energy_high_gev=float(row.energy_high_gev),
                mass_low_gev=float(row.mass_low_gev),
                mass_high_gev=float(row.mass_high_gev),
                mass_mean_gev=float(row.mass_mean_gev),
                sigma=float(row.sigma),
                stat_low=float(row.stat_low),
                stat_high=float(row.stat_high),
                diagnostics=diagnostics,
            )
            points.append(
                OutputPoint(
                    phi_bins=_read_phi_bins(row, tree, maps, path, best_binning),
                    uncertainty_kind=kinds[len(points)] if kinds is not None else "legacy_stat_branches_unclassified",
                    sample=_mapped(maps, "sample", int(row.sample_id), path),
                    estimator=_mapped(
                        maps, "estimator", int(row.estimator_id), path
                    ),
                    point=point,
                    sigma_uncorrected=float(row.sigma_uncorrected),
                    systematic_total=float(row.syst_total),
                    background_fraction=float(row.background_fraction),
                    count_vertical=int(row.count_vertical),
                    count_horizontal=int(row.count_horizontal),
                    flux_vertical=float(row.flux_vertical),
                    flux_horizontal=float(row.flux_horizontal),
                    polarization_vertical=float(row.polarization_vertical),
                    polarization_horizontal=float(row.polarization_horizontal),
                )
            )
        return tuple(points)


def _read_phi_bins(row, tree, maps, path, best_binning):
    bins = int(row.phi_bins) if tree.GetBranch("phi_bins") else 0
    estimator = _mapped(maps, "estimator", int(row.estimator_id), path)
    if bins not in (0, *PHI_BIN_DIVISORS) or (estimator == "likelihood" and bins):
        raise RuntimeError(f"{path}: invalid per-point phi_bins")
    if best_binning and estimator == "ratio" and not bins:
        raise RuntimeError(f"{path}: best-binning requires per-point phi_bins")
    if bins:
        if not tree.GetBranch("phi_bin_divisor") or not math.isclose(
            float(row.phi_bin_divisor), PHI_BIN_DIVISORS[bins], rel_tol=0, abs_tol=1e-12
        ):
            raise RuntimeError(f"{path}: invalid per-point phi_bin_divisor")
    return bins


@dataclass(frozen=True)
class RootUncertainties:
    point_keys: tuple[dict, ...] | None
    matrices: dict[str, np.ndarray]
    metadata: dict


def read_output_uncertainties(path: Path) -> RootUncertainties:
    """Detach matrices and audit metadata; legacy zeros carry no independence claim."""
    path = Path(path)
    points = read_output_points(path)
    with _open_output(path) as source:
        keys_object = source.Get("covariance/point_keys")
        point_keys = tuple(json.loads(keys_object.GetTitle())) if keys_object else None
        if point_keys is not None:
            if len(point_keys) != len(points):
                raise ValueError("covariance point keys dimension mismatch")
            if point_keys and list(point_keys) != ordered_point_keys(points, point_keys[0]):
                raise ValueError("covariance point keys do not match sigma_points order")
        metadata_object = source.Get("covariance/uncertainty_metadata")
        metadata = json.loads(metadata_object.GetTitle()) if metadata_object else {
            "schema": "legacy", "statistical_correlations": "unknown",
            "source_availability": "unknown", "final_inference": "unvalidated",
        }
        matrices = {}
        def visit(directory, prefix=""):
            if not directory:
                return
            for key in directory.GetListOfKeys():
                obj = directory.Get(key.GetName())
                name = prefix + key.GetName()
                if obj.InheritsFrom("TDirectory"):
                    visit(obj, name + "/")
                elif obj.InheritsFrom("TH2"):
                    size = len(points)
                    if obj.GetNbinsX() != size or obj.GetNbinsY() != size:
                        raise ValueError(f"{name}: covariance dimension mismatch")
                    if point_keys is not None:
                        for index, point_key in enumerate(point_keys, 1):
                            expected = point_key_label(point_key)
                            if (obj.GetXaxis().GetBinLabel(index) != expected
                                    or obj.GetYaxis().GetBinLabel(index) != expected):
                                raise ValueError(f"{name}: covariance axis keys mismatch")
                    matrix = np.array([[obj.GetBinContent(i + 1, j + 1) for j in range(size)]
                                       for i in range(size)])
                    matrices[name] = validate_covariance(matrix, size=size)
        visit(source.GetDirectory("covariance"))
        if points and "total" not in matrices:
            raise ValueError("missing total covariance")
        if "statistical" in matrices:
            expected = matrices["statistical"] + sum(
                (matrix for name, matrix in matrices.items() if name.startswith("systematic/")),
                np.zeros_like(matrices["total"]))
            if not np.allclose(expected, matrices["total"], rtol=1e-10, atol=1e-12):
                raise ValueError("total covariance does not close")
        return RootUncertainties(point_keys, matrices, metadata)


def read_bootstrap_diagnostics(path: Path):
    """Read the complete diagnostic ensemble; absent study returns None."""
    from observable_extraction.core.systematics import PairedBootstrapResult

    with _open_output(path) as source:
        directory = source.GetDirectory("diagnostics/paired_bootstrap")
        if not directory:
            return None
        metadata = json.loads(directory.Get("metadata").GetTitle())
        keys = tuple(metadata["point_keys"])
        count = metadata["replicas"]
        values = np.full((count, len(keys)), np.nan)
        seen = set()
        for row in directory.Get("replicas"):
            index = (int(row.replica), int(row.point_index))
            if index in seen or not (0 <= index[0] < count and 0 <= index[1] < len(keys)):
                raise ValueError("invalid or duplicate bootstrap replica index")
            seen.add(index)
            values[index] = float(row.sigma)
        if len(seen) != values.size:
            raise ValueError("incomplete bootstrap replicas")
        draws = [[] for _ in range(count)]
        for row in directory.Get("run_draws"):
            index = int(row.replica)
            if not 0 <= index < count or int(row.draw_index) != len(draws[index]):
                raise ValueError("invalid bootstrap run draw index")
            draws[index].append(int(row.run_number))
        if any(len(draw) != metadata["draws_per_replica"] for draw in draws):
            raise ValueError("incomplete bootstrap run draw history")
        def matrix(name):
            obj = directory.Get(name)
            if not obj:
                return None
            if obj.GetNbinsX() != len(keys) or obj.GetNbinsY() != len(keys):
                raise ValueError("bootstrap matrix dimension mismatch")
            for index, key in enumerate(keys, 1):
                if obj.GetXaxis().GetBinLabel(index) != key or obj.GetYaxis().GetBinLabel(index) != key:
                    raise ValueError("bootstrap matrix point keys mismatch")
            return np.array([[obj.GetBinContent(i + 1, j + 1) for j in range(len(keys))]
                             for i in range(len(keys))])
        covariance = matrix("covariance")
        failures = {int(key): value for key, value in metadata["failures"].items()}
        if covariance is not None:
            validate_covariance(covariance, size=len(keys))
            if failures or not np.isfinite(values).all():
                raise ValueError("failed bootstrap replicas cannot have covariance")
        return PairedBootstrapResult(
            keys, values, tuple(tuple(draw) for draw in draws), failures, covariance,
            matrix("covariance_mc_error"), metadata["rank"],
            {name: tuple(runs) for name, runs in metadata["zero_event_runs"].items()},
            metadata["effective_runs"], metadata["seed"])
