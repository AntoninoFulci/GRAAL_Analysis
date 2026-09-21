import pytest

from graal_common.physics.compton import (
    ELECTRON_ENERGY_MEV,
    UV_WAVELENGTH_NM,
    compton_edge_mev,
    linear_polarization_transfer,
)


def test_uv_compton_edge_and_polarization_match_graal_curve():
    edge = compton_edge_mev(ELECTRON_ENERGY_MEV, UV_WAVELENGTH_NM)

    assert edge == pytest.approx(1482.4, abs=0.1)
    assert linear_polarization_transfer(
        edge, ELECTRON_ENERGY_MEV, UV_WAVELENGTH_NM
    ) == pytest.approx(0.961, abs=0.002)
