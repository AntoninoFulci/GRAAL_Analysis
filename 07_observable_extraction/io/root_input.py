"""Read public beam-asymmetry points back from ROOT output files."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path

import ROOT

from observable_extraction.core.models import FitDiagnostics, SigmaPoint
from observable_extraction.core.binning import PHI_EDGES_RAD, phi_bin_divisor
from observable_extraction.io.root_output import OutputPoint


@dataclass(frozen=True)
class RootOutputContract:
    """Profile identity and energy/azimuth binning stored in one ROOT output."""

    profile: str | None
    energy_edges_gev: tuple[float, ...]
    phi_edges_rad: tuple[float, ...] = tuple(PHI_EDGES_RAD)
    phi_bin_divisor: float = 1.0


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
    source = ROOT.TFile.Open(str(path), "READ")
    if not source or source.IsZombie():
        raise RuntimeError(f"cannot open beam-asymmetry ROOT file: {path}")
    try:
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
        if provenance:
            if not provenance.InheritsFrom("TNamed"):
                raise RuntimeError(f"{path}: malformed provenance")
            profile_values = [
                line.partition("=")[2].strip()
                for line in provenance.GetTitle().splitlines()
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
                for line in provenance.GetTitle().splitlines()
                if line.startswith("phi_bin_divisor=")
            ]
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
        if divisor_values:
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
            phi_edges_rad=phi_edges, phi_bin_divisor=divisor,
        )
    finally:
        source.Close()


def read_output_points(path: Path) -> tuple[OutputPoint, ...]:
    """Rebuild immutable output-point contracts from one ROOT result file."""
    path = Path(path)
    source = ROOT.TFile.Open(str(path), "READ")
    if not source or source.IsZombie():
        raise RuntimeError(f"cannot open beam-asymmetry ROOT file: {path}")
    try:
        tree = source.Get("sigma_points")
        if not tree or not tree.InheritsFrom("TTree"):
            raise RuntimeError(f"{path}: missing sigma_points TTree")
        mapping = source.Get("id_mapping")
        if not mapping or not mapping.InheritsFrom("TNamed"):
            raise RuntimeError(f"{path}: missing id_mapping")
        maps = _id_maps(mapping.GetTitle(), path)

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
    finally:
        source.Close()
