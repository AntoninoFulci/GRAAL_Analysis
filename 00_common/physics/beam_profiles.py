"""Beam-specific constants shared across calibration and analysis stages."""

from __future__ import annotations

from dataclasses import dataclass
import math

from graal_common.physics.compton import (
    ELECTRON_ENERGY_MEV,
    GREEN_WAVELENGTH_NM,
    UV_WAVELENGTH_NM,
    linear_polarization_transfer,
)


@dataclass(frozen=True)
class BeamProfile:
    """One coherent beam configuration and its analysis energy bins."""

    name: str
    target: str
    beam_type: str
    manifest_group: str
    laser_wavelength_nm: float
    energy_edges_gev: tuple[float, ...]

    def __post_init__(self) -> None:
        for field_name in ("name", "target", "beam_type", "manifest_group"):
            if not getattr(self, field_name):
                raise ValueError(f"{field_name} must be non-empty")
        if (
            not math.isfinite(self.laser_wavelength_nm)
            or self.laser_wavelength_nm <= 0.0
        ):
            raise ValueError("laser wavelength must be finite and positive")
        if len(self.energy_edges_gev) < 2:
            raise ValueError("energy edges must contain at least two values")
        if not all(math.isfinite(edge) for edge in self.energy_edges_gev):
            raise ValueError("energy edges must be finite")
        if any(
            high <= low
            for low, high in zip(
                self.energy_edges_gev[:-1], self.energy_edges_gev[1:]
            )
        ):
            raise ValueError("energy edges must be strictly increasing")

    @property
    def energy_range_gev(self) -> tuple[float, float]:
        return self.energy_edges_gev[0], self.energy_edges_gev[-1]

    def polarization(self, energy_gev: float) -> float:
        """Linear Compton polarization transfer at tagged energy in GeV."""
        return linear_polarization_transfer(
            energy_gev * 1000.0,
            ELECTRON_ENERGY_MEV,
            self.laser_wavelength_nm,
        )


UV_PROFILE = BeamProfile(
    name="uv",
    target="P",
    beam_type="UV",
    manifest_group="P_UV",
    laser_wavelength_nm=UV_WAVELENGTH_NM,
    energy_edges_gev=(1.10, 1.20, 1.30, 1.40, 1.50),
)

VIS_PROFILE = BeamProfile(
    name="vis",
    target="P",
    beam_type="VIS",
    manifest_group="P_VIS",
    laser_wavelength_nm=GREEN_WAVELENGTH_NM,
    energy_edges_gev=(0.9313, 1.10),
)

BEAM_PROFILES = {
    profile.name: profile for profile in (UV_PROFILE, VIS_PROFILE)
}


def get_beam_profile(name: str) -> BeamProfile:
    try:
        return BEAM_PROFILES[name]
    except KeyError:
        choices = ", ".join(BEAM_PROFILES)
        raise ValueError(
            f"unknown beam profile {name!r}; choose one of: {choices}"
        ) from None
