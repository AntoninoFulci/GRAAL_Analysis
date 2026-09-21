"""GRAAL inverse-Compton photon energy and linear-polarization transfer."""

from __future__ import annotations

ELECTRON_ENERGY_MEV = 6027.6
GREEN_WAVELENGTH_NM = 514.0
UV_WAVELENGTH_NM = 351.0
ELECTRON_MASS_MEV = 0.51099895
HC_MEV_NM = 1.239841984e-3


def laser_energy_mev(wavelength_nm: float) -> float:
    return HC_MEV_NM / wavelength_nm


def compton_x(electron_energy_mev: float, wavelength_nm: float) -> float:
    laser_energy = laser_energy_mev(wavelength_nm)
    return 4.0 * electron_energy_mev * laser_energy / ELECTRON_MASS_MEV**2


def compton_edge_mev(electron_energy_mev: float, wavelength_nm: float) -> float:
    x = compton_x(electron_energy_mev, wavelength_nm)
    return electron_energy_mev * x / (1.0 + x)


def linear_polarization_transfer(
    photon_energy_mev: float,
    electron_energy_mev: float,
    wavelength_nm: float,
) -> float:
    x = compton_x(electron_energy_mev, wavelength_nm)
    y = photon_energy_mev / electron_energy_mev
    if not 0.0 <= y <= x / (1.0 + x):
        raise ValueError("photon energy outside Compton range")
    r = y / (x * (1.0 - y))
    return 2.0 * r * r / (
        1.0 / (1.0 - y) + (1.0 - y) - 4.0 * r * (1.0 - r)
    )
