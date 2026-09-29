import numpy as np
import pytest

from observable_extraction.core.conditional_likelihood import (
    extract_likelihood_grid,
    fit_conditional_sigma,
    vertical_probability,
)
from observable_extraction.core.models import FluxExposure


EXPOSURES = {
    (811, 17): FluxExposure(811, 17, 1.15, 120.0, 80.0, 20.0, 0.62, 0.58),
    (812, 31): FluxExposure(812, 31, 1.15, 60.0, 110.0, 18.0, 0.48, 0.66),
    (813, 44): FluxExposure(813, 44, 1.15, 95.0, 90.0, 15.0, 0.55, 0.52),
}


def _toy(sigma, events_per_stratum=20_000, seed=9917):
    rng = np.random.default_rng(seed)
    phi_parts = []
    pol_parts = []
    run_parts = []
    strip_parts = []
    for (run, strip), exposure in EXPOSURES.items():
        phi = rng.uniform(0.0, 2.0 * np.pi, events_per_stratum)
        probability = vertical_probability(phi, sigma, exposure)
        polarization = np.where(rng.random(events_per_stratum) < probability, 1, 2)
        phi_parts.append(phi)
        pol_parts.append(polarization)
        run_parts.append(np.full(events_per_stratum, run))
        strip_parts.append(np.full(events_per_stratum, strip))
    return tuple(
        np.concatenate(parts)
        for parts in (phi_parts, pol_parts, run_parts, strip_parts)
    )


def test_conditional_likelihood_recovers_injected_sigma():
    phi, polarization, run, strip = _toy(0.42)

    result = fit_conditional_sigma(
        phi, polarization, run, strip, EXPOSURES
    )

    assert result.sigma == pytest.approx(0.42, abs=0.02)
    assert result.interval_low < 0.42 < result.interval_high
    assert result.converged is True


def test_vertical_probability_uses_fixed_pol1_vertical_sign():
    exposure = EXPOSURES[(811, 17)]

    probability = vertical_probability(np.array([0.0, np.pi / 2.0]), 0.4, exposure)

    assert probability[0] > exposure.flux_vertical / (
        exposure.flux_vertical + exposure.flux_horizontal
    )
    assert probability[1] < exposure.flux_vertical / (
        exposure.flux_vertical + exposure.flux_horizontal
    )


def test_missing_event_stratum_is_fatal():
    with pytest.raises(ValueError, match=r"missing exposure.*\(999, 1\)"):
        fit_conditional_sigma(
            np.array([0.0]),
            np.array([1]),
            np.array([999]),
            np.array([1]),
            EXPOSURES,
        )


def test_physical_boundary_and_unbounded_pressure_are_reported():
    exposure = {(811, 17): EXPOSURES[(811, 17)]}
    phi = np.zeros(500)
    polarization = np.ones(500, dtype=int)
    run = np.full(500, 811)
    strip = np.full(500, 17)

    result = fit_conditional_sigma(phi, polarization, run, strip, exposure)

    assert result.sigma == pytest.approx(1.0, abs=1e-4)
    assert result.interval_high == 1.0
    assert result.at_upper_boundary is True
    assert result.unbounded_sigma > 1.0
    assert result.pressure_against_boundary is True


def test_invalid_polarization_state_is_rejected():
    with pytest.raises(ValueError, match="polarization states"):
        fit_conditional_sigma(
            np.array([0.0]),
            np.array([0]),
            np.array([811]),
            np.array([17]),
            {(811, 17): EXPOSURES[(811, 17)]},
        )


def test_likelihood_grid_preserves_profile_errors_and_bin_identity():
    phi, polarization, run, strip = _toy(0.3, events_per_stratum=3_000, seed=12)
    mass = np.full(len(phi), 1.10)
    energy = np.full(len(phi), 1.15)

    (result,) = extract_likelihood_grid(
        pair="p_pi0",
        mass_gev=mass,
        phi_rad=phi,
        beam_energy_gev=energy,
        polarization=polarization,
        run_number=run,
        xstrip=strip,
        exposures=EXPOSURES,
    )

    assert result.point.energy_bin == 0
    assert result.point.mass_bin == 0
    assert result.point.sigma == pytest.approx(0.3, abs=0.04)
    assert result.point.stat_low > 0.0
    assert result.point.stat_high > 0.0
