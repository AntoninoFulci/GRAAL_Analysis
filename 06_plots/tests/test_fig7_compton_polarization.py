import math

import pytest

from plots import fig7_compton_polarization as fig7


def test_compton_edges_match_fig7():
    # A broken laser-energy conversion or Compton denominator moves both edges.
    assert fig7.compton_edge_mev(
        fig7.ELECTRON_ENERGY_MEV, fig7.GREEN_WAVELENGTH_NM
    ) == pytest.approx(1100, abs=10)
    assert fig7.compton_edge_mev(
        fig7.ELECTRON_ENERGY_MEV, fig7.UV_WAVELENGTH_NM
    ) == pytest.approx(1480, abs=10)


def test_fig7_operating_constants_are_exact():
    # These inputs define the published Figure 7 curves; rounded substitutes
    # visibly change the physical Compton edge.
    assert fig7.ELECTRON_ENERGY_MEV == 6027.6
    assert fig7.GREEN_WAVELENGTH_NM == 514.0
    assert fig7.UV_WAVELENGTH_NM == 351.0
    assert fig7.TAGGING_THRESHOLD_MEV == 550.0


def test_edge_polarizations_match_fig7():
    # The transfer expression must reproduce the figure's rounded edge values.
    for wavelength, expected in (
        (fig7.GREEN_WAVELENGTH_NM, 0.980),
        (fig7.UV_WAVELENGTH_NM, 0.962),
    ):
        edge = fig7.compton_edge_mev(fig7.ELECTRON_ENERGY_MEV, wavelength)
        assert fig7.linear_polarization_transfer(
            edge, fig7.ELECTRON_ENERGY_MEV, wavelength
        ) == pytest.approx(expected, abs=0.002)


def test_polarization_rejects_energies_outside_the_compton_range():
    # A negative energy and the next representable value above the UV edge are
    # both unphysical; the physical bound must have no tolerance.
    uv_edge = fig7.compton_edge_mev(
        fig7.ELECTRON_ENERGY_MEV, fig7.UV_WAVELENGTH_NM
    )
    for photon_energy_mev in (-1.0, math.nextafter(uv_edge, math.inf)):
        with pytest.raises(ValueError, match="outside Compton range"):
            fig7.linear_polarization_transfer(
                photon_energy_mev,
                fig7.ELECTRON_ENERGY_MEV,
                fig7.UV_WAVELENGTH_NM,
            )
