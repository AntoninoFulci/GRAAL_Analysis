import numpy as np
import pytest

from graal_theory.beam_asymmetry import fit_binned_asymmetry


def test_center_fit_shows_finite_phi_bin_attenuation_with_unequal_flux_and_polarization():
    edges = np.linspace(0.0, 2.0 * np.pi, 13)
    centers = 0.5 * (edges[1:] + edges[:-1])
    sigma = -0.5
    bin_mean_cosine = np.sin(np.pi / 6) / (np.pi / 6) * np.cos(2.0 * centers)
    vertical = 100.0 * (1.0 + 0.9 * sigma * bin_mean_cosine)
    horizontal = 200.0 * (1.0 - 0.8 * sigma * bin_mean_cosine)
    result = fit_binned_asymmetry(vertical, horizontal, 100.0, 200.0, 0.9, 0.8, edges)
    assert result == pytest.approx(-0.5 * np.sin(np.pi / 6) / (np.pi / 6), abs=1e-12)


def test_fit_rejects_unpopulated_mass_bin():
    with pytest.raises(ValueError, match="populated"):
        fit_binned_asymmetry(
            np.zeros(12), np.zeros(12), 1.0, 1.0, 0.9, 0.9,
            np.linspace(0.0, 2.0 * np.pi, 13),
        )
