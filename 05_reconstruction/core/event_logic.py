"""ROOT-free physics decisions for one reconstructed event."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

import numpy as np

from graal_common.physics.channels import Hypothesis
from graal_common.physics.pairing import Pairing
from reconstruction.core import reco_physics as rp


@dataclass(frozen=True)
class EventInput:
    photons: np.ndarray
    proton: np.ndarray
    neutron: np.ndarray
    beam: np.ndarray
    run_number: int
    polarization: int
    strip: float
    n_photons_input: int = 4


@dataclass(frozen=True)
class ReconstructedEvent:
    pairing: Pairing
    photons: np.ndarray
    proton: np.ndarray
    neutron: np.ndarray
    beam: np.ndarray
    heavy: np.ndarray
    light: np.ndarray
    missing: np.ndarray
    heavy_mass: float
    light_mass: float
    chi2: float
    run_number: int
    polarization: int
    strip: float


class RejectionReason(Enum):
    CHI_SQUARE = "chi_square"
    IMPOSSIBLE_ENERGY = "impossible_energy"
    MISSING_MASS = "missing_mass"


class _ReconstructionConfig(Protocol):
    chi2_cut: float
    partner_mass: float
    missing_mass_window: float | None


PairingFunction = Callable[[np.ndarray, Hypothesis], tuple[Pairing, float]]


def _mass(vector: np.ndarray) -> float:
    """Match TLorentzVector.M(), including its sign for space-like vectors."""
    spatial_squared = (
        vector[0] * vector[0]
        + vector[1] * vector[1]
        + vector[2] * vector[2]
    )
    mass_squared = vector[3] * vector[3] - spatial_squared
    if mass_squared < 0.0:
        return -float(np.sqrt(-mass_squared))
    return float(np.sqrt(mass_squared))


def reconstruct_event(
    event: EventInput,
    channel: rp.Channel,
    config: _ReconstructionConfig,
    *,
    pairing_fn: PairingFunction,
) -> ReconstructedEvent | RejectionReason:
    """Apply reconstruction decisions to one event, preserving cut order."""
    pairing, chi2_value = pairing_fn(event.photons, channel.hypothesis)
    if chi2_value >= config.chi2_cut:
        return RejectionReason.CHI_SQUARE

    heavy_indices, light_indices = pairing.heavy, pairing.light
    photons = np.stack(
        [
            event.photons[heavy_indices[0]],
            event.photons[heavy_indices[1]],
            event.photons[light_indices[0]],
            event.photons[light_indices[1]],
        ]
    )
    heavy = photons[0] + photons[1]
    light = photons[2] + photons[3]

    if heavy[3] > event.beam[3] or light[3] > event.beam[3]:
        return RejectionReason.IMPOSSIBLE_ENERGY

    target = np.array([0.0, 0.0, 0.0, config.partner_mass])
    missing = (event.beam + target) - (heavy + light)

    if not rp.passes_missing_mass(
        _mass(missing),
        config.partner_mass,
        config.missing_mass_window,
    ):
        return RejectionReason.MISSING_MASS

    return ReconstructedEvent(
        pairing=pairing,
        photons=photons,
        proton=event.proton,
        neutron=event.neutron,
        beam=event.beam,
        heavy=heavy,
        light=light,
        missing=missing,
        heavy_mass=_mass(heavy),
        light_mass=_mass(light),
        chi2=chi2_value,
        run_number=event.run_number,
        polarization=event.polarization,
        strip=event.strip,
    )
