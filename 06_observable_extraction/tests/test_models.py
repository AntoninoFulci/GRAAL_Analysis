import math

import pytest

from observable_extraction.core.models import (
    FitDiagnostics,
    FluxExposure,
    PairProjection,
    SigmaPoint,
)


def _diagnostics():
    return FitDiagnostics(
        converged=True,
        chi2=8.0,
        ndf=10,
        p_value=0.63,
        used_fallback=False,
    )


def test_flux_exposure_requires_positive_selected_fluxes():
    with pytest.raises(ValueError, match="selected flux"):
        FluxExposure(811, 17, 1.25, 0.0, 20.0, 4.0, 0.61, 0.58)


def test_flux_exposure_accepts_fixed_vertical_horizontal_mapping():
    exposure = FluxExposure(811, 17, 1.25, 120.0, 80.0, 25.0, 0.61, 0.58)

    assert exposure.flux_vertical == 120.0
    assert exposure.flux_horizontal == 80.0
    assert exposure.flux_brem == 25.0


@pytest.mark.parametrize("polarization", [-0.01, 1.01, math.nan])
def test_flux_exposure_rejects_invalid_polarization(polarization):
    with pytest.raises(ValueError, match="polarization"):
        FluxExposure(811, 17, 1.25, 120.0, 80.0, 25.0, polarization, 0.58)


def test_pair_projection_rejects_unwrapped_phi():
    with pytest.raises(ValueError, match="phi_rad"):
        PairProjection("p_pi0", 1.2, 2.0 * math.pi)


def test_sigma_point_rejects_reversed_mass_interval():
    with pytest.raises(ValueError, match="mass interval"):
        SigmaPoint(
            pair="p_pi0",
            energy_bin=0,
            mass_bin=0,
            energy_low_gev=1.1,
            energy_high_gev=1.2,
            mass_low_gev=1.3,
            mass_high_gev=1.2,
            mass_mean_gev=1.25,
            sigma=0.2,
            stat_low=0.1,
            stat_high=0.1,
            diagnostics=_diagnostics(),
        )


def test_sigma_point_accepts_asymmetric_statistical_interval():
    point = SigmaPoint(
        pair="eta_pi0",
        energy_bin=3,
        mass_bin=4,
        energy_low_gev=1.4,
        energy_high_gev=1.5,
        mass_low_gev=0.9,
        mass_high_gev=1.0,
        mass_mean_gev=0.96,
        sigma=-0.2,
        stat_low=0.08,
        stat_high=0.11,
        diagnostics=_diagnostics(),
    )

    assert point.stat_low == 0.08
    assert point.stat_high == 0.11
