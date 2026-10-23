from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from flux_studies.flux_observable_closure import (
    project_to_strip_axis, replace_masked_exposures, run_observable_closure,
)
from observable_extraction.core.models import FluxExposure


def test_projection_identity_and_cropped_mass_audit():
    values, audit = project_to_strip_axis([2., 4.], [0., 1., 2.], [.5, 1., 1.5])
    np.testing.assert_allclose(values, [1., 2.])
    assert audit['outside_strip_axis_integral'] == pytest.approx(3.)
    values, audit = project_to_strip_axis([2., 4.], [0., 1., 2.], [0., 1., 2.])
    np.testing.assert_array_equal(values, [2., 4.])
    assert audit['outside_strip_axis_integral'] == 0.


@pytest.mark.parametrize('values, common, native', [
    ([1., -1.], [0., 1., 2.], [0., 1., 2.]),
    ([1., np.nan], [0., 1., 2.], [0., 1., 2.]),
    ([1., 2.], [0., 1., 2.], [-1., 1., 2.]),
    ([1., 2.], [0., 1., 2.], [0., 1., 1.]),
])
def test_invalid_projection_fails_explicitly(values, common, native):
    with pytest.raises(ValueError):
        project_to_strip_axis(values, common, native)


def test_only_requested_states_are_changed_and_zero_pol_fails():
    a = FluxExposure(811, 1, 1.15, 3., 4., 5., .6, .6)
    b = replace(a, run_number=812)
    native = {(811, 1): a, (812, 1): b}
    replaced = replace_masked_exposures(native, {(811, 'BREM'): np.array([9.])})
    assert replaced[(811, 1)] == replace(a, flux_brem=9.)
    assert replaced[(812, 1)] is b
    assert native[(811, 1)] is a
    with pytest.raises(ValueError, match='selected flux must be positive'):
        replace_masked_exposures(native, {(811, 'POL1'): np.array([0.])})
    with pytest.raises(ValueError, match='no native exposure'):
        replace_masked_exposures(native, {(999, 'BREM'): np.array([9.])})


def _mock_inputs(monkeypatch):
    import flux_studies.flux_observable_closure as closure
    from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events
    from calibration.run_manifest import RunRecord
    events = _synthetic_events()
    exposures = {(811, 17): FluxExposure(811, 17, 1.15, 1.2, .9, .2, .6, .55)}
    records = [RunRecord(811, 'uv_a', 'P', 'UV', 'P_UV', 'manual', 'uv/run811.root')]
    axes = {(811, 'POL1'): np.linspace(1., 1.6, 129),
            (811, 'BREM'): np.linspace(1., 1.6, 129)}
    monkeypatch.setattr(closure, 'validate_manifest', lambda _: records)
    monkeypatch.setattr(closure, 'load_known_axes', lambda *a: axes)
    monkeypatch.setattr(closure, 'read_run_universe', lambda *a: ({811}, []))
    reads = []
    monkeypatch.setattr(closure, 'read_reconstructed', lambda *a, **k: reads.append(a) or events)
    monkeypatch.setattr(closure, 'load_exposures', lambda *a, **k: exposures)
    return closure, reads


def test_identity_predictions_equal_roundtrip_and_universe_is_paired(tmp_path, monkeypatch):
    closure, reads = _mock_inputs(monkeypatch)
    calls = []
    original = closure.extract_sample
    def extract(**kwargs):
        calls.append((id(kwargs['events']), set(kwargs['exposures'])))
        return original(**kwargs)
    monkeypatch.setattr(closure, 'extract_sample', extract)
    predictions = [dict(run=811, state='POL1', period='uv_a', role='test', method=method,
                        truth=np.full(128, 1.2), estimate=np.full(128, 1.2))
                   for method in closure.DEFAULT_METHODS]
    result = run_observable_closure(predictions, common_edges_by_period={'uv_a': np.linspace(1., 1.6, 129)},
                                    flux_path=Path('flux.root'), manifest_path=Path('manifest.csv'),
                                    reco_paths={'uv': Path('reco.root')}, output_dir=tmp_path)
    assert len(reads) == 1
    assert len(calls) == 5
    assert all(call == calls[0] for call in calls)
    period = result['periods'][0]
    assert period['expected_points_per_scenario'] == 240
    rows = [row for row in period['comparisons'] if row['reference'] == 'roundtrip_truth'
            and row['status'] == 'matched']
    assert rows and {row['estimator'] for row in rows} == {'ratio', 'likelihood'}
    assert all(abs(row['delta_sigma']) < 1e-12 for row in rows)
    assert period['scenarios']['linear']['missing_points'] > 0
    assert result['production_gate']['adopted'] is False
    assert (tmp_path / 'observable_closure.json').is_file()


def test_missing_prediction_is_explicit_not_a_smaller_universe(tmp_path, monkeypatch):
    closure, _ = _mock_inputs(monkeypatch)
    predictions = [dict(run=811, state='POL1', period='uv_a', role='test', method='linear',
                        truth=np.ones(128), estimate=np.ones(128))]
    result = run_observable_closure(predictions, common_edges_by_period={'uv_a': np.linspace(1., 1.6, 129)},
                                    flux_path=Path('flux.root'), manifest_path=Path('manifest.csv'),
                                    reco_paths={'uv': Path('reco.root')}, output_dir=tmp_path)
    missing = result['periods'][0]['scenarios']['extra_trees_hybrid']
    assert missing['status'] == 'invalid_projection'
    assert 'missing prediction' in missing['reason']
    assert missing['missing_points'] == 240


def test_missing_independent_axis_is_reported_for_every_projected_scenario(tmp_path, monkeypatch):
    closure, _ = _mock_inputs(monkeypatch)
    monkeypatch.setattr(closure, 'load_known_axes', lambda *a: {})
    predictions = [dict(run=811, state='POL1', period='uv_a', role='test', method=method,
                        truth=np.ones(128), estimate=np.ones(128)) for method in closure.DEFAULT_METHODS]
    result = run_observable_closure(predictions, common_edges_by_period={'uv_a': np.linspace(1., 1.6, 129)},
                                    flux_path=Path('flux.root'), manifest_path=Path('manifest.csv'),
                                    reco_paths={'uv': Path('reco.root')}, output_dir=tmp_path)
    scenarios = result['periods'][0]['scenarios']
    assert scenarios['native_truth']['estimable_points'] > 0
    for scenario in ('roundtrip_truth', *closure.DEFAULT_METHODS):
        assert scenarios[scenario]['status'] == 'invalid_projection'
        assert 'missing independent target axis' in scenarios[scenario]['reason']
        assert scenarios[scenario]['missing_points'] == 240


def test_zero_projected_polarized_flux_invalidates_scenario_without_dropping_events(tmp_path, monkeypatch):
    closure, _ = _mock_inputs(monkeypatch)
    predictions = [dict(run=811, state='POL1', period='uv_a', role='test', method=method,
                        truth=np.full(128, 1.2), estimate=np.full(128, 0. if method == 'linear' else 1.2))
                   for method in closure.DEFAULT_METHODS]
    result = run_observable_closure(predictions, common_edges_by_period={'uv_a': np.linspace(1., 1.6, 129)},
                                    flux_path=Path('flux.root'), manifest_path=Path('manifest.csv'),
                                    reco_paths={'uv': Path('reco.root')}, output_dir=tmp_path)
    period = result['periods'][0]
    assert period['selected_events'] > 0
    assert period['scenarios']['linear']['status'] == 'invalid_projection'
    assert period['scenarios']['linear']['missing_points'] == 240
    assert period['scenarios']['extra_trees_hybrid']['estimable_points'] > 0
    assert period['matched_all_scenarios_points'] == 0


def test_known_axes_are_loaded_per_state_and_missing_axis_is_rejected(tmp_path):
    import uproot
    from flux_studies.flux_observable_closure import load_known_axes
    path = tmp_path / 'flux.root'
    first, second = np.linspace(1., 1.6, 129), np.linspace(1.01, 1.61, 129)
    with uproot.recreate(path) as output:
        output['run811_POL1'] = (np.ones(128), first)
        output['run811_POL2'] = (np.ones(128), second)
    axes = load_known_axes(path, {(811, 'POL1'), (811, 'POL2')})
    np.testing.assert_array_equal(axes[(811, 'POL1')], first)
    np.testing.assert_array_equal(axes[(811, 'POL2')], second)
    with pytest.raises(ValueError, match='missing or duplicate independent target axis'):
        load_known_axes(path, {(811, 'BREM')})


def test_native_identity_removes_whole_runs_and_never_loads_target_axes(tmp_path, monkeypatch):
    closure, _ = _mock_inputs(monkeypatch)
    monkeypatch.setattr(closure, 'load_known_axes', lambda *a: pytest.fail('native must not project'))
    calls = []
    original = closure.extract_sample
    def extract(**kwargs):
        calls.append((set(map(int, kwargs['events'].run_number)), set(kwargs['exposures'])))
        return original(**kwargs)
    monkeypatch.setattr(closure, 'extract_sample', extract)
    predictions = [dict(run=811, state='POL1', period='uv_a', role='test', method='mlp_hybrid',
                        truth=np.full(128, 1.2), estimate=np.full(128, 1.2))]
    result = run_observable_closure(predictions, representation='native_strip',
        flux_path='flux.root', manifest_path='manifest.csv', reco_paths={'uv': 'reco.root'},
        output_dir=tmp_path, methods=('mlp_hybrid',))
    period = result['periods'][0]
    assert (set(), set()) in calls
    assert period['scenarios']['without_recovery']['selected_events'] == 0
    assert period['scenarios']['without_recovery']['native_strata'] == 0
    rows = [r for r in period['comparisons'] if r['reference'] == 'native_truth'
            and r['scenario'] in ('roundtrip_truth', 'mlp_hybrid') and r['status'] == 'matched']
    assert rows and all(abs(r['delta_sigma']) < 1e-12 for r in rows)
    assert period['acceptance']['representation']['status'] == 'passed'
    assert period['acceptance']['bias']['status'] == 'unvalidated'


def test_replicas_keep_missing_denominators_and_native_covariance(tmp_path, monkeypatch):
    closure, _ = _mock_inputs(monkeypatch)
    predictions = [dict(run=811, state='POL1', period='uv_a', role='test', method='linear',
                        truth=np.full(128, 1.2), estimate=np.full(128, 1.2))]
    replicas = {'linear': {'uv_a': [{(811, 'POL1'): np.full(128, v)} for v in (1.15, 1.25)] + [{}]}}
    report = run_observable_closure(predictions, representation='native_strip',
        flux_path='flux.root', manifest_path='manifest.csv', reco_paths={'uv': 'reco.root'},
        output_dir=tmp_path, methods=('linear',), flux_replicas=replicas, flux_replica_count=4)
    period = report['periods'][0]
    uncertainty = period['flux_replica_results']['linear']
    assert uncertainty['requested_replicas'] == 4
    assert uncertainty['complete_replicas'] == 2
    assert uncertainty['failed_replicas'] == 2
    assert len(uncertainty['replicas']) == 4
    assert uncertainty['covariance']
    points = [p for p in period['recovery_precision'] if p['flux_std'] is not None]
    assert points
    for point in points:
        assert point['total_error'] == pytest.approx(np.hypot(point['stat_error'], point['flux_std']))
        assert point['bias_validation'] == 'unvalidated'
        assert point['replica_failures'] == 2
    assert report['production_gate']['adopted'] is False


def test_precision_ratio_uses_flux_spread_and_common_complete_covariance(monkeypatch):
    from types import SimpleNamespace
    import flux_studies.flux_observable_closure as closure
    keys = [('ratio', 'p_eta', 0, 0), ('ratio', 'p_eta', 0, 1)]
    def point(sigma, stat):
        return dict(sigma=sigma, stat_low=stat, stat_high=stat)
    oracle = {key: point(.2, 1.) for key in keys}
    model = {key: point(.25, .8) for key in keys}
    baseline = {key: point(.2, 2.) for key in keys}
    scenarios = dict(native_truth=oracle, roundtrip_truth=oracle,
                     without_recovery=baseline, linear=model)
    entry = dict(period='uv_a', comparisons=[dict(reference='native_truth', scenario='roundtrip_truth',
                                                 delta_over_nominal_stat=0.)])
    def extraction(**kwargs):
        value = kwargs['exposures'][(811, 1)].flux_vertical
        outputs = []
        for index, key in enumerate(keys):
            if value == 2. and index == 1:
                continue
            p = SimpleNamespace(pair=key[1], energy_bin=key[2], mass_bin=key[3],
                sigma=value * (index + 1), stat_low=.8, stat_high=.8,
                energy_low_gev=1., energy_high_gev=1.2, mass_low_gev=1., mass_high_gev=2.,
                diagnostics=SimpleNamespace(converged=True))
            outputs.append(SimpleNamespace(estimator=key[0], point=p))
        return SimpleNamespace(points=outputs)
    monkeypatch.setattr(closure, 'extract_sample', extraction)
    payloads = [{(811, 'POL1'): np.full(128, v)} for v in (1., 2., 3.)]
    native = {(811, 1): FluxExposure(811, 1, 1.15, 1.2, .9, .2, .6, .55)}
    closure._add_recovery_uncertainty(entry, scenarios, ('linear',),
        {'linear': {'uv_a': payloads}}, 3, native, {(811, 'POL1')}, None, np.array([1., 2.]), 1, keys)
    summary = entry['flux_replica_results']['linear']
    assert summary['complete_replica_indices'] == [0, 2]
    np.testing.assert_allclose(summary['covariance'], [[2., 4.], [4., 8.]])
    first, second = entry['recovery_precision']
    assert first['replica_failures'] == 0
    assert second['replica_failures'] == 1
    assert first['total_error'] == pytest.approx(np.sqrt(.8 ** 2 + 2.))
    assert first['precision_ratio'] == pytest.approx(np.sqrt(.8 ** 2 + 2.) / 2.)
    assert first['bias_over_oracle_stat'] == pytest.approx(.05)
    assert first['bias_estimate_uncertainty'] is None
    assert first['paired_rmse_proxy'] == pytest.approx(np.sqrt(.8 ** 2 + 2. + .05 ** 2))
    assert first['rmse_ratio'] == pytest.approx(first['paired_rmse_proxy'] / 2.)
    assert first['benefit_status'] == 'unvalidated'
    assert 'conditional' in first['total_error_definition']
    assert first['replica_lower68'] == pytest.approx(1.32)
    assert first['replica_upper68'] == pytest.approx(2.68)
    assert first['replica_lower95'] == pytest.approx(1.05)
    assert first['replica_upper95'] == pytest.approx(2.95)
    assert first['oracle_in_replica_interval68'] is False
    assert first['oracle_in_replica_interval95'] is False
    coverage = summary['coverage_diagnostics']['ratio']
    assert coverage['evaluable_points'] == 2
    assert coverage['covered68_points'] == 0
    assert coverage['coverage95_fraction'] == 0.
    assert 'correlated' in coverage['caveat']
    assert entry['acceptance']['bias']['status'] == 'unvalidated'


def test_brem_replica_validation_precedes_fit_reuse(tmp_path, monkeypatch):
    closure, _ = _mock_inputs(monkeypatch)
    calls = []
    original = closure.extract_sample
    def extract(**kwargs):
        calls.append(1)
        return original(**kwargs)
    monkeypatch.setattr(closure, 'extract_sample', extract)
    predictions = [dict(run=811, state='BREM', period='uv_a', role='test', method='linear',
                        truth=np.full(128, .2), estimate=np.full(128, .3))]
    payloads = [{(811, 'BREM'): np.full(128, v)} for v in (.1, .4, -1.)]
    report = closure.run_observable_closure(predictions, representation='native_strip',
        flux_path='flux.root', manifest_path='manifest.csv', reco_paths={'uv': 'reco.root'},
        output_dir=tmp_path, methods=('linear',), flux_replicas={'linear': {'uv_a': payloads}},
        flux_replica_count=3)
    assert len(calls) == 4
    uncertainty = report['periods'][0]['flux_replica_results']['linear']
    assert [r['reused_native_fit'] for r in uncertainty['replicas']] == [True, True, False]
    assert uncertainty['failed_replicas'] == 1
    assert np.all(np.asarray(uncertainty['covariance']) == 0.)
    evaluated = [row for row in report['periods'][0]['recovery_precision']
                 if row['oracle_in_replica_interval68'] is not None]
    assert evaluated
    assert all(row['oracle_in_replica_interval68'] and row['oracle_in_replica_interval95']
               and row['benefit_status'] == 'unvalidated' for row in evaluated)
