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
