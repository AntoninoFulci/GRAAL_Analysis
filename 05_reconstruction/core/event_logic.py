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
from reconstruction.core.kinematic_fit import (
    FitReactionModel,
    FitResult,
    ResolutionModel,
    confidence_level,
)


@dataclass(frozen=True)
class EventInput:
    photons: np.ndarray
    proton: np.ndarray
    neutron: np.ndarray
    beam: np.ndarray
    run_number: int
    polarization: int
    strip: float


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
    fitted_photons: np.ndarray | None = None
    fitted_proton: np.ndarray | None = None
    fitted_heavy: np.ndarray | None = None
    fitted_light: np.ndarray | None = None
    fit_chi2: float | None = None
    fit_ndf: int | None = None
    fit_converged: bool | None = None


class RejectionReason(Enum):
    CHI_SQUARE = "chi_square"
    IMPOSSIBLE_ENERGY = "impossible_energy"
    MISSING_MASS = "missing_mass"
    FIT = "fit"


class _ReconstructionConfig(Protocol):
    chi2_cut: float
    partner_mass: float
    missing_mass_window: float | None
    do_fit: bool
    fit_cl: float
    fit_cov: ResolutionModel
    fit_reaction: FitReactionModel


PairingFunction = Callable[[np.ndarray, Hypothesis], tuple[Pairing, float]]
FitFunction = Callable[..., FitResult]

_FIT_PAIRING = Pairing(heavy=(0, 1), light=(2, 3))


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
    fit_fn: FitFunction,
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

    fitted_photons = None
    fitted_proton = None
    fitted_heavy = None
    fitted_light = None
    fit_chi2 = None
    fit_ndf = None
    fit_converged = None

    if config.do_fit:
        fit_result = fit_fn(
            photons,
            event.proton,
            event.beam,
            _FIT_PAIRING,
            channel.hypothesis,
            config.fit_cov,
            reaction=config.fit_reaction,
        )
        if (
            not fit_result.converged
            or confidence_level(fit_result.chi2, fit_result.ndf) < config.fit_cl
        ):
            return RejectionReason.FIT
        fitted_photons = fit_result.fitted_photons
        fitted_proton = fit_result.fitted_proton
        fitted_heavy = fitted_photons[0] + fitted_photons[1]
        fitted_light = fitted_photons[2] + fitted_photons[3]
        fit_chi2 = fit_result.chi2
        fit_ndf = fit_result.ndf
        fit_converged = fit_result.converged
    elif not rp.passes_missing_mass(
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
        fitted_photons=fitted_photons,
        fitted_proton=fitted_proton,
        fitted_heavy=fitted_heavy,
        fitted_light=fitted_light,
        fit_chi2=fit_chi2,
        fit_ndf=fit_ndf,
        fit_converged=fit_converged,
    )
