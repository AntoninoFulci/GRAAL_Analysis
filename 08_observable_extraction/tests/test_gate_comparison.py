from dataclasses import replace

import numpy as np
import pytest

from observable_extraction.core.gate_comparison import (
    compare_contracts, subset_audit, paired_difference_summary, align_points,
)
from observable_extraction.io.reconstructed_events import EventArrays


def metadata(threshold=None):
    return dict(schema=2, selection_algorithm="pairing_missing_mass", channel="eta_pi0", input_tree="h85",
                inputs=[dict(path="input.root", size=10, sha256="abc")],
                source_files=[dict(path="core.py", size=20, sha256="def")],
                selection=dict(chi2_cut=10., chi2_resolution_relative=.08,
                               missing_mass_window_gev=.06, partner_mass_gev=.938272,
                               energy_range_gev=[1.1, 1.5],
                               photons="first_four_of_at_least_four", protons="exactly_one",
                               bdt_threshold=threshold),
                counts_by_run_state=[dict(run=1, polarization=1, input=100)])


def events(values=(1., 2., 3.)):
    n = len(values)
    vec = np.zeros((n, 4)); vec[:, 3] = values
    return EventArrays(np.ones(n, dtype=int), np.ones(n, dtype=int),
                       np.ones(n, dtype=int), np.full(n, 1.2), vec, vec, vec,
                       np.full(n, .938), np.full(n, .548), np.full(n, .135),
                       np.full(n, np.nan), np.full(n, 4))


def test_contract_allows_only_gate_difference():
    assert compare_contracts(metadata(), metadata(.7))["bdt_threshold"] == .7
    changed = metadata(.7); changed["selection"]["chi2_cut"] = 11
    with pytest.raises(ValueError, match="selection"):
        compare_contracts(metadata(), changed)


@pytest.mark.parametrize("field", ["inputs", "source_files", "counts_by_run_state"])
def test_contract_rejects_unproven_common_universe(field):
    changed = metadata(.7); changed[field] = []
    with pytest.raises(ValueError):
        compare_contracts(metadata(), changed)


def test_subset_is_order_independent_ignores_score_and_counts_duplicates():
    result = subset_audit(events(), replace(events((3., 1.)), bdt_score=np.array([.8, .9])))
    assert result["matched"] == 2
    assert result["removed"] == 1
    with pytest.raises(ValueError, match="subset"):
        subset_audit(events(), events((1., 1.)))
    assert subset_audit(events((1., 1.)), events((1.,)))["ambiguous_fingerprints"] == 1


def test_paired_difference_keeps_cross_covariance_and_never_drops_failed_draws():
    # Columns ordered pairing bins, then BDT bins; gate open => exactly zero difference.
    a = np.array([[.1, .2], [.2, .4], [.3, .1], [.4, .3]])
    result = paired_difference_summary(np.column_stack((a, a)), ("bin0", "bin1"))
    np.testing.assert_allclose(result["difference_covariance"], np.zeros((2, 2)), atol=1e-16)
    assert np.asarray(result["cross_covariance"])[0, 0] > 0
    bad = np.column_stack((a, a)); bad[0, 3] = np.nan
    result = paired_difference_summary(bad, ("bin0", "bin1"))
    assert result["available_keys"] == ["bin0"]
    assert result["unavailable_keys"] == ["bin1"]
    assert result["failed_replicas_by_key"] == {"bin0": 0, "bin1": 1}
    assert result["replicas"] == 4


def test_alignment_accounts_for_whole_grid_even_when_no_fit_exists():
    rows = align_points([], [], np.array([1.1, 1.2]))
    assert len(rows) == 60  # 3 projections x 10 mass bins x 2 estimators
    assert all(row["status"] == "neither_estimable" for row in rows)
    assert all(row["delta"] is None for row in rows)


def test_cutflow_counts_zero_yield_exposures_and_energy_state_bins():
    from observable_extraction.compare_gate import selected_cutflow
    from observable_extraction.core.models import FluxExposure
    exp = {(run, 1): FluxExposure(run, 1, 1.2, 1., 1., 0., .6, .6) for run in (1, 2)}
    rows = selected_cutflow(events(), events((1.,)), exp, {1: "p", 2: "p"}, [1.1, 1.3])
    zero = [row for row in rows if row["run"] == 2]
    assert len(zero) == 2
    assert all(row["pairing"] == row["bdt"] == 0 for row in zero)
    assert sum(row["pairing"] for row in rows) == 3
    assert sum(row["bdt"] for row in rows) == 1


def test_root_roundtrip_keeps_grid_metadata_and_no_fake_covariance(tmp_path):
    import json
    import ROOT
    from observable_extraction.compare_gate import write_comparison_root
    rows = align_points([], [], np.array([1.1, 1.2]))
    report = dict(rows=rows, bootstrap=dict(available_keys=[], difference_covariance=None))
    destination = tmp_path / "comparison.root"
    write_comparison_root(destination, report)
    source = ROOT.TFile.Open(str(destination))
    try:
        assert source.Get("comparison").GetEntries() == 60
        assert json.loads(source.Get("comparison_metadata").GetTitle()) == report
        assert not source.Get("difference_covariance")
    finally:
        source.Close()


def test_selective_phi_dependent_state_blind_gate_closes_at_known_sigma():
    from observable_extraction.core.binning import PHI_EDGES_RAD, phi_bin_divisor
    from observable_extraction.core.ratio_fit import fit_ratio
    phi = (PHI_EDGES_RAD[1:] + PHI_EDGES_RAD[:-1]) / 2
    divisor = phi_bin_divisor(PHI_EDGES_RAD)
    sigma, pol = .35, .6
    expected_ratio = sigma * divisor * np.cos(2 * phi)
    vertical = np.full(12, 200000.)
    horizontal = vertical * (1 - pol * expected_ratio) / (1 + pol * expected_ratio)
    retention = .45 + .2 * np.cos(phi)
    nominal = fit_ratio(phi, vertical, horizontal, 1., 1., pol, pol)
    gated = fit_ratio(phi, vertical * retention, horizontal * retention, 1., 1., pol, pol)
    assert nominal.sigma / divisor == pytest.approx(sigma, abs=1e-10)
    assert gated.sigma / divisor == pytest.approx(sigma, abs=1e-10)


def test_open_gate_reuses_both_estimators_with_identical_results():
    from observable_extraction.compare_gate import _extract, bootstrap_comparison
    from observable_extraction.core.models import FluxExposure
    phi = np.linspace(0, 2 * np.pi, 1200, endpoint=False)
    base = events(np.ones(len(phi)))
    vector = np.column_stack((.05 * np.cos(phi), .05 * np.sin(phi), np.zeros(len(phi)), np.ones(len(phi))))
    eta, pi0 = vector.copy(), vector.copy()
    eta[:, 3], pi0[:, 3] = .6, .25
    sample = replace(base, proton=vector, eta=eta, pi0=pi0,
                     run_number=np.where(np.arange(len(phi)) < 600, 1, 2),
                     polarization=np.where(np.arange(len(phi)) % 2, 1, 2))
    exp = {(run, 1): FluxExposure(run, 1, 1.2, 1., 1., 0., .6, .6) for run in (1, 2)}
    fitted = _extract(dict(pairing=sample, bdt=sample), exp, np.array([1.1, 1.3]))
    rows = align_points(fitted["pairing"], fitted["bdt"], [1.1, 1.3])
    common = [row for row in rows if row["status"] == "both_estimable"]
    assert len(common) == 6
    assert {row["estimator"] for row in common} == {"ratio", "likelihood"}
    for row in common:
        assert row["delta"] == 0.
        assert row["pairing"]["point"] == row["bdt"]["point"]
    result, _, _, _ = bootstrap_comparison(dict(pairing=sample, bdt=sample), exp,
        {1: "period1", 2: "period1"}, [row["key"] for row in common], np.array([1.1, 1.3]), 4, 12)
    assert len(result["available_keys"]) == 6
    np.testing.assert_allclose(result["difference_covariance"], np.zeros((6, 6)), atol=1e-18)


def test_ratio_grid_marks_unphysical_bin_unavailable_without_losing_valid_neighbor():
    from observable_extraction.core.binning import PHI_EDGES_RAD
    from observable_extraction.core.models import FluxExposure
    from observable_extraction.core.ratio_fit import extract_ratio_grid
    centers = (PHI_EDGES_RAD[1:] + PHI_EDGES_RAD[:-1]) / 2
    phis, states, masses = [], [], []
    for mass, sigma in ((1.02, 1.02), (1.06, .3)):
        nv = np.full(12, 200)
        ratio = sigma * np.cos(2 * centers)
        nh = np.rint(nv * (1 - .6 * ratio) / (1 + .6 * ratio)).astype(int)
        for state, counts in ((1, nv), (2, nh)):
            phis.extend(np.repeat(centers, counts))
            states.extend([state] * counts.sum())
            masses.extend([mass] * counts.sum())
    results = extract_ratio_grid(pair="p_pi0", mass_gev=np.array(masses),
        phi_rad=np.array(phis), beam_energy_gev=np.full(len(phis), 1.2),
        polarization=np.array(states), energy_edges=np.array([1.1, 1.3]),
        exposures={(1, 1): FluxExposure(1, 1, 1.2, 1., 1., 0., .6, .6)})
    assert [item.point.mass_bin for item in results] == [1]


def test_empty_joint_grid_records_no_bootstrap_without_failure():
    from observable_extraction.compare_gate import bootstrap_comparison
    diagnostic, values, keys, draws = bootstrap_comparison({}, {}, {}, [], [1.1, 1.3], 4, 12)
    assert diagnostic["status"] == "no_common_estimable_bins"
    assert diagnostic["replicas"] == 0
    assert diagnostic["difference_covariance"] is None
    assert values.shape == (0, 0)
    assert len(keys) == len(draws) == 0


def test_closed_gate_writes_full_coverage_report(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from observable_extraction import compare_gate
    from observable_extraction.core.models import FluxExposure
    import json
    paths = [tmp_path / name for name in ("pairing.root", "bdt.root", "flux.root", "manifest.csv")]
    for path in paths:
        path.touch()
    monkeypatch.setattr(compare_gate, "_read", lambda path, tree:
                        (events(), metadata()) if path == paths[0] else (events(()), metadata(.99)))
    monkeypatch.setattr(compare_gate, "validate_manifest", lambda path: [
        SimpleNamespace(run_number=1, source_period="period1", target="P", beam_type="UV")])
    monkeypatch.setattr(compare_gate, "load_exposures", lambda *args, **kwargs: {
        (1, 1): FluxExposure(1, 1, 1.2, 1., 1., 0., .6, .6)})
    args = SimpleNamespace(pairing=paths[0], bdt=paths[1], flux_file=paths[2], run_manifest=paths[3],
                           output_dir=tmp_path / "study", replicas=2, seed=12, profile="uv")
    compare_gate.run(args)
    report = json.loads((args.output_dir / "comparison.json").read_text())
    assert len(report["rows"]) == 240
    assert report["bootstrap"]["status"] == "no_common_estimable_bins"
    assert report["selected_subset"]["matched"] == 0
    assert (args.output_dir / "comparison.root").is_file()
    assert (args.output_dir / "comparison.pdf").is_file()
    with pytest.raises(FileExistsError):
        compare_gate.run(args)
