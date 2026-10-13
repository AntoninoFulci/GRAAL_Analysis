import numpy as np
import ROOT

from observable_extraction.core.models import FitDiagnostics, SigmaPoint
from observable_extraction.io.root_output import (
    OutputPoint,
    RatioObject,
    RootOutputPayload,
    write_root_output,
)


def _point():
    return OutputPoint(
        sample="raw_bdt",
        estimator="ratio",
        point=SigmaPoint(
            pair="p_pi0",
            energy_bin=0,
            mass_bin=0,
            energy_low_gev=1.1,
            energy_high_gev=1.2,
            mass_low_gev=1.07,
            mass_high_gev=1.10,
            mass_mean_gev=1.085,
            sigma=0.3,
            stat_low=0.05,
            stat_high=0.06,
            diagnostics=FitDiagnostics(True, 8.0, 10, 0.63, False),
        ),
        sigma_uncorrected=0.28,
        systematic_total=0.04,
        background_fraction=0.12,
        count_vertical=120,
        count_horizontal=100,
        flux_vertical=1000.0,
        flux_horizontal=900.0,
        polarization_vertical=0.60,
        polarization_horizontal=0.58,
    )


def test_root_output_contains_points_edges_covariance_and_ratio_objects(tmp_path):
    output = tmp_path / "beam_asymmetry.root"
    ratio = RatioObject(
        pair="p_pi0",
        energy_bin=0,
        mass_bin=0,
        phi=np.array([0.2, 0.7]),
        value=np.array([0.1, -0.1]),
        error=np.array([0.02, 0.03]),
        sigma=0.3,
    )
    payload = RootOutputPayload(
        points=(_point(),),
        energy_edges=np.array([1.1, 1.2, 1.3, 1.4, 1.5]),
        mass_edges={"p_pi0": np.linspace(1.07, 1.37, 11)},
        covariance_total=np.array([[0.01]]),
        systematic_covariances={"polarization_scale_3pct": np.array([[0.001]])},
        ratio_objects=(ratio,),
        provenance="synthetic test",
        statistical_covariance=np.array([[0.009]]),
        bootstrap_covariance=np.array([[0.008]]),
    )

    write_root_output(output, payload)

    source = ROOT.TFile.Open(str(output))
    try:
        assert source.Get("sigma_points").GetEntries() == 1
        assert source.Get("binning/energy_edges")
        assert source.Get("binning/p_pi0_mass_edges")
        assert source.Get("covariance/total")
        assert source.Get("covariance/statistical")
        assert source.Get("covariance/bootstrap_run")
        assert source.Get("covariance/correlation_total")
        assert source.Get("diagnostics/ratio_vs_likelihood")
        assert source.Get("covariance/systematic/polarization_scale_3pct")
        assert source.Get("ratio_objects/p_pi0/e0/m0/ratio")
        assert source.Get("ratio_objects/p_pi0/e0/m0/fit")
        overlay = source.Get("ratio_overlays/p_pi0/e0/m0/overlay")
        assert overlay and overlay.InheritsFrom("TCanvas")
        assert overlay.GetPrimitive("ratio").InheritsFrom("TGraphErrors")
        assert overlay.GetPrimitive("fit").InheritsFrom("TF1")
        assert overlay.GetPrimitive("fit").GetParameter(0) == 0.3
        assert source.Get("provenance")
    finally:
        source.Close()


def _covariance_payload(points=None):
    return RootOutputPayload(
        points=points or (_point(),), energy_edges=np.array([1.1, 1.2]),
        mass_edges={'p_pi0': np.array([1.07, 1.10])},
        covariance_total=np.array([[.01]]), statistical_covariance=np.array([[.009]]),
        systematic_covariances={'test': np.array([[.001]])},
        ratio_objects=(), provenance='profile=uv')


def test_root_covariance_roundtrip_has_same_keys_on_every_matrix(tmp_path):
    from dataclasses import replace
    from observable_extraction.io.root_input import read_output_uncertainties

    payload = replace(_covariance_payload(),
        point_context={'campaign': 'toy', 'selection': 'no-fit', 'profile': 'uv', 'period': '1998_uv'},
        uncertainty_metadata={'final_inference': 'suspended', 'sources': {'missing': {'status': 'unavailable'}}})
    path = tmp_path / 'covariance.root'
    write_root_output(path, payload)
    result = read_output_uncertainties(path)
    assert result.point_keys[0]['campaign'] == 'toy'
    assert result.point_keys[0]['sample'] == 'raw_bdt'
    assert result.metadata['sources']['missing']['status'] == 'unavailable'
    np.testing.assert_allclose(result.matrices['total'], [[.01]])
    np.testing.assert_allclose(result.matrices['correlation_statistical'], [[1.]])
    np.testing.assert_allclose(result.matrices['systematic/test'], [[.001]])


def test_root_writer_rejects_bad_covariance_without_replacing_output(tmp_path):
    from dataclasses import replace
    import pytest

    path = tmp_path / 'preserved.root'
    path.write_bytes(b'previous artifact')
    payload = _covariance_payload()
    for invalid in (replace(payload, covariance_total=np.eye(2)),
                    replace(payload, covariance_total=np.array([[-1.]])),
                    replace(payload, covariance_total=np.array([[.5]])),
                    replace(payload, points=(_point(), _point()))):
        with pytest.raises(ValueError):
            write_root_output(path, invalid)
        assert path.read_bytes() == b'previous artifact'


def test_root_roundtrip_preserves_failed_bootstrap_replicas(tmp_path):
    from dataclasses import replace
    from observable_extraction.core.systematics import paired_bootstrap_by_run
    from observable_extraction.tests.test_systematics import _run_events, _run_exposures
    from observable_extraction.io.root_output import ordered_point_keys, point_key_label
    from observable_extraction.io.root_input import read_bootstrap_diagnostics

    payload = _covariance_payload()
    labels = tuple(point_key_label(key) for key in ordered_point_keys(payload.points, {}))
    diagnostic = paired_bootstrap_by_run(
        lambda samples, exposures: [np.nan if not len(samples['a']) else .2],
        {'a': _run_events([11])}, _run_exposures([11, 12]),
        run_strata={11: 'uv:1998', 12: 'uv:1998'}, point_keys=labels, replicas=20, seed=4)
    assert diagnostic.failures
    path = tmp_path / 'diagnostic.root'
    write_root_output(path, replace(payload, bootstrap_diagnostics=diagnostic))
    restored = read_bootstrap_diagnostics(path)
    assert restored.failures == diagnostic.failures
    assert restored.run_draws == diagnostic.run_draws
    np.testing.assert_array_equal(restored.replicas, diagnostic.replicas)
    assert restored.covariance is None
    assert restored.point_keys == diagnostic.point_keys


def test_root_keys_and_covariances_follow_permuted_points_and_reject_wrong_axis(tmp_path):
    from dataclasses import replace
    import pytest
    from observable_extraction.io.root_input import read_output_uncertainties

    first = _point()
    second = replace(first, point=replace(first.point, mass_bin=1))
    stat = np.diag([.01, .04])
    syst = np.array([[.01, -.02], [-.02, .04]])
    payload = replace(_covariance_payload(), points=(first, second),
                      statistical_covariance=stat, systematic_covariances={'shared': syst},
                      covariance_total=stat+syst)
    paths = [tmp_path / 'forward.root', tmp_path / 'reverse.root']
    write_root_output(paths[0], payload)
    write_root_output(paths[1], replace(payload, points=(second, first),
        statistical_covariance=stat[::-1, ::-1], systematic_covariances={'shared': syst[::-1, ::-1]},
        covariance_total=(stat+syst)[::-1, ::-1]))
    forward, reverse = map(read_output_uncertainties, paths)
    assert reverse.point_keys == forward.point_keys[::-1]
    for name, matrix in forward.matrices.items():
        np.testing.assert_array_equal(reverse.matrices[name], matrix[::-1, ::-1])
    source = ROOT.TFile(str(paths[0]), 'UPDATE')
    covariance = source.Get('covariance/total')
    covariance.GetXaxis().SetBinLabel(1, 'wrong point')
    source.cd('covariance')
    covariance.Write('total', ROOT.TObject.kOverwrite)
    source.Close()
    with pytest.raises(ValueError, match='axis keys'):
        read_output_uncertainties(paths[0])


def test_legacy_covariance_zeros_remain_unknown(tmp_path):
    from observable_extraction.io.root_input import read_output_uncertainties, read_output_points

    path = tmp_path / 'legacy.root'
    write_root_output(path, _covariance_payload())
    source = ROOT.TFile(str(path), 'UPDATE')
    source.GetDirectory('covariance').Delete('point_keys;*')
    source.GetDirectory('covariance').Delete('uncertainty_metadata;*')
    source.Delete('point_uncertainty_kinds;*')
    source.Close()
    result = read_output_uncertainties(path)
    assert result.point_keys is None
    assert result.metadata['statistical_correlations'] == 'unknown'
    assert read_output_points(path)[0].uncertainty_kind == 'legacy_stat_branches_unclassified'


def test_bootstrap_reader_rejects_deleted_draw_history(tmp_path):
    from dataclasses import replace
    import pytest
    from observable_extraction.core.systematics import paired_bootstrap_by_run
    from observable_extraction.tests.test_systematics import _run_events, _run_exposures
    from observable_extraction.io.root_output import ordered_point_keys, point_key_label
    from observable_extraction.io.root_input import read_bootstrap_diagnostics

    payload = _covariance_payload()
    diagnostic = paired_bootstrap_by_run(
        lambda samples, exposures: [len(samples['a']) / 10.],
        {'a': _run_events([11])}, _run_exposures([11, 12]),
        run_strata={11: 'uv:1998', 12: 'uv:1998'},
        point_keys=tuple(point_key_label(key) for key in ordered_point_keys(payload.points, {})), replicas=5, seed=4)
    path = tmp_path / 'incomplete.root'
    write_root_output(path, replace(payload, bootstrap_diagnostics=diagnostic))
    source = ROOT.TFile(str(path), 'UPDATE')
    source.cd('diagnostics/paired_bootstrap')
    ROOT.TTree('run_draws', 'deleted draws').Write('run_draws', ROOT.TObject.kOverwrite)
    source.Close()
    with pytest.raises(ValueError, match='draw'):
        read_bootstrap_diagnostics(path)
