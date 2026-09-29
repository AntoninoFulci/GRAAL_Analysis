import numpy as np
import pytest

from observable_extraction.core.binning import PHI_EDGES_RAD, pair_mass_edges
from observable_extraction.core.models import FluxExposure
from observable_extraction.core.ratio_fit import (
    extract_ratio_grid,
    fit_ratio,
    normalized_ratio,
)


PHI_CENTERS = 0.5 * (PHI_EDGES_RAD[:-1] + PHI_EDGES_RAD[1:])


def _counts_from_ratio(ratio, *, flux_v, flux_h, pol_v, pol_h, scale=2.0e5):
    # Solve R=(a-b)/(P_h*a+P_v*b) for b/a, then convert yields to counts.
    yield_v = np.full_like(ratio, scale, dtype=float)
    yield_h = yield_v * (1.0 - pol_h * ratio) / (1.0 + pol_v * ratio)
    return np.rint(flux_v * yield_v), np.rint(flux_h * yield_h)


def test_ratio_fit_recovers_positive_sigma_for_vertical_cos2_excess():
    sigma_true = 0.35
    pol_v, pol_h = 0.62, 0.58
    flux_v, flux_h = 1.2, 0.9
    desired = sigma_true * np.cos(2.0 * PHI_CENTERS)
    n_v, n_h = _counts_from_ratio(
        desired,
        flux_v=flux_v,
        flux_h=flux_h,
        pol_v=pol_v,
        pol_h=pol_h,
    )

    result = fit_ratio(
        PHI_CENTERS, n_v, n_h, flux_v, flux_h, pol_v, pol_h
    )

    assert result.sigma == pytest.approx(sigma_true, abs=2e-5)
    assert result.sigma > 0.0
    assert result.diagnostics.used_fallback is False


def test_normalized_ratio_propagates_poisson_counts_with_fixed_flux():
    ratio, error = normalized_ratio(
        np.array([120.0]),
        np.array([80.0]),
        flux_v=2.0,
        flux_h=1.0,
        pol_v=0.6,
        pol_h=0.5,
    )

    assert ratio[0] == pytest.approx(-20.0 / 78.0)
    # Hand derivative: dR/dNv=(Pv+Ph)*yh/(D^2*Fv), dR/dNh=-(Pv+Ph)*yv/(D^2*Fh).
    expected_variance = (
        ((1.1 * 80.0) / (78.0**2 * 2.0)) ** 2 * 120.0
        + ((1.1 * 60.0) / (78.0**2 * 1.0)) ** 2 * 80.0
    )
    assert error[0] == pytest.approx(np.sqrt(expected_variance))


def test_bad_nominal_fit_uses_constant_cosine_sine_diagnostic():
    desired = (
        0.12
        + 0.30 * np.cos(2.0 * PHI_CENTERS)
        - 0.16 * np.sin(2.0 * PHI_CENTERS)
    )
    n_v, n_h = _counts_from_ratio(
        desired,
        flux_v=1.0,
        flux_h=1.0,
        pol_v=0.6,
        pol_h=0.6,
        scale=1.0e7,
    )

    result = fit_ratio(PHI_CENTERS, n_v, n_h, 1.0, 1.0, 0.6, 0.6)

    assert result.diagnostics.used_fallback is True
    assert result.sigma == pytest.approx(0.30, abs=2e-5)
    assert result.diagnostics.c0 == pytest.approx(0.12, abs=2e-5)
    assert result.diagnostics.s2 == pytest.approx(-0.16, abs=2e-5)
    assert set(result.flags) == {"significant_c0", "significant_s2"}


def test_empty_phi_bin_is_masked_without_biasing_remaining_fit():
    desired = 0.2 * np.cos(2.0 * PHI_CENTERS)
    n_v, n_h = _counts_from_ratio(
        desired,
        flux_v=1.0,
        flux_h=1.0,
        pol_v=0.5,
        pol_h=0.5,
    )
    n_v[3] = 0.0
    n_h[3] = 0.0

    result = fit_ratio(PHI_CENTERS, n_v, n_h, 1.0, 1.0, 0.5, 0.5)

    assert result.used_mask[3] == np.bool_(False)
    assert result.sigma == pytest.approx(0.2, abs=2e-5)


def test_ratio_fit_rejects_nonpositive_selected_flux():
    with pytest.raises(ValueError, match="flux"):
        fit_ratio(PHI_CENTERS, np.ones(12), np.ones(12), 0.0, 1.0, 0.5, 0.5)


def test_grid_uses_all_exposure_strata_not_only_strata_with_events():
    exposures = {
        (811, 17): FluxExposure(811, 17, 1.15, 0.6, 0.4, 0.1, 0.6, 0.5),
        (812, 18): FluxExposure(812, 18, 1.15, 0.6, 0.5, 0.1, 0.4, 0.7),
    }
    flux_v, flux_h = 1.2, 0.9
    pol_v = (0.6 * 0.6 + 0.6 * 0.4) / flux_v
    pol_h = (0.4 * 0.5 + 0.5 * 0.7) / flux_h
    desired = 0.25 * np.cos(2.0 * PHI_CENTERS)
    n_v, n_h = _counts_from_ratio(
        desired,
        flux_v=flux_v,
        flux_h=flux_h,
        pol_v=pol_v,
        pol_h=pol_h,
        scale=200.0,
    )
    phi = np.concatenate(
        [np.repeat(PHI_CENTERS, n_v.astype(int)), np.repeat(PHI_CENTERS, n_h.astype(int))]
    )
    polarization = np.concatenate(
        [np.ones(int(n_v.sum()), dtype=int), np.full(int(n_h.sum()), 2, dtype=int)]
    )
    mass_edges = pair_mass_edges("p_pi0")
    mass = np.full(len(phi), 0.5 * (mass_edges[0] + mass_edges[1]))
    energy = np.full(len(phi), 1.15)

    (result,) = extract_ratio_grid(
        pair="p_pi0",
        mass_gev=mass,
        phi_rad=phi,
        beam_energy_gev=energy,
        polarization=polarization,
        exposures=exposures,
    )

    assert result.flux_vertical == pytest.approx(flux_v)
    assert result.flux_horizontal == pytest.approx(flux_h)
    assert result.polarization_vertical == pytest.approx(pol_v)
    assert result.polarization_horizontal == pytest.approx(pol_h)
    assert result.point.sigma == pytest.approx(0.25, abs=0.01)
