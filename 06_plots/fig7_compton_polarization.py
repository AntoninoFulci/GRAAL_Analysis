"""Compton-backscattering quantities used to reproduce GRAAL Figure 7.

All energies are MeV.  The two laser lines and ESRF electron energy are the
GRAAL operating values; the tagging threshold marks the lower energy shown in
the figure.
"""
from __future__ import annotations

ELECTRON_ENERGY_MEV = 6030.0
GREEN_WAVELENGTH_NM = 514.5
UV_WAVELENGTH_NM = 351.0
TAGGING_THRESHOLD_MEV = 600.0

_ELECTRON_MASS_MEV = 0.51099895
_HC_MEV_NM = 1.239841984e-3

__all__ = [
    "ELECTRON_ENERGY_MEV",
    "GREEN_WAVELENGTH_NM",
    "UV_WAVELENGTH_NM",
    "TAGGING_THRESHOLD_MEV",
    "laser_energy_mev",
    "compton_x",
    "compton_edge_mev",
    "linear_polarization_transfer",
]


def laser_energy_mev(wavelength_nm: float) -> float:
    """Return a laser photon's energy from its vacuum wavelength."""
    return _HC_MEV_NM / wavelength_nm


def compton_x(electron_energy_mev: float, wavelength_nm: float) -> float:
    """Return the dimensionless inverse-Compton parameter for a laser line."""
    laser_energy = laser_energy_mev(wavelength_nm)
    return 4.0 * electron_energy_mev * laser_energy / _ELECTRON_MASS_MEV**2


def compton_edge_mev(electron_energy_mev: float, wavelength_nm: float) -> float:
    """Return the maximum backscattered photon energy."""
    x = compton_x(electron_energy_mev, wavelength_nm)
    return electron_energy_mev * x / (1.0 + x)


def linear_polarization_transfer(
    photon_energy_mev: float,
    electron_energy_mev: float,
    wavelength_nm: float,
) -> float:
    """Return the laser's linear-polarization transfer to a photon."""
    x = compton_x(electron_energy_mev, wavelength_nm)
    y = photon_energy_mev / electron_energy_mev
    maximum_y = x / (1.0 + x)
    if y < 0.0 or y > maximum_y and not abs(y - maximum_y) <= 1e-12:
        raise ValueError("photon energy outside Compton range")
    y = min(y, maximum_y)
    r = y / (x * (1.0 - y))
    return 2.0 * r * r / (
        1.0 / (1.0 - y) + (1.0 - y) - 4.0 * r * (1.0 - r)
    )
