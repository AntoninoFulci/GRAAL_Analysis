"""Reduced charge-+1 N*(1535) coupled-channel strong interaction, in GeV."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from numpy.typing import NDArray

from graal_theory.sources import PhysicalParameter, SourceRef, load_source_registry


CHANNELS = (
    "pi0_p", "pi_plus_n", "eta_p", "k_plus_sigma0", "k_plus_lambda", "k0_sigma_plus",
)
C_COEFFICIENTS = np.array([
    [0, np.sqrt(2), 0, -0.5, -np.sqrt(3)/2, 1/np.sqrt(2)],
    [np.sqrt(2), 1, 0, 1/np.sqrt(2), -np.sqrt(3/2), 0],
    [0, 0, 0, -np.sqrt(3)/2, -1.5, -np.sqrt(3/2)],
    [-0.5, 1/np.sqrt(2), -np.sqrt(3)/2, 0, 0, np.sqrt(2)],
    [-np.sqrt(3)/2, -np.sqrt(3/2), -1.5, 0, 0, 0],
    [1/np.sqrt(2), 0, -np.sqrt(3/2), np.sqrt(2), 0, 1],
], dtype=float)
C_COEFFICIENTS.setflags(write=False)


@dataclass(frozen=True)
class ReducedTParameters:
    meson_masses_gev: tuple[float, ...]
    baryon_masses_gev: tuple[float, ...]
    decay_constants_gev: tuple[float, ...]
    subtraction_constants: tuple[float, ...]
    mu_gev: float

    def __post_init__(self) -> None:
        for name in ("meson_masses_gev", "baryon_masses_gev",
                     "decay_constants_gev", "subtraction_constants"):
            values = getattr(self, name)
            if len(values) != 6 or not np.all(np.isfinite(values)):
                raise ValueError(f"{name} requires six finite values")
            if name != "subtraction_constants" and any(value <= 0 for value in values):
                raise ValueError(f"{name} requires positive values")
        if not np.isfinite(self.mu_gev) or self.mu_gev <= 0:
            raise ValueError("mu_gev must be finite and positive")


_MASS_NAMES = (
    "pi0_mass", "charged_pion_mass", "eta_mass", "charged_kaon_mass",
    "neutral_kaon_mass", "proton_mass", "neutron_mass", "sigma0_mass",
    "sigma_plus_mass", "lambda_mass",
)
_FIT_UNITS = {
    "f_pi": "GeV", "f_k_over_f_pi": "1", "f_eta_over_f_pi": "1", "mu": "GeV",
    "a_piN": "1", "a_etaN": "1", "a_KLambda": "1", "a_KSigma": "1",
}
_UNITS = {**dict.fromkeys(_MASS_NAMES, "GeV"), **_FIT_UNITS}


def load_reduced_parameters(parameter_path: Path, source_path: Path) -> ReducedTParameters:
    """Load exactly the reduced-model inputs, with per-value provenance."""
    raw = json.loads(parameter_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or set(raw) != set(_UNITS):
        raise ValueError("reduced parameter names differ from source schema")
    sources = load_source_registry(source_path)
    values: dict[str, float] = {}
    for name, expected_unit in _UNITS.items():
        entry = raw[name]
        if (not isinstance(entry, dict)
                or set(entry) != {"value", "unit", "source_key", "locator"}
                or entry["unit"] != expected_unit):
            raise ValueError(f"invalid unit or source fields for {name}")
        key = entry["source_key"]
        if (key not in sources or not isinstance(entry["value"], (int, float))
                or isinstance(entry["value"], bool)):
            raise ValueError(f"invalid source or value for {name}")
        source = sources[key]
        ref = SourceRef(key, source.get("doi") or source.get("arxiv"), entry["locator"])
        values[name] = float(PhysicalParameter(
            name, float(entry["value"]), expected_unit, ref,
        ).value)
        if name in _MASS_NAMES and values[name] <= 0:
            raise ValueError(f"{name} must be positive")
    f_pi = values["f_pi"]
    f_k = f_pi * values["f_k_over_f_pi"]
    f_eta = f_pi * values["f_eta_over_f_pi"]
    return ReducedTParameters(
        meson_masses_gev=(values["pi0_mass"], values["charged_pion_mass"],
                          values["eta_mass"], values["charged_kaon_mass"],
                          values["charged_kaon_mass"], values["neutral_kaon_mass"]),
        baryon_masses_gev=(values["proton_mass"], values["neutron_mass"],
                           values["proton_mass"], values["sigma0_mass"],
                           values["lambda_mass"], values["sigma_plus_mass"]),
        decay_constants_gev=(f_pi, f_pi, f_eta, f_k, f_k, f_k),
        subtraction_constants=(values["a_piN"], values["a_piN"],
                               values["a_etaN"], values["a_KSigma"],
                               values["a_KLambda"], values["a_KSigma"]),
        mu_gev=values["mu"],
    )


def _validated_energy(w_gev: float, parameters: ReducedTParameters) -> float:
    if isinstance(w_gev, bool) or not isinstance(w_gev, (int, float, np.integer, np.floating)):
        raise ValueError("W must be a finite real scalar")
    w = float(w_gev)
    threshold = min(np.add(parameters.meson_masses_gev, parameters.baryon_masses_gev))
    if not np.isfinite(w) or not threshold <= w <= 1.70:
        raise ValueError("W outside reduced real-axis domain")
    return w


def wt_kernel(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.float64]:
    """P65 Eq. (5) Weinberg-Tomozawa s-wave kernel, in GeV^-1."""
    w = _validated_energy(w_gev, parameters)
    meson = np.asarray(parameters.meson_masses_gev)
    baryon = np.asarray(parameters.baryon_masses_gev)
    f = np.asarray(parameters.decay_constants_gev)
    energy = (w*w + baryon*baryon - meson*meson) / (2*w)
    norm = np.sqrt((baryon + energy) / (2*baryon))
    return (-C_COEFFICIENTS * (2*w - baryon[:, None] - baryon[None, :])
            * norm[:, None] * norm[None, :]
            / (4*f[:, None]*f[None, :]))


def loop_functions(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.complex128]:
    """P65 Eq. (6) physical-sheet meson-baryon loops, in GeV."""
    w = _validated_energy(w_gev, parameters)
    s = w*w
    meson = np.asarray(parameters.meson_masses_gev)
    baryon = np.asarray(parameters.baryon_masses_gev)
    subtraction = np.asarray(parameters.subtraction_constants)
    delta = baryon*baryon - meson*meson
    q = np.sqrt(((s-(baryon+meson)**2)*(s-(baryon-meson)**2)).astype(complex))/(2*w)
    logs = (np.log(s-delta+2*w*q) + np.log(s+delta+2*w*q)
            - np.log(-s+delta+2*w*q) - np.log(-s-delta+2*w*q))
    return (2*baryon/(4*np.pi)**2 *
            (subtraction + np.log(meson*meson/parameters.mu_gev**2)
             + (delta+s)/(2*s)*np.log(baryon*baryon/(meson*meson))
             + q/w*logs)).astype(np.complex128)


def reduced_tmatrix(w_gev: float, parameters: ReducedTParameters) -> NDArray[np.complex128]:
    """Solve (I - VG)T = V for the reduced on-shell strong amplitude."""
    v = wt_kernel(w_gev, parameters)
    g = loop_functions(w_gev, parameters)
    try:
        t = np.linalg.solve(np.eye(6, dtype=complex)-v*g[None, :], v)
    except np.linalg.LinAlgError as exc:
        raise ValueError("reduced T linear solve is singular") from exc
    if not np.all(np.isfinite(t)):
        raise ValueError("reduced T is nonfinite")
    return np.asarray(t, dtype=np.complex128)
