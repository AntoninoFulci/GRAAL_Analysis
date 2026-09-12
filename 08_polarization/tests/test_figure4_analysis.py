from __future__ import annotations

import numpy as np
import pytest

from contracts import PolarizationContractError
from figure4_analysis import (
    PanelExposure,
    analyze_sigma_grid,
    event_pair_observables,
    fit_panel_histograms,
    histogram_panel,
    invariant_mass,
    physical_mass_edges,
)


def test_analyze_sigma_grid_builds_every_energy_pair_panel():
    rng = np.random.default_rng(813)
    count = 800
    energy = rng.uniform(1.1, 1.5, count)
    signs = np.where(np.arange(count) % 2, -1, 1)

    def particles(mass, momentum_scale):
        momentum = rng.normal(0.0, momentum_scale, (count, 3))
        total_energy = np.sqrt(mass**2 + np.sum(momentum**2, axis=1))
        return np.column_stack((momentum, total_energy))

    energy_ranges = tuple((low, low + 0.1) for low in (1.1, 1.2, 1.3, 1.4))
    mass_edges = tuple(
        physical_mass_edges(
            high,
            bins=10,
            masses_gev={"proton": 0.938, "eta": 0.548, "pi0": 0.135},
        )
        for _, high in energy_ranges
    )
    exposures = [PanelExposure(1000.0, 900.0, 0.8, 0.75)] * 4
    results = analyze_sigma_grid(
        energy,
        particles(0.938, 0.25),
        particles(0.548, 0.18),
        particles(0.135, 0.12),
        signs,
        energy_ranges=energy_ranges,
        mass_edges=mass_edges,
        phi_edges=np.linspace(0.0, np.pi, 13),
        exposures=exposures,
    )
    assert set(results) == {
        (row, pair)
        for row in range(4)
        for pair in ("p_pi0", "p_eta", "eta_pi0")
    }
    assert all(len(points) == 10 for points in results.values())
    assert results[(0, "p_pi0")][-1].mass_high < results[(3, "p_pi0")][-1].mass_high


def test_invariant_mass_matches_hand_calculated_four_vector():
    # E=5, |p|=3 -> m=4.
    assert invariant_mass(np.array([[3.0, 0.0, 0.0, 5.0]]))[0] == pytest.approx(4.0)


def test_event_pair_observables_uses_pair_sum_for_mass_and_azimuth():
    proton = np.array([[1.0, 0.0, 0.0, 2.0]])
    eta = np.array([[0.0, -1.0, 0.0, 1.5]])
    pi0 = np.array([[0.0, 1.0, 0.0, 1.2]])
    observables = event_pair_observables(proton, eta, pi0)
    assert observables["p_pi0"].mass[0] == pytest.approx(np.sqrt(3.2**2 - 2.0))
    assert observables["p_pi0"].phi[0] == pytest.approx(np.pi / 4.0)
    assert observables["p_eta"].phi[0] == pytest.approx(7.0 * np.pi / 4.0 % np.pi)
    assert not observables["eta_pi0"].valid_phi[0]


def test_event_pair_observables_rejects_bad_shapes_and_spacelike_vectors():
    good = np.array([[0.0, 0.0, 0.0, 1.0]])
    with pytest.raises(PolarizationContractError, match="shape"):
        event_pair_observables(good[:, :3], good, good)
    spacelike = np.array([[2.0, 0.0, 0.0, 1.0]])
    with pytest.raises(PolarizationContractError, match="spacelike"):
        invariant_mass(spacelike)


def test_histogram_panel_uses_left_closed_bins_and_includes_final_upper_edge():
    energy = np.array([1.10, 1.20, 1.499, 1.50, 1.05])
    mass = np.array([0.70, 0.80, 0.899, 0.90, 0.75])
    phi = np.array([0.0, np.pi / 4, np.pi / 2, np.nextafter(np.pi, 0), 0.1])
    sign = np.array([1, -1, 1, -1, 1])
    counts = histogram_panel(
        energy,
        mass,
        phi,
        sign,
        energy_range=(1.1, 1.5),
        mass_edges=np.array([0.7, 0.8, 0.9]),
        phi_edges=np.linspace(0.0, np.pi, 5),
        final_energy_bin=True,
    )
    assert counts.vertical.sum() == 2
    assert counts.horizontal.sum() == 2
    assert counts.vertical[0, 0] == 1
    assert counts.horizontal[1, 1] == 1
    assert counts.horizontal[1, 3] == 1


def test_histogram_panel_rejects_finite_phi_outside_periodic_domain():
    with pytest.raises(PolarizationContractError, match="phi must lie"):
        histogram_panel(
            [1.2], [0.8], [np.pi], [1],
            energy_range=(1.1, 1.3), mass_edges=[0.7, 0.9],
            phi_edges=np.linspace(0.0, np.pi, 13),
        )


def test_panel_fit_recovers_one_sigma_per_mass_bin():
    phi = (np.arange(12, dtype=float) + 0.5) * np.pi / 12.0
    cosine = np.cos(2.0 * phi)
    exposure = PanelExposure(
        vertical_flux=1.1e6,
        horizontal_flux=0.8e6,
        vertical_polarization=0.82,
        horizontal_polarization=0.73,
    )
    injected = (-0.35, 0.42)
    vertical = []
    horizontal = []
    for index, sigma in enumerate(injected):
        acceptance = 0.25 + 0.6 * np.sin(phi + 0.2 * index) ** 2
        rate = (0.0025 + 0.0005 * index) * acceptance
        vertical.append(
            rate * exposure.vertical_flux * (1 + exposure.vertical_polarization * sigma * cosine)
        )
        horizontal.append(
            rate
            * exposure.horizontal_flux
            * (1 - exposure.horizontal_polarization * sigma * cosine)
        )
    points = fit_panel_histograms(
        np.asarray(vertical),
        np.asarray(horizontal),
        phi,
        np.array([0.7, 0.8, 0.9]),
        exposure,
    )
    assert [point.mass_center for point in points] == pytest.approx([0.75, 0.85])
    assert [point.sigma for point in points] == pytest.approx(injected, abs=2e-6)
    assert all(point.valid for point in points)


def test_panel_fit_marks_empty_or_angularly_incomplete_mass_bin_invalid():
    phi = (np.arange(12, dtype=float) + 0.5) * np.pi / 12.0
    vertical = np.zeros((2, 12))
    horizontal = np.zeros((2, 12))
    vertical[0, 0] = 10
    horizontal[0, 0] = 8
    exposure = PanelExposure(10.0, 12.0, 0.8, 0.7)
    points = fit_panel_histograms(
        vertical,
        horizontal,
        phi,
        np.array([0.7, 0.8, 0.9]),
        exposure,
    )
    assert not points[0].valid
    assert "angular coverage" in points[0].reason
    assert not points[1].valid
    assert "empty" in points[1].reason


def test_physical_mass_edges_follow_threshold_and_three_body_limit():
    masses = {"proton": 0.938, "eta": 0.548, "pi0": 0.135}
    edges = physical_mass_edges(1.5, bins=10, masses_gev=masses)
    total_energy = np.sqrt(0.938**2 + 2.0 * 0.938 * 1.5)
    assert edges["p_pi0"][0] == pytest.approx(0.938 + 0.135)
    assert edges["p_pi0"][-1] == pytest.approx(total_energy - 0.548)
    assert edges["p_eta"][0] == pytest.approx(0.938 + 0.548)
    assert edges["p_eta"][-1] == pytest.approx(total_energy - 0.135)
    assert edges["eta_pi0"][0] == pytest.approx(0.548 + 0.135)
    assert edges["eta_pi0"][-1] == pytest.approx(total_energy - 0.938)
    assert all(value.size == 11 for value in edges.values())
