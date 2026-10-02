"""Six-channel N*(1535) VMD kernel with source-linked vector masses."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from scipy.optimize import brentq

from graal_theory.amplitudes import _reduced_t_core
from graal_theory.amplitudes.nstar1535_reduced import C_COEFFICIENTS, ReducedTParameters
from graal_theory.amplitudes.vmd import angular_factor
from graal_theory.sources import PhysicalParameter, SourceRef, load_source_registry


# Charge-channel convention: equal meson strangeness exchanges rho; changed
# meson strangeness exchanges K*. Zero WT coefficients carry no exchange.
MESON_STRANGENESS = (0, 0, 0, 1, 1, 1)
VECTOR_SPECIES = tuple(tuple(
    None if C_COEFFICIENTS[i, j] == 0 else
    "rho" if MESON_STRANGENESS[i] == MESON_STRANGENESS[j] else "kstar"
    for j in range(6)) for i in range(6))


@dataclass(frozen=True)
class VectorMasses:
    rho_gev: float
    kstar_gev: float

    def __post_init__(self) -> None:
        for name in ("rho_gev", "kstar_gev"):
            value = getattr(self, name)
            if (isinstance(value, (bool, np.bool_))
                    or not isinstance(value, (int, float, np.integer, np.floating))
                    or not np.isfinite(value) or value <= 0):
                raise ValueError(f"{name} must be a finite positive real")


def load_vector_masses(parameter_path: Path, source_path: Path) -> VectorMasses:
    """Load positive GeV masses with the Inoue source and paper locators."""
    raw = json.loads(parameter_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"m_rho", "m_kstar"}:
        raise ValueError("VMD parameter names differ from source schema")
    sources = load_source_registry(source_path)
    values = {}
    for name in ("m_rho", "m_kstar"):
        entry = raw[name]
        if (not isinstance(entry, dict)
                or set(entry) != {"value", "unit", "source_key", "locator"}
                or entry["unit"] != "GeV"
                or entry["source_key"] != "inoue_2002"
                or "inoue_2002" not in sources
                or not isinstance(entry["locator"], str)
                or not entry["locator"].strip()
                or "://" in entry["locator"]
                or isinstance(entry["value"], (bool, np.bool_))
                or not isinstance(entry["value"], (int, float, np.integer, np.floating))
                or not np.isfinite(entry["value"])
                or entry["value"] <= 0):
            raise ValueError(f"invalid VMD entry {name}")
        source = sources["inoue_2002"]
        ref = SourceRef("inoue_2002", source.get("doi") or source.get("arxiv"),
                        entry["locator"])
        values[name] = float(PhysicalParameter(
            name, float(entry["value"]), "GeV", ref).value)
    return VectorMasses(values["m_rho"], values["m_kstar"])


def _factor(
    w_gev: float, i: int, j: int, parameters: ReducedTParameters, masses: VectorMasses,
) -> float:
    mass = masses.rho_gev if VECTOR_SPECIES[i][j] == "rho" else masses.kstar_gev
    return angular_factor(
        w_gev, parameters.meson_masses_gev[i], parameters.baryon_masses_gev[i],
        parameters.meson_masses_gev[j], parameters.baryon_masses_gev[j], mass,
    )


@lru_cache(maxsize=128)
def switching_energies(
    parameters: ReducedTParameters, masses: VectorMasses,
) -> NDArray[np.float64]:
    """Return read-only F=1 switches in GeV, bracketed by pair thresholds.

    Only nonzero WT pairs are evaluated. Zero coefficients have NaN switches;
    a missing crossing raises rather than silently changing the prescription.
    """
    roots = np.full((6, 6), np.nan, dtype=float)
    thresholds = np.add(parameters.meson_masses_gev, parameters.baryon_masses_gev)
    for i in range(6):
        for j in range(i, 6):
            if C_COEFFICIENTS[i, j] == 0:
                continue
            lo, hi = sorted((thresholds[i], thresholds[j]))
            f_lo = _factor(lo, i, j, parameters, masses) - 1.0
            f_hi = _factor(hi, i, j, parameters, masses) - 1.0
            if abs(f_lo) <= 1e-12:
                root = lo
            elif abs(f_hi) <= 1e-12:
                root = hi
            elif hi <= lo or f_lo * f_hi >= 0:
                raise ValueError(f"VMD switch not bracketed for ({i},{j})")
            else:
                root = brentq(
                    lambda w: _factor(w, i, j, parameters, masses) - 1.0,
                    lo, hi, xtol=1e-12,
                )
            roots[i, j] = roots[j, i] = root
    # Immutable bytes prevent callers from re-enabling writes to cached data.
    return np.frombuffer(roots.tobytes(), dtype=np.float64).reshape((6, 6))


def corrected_coefficients(
    w_gev: float, parameters: ReducedTParameters, masses: VectorMasses,
) -> NDArray[np.float64]:
    """Replace each nonzero C by C F(W) strictly above its pair switch."""
    w = _reduced_t_core.validated_energy(w_gev, parameters)
    roots = switching_energies(parameters, masses)
    result = C_COEFFICIENTS.copy()
    for i in range(6):
        for j in range(i, 6):
            if C_COEFFICIENTS[i, j] != 0 and w > roots[i, j]:
                value = C_COEFFICIENTS[i, j] * _factor(w, i, j, parameters, masses)
                result[i, j] = result[j, i] = value
    result.setflags(write=False)
    return result


def vmd_kernel(
    w_gev: float, parameters: ReducedTParameters, masses: VectorMasses,
) -> NDArray[np.float64]:
    """WT Eq. (5) kernel in GeV^-1 with the VMD coefficients substituted."""
    w = _reduced_t_core.validated_energy(w_gev, parameters)
    return _reduced_t_core.wt_kernel(
        w, parameters, corrected_coefficients(w, parameters, masses))
