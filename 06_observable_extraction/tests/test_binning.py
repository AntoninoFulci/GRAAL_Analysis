import numpy as np
import pytest

from graal_common.physics.channels import M_ETA, M_PI0, M_PROTON
from observable_extraction.core.binning import (
    ENERGY_EDGES_GEV,
    PHI_EDGES_RAD,
    energy_bin_index,
    pair_mass_edges,
    w_max,
)


def test_energy_bin_includes_final_right_edge_only_in_last_bin():
    assert energy_bin_index(1.10) == 0
    assert energy_bin_index(1.20) == 1
    assert energy_bin_index(1.50) == 3
    assert energy_bin_index(np.nextafter(1.50, np.inf)) is None


def test_fixed_energy_and_phi_binning_matches_figure4_contract():
    np.testing.assert_allclose(ENERGY_EDGES_GEV, [1.1, 1.2, 1.3, 1.4, 1.5])
    assert len(PHI_EDGES_RAD) == 13
    assert PHI_EDGES_RAD[0] == 0.0
    assert PHI_EDGES_RAD[-1] == pytest.approx(2.0 * np.pi)


@pytest.mark.parametrize(
    ("pair", "threshold", "spectator"),
    [
        ("p_pi0", M_PROTON + M_PI0, M_ETA),
        ("p_eta", M_PROTON + M_ETA, M_PI0),
        ("eta_pi0", M_ETA + M_PI0, M_PROTON),
    ],
)
def test_pair_mass_ranges_use_threshold_and_global_maximum(
    pair, threshold, spectator
):
    edges = pair_mass_edges(pair)

    assert edges[0] == pytest.approx(threshold)
    assert edges[-1] == pytest.approx(w_max(1.5) - spectator)
    assert len(edges) == 11
    np.testing.assert_allclose(np.diff(edges), np.diff(edges)[0])
