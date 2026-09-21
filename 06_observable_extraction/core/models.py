"""Immutable contracts shared by beam-asymmetry extraction modules."""

from __future__ import annotations

from dataclasses import dataclass
import math


PAIR_NAMES = frozenset({"p_pi0", "p_eta", "eta_pi0"})


def _finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise ValueError(f"{name} must be finite")


@dataclass(frozen=True)
class FluxExposure:
    run_number: int
    xstrip: int
    energy_gev: float
    flux_vertical: float
    flux_horizontal: float
    flux_brem: float
    polarization_vertical: float
    polarization_horizontal: float

    def __post_init__(self) -> None:
        if self.run_number <= 0:
            raise ValueError("run_number must be positive")
        if not 1 <= self.xstrip <= 128:
            raise ValueError("xstrip must be in 1..128")
        _finite("energy_gev", self.energy_gev)
        if self.energy_gev <= 0.0:
            raise ValueError("energy_gev must be positive")
        for name, value in (
            ("flux_vertical", self.flux_vertical),
            ("flux_horizontal", self.flux_horizontal),
            ("flux_brem", self.flux_brem),
        ):
            _finite(name, value)
        if self.flux_vertical <= 0.0 or self.flux_horizontal <= 0.0:
            raise ValueError("selected flux must be positive")
        if self.flux_brem < 0.0:
            raise ValueError("flux_brem must be non-negative")
        for name, value in (
            ("polarization_vertical", self.polarization_vertical),
            ("polarization_horizontal", self.polarization_horizontal),
        ):
            _finite(name, value)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1]")


@dataclass(frozen=True)
class PairProjection:
    pair: str
    mass_gev: float
    phi_rad: float

    def __post_init__(self) -> None:
        if self.pair not in PAIR_NAMES:
            raise ValueError(f"unknown pair: {self.pair}")
        _finite("mass_gev", self.mass_gev)
        if self.mass_gev < 0.0:
            raise ValueError("mass_gev must be non-negative")
        _finite("phi_rad", self.phi_rad)
        if not 0.0 <= self.phi_rad < 2.0 * math.pi:
            raise ValueError("phi_rad must be in [0, 2 pi)")


@dataclass(frozen=True)
class FitDiagnostics:
    converged: bool
    chi2: float
    ndf: int
    p_value: float
    used_fallback: bool
    c0: float | None = None
    s2: float | None = None

    def __post_init__(self) -> None:
        _finite("chi2", self.chi2)
        if self.chi2 < 0.0:
            raise ValueError("chi2 must be non-negative")
        if self.ndf < 0:
            raise ValueError("ndf must be non-negative")
        _finite("p_value", self.p_value)
        if not 0.0 <= self.p_value <= 1.0:
            raise ValueError("p_value must be in [0, 1]")
        for name, value in (("c0", self.c0), ("s2", self.s2)):
            if value is not None:
                _finite(name, value)


@dataclass(frozen=True)
class SigmaPoint:
    pair: str
    energy_bin: int
    mass_bin: int
    energy_low_gev: float
    energy_high_gev: float
    mass_low_gev: float
    mass_high_gev: float
    mass_mean_gev: float
    sigma: float
    stat_low: float
    stat_high: float
    diagnostics: FitDiagnostics

    def __post_init__(self) -> None:
        if self.pair not in PAIR_NAMES:
            raise ValueError(f"unknown pair: {self.pair}")
        if self.energy_bin < 0 or self.mass_bin < 0:
            raise ValueError("bin indices must be non-negative")
        for name, value in (
            ("energy_low_gev", self.energy_low_gev),
            ("energy_high_gev", self.energy_high_gev),
            ("mass_low_gev", self.mass_low_gev),
            ("mass_high_gev", self.mass_high_gev),
            ("mass_mean_gev", self.mass_mean_gev),
            ("sigma", self.sigma),
            ("stat_low", self.stat_low),
            ("stat_high", self.stat_high),
        ):
            _finite(name, value)
        if self.energy_high_gev <= self.energy_low_gev:
            raise ValueError("invalid energy interval")
        if self.mass_high_gev <= self.mass_low_gev:
            raise ValueError("invalid mass interval")
        if not self.mass_low_gev <= self.mass_mean_gev <= self.mass_high_gev:
            raise ValueError("mass_mean_gev must lie inside mass interval")
        if not -1.0 <= self.sigma <= 1.0:
            raise ValueError("sigma must be in [-1, 1]")
        if self.stat_low < 0.0 or self.stat_high < 0.0:
            raise ValueError("statistical errors must be non-negative")
