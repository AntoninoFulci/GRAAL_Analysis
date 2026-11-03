"""Azimuth origin, periodic event conservation and historical compatibility."""

from dataclasses import replace

import numpy as np
import pytest

from observable_extraction.core import binning
from observable_extraction.core.models import FluxExposure
from observable_extraction.core.ratio_fit import extract_ratio_grid


@pytest.mark.parametrize("bins", [8, 12, 16])
def test_new_phi_bins_center_on_cardinal_directions(bins):
    edges = binning.phi_edges_rad(bins)
    centers = (edges[1:] + edges[:-1]) / 2
    np.testing.assert_allclose(centers[::bins // 4], np.arange(4) * np.pi / 2, atol=1e-14)
    assert edges[0] == pytest.approx(-np.pi / bins)
    assert edges[-1] == pytest.approx(2 * np.pi - np.pi / bins)


@pytest.mark.parametrize("bins", [8, 12, 16])
def test_ratio_histograms_conserve_periodic_events_at_circle_boundaries(bins):
    edges = np.linspace(-np.pi / bins, 2 * np.pi - np.pi / bins, bins + 1)
    centers = (edges[1:] + edges[:-1]) / 2
    single = np.r_[centers, 0., 2 * np.pi, -2 * np.pi,
                   edges[0], edges[-1], np.nextafter(edges[0], -np.inf),
                   np.nextafter(edges[-1], -np.inf), np.nextafter(edges[-1], np.inf)]
    phi = np.tile(single, 2)
    (result,) = extract_ratio_grid(
        pair="p_pi0", mass_gev=np.full(len(phi), 1.02), phi_rad=phi,
        beam_energy_gev=np.full(len(phi), 1.15),
        polarization=np.repeat([1, 2], len(single)),
        exposures={(811, 17): FluxExposure(811, 17, 1.15, 1., 1., .2, .6, .6)},
        phi_edges=edges,
    )
    assert result.counts_vertical.sum() == len(single)
    assert result.counts_horizontal.sum() == len(single)
    assert result.counts_vertical[0] == 7  # center, three turns of zero, low/high, just above high
    assert result.counts_vertical[-1] == 3  # center, just below low/high
    assert result.point.sigma == pytest.approx(0., abs=1e-14)


@pytest.mark.parametrize("bins", [8, 12, 16])
def test_wrapping_preserves_phase_and_half_open_range(bins):
    edges = binning.phi_edges_rad(bins)
    values = np.r_[np.linspace(-20., 20., 103), edges,
                   np.nextafter(edges[0], -np.inf), np.nextafter(edges[-1], np.inf)]
    wrapped = binning.wrap_phi_rad(values, edges)
    assert np.all(wrapped >= edges[0])
    assert np.all(wrapped < edges[-1])
    np.testing.assert_allclose(np.cos(wrapped), np.cos(values), atol=5e-15)
    np.testing.assert_allclose(np.sin(wrapped), np.sin(values), atol=5e-15)


def test_selection_retention_keeps_events_near_two_pi():
    from observable_extraction.core.gate_comparison import phi_retention
    from observable_extraction.tests.test_gate_comparison import events

    phi = np.array([0., -.01, .01, np.pi, 2 * np.pi - .01])
    vectors = np.column_stack((np.cos(phi), np.sin(phi), np.zeros(len(phi)), np.full(len(phi), 3.)))
    sample = replace(events(tuple(range(len(phi)))), proton=vectors, eta=vectors, pi0=vectors)
    result = phi_retention({"full": sample}, np.array([1.1, 1.3]))
    for pair in binning.PAIR_NAMES:
        assert np.sum(result["full"][pair]["1"]) == len(phi)
        assert result["full"][pair]["1"][0][0] == 4


def test_brem_control_histogram_conserves_wrapped_events(tmp_path, monkeypatch):
    from observable_extraction.plotting import diagnostics
    import matplotlib.pyplot as plt

    figures = []
    monkeypatch.setattr(diagnostics, "_save", lambda path, figure: figures.append(figure))
    phi = np.array([0., -.01, 2 * np.pi - .01, 2 * np.pi])
    diagnostics.write_false_asymmetry_controls_pdf(tmp_path / "controls.pdf", {"p_pi0": phi})
    try:
        polygon = figures[0].axes[0].patches[0]
        assert polygon.get_xy()[:, 1].max() == len(phi)
    finally:
        plt.close(figures[0])


@pytest.mark.parametrize("bins", [8, 12, 16])
@pytest.mark.parametrize("origin", ["legacy", "center_zero"])
def test_corrected_root_preserves_both_historical_and_aligned_edges(tmp_path, bins, origin):
    from observable_extraction.tests.test_root_input import _write
    from observable_extraction.io.root_output import write_root_output
    from observable_extraction.io.root_input import read_output_contract

    path = tmp_path / "corrected.root"
    payload = _write(path)
    low = 0. if origin == "legacy" else -np.pi / bins
    edges = np.linspace(low, low + 2 * np.pi, bins + 1)
    write_root_output(path, replace(payload, phi_edges=edges,
        provenance=f"phi_bin_divisor={binning.PHI_BIN_DIVISORS[bins]}"))
    contract = read_output_contract(path)
    np.testing.assert_array_equal(contract.phi_edges_rad, edges)
    assert contract.phi_bin_divisor == binning.PHI_BIN_DIVISORS[bins]


@pytest.mark.parametrize("origin", ["legacy_edge_zero", "center_zero"])
def test_best_binning_round_trip_preserves_origin(tmp_path, origin):
    from observable_extraction.tests.test_root_input import _write
    from observable_extraction.io.root_output import write_root_output
    from observable_extraction.io.root_input import read_output_contract

    path = tmp_path / "best.root"
    payload = _write(path)
    points = tuple(replace(p, phi_bins=12 if p.estimator == "ratio" else 0) for p in payload.points)
    edges = (np.linspace(0., 2 * np.pi, 13) if origin == "legacy_edge_zero"
             else binning.phi_edges_rad())
    write_root_output(path, replace(payload, points=points, phi_edges=edges,
        provenance="phi_bins=best-binning\nphi_bin_divisor=per_point"))
    contract = read_output_contract(path)
    assert contract.best_binning
    assert binning.phi_bin_origin(contract.phi_edges_rad) == origin


def test_best_binning_reader_rejects_mixed_candidate_origins(tmp_path):
    import ROOT
    from observable_extraction.tests.test_root_input import _write
    from observable_extraction.io.root_output import write_root_output
    from observable_extraction.io.root_input import read_output_contract

    path = tmp_path / "mixed.root"
    payload = _write(path)
    points = tuple(replace(p, phi_bins=12 if p.estimator == "ratio" else 0) for p in payload.points)
    write_root_output(path, replace(payload, points=points,
        provenance="phi_bins=best-binning\nphi_bin_divisor=per_point"))
    source = ROOT.TFile(str(path), "UPDATE")
    directory = source.GetDirectory("binning_candidates/8")
    directory.cd()
    directory.Delete("phi_edges;*")
    vector = ROOT.TVectorD(9)
    for index, value in enumerate(np.linspace(0., 2 * np.pi, 9)):
        vector[index] = value
    vector.Write("phi_edges")
    source.Close()
    with pytest.raises(RuntimeError, match="phi.*origin"):
        read_output_contract(path)
