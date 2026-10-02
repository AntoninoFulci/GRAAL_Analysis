"""Sourced inputs and numerical controls for coherent production loops."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from math import isfinite
from numbers import Integral, Real
from pathlib import Path
from types import MappingProxyType
from typing import Mapping

from ..sources import PhysicalParameter, SourceRef, load_source_registry


def _finite_real(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"parameter {name!r} must be a finite real scalar")
    try:
        numeric = float(value)
    except (ValueError, OverflowError):
        raise ValueError(f"parameter {name!r} must be a finite real scalar") from None
    if not isfinite(numeric):
        raise ValueError(f"parameter {name!r} must be a finite real scalar")
    return numeric


@dataclass(frozen=True)
class QuadratureSettings:
    """Validated reproducibility controls, separate from physical provenance."""

    q_order: int = 64
    angle_order: int = 48
    relative_tolerance: float = 1e-5
    absolute_tolerance: float = 1e-10

    def __post_init__(self) -> None:
        for name in ("q_order", "angle_order"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, Integral) or value < 16:
                raise ValueError(f"{name} must be a non-bool integer >=16")
        for name in ("relative_tolerance", "absolute_tolerance"):
            if _finite_real(getattr(self, name), name) <= 0:
                raise ValueError(f"{name} must be positive")


@dataclass(frozen=True)
class ProductionParameters:
    electric_charge: float
    axial_d: float
    axial_f: float
    b6d: float
    b6f: float
    first_loop_cutoff_gev: float
    pion_form_factor_cutoff_gev: float
    nstar1520_mass_gev: float
    nstar1520_npi_width_gev: float
    f_tilde_nstar_delta_pi: float
    g_tilde_nstar_delta_pi: float
    g1_nstar_per_gev: float
    g2_nstar_per_gev2: float
    g_rho_nstar: float
    sigma_star_mass_gev: float
    sigma_star_width_gev: float
    g_k_sigma_star: complex
    sigma_star_su3_correction: float
    quadrature: QuadratureSettings
    provenance: Mapping[str, PhysicalParameter] = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        # Copy before freezing so retained caller dictionaries cannot mutate it.
        object.__setattr__(self, "provenance", MappingProxyType(dict(self.provenance)))


_SCHEMA = {
    "electric_charge": ("1", "nacher_2001"),
    "axial_d": ("1", "doering_2006_prc"),
    "axial_f": ("1", "doering_2006_prc"),
    "b6d": ("1", "doering_2006_prc"),
    "b6f": ("1", "doering_2006_prc"),
    "first_loop_cutoff_gev": ("GeV", "doering_2006_prc"),
    "pion_form_factor_cutoff_gev": ("GeV", "doering_2006_prc"),
    "nstar1520_mass_gev": ("GeV", "nacher_2001"),
    "nstar1520_npi_width_gev": ("GeV", "nacher_2001"),
    "f_tilde_nstar_delta_pi": ("1", "nacher_2001"),
    "g_tilde_nstar_delta_pi": ("1", "nacher_2001"),
    "g1_nstar": ("m_N^-1", "nacher_2001"),
    "g2_nstar": ("m_N^-2", "nacher_2001"),
    "g_rho_nstar": ("1", "nacher_2001"),
    "sigma_star_mass_gev": ("GeV", "pdg_2024"),
    "sigma_star_width_gev": ("GeV", "doering_2006_prc"),
    "g_k_sigma_star": ("1", "doering_2006_prc"),
    "sigma_star_su3_correction": ("1", "doering_2006_prc"),
    "proton_mass": ("GeV", "pdg_2024"),
}
_POSITIVE = frozenset({
    "first_loop_cutoff_gev", "pion_form_factor_cutoff_gev",
    "nstar1520_mass_gev", "sigma_star_mass_gev", "proton_mass",
})
_WIDTHS = frozenset({"nstar1520_npi_width_gev", "sigma_star_width_gev"})


def load_production_parameters(parameter_path: Path, source_path: Path) -> ProductionParameters:
    """Load a closed source-linked record, retaining source units in provenance.

    The proton mass is a sourced conversion input, not a new production field.
    Electromagnetic couplings are returned in GeV^-1 and GeV^-2, matching the
    existing Delta1700Parameters nucleon-mass convention.
    """
    raw = json.loads(parameter_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("production parameters must be an object")
    missing = sorted(_SCHEMA.keys() - raw.keys())
    unexpected = sorted(raw.keys() - _SCHEMA.keys())
    if missing or unexpected:
        raise ValueError(f"production parameter names: missing={missing}, unexpected={unexpected}")
    sources = load_source_registry(source_path)
    provenance = {}
    for name, (unit, source_key) in _SCHEMA.items():
        entry = raw[name]
        if not isinstance(entry, dict) or set(entry) != {"value", "unit", "source_key", "locator"}:
            raise ValueError(f"parameter {name!r} requires value, unit, source_key, locator")
        if entry["unit"] != unit:
            raise ValueError(f"parameter {name!r} requires unit {unit!r}")
        if entry["source_key"] != source_key or source_key not in sources:
            raise ValueError(f"parameter {name!r} requires registered source {source_key!r}")
        locator = entry["locator"]
        if not isinstance(locator, str) or not locator.strip() or "://" in locator:
            raise ValueError(f"parameter {name!r} requires a source locator")
        value = entry["value"]
        if name == "g_k_sigma_star":
            if not isinstance(value, dict) or set(value) != {"real", "imag"}:
                raise ValueError(f"parameter {name!r} requires real and imag components")
            numeric = complex(_finite_real(value["real"], name), _finite_real(value["imag"], name))
        else:
            numeric = _finite_real(value, name)
            if name in _POSITIVE and numeric <= 0:
                raise ValueError(f"parameter {name!r} must be positive")
            if name in _WIDTHS and numeric < 0:
                raise ValueError(f"parameter {name!r} must be nonnegative")
        record = sources[source_key]
        ref = SourceRef(source_key, record.get("doi") or record.get("arxiv"), locator)
        provenance[name] = PhysicalParameter(name, numeric, unit, ref)
    values = {name: parameter.value for name, parameter in provenance.items()}
    proton_mass = values.pop("proton_mass")
    for name, field_name, power in (
        ("g1_nstar", "g1_nstar_per_gev", 1),
        ("g2_nstar", "g2_nstar_per_gev2", 2),
    ):
        try:
            converted = values.pop(name) / proton_mass**power
        except (ZeroDivisionError, OverflowError):
            raise ValueError(f"parameter {name!r} has nonfinite unit conversion") from None
        values[field_name] = _finite_real(converted, name)
    return ProductionParameters(**values, quadrature=QuadratureSettings(), provenance=provenance)
