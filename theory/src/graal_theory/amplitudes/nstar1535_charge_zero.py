"""P65 Table I charge-zero reduced N*(1535) basis, in GeV."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from graal_theory.amplitudes import _reduced_t_core
from graal_theory.amplitudes.nstar1535_reduced import (
    ReducedTParameters,
    load_reduced_parameters,
)
from graal_theory.sources import PhysicalParameter, SourceRef, load_source_registry


CHANNELS_ZERO = (
    "k_plus_sigma_minus", "k0_sigma0", "k0_lambda",
    "pi_minus_p", "pi0_n", "eta_n",
)
CHANNEL_INDEX_ZERO = {name: index for index, name in enumerate(CHANNELS_ZERO)}
C_COEFFICIENTS_ZERO = np.array([
    [1, -np.sqrt(2), 0, 0, -1/np.sqrt(2), -np.sqrt(3/2)],
    [-np.sqrt(2), 0, 0, -1/np.sqrt(2), -1/2, np.sqrt(3)/2],
    [0, 0, 0, -np.sqrt(3/2), np.sqrt(3)/2, -3/2],
    [0, -1/np.sqrt(2), -np.sqrt(3/2), 1, -np.sqrt(2), 0],
    [-1/np.sqrt(2), -1/2, np.sqrt(3)/2, -np.sqrt(2), 0, 0],
    [-np.sqrt(3/2), np.sqrt(3)/2, -3/2, 0, 0, 0],
], dtype=float)
C_COEFFICIENTS_ZERO.setflags(write=False)


def load_charge_zero_parameters(
    parameter_path: Path, source_path: Path, extra_path: Path,
) -> ReducedTParameters:
    """Map source-linked P65 inputs into Table I charge-zero order."""
    p = load_reduced_parameters(parameter_path, source_path)
    raw = json.loads(extra_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != {"sigma_minus_mass"}:
        raise ValueError("sigma_minus_mass must be the only extra parameter")
    entry = raw["sigma_minus_mass"]
    if (not isinstance(entry, dict)
            or set(entry) != {"value", "unit", "source_key", "locator"}
            or entry["unit"] != "GeV"
            or entry["source_key"] != "pdg_2024"
            or not isinstance(entry["locator"], str)
            or not entry["locator"].strip()):
        raise ValueError("sigma_minus_mass has invalid unit or source fields")
    value = entry["value"]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("sigma_minus_mass requires a finite positive real value")
    try:
        value = float(value)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(
            "sigma_minus_mass requires a finite positive real value"
        ) from exc
    if not np.isfinite(value) or value <= 0:
        raise ValueError("sigma_minus_mass requires a finite positive real value")
    source = load_source_registry(source_path)["pdg_2024"]
    ref = SourceRef(entry["source_key"], source.get("doi") or source.get("arxiv"),
                    entry["locator"])
    sigma_minus = PhysicalParameter(
        "sigma_minus_mass", value, entry["unit"], ref,
    ).value
    return ReducedTParameters(
        meson_masses_gev=(p.meson_masses_gev[3], p.meson_masses_gev[5],
                          p.meson_masses_gev[5], p.meson_masses_gev[1],
                          p.meson_masses_gev[0], p.meson_masses_gev[2]),
        baryon_masses_gev=(sigma_minus, p.baryon_masses_gev[3],
                           p.baryon_masses_gev[4], p.baryon_masses_gev[0],
                           p.baryon_masses_gev[1], p.baryon_masses_gev[1]),
        decay_constants_gev=(p.decay_constants_gev[3],)*3 +
                            (p.decay_constants_gev[0], p.decay_constants_gev[1],
                             p.decay_constants_gev[2]),
        subtraction_constants=(p.subtraction_constants[3],)*2 +
                              (p.subtraction_constants[4], p.subtraction_constants[0],
                               p.subtraction_constants[1], p.subtraction_constants[2]),
        mu_gev=p.mu_gev,
    )


def charge_zero_wt_kernel(
    w_gev: float, parameters: ReducedTParameters,
) -> NDArray[np.float64]:
    """P65 Eq. (5) charge-zero Weinberg-Tomozawa kernel, in GeV^-1."""
    return _reduced_t_core.wt_kernel(w_gev, parameters, C_COEFFICIENTS_ZERO)


def charge_zero_loop_functions(
    w_gev: float, parameters: ReducedTParameters,
) -> NDArray[np.complex128]:
    """P65 Eq. (6) charge-zero physical-sheet loops, in GeV."""
    return _reduced_t_core.loop_functions(w_gev, parameters)


def charge_zero_tmatrix(
    w_gev: float, parameters: ReducedTParameters,
) -> NDArray[np.complex128]:
    """Solve (I - VG)T = V in P65 Table I channel order."""
    return _reduced_t_core.reduced_tmatrix(w_gev, parameters, C_COEFFICIENTS_ZERO)
