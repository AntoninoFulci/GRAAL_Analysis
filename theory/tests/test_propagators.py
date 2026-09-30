import numpy as np
import pytest

from graal_theory.amplitudes.propagators import (
    Delta1700WidthParameters,
    breit_wigner,
    delta1700_width,
    p_wave_width,
)


def test_p_wave_width_is_zero_below_decay_threshold():
    assert p_wave_width(1.0, pole_mass=1.232, pole_width=0.117,
                        daughter_masses=(0.9382721, 0.1349768)) == 0.0


def test_breit_wigner_at_pole_is_purely_negative_imaginary():
    value = breit_wigner(1.7, pole_mass=1.7, width=0.3)
    assert value.real == pytest.approx(0.0, abs=1e-15)
    assert value.imag == pytest.approx(-2.0 / 0.3)


def test_negative_width_is_rejected():
    with pytest.raises(ValueError, match="width"):
        breit_wigner(1.7, pole_mass=1.7, width=-0.1)


@pytest.fixture
def central_width_parameters():
    return Delta1700WidthParameters(
        pole_mass_gev=1.700,
        nominal_pole_width_gev=0.300,
        proton_mass_gev=0.9382720813,
        pion_mass_gev=0.13957039,
        delta_mass_gev=1.232,
        delta_pole_width_gev=0.117,
        rho_mass_gev=0.77526,
        n_pi_branching_fraction=0.15,
        g_rho=2.60,
        f_rho=6.14,
        f_tilde_delta_pi=-1.325,
        g_tilde_delta_pi=0.146,
    )


def test_delta1700_width_is_sum_of_eq37_components(central_width_parameters):
    parts = central_width_parameters.components_at_pole()
    assert parts["n_pi"] == pytest.approx(0.045, rel=1e-10)
    assert parts["n_rho"] == pytest.approx(0.0381, rel=0.05)
    assert parts["delta_pi"] == pytest.approx(0.1326, rel=0.05)
    assert delta1700_width(1.7, central_width_parameters) == pytest.approx(sum(parts.values()), rel=1e-12)


def test_delta1700_width_is_zero_below_all_decay_thresholds(central_width_parameters):
    assert delta1700_width(1.0, central_width_parameters) == 0.0


def test_branching_fraction_outside_unit_interval_is_rejected(central_width_parameters):
    from dataclasses import replace

    with pytest.raises(ValueError, match="branching"):
        replace(central_width_parameters, n_pi_branching_fraction=1.1)


@pytest.mark.parametrize("threshold", [
    0.9382720813 + 0.13957039,
    0.9382720813 + 2 * 0.13957039,
    1.232 + 0.13957039,
])
def test_delta1700_width_is_continuous_across_channel_boundaries(central_width_parameters, threshold):
    below = delta1700_width(threshold - 1e-5, central_width_parameters)
    above = delta1700_width(threshold + 1e-5, central_width_parameters)
    assert below >= 0.0
    assert above >= 0.0
    assert abs(above - below) < 1e-3
