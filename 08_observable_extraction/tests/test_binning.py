import numpy as np
import pytest

from observable_extraction.core.binning import (
    ENERGY_EDGES_GEV,
    PHI_EDGES_RAD,
    energy_bin_index,
    pair_mass_edges,
)


def test_energy_bin_includes_final_right_edge_only_in_last_bin():
    assert energy_bin_index(1.10) == 0
    assert energy_bin_index(1.20) == 1
    assert energy_bin_index(1.50) == 3
    assert energy_bin_index(np.nextafter(1.50, np.inf)) is None


def test_vis_energy_bin_includes_both_outer_edges():
    edges = np.array([0.9313, 1.10])

    assert energy_bin_index(0.9313, edges) == 0
    assert energy_bin_index(1.10, edges) == 0
    assert energy_bin_index(0.9312, edges) is None
    assert energy_bin_index(1.1001, edges) is None


def test_fixed_energy_and_phi_binning_matches_figure4_contract():
    np.testing.assert_allclose(ENERGY_EDGES_GEV, [1.1, 1.2, 1.3, 1.4, 1.5])
    assert len(PHI_EDGES_RAD) == 13
    assert PHI_EDGES_RAD[0] == 0.0
    assert PHI_EDGES_RAD[-1] == pytest.approx(2.0 * np.pi)


@pytest.mark.parametrize(
    ("pair", "expected_edges"),
    [
        (
            "p_pi0",
            [1.00, 1.04, 1.08, 1.12, 1.16, 1.20, 1.24, 1.28, 1.32, 1.36, 1.40],
        ),
        (
            "p_eta",
            [1.40, 1.44, 1.48, 1.52, 1.56, 1.60, 1.64, 1.68, 1.72, 1.76, 1.80],
        ),
        (
            "eta_pi0",
            [0.60, 0.64, 0.68, 0.72, 0.76, 0.80, 0.84, 0.88, 0.92, 0.96, 1.00],
        ),
    ],
)
def test_pair_mass_edges_match_ajaka_figure4(pair, expected_edges):
    np.testing.assert_allclose(pair_mass_edges(pair), expected_edges, atol=1e-12)
