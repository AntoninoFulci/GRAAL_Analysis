from dataclasses import fields, replace
from types import SimpleNamespace

import numpy as np
import pytest

from observable_extraction.core.models import FluxExposure
from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events


def _inputs():
    events = _synthetic_events()
    native = {(811, 17): FluxExposure(811, 17, 1.15, 1.2, .9, .2, .6, .55)}
    return events, native


def _fast_extraction(**kwargs):
    from observable_extraction.core.models import FitDiagnostics, SigmaPoint
    if not len(kwargs['events']):
        return SimpleNamespace(points=[])
    sigma = float(np.mean(kwargs['events'].polarization)) / 3
    return SimpleNamespace(points=[SimpleNamespace(estimator='ratio', point=SigmaPoint(
        'p_eta', 0, 0, 1.1, 1.5, 1.4, 1.5, 1.45, sigma, .1, .1,
        FitDiagnostics(True, 1., 1, .5, False)))])


def test_brem_mask_preserves_baseline_and_does_not_count_recovery(monkeypatch):
    from flux_studies import energy_closure as closure
    monkeypatch.setattr(closure, 'extract_sample', _fast_extraction)
    events, native = _inputs()
    result = closure.compare_energy_scenarios(events, native, native, native,
        masked_states={(811, 'BREM')}, accepted_runs={811}, energy_edges=[1.1, 1.5])
    assert result['counts']['recovered_pol_events'] == 0
    assert result['scenarios']['A']['selected_events'] == len(events)
    assert result['scenarios']['C']['selected_events'] == len(events)
    assert result['counts']['unique_selected_events'] == len(events)


def test_rejected_polarized_runs_absent_from_all_oracles(monkeypatch):
    from flux_studies import energy_closure as closure
    monkeypatch.setattr(closure, 'extract_sample', _fast_extraction)
    events, native = _inputs()
    result = closure.compare_energy_scenarios(events, native, native, native,
        masked_states={(811, 'POL1')}, accepted_runs=set(), energy_edges=[1.1, 1.5])
    assert all(s['selected_events'] == 0 for s in result['scenarios'].values())
    assert result['counts']['recovered_pol_events'] == 0
    assert all(row['status'] == 'missing_fit' for row in result['comparisons'])


def test_synchronized_replicas_zero_paired_shift_and_retain_missing_points(monkeypatch):
    from flux_studies import energy_closure as closure
    monkeypatch.setattr(closure, 'extract_sample', _fast_extraction)
    events, native = _inputs()
    result = closure.compare_energy_scenarios(events, native, native, native,
        masked_states={(811, 'POL1')}, accepted_runs={811}, energy_edges=[1.1, 1.5],
        event_replicas=4, seed=9, flux_replicas=[native, native, None, native])
    paired = result['uncertainty']['paired']['B-C']
    assert paired['requested'] == 4
    row = next(row for row in paired['points'] if row['successful'] == 3)
    assert row['failed'] == 1
    assert row['shift_std'] == 0
    assert len(paired['points']) == result['expected_points']
    assert paired['complete_replicas'] == 0  # Unestimable grid points stay in denominator.
    assert result['uncertainty']['total_uncertainty_available'] is False


def test_changed_strata_fail_without_silently_reselecting_events(monkeypatch):
    from flux_studies import energy_closure as closure
    monkeypatch.setattr(closure, 'extract_sample', _fast_extraction)
    events, native = _inputs()
    result = closure.compare_energy_scenarios(events, native, {}, native,
        masked_states={(811, 'POL1')}, accepted_runs={811}, energy_edges=[1.1, 1.5])
    assert result['scenarios']['B']['status'] == 'invalid_exposures'
    assert result['counts']['proposed_recovered_pol_events'] == len(events)
    assert result['counts']['recovered_pol_events'] == 0
    assert result['scenarios']['C']['estimable_points'] == 1
    assert all(r['status'] == 'missing_fit' for r in result['comparisons'] if r['scenario'] == 'B')


@pytest.mark.parametrize('mask,change', [
    ({(811, 'BREM')}, dict(flux_vertical=2.4)),
    ({(811, 'BREM')}, dict(polarization_horizontal=.8)),
    ({(811, 'BREM')}, dict(energy_gev=1.16)),
    (set(), dict(flux_horizontal=1.8)),
    ({(811, 'POL1')}, dict(xstrip=18)),
    ({(811, 'POL1')}, dict(flux_horizontal=1.8)),
])
def test_only_masked_state_may_change_and_identity_is_preserved(monkeypatch, mask, change):
    from flux_studies import energy_closure as closure
    monkeypatch.setattr(closure, 'extract_sample', _fast_extraction)
    events, native = _inputs()
    changed = {(811, 17): replace(native[(811, 17)], **change)}
    result = closure.compare_energy_scenarios(events, native, changed, native,
        masked_states=mask, accepted_runs={r for r, _ in mask}, energy_edges=[1.1, 1.5])
    assert result['scenarios']['B']['status'] == 'invalid_exposures'
    assert result['scenarios']['B']['reason']
    assert result['scenarios']['C']['estimable_points'] == 1


def test_declared_quality_filters_both_event_and_exposure_universes(monkeypatch):
    from flux_studies import energy_closure as closure
    monkeypatch.setattr(closure, 'extract_sample', _fast_extraction)
    events, native = _inputs()
    quality = dict(excluded_runs=[dict(run=811)])
    result = closure.compare_energy_scenarios(events, native, native, native,
        masked_states=set(), accepted_runs=set(), energy_edges=[1.1, 1.5], run_quality=quality)
    assert result['counts']['unique_selected_events'] == 0
    assert all(item['strata'] == 0 and item['selected_events'] == 0
               for item in result['scenarios'].values())


def test_flux_replica_invariant_failure_remains_in_denominator(monkeypatch):
    from flux_studies import energy_closure as closure
    monkeypatch.setattr(closure, 'extract_sample', _fast_extraction)
    events, native = _inputs()
    changed = {(811, 17): replace(native[(811, 17)], flux_horizontal=1.8)}
    result = closure.compare_energy_scenarios(events, native, native, native,
        masked_states={(811, 'POL1')}, accepted_runs={811}, energy_edges=[1.1, 1.5],
        event_replicas=2, flux_replicas=[native, changed], point_universe=[('ratio', 'p_eta', 0, 0)])
    paired = result['uncertainty']['paired']['B-C']
    assert paired['points'][0]['successful'] == 1
    assert paired['points'][0]['failed'] == 1
    assert result['uncertainty']['scenario_replicas'][1]['failures']['B']


def test_cannot_mask_missing_brem_as_measured_truth(monkeypatch):
    from flux_studies import energy_closure as closure
    monkeypatch.setattr(closure, 'extract_sample', _fast_extraction)
    events, native = _inputs()
    native = {(811, 17): replace(native[(811, 17)], flux_brem=None, brem_status='missing')}
    with pytest.raises(ValueError, match='measured BREM'):
        closure.compare_energy_scenarios(events, native, native, native,
            masked_states={(811, 'BREM')}, accepted_runs={811}, energy_edges=[1.1, 1.5])


def test_unmasked_roundoff_from_root_bin_centers_is_not_a_physics_change(monkeypatch):
    from flux_studies import energy_closure as closure
    monkeypatch.setattr(closure, 'extract_sample', _fast_extraction)
    events, native = _inputs()
    changed = {(811, 17): replace(native[(811, 17)],
        energy_gev=np.nextafter(1.15, 2.), polarization_vertical=np.nextafter(.6, 1.))}
    result = closure.compare_energy_scenarios(events, native, changed, native,
        masked_states=set(), accepted_runs=set(), energy_edges=[1.1, 1.5])
    assert result['scenarios']['B']['status'] == 'estimable'


def test_real_application_recovers_unique_events_without_creating_an_oracle():
    from flux_studies.energy_closure import compare_recovered_sample
    events, native = _inputs()
    events = replace(events, run_number=np.where(np.arange(len(events)) % 2, 812, 811))
    recovered = {**native, (812, 17): replace(native[(811, 17)], run_number=812,
                                            flux_brem=None, brem_status='missing')}
    result = compare_recovered_sample(events, native, recovered, energy_edges=[1.1, 1.5],
        point_universe=[('ratio', 'p_eta', 0, 2)], event_replicas=2,
        flux_replicas=[recovered, None], seed=4)
    assert result['counts']['before_events'] == (len(events) + 1) // 2
    assert result['counts']['after_events'] == len(events)
    assert result['counts']['recovered_events'] == len(events) // 2
    assert set(result['scenarios']) == {'A', 'B'}
    assert result['interpretation'] == 'benefit_and_stability_not_bias'
    assert result['uncertainty']['total_uncertainty_available'] is False
    row = result['uncertainty']['paired']['B-A']['points'][0]
    assert (row['successful'], row['failed']) == (1, 1)
    assert result['uncertainty']['scenario_replicas'][1]['failures']['B']


def test_real_application_identical_maps_have_zero_paired_shift_and_equal_precision():
    from flux_studies.energy_closure import compare_recovered_sample
    events, native = _inputs()
    result = compare_recovered_sample(events, native, native, energy_edges=[1.1, 1.5],
        point_universe=[('ratio', 'p_eta', 0, 2)], event_replicas=3, seed=4,
        flux_replicas=[native, native, native])
    assert result['counts']['recovered_events'] == 0
    pair = result['uncertainty']['paired']['B-A']
    assert pair['points'][0]['mean_shift'] == 0.
    assert pair['points'][0]['shift_std'] == 0.
    assert pair['covariance'] == [[0.]]
    assert result['precision'][0]['joint_replica_std_ratio_B_over_A'] == 1.


def test_real_application_rejects_rewriting_existing_measured_pol():
    from flux_studies.energy_closure import compare_recovered_sample
    events, native = _inputs()
    changed = {(811, 17): replace(native[(811, 17)], flux_vertical=2.4)}
    with pytest.raises(ValueError, match='unmasked POL1'):
        compare_recovered_sample(events, native, changed, energy_edges=[1.1, 1.5])


def test_real_application_zero_available_baseline_retains_all_failed_points():
    from flux_studies.energy_closure import compare_recovered_sample
    events, recovered = _inputs()
    result = compare_recovered_sample(events, {}, recovered, energy_edges=[1.1, 1.5],
        point_universe=[('ratio', 'p_eta', 0, 2)], event_replicas=0)
    assert result['counts']['before_events'] == 0
    assert result['counts']['recovered_events'] == len(events)
    assert result['scenarios']['A']['missing_points'] == 1
    assert result['comparisons'][0]['status'] == 'missing_fit'
    assert result['precision'][0]['stat_ratio_B_over_A'] is None


def test_real_application_cannot_rewrite_measured_brem_near_missing_strip():
    from flux_studies.energy_closure import compare_recovered_sample
    events, native = _inputs()
    native[(811, 18)] = replace(native[(811, 17)], xstrip=18, flux_brem=None, brem_status='missing')
    recovered = {**native, (811, 17): replace(native[(811, 17)], flux_brem=99.),
                 (811, 18): replace(native[(811, 18)], flux_brem=.2, brem_status='estimated')}
    with pytest.raises(ValueError, match='measured BREM'):
        compare_recovered_sample(events, native, recovered, energy_edges=[1.1, 1.5])


def test_real_application_brem_only_recovery_does_not_gain_pol_events():
    from flux_studies.energy_closure import compare_recovered_sample
    events, native = _inputs()
    native = {(811, 17): replace(native[(811, 17)], flux_brem=None, brem_status='missing')}
    recovered = {(811, 17): replace(native[(811, 17)], flux_brem=.2, brem_status='estimated')}
    result = compare_recovered_sample(events, native, recovered, energy_edges=[1.1, 1.5])
    assert result['counts']['recovered_events'] == 0
    assert result['scenarios']['A']['points'] == result['scenarios']['B']['points']


def test_real_application_replica_cannot_change_independent_axis():
    from flux_studies.energy_closure import compare_recovered_sample
    events, recovered = _inputs()
    changed = {(811, 17): replace(recovered[(811, 17)], energy_gev=1.16)}
    result = compare_recovered_sample(events, {}, recovered, energy_edges=[1.1, 1.5],
        point_universe=[('ratio', 'p_eta', 0, 2)], event_replicas=1, flux_replicas=[changed])
    assert 'fixed calibration' in result['uncertainty']['scenario_replicas'][0]['failures']['B']
