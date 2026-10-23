"""Partial acceptance must never change the baseline or leak rejected oracle runs."""
from types import SimpleNamespace

import numpy as np
import pytest

from calibration.run_manifest import RunRecord
from observable_extraction.core.models import FluxExposure
import flux_studies.flux_observable_closure as closure


class RunEvents:
    def __init__(self, runs):
        self.run_number = np.asarray(runs)

    def __len__(self):
        return len(self.run_number)

    def take(self, mask):
        return RunEvents(self.run_number[mask])


@pytest.fixture
def inputs(monkeypatch, tmp_path):
    # Keep extraction fast and deterministic; expose sample contamination directly
    # through Sigma, while exercising the real scenario/replica selection.
    events = RunEvents([811, 812, 813])
    records = [RunRecord(r, 'uv_a', 'P', 'UV', 'P_UV', 'manual', f'uv/run{r}.root')
               for r in (811, 812, 813)]
    native = {(r, 1): FluxExposure(r, 1, 1.15, float(r - 810), .9, .2, .6, .55)
              for r in (811, 812, 813)}
    calls = []

    def extract(**kwargs):
        runs = set(map(int, kwargs['events'].run_number))
        exposures = kwargs['exposures']
        calls.append((runs, {key[0] for key in exposures}))
        assert runs == {key[0] for key in exposures}
        sigma = sum(value.flux_vertical for value in exposures.values())
        point = SimpleNamespace(pair='p_eta', energy_bin=0, mass_bin=0, sigma=sigma,
                                stat_low=1., stat_high=1., energy_low_gev=1.,
                                energy_high_gev=1.2, mass_low_gev=1., mass_high_gev=2.,
                                diagnostics=SimpleNamespace(converged=True))
        return SimpleNamespace(points=[SimpleNamespace(estimator='ratio', point=point)])

    monkeypatch.setattr(closure, 'validate_manifest', lambda _: records)
    monkeypatch.setattr(closure, 'read_run_universe', lambda *a: ({811, 812, 813}, []))
    monkeypatch.setattr(closure, 'read_reconstructed', lambda *a, **k: events)
    monkeypatch.setattr(closure, 'load_exposures', lambda *a, **k: native)
    monkeypatch.setattr(closure, 'select_sigma_events', lambda events, *a, **k: events)
    monkeypatch.setattr(closure, 'extract_sample', extract)
    monkeypatch.setattr(closure, '_plot_closure', lambda *a: None)
    monkeypatch.setattr(closure, '_plot_recovery', lambda *a: None)
    rows = [dict(run=r, state=s, period='uv_a', role='test', method='linear',
                 truth=np.full(128, v), estimate=np.full(128, v))
            for r, s, v in ((811, 'POL1', 1.), (811, 'BREM', .2), (812, 'POL1', 2.))]
    kwargs = dict(predictions=rows, representation='native_strip', flux_path='flux.root',
                  manifest_path='manifest.csv', reco_paths={'uv': 'reco.root'},
                  output_dir=tmp_path, methods=('linear',))
    return kwargs, calls


def test_thresholds_keep_fixed_baseline_and_matched_oracle(inputs):
    kwargs, calls = inputs
    for accepted, expected_sigma in (({811, 812}, 6.), ({811}, 4.), (set(), 3.)):
        calls.clear()
        report = closure.run_observable_closure(**kwargs, accepted_runs=accepted)
        period = report['periods'][0]
        scenarios = period['scenarios']
        assert scenarios['without_recovery']['points'][0]['sigma'] == 3.
        for name in ('native_truth', 'roundtrip_truth', 'linear'):
            assert scenarios[name]['points'][0]['sigma'] == expected_sigma
        assert all(runs <= accepted | {813} for runs, _ in calls)
        assert period['masked_runs'] == [811, 812]
        assert period['accepted_runs'] == sorted(accepted)
        assert period['rejected_runs'] == sorted({811, 812} - accepted)
        assert all(row['bias_sigma'] == 0. for row in period['recovery_precision']
                   if row['bias_sigma'] is not None)
        assert report['production_gate']['adopted'] is False


@pytest.mark.parametrize('accepted', [{813}, {999}, {(811, 'POL1')}, {True}, {'811'}])
def test_acceptance_rejects_unknown_unmasked_or_non_run_values(inputs, accepted):
    kwargs, _ = inputs
    with pytest.raises(ValueError, match='accepted_runs'):
        closure.run_observable_closure(**kwargs, accepted_runs=accepted)


def test_replicas_filter_only_rejected_targets_and_require_all_accepted_states(inputs):
    kwargs, calls = inputs
    accepted = {(811, 'POL1'): np.ones(128), (811, 'BREM'): np.full(128, .2)}
    payloads = [
        {**accepted, (812, 'POL1'): np.full(128, np.nan)},
        {(811, 'POL1'): np.ones(128)},
        {**accepted, (999, 'POL1'): np.ones(128)},
    ]
    report = closure.run_observable_closure(
        **kwargs, accepted_runs={811},
        flux_replicas={'linear': {'uv_a': payloads}}, flux_replica_count=3)
    summary = report['periods'][0]['flux_replica_results']['linear']
    assert summary['complete_replica_indices'] == [0]
    assert summary['failed_replicas'] == 2
    assert all(runs <= {811, 813} for runs, _ in calls)


def test_no_acceptance_reuses_matched_oracle_without_payloads_and_flags_no_recovery(inputs):
    kwargs, calls = inputs
    report = closure.run_observable_closure(
        **kwargs, accepted_runs=set(), flux_replica_count=2)
    period = report['periods'][0]
    summary = period['flux_replica_results']['linear']
    assert len(calls) == 4  # central scenarios only, no replica extraction
    assert summary['complete_replicas'] == 2
    assert all(row['reused_native_fit'] for row in summary['replicas'])
    assert period['recovered_events'] == 0
    assert period['recovery_status'] == 'no_recovered_events'
    assert period['acceptance']['representation']['status'] == 'unvalidated'
    assert all(row['benefit_status'] == 'unvalidated' for row in period['recovery_precision'])


def test_none_preserves_original_all_run_selection(inputs):
    kwargs, _ = inputs
    period = closure.run_observable_closure(**kwargs)['periods'][0]
    assert period['scenarios']['native_truth']['points'][0]['sigma'] == 6.
    assert period['scenarios']['without_recovery']['points'][0]['sigma'] == 3.


def test_brem_reuse_uses_only_matched_accepted_oracle(inputs):
    kwargs, calls = inputs
    kwargs['predictions'] = [row for row in kwargs['predictions']
                             if (row['run'], row['state']) != (811, 'POL1')]
    payloads = [{(811, 'BREM'): np.full(128, value), (812, 'POL1'): np.full(128, np.nan)}
                for value in (.1, .4)]
    report = closure.run_observable_closure(
        **kwargs, accepted_runs={811},
        flux_replicas={'linear': {'uv_a': payloads}}, flux_replica_count=2)
    period = report['periods'][0]
    summary = period['flux_replica_results']['linear']
    assert len(calls) == 4
    assert summary['complete_replicas'] == 2
    assert all(row['reused_native_fit'] for row in summary['replicas'])
    row = next(row for row in period['recovery_precision'] if row['bias_sigma'] is not None)
    assert row['bias_sigma'] == 0.
    assert row['replica_lower68'] == 4.
    assert row['replica_upper68'] == 4.


def test_analysis_universe_excludes_outer_events_and_flux_before_loading(inputs, monkeypatch):
    kwargs, calls = inputs
    kwargs['predictions'] = [row for row in kwargs['predictions'] if row['run'] == 811]
    outputs = []
    for outer_count, outer_flux in ((1, 2.), (20, 1e9)):
        monkeypatch.setattr(closure, 'read_reconstructed',
                            lambda *a, **k: RunEvents([811, 813] + [812] * outer_count))
        available = {
            (r, 1): FluxExposure(r, 1, 1.15, value, .9, .2, .6, .55)
            for r, value in ((811, 1.), (812, outer_flux), (813, 3.))}

        def load(*args, **options):
            # The reserved run must not even be requested from the flux source.
            assert options['run_numbers'] == {811, 813}
            return {key: value for key, value in available.items()
                    if key[0] in options['run_numbers']}

        monkeypatch.setattr(closure, 'load_exposures', load)
        report = closure.run_observable_closure(
            **kwargs, accepted_runs={811}, analysis_runs={811, 813})
        period = report['periods'][0]
        assert report['analysis_runs'] == [811, 813]
        assert period['analysis_runs'] == [811, 813]
        assert period['run_universe'] == [811, 813]
        assert period['input_events'] == 2
        assert all(runs <= {811, 813} and exposures <= {811, 813}
                   for runs, exposures in calls)
        outputs.append({name: (scenario['points'], scenario['selected_events'])
                        for name, scenario in period['scenarios'].items()})
    assert outputs[0] == outputs[1]
    assert outputs[0]['without_recovery'][0][0]['sigma'] == 3.
    assert outputs[0]['native_truth'][0][0]['sigma'] == 4.


@pytest.mark.parametrize('allowed', [{811, 999}, {811}, {'811', '812'}, {True}, [811, 812]])
def test_analysis_universe_validates_ids_and_contains_every_masked_run(inputs, allowed):
    kwargs, _ = inputs
    with pytest.raises(ValueError, match='analysis_runs'):
        closure.run_observable_closure(**kwargs, analysis_runs=allowed)
