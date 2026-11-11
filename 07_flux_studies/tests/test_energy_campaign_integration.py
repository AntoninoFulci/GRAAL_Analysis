"""Synthetic interfaces through model, uncertainty, policy, strips and closure.

The numeric policy here exists only to exercise software boundaries. The small
extractor observes event and flux changes; it makes no physics validation claim.
"""
from dataclasses import fields
from types import SimpleNamespace

import numpy as np

from flux_studies.tests.test_energy_validation import cohort


class _NoTruth(dict):
    def __getitem__(self, key):
        if key in ('truth', 'metrics', 'sigma'):
            raise AssertionError('acceptance accessed masked truth')
        return super().__getitem__(key)

    def get(self, key, *args):
        if key in ('truth', 'metrics', 'sigma'):
            raise AssertionError('acceptance accessed masked truth')
        return super().get(key, *args)


def _small_extraction(**kwargs):
    from observable_extraction.core.models import FitDiagnostics, SigmaPoint
    events, exposures = kwargs['events'], kwargs['exposures']
    if not len(events):
        return SimpleNamespace(points=[])
    # This lightweight boundary consumer responds to BOTH event resampling and
    # flux changes. Production ratio/likelihood fits have their own integration tests.
    flux_ratios = [exposures[int(r), int(s)].flux_vertical / exposures[int(r), int(s)].flux_horizontal
                   for r, s in zip(events.run_number, events.xstrip, strict=True)]
    sigma = float(np.mean(events.polarization) / 3 + np.mean(flux_ratios) / 100)
    return SimpleNamespace(points=[SimpleNamespace(estimator='ratio', point=SigmaPoint(
        'p_eta', 0, 0, 1.1, 1.5, 1.4, 1.5, 1.45, sigma, .1, .1,
        FitDiagnostics(True, 1., 1, .5, False)))])


def test_model_to_paired_closure_retains_truth_boundary_strips_and_failed_replicas(monkeypatch):
    from flux_studies.energy_validation import (evaluate_energy, calibrate_energy_uncertainty,
                                                energy_replicas, grouped_energy_coverage)
    from flux_studies.energy_protocol import decide_energy_runs
    from flux_studies.energy_recovery import IndependentStripAxis, map_energy_to_strips
    from flux_studies import energy_closure
    from observable_extraction.calibration.energy_exposures import build_projected_exposures
    from observable_extraction.io.reconstructed_events import EventArrays
    from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events

    rows, assignments = cohort()
    parameters = {('p', 'P', 'UV', state): dict(min_samples_leaf=1, max_features=1.)
                  for state in ('POL1', 'POL2')}
    masks = [(r['run'], 'POL1') for r in rows if r['state'] == 'POL1' and r['run'] % 6 == 3]
    masks.append((4, 'POL1'))
    study = evaluate_energy(rows, assignments=assignments, masks=masks, seed=3, parameters=parameters)
    calibrated = calibrate_energy_uncertainty(study, min_groups=1)
    uncertainty = energy_replicas(rows, study, calibrated, roles=('development',),
                                  n_replicas=8, seed=3, min_groups=1)
    predictions = [p for p in study['predictions'] if p['role'] == 'development']
    common_edges = np.array([1.1, 1.2, 1.3, 1.5])
    axes = {(run, state): IndependentStripAxis(run, state, np.linspace(1.1, 1.5, 129),
              dict(kind='inclusive_h80_calibration', source='synthetic independent acquisition'))
            for run in (1, 4) for state in ('POL1', 'POL2')}
    inventory = [dict(run=run, state=state, measurement_status='measured_valid', reasons=[])
                 for run in (1, 4) for state in ('POL1', 'POL2')]
    rule = dict(max_gap=100., min_count=1, min_replicas=2, min_groups=1,
                max_relative_integral_std=.1, min_valid_replica_fraction=.1)
    decision = decide_energy_runs([_NoTruth(p) for p in predictions], uncertainty, inventory, axes,
        rule, [dict(period='p', state='POL1', qualified=True, evidence='synthetic fixture only')],
        masked_states={(4, 'POL1')})
    assert decision['accepted_runs'] == [4]
    report = grouped_energy_coverage(study, uncertainty, min_groups=1, n_resamples=8, seed=3)
    hybrid = next(d for d in report['domains'] if d['method'] == 'extra_trees_hybrid')
    assert hybrid['group'] == ['p', 'P', 'UV', 'POL1']
    assert hybrid['expected_targets'] == 1

    measured = {}
    for row in rows:
        key = row['run'], row['state']
        if key in axes:
            projected = map_energy_to_strips(row['values'], common_edges, axes[key])
            measured[key] = dict(values=projected['values'], calibration_edges=projected['calibration_edges'])
    build = lambda projected: build_projected_exposures(measured, projected,
        polarization_model=lambda energy: .6, energy_range=(1.1, 1.5), replace_measured=True)[0]
    native = build({})
    prediction = next(p for p in predictions if p['method'] == 'extra_trees_hybrid')
    recovered_projection = map_energy_to_strips(prediction['estimate'], common_edges, axes[4, 'POL1'])
    recovered = build({(4, 'POL1'): recovered_projection})
    roundtrip = build({(4, 'POL1'): map_energy_to_strips(prediction['truth'], common_edges, axes[4, 'POL1'])})
    assert len(recovered) == 256
    assert set(recovered) == set(native)
    assert recovered[4, 17].xstrip == 17
    assert recovered[4, 17].brem_status == 'missing'
    assert recovered[4, 17].flux_brem is None
    assert recovered_projection['audit']['destination_integral'] == prediction['estimate'].sum()

    index = next(i for i, k in enumerate(uncertainty['keys']) if k['method'] == 'extra_trees_hybrid')
    maps = []
    for draw in uncertainty['draws'][:, index]:
        maps.append(build({(4, 'POL1'): map_energy_to_strips(draw, common_edges, axes[4, 'POL1'])})
                    if np.isfinite(draw).all() else None)
    maps[0] = None  # Lost replica remains aligned and counted through extraction.
    source = _synthetic_events()
    events = EventArrays(**{field.name: (None if getattr(source, field.name) is None else
        np.concatenate([np.full(len(source), run) if field.name == 'run_number'
                        else getattr(source, field.name) for run in (1, 4)])) for field in fields(source)})
    monkeypatch.setattr(energy_closure, 'extract_sample', _small_extraction)
    closure = energy_closure.compare_energy_scenarios(events, native, recovered, roundtrip,
        masked_states={(4, 'POL1')}, accepted_runs=set(decision['accepted_runs']),
        energy_edges=[1.1, 1.5], event_replicas=8, flux_replicas=maps, seed=3,
        point_universe=[('ratio', 'p_eta', 0, 0)])
    assert closure['counts']['baseline_pol_events'] == len(source)
    assert closure['counts']['paired_pol_events'] == 2 * len(source)
    assert closure['counts']['recovered_pol_events'] == len(source)
    paired = closure['uncertainty']['paired']['B-C']
    valid = sum(mapping is not None for mapping in maps)
    assert paired['requested'] == 8
    assert paired['points'][0]['successful'] == valid
    assert paired['points'][0]['failed'] == 8 - valid
    assert paired['points'][0]['shift_std'] == 0.
    assert closure['uncertainty']['total_uncertainty_available'] is False


def _campaign_fixture(monkeypatch, *, missing_states=()):
    import json
    from flux_studies import energy_campaign, energy_closure
    from flux_studies.energy_recovery import IndependentStripAxis, map_energy_to_strips
    from flux_studies.tests.test_energy_protocol import _limits
    from observable_extraction.calibration.energy_exposures import build_projected_exposures
    from observable_extraction.io.reconstructed_events import EventArrays
    from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events

    rows, assignments = cohort()
    rows = [r for r in rows if r['run'] > 0]
    assignments = [a for a in assignments if a['run'] > 0]
    edges = [1.1, 1.2, 1.3, 1.5]
    masks = [(r['run'], 'POL1') for r in rows if r['state'] == 'POL1' and r['run'] % 6 == 3]
    masks.append((4, 'POL1'))
    parameters = [dict(group=['p', 'P', 'UV', state],
                       parameters=dict(min_samples_leaf=1, max_features=1.)) for state in ('POL1', 'POL2')]
    config = dict(inputs={'reco': {'uv': 'synthetic'}}, cohort_runs=[a['run'] for a in assignments],
        energy_edges=edges, assignments=assignments, masks=masks, seed=3, replicas=8,
        min_groups=1, coverage_resamples=8, parameters=parameters,
        rule=dict(max_gap=100., min_count=1, min_replicas=2, min_groups=1,
                  max_relative_integral_std=.1, min_valid_replica_fraction=.1),
        normalization_domains=[dict(period='p', state='POL1', qualified=True, evidence='synthetic only')],
        limits=_limits(), point_universe=[['p', 'ratio', 'p_eta', 0, 0]],
        systematics=dict(status='not_qualified', scope='synthetic contract test'))
    axes = {(r['run'], r['state']): IndependentStripAxis(r['run'], r['state'], np.linspace(1.1, 1.5, 129),
            dict(kind='inclusive_h80_calibration', source='synthetic independent acquisition')) for r in rows}
    measured = {}
    for row in rows:
        key = row['run'], row['state']
        projected = map_energy_to_strips(row['values'], edges, axes[key])
        row['native_values'] = projected['values']
        row['calibration_edges'] = projected['calibration_edges']
        measured[key] = dict(values=row['native_values'], calibration_edges=row['calibration_edges'])
    inventory = [dict(run=a['run'], state=state, period='p',
                      measurement_status='missing_histogram' if state == 'BREM' or (a['run'], state) in missing_states
                      else 'measured_valid', reasons=[], position=a['run'] * 15., count=10.)
                 for a in assignments for state in ('POL1', 'POL2', 'BREM')]
    available_rows = [r for r in rows if (r['run'], r['state']) not in missing_states]
    dataset = dict(records=available_rows, diagnostic_records=available_rows, inventory=inventory,
                   run_quality={'excluded_runs': []}, input_audit={}, position_assumption='synthetic positions')
    manifest = {a['run']: SimpleNamespace(source_period='p', target='P', beam_type='UV') for a in assignments}
    campaign = dict(config=config, dataset=dataset, axes=axes, manifest=manifest, input_sha256={}, sources=[])
    source = _synthetic_events()
    events = EventArrays(**{field.name: (None if getattr(source, field.name) is None else
        np.concatenate([np.full(len(source), run) if field.name == 'run_number'
                        else getattr(source, field.name) for run in (1, 4)])) for field in fields(source)})
    native, audit = build_projected_exposures({k: v for k, v in measured.items() if k[0] in (1, 4) and k not in missing_states}, {},
        polarization_model=lambda energy: .6, energy_range=(1.1, 1.5))
    profile = SimpleNamespace(polarization=lambda energy: .6, energy_range_gev=(1.1, 1.5),
                              energy_edges_gev=np.array([1.1, 1.5]))
    loaded = dict(profile=profile, events=events, native=native, audit=audit, cutflow={},
                  runs={1, 4}, input_identity={'source': 'synthetic'})
    monkeypatch.setattr(energy_campaign, 'input_paths', lambda config: [])
    monkeypatch.setattr(energy_campaign, 'load_campaign', lambda config: campaign)
    monkeypatch.setattr(energy_campaign, '_profile_inputs', lambda campaign, runs: {'uv': loaded})
    monkeypatch.setattr(energy_closure, 'extract_sample', _small_extraction)
    return campaign, loaded, len(source)


def test_run_study_publishes_real_model_policy_projection_and_closure_contract(tmp_path, monkeypatch):
    import json
    from flux_studies import energy_campaign
    campaign, loaded, event_count = _campaign_fixture(monkeypatch)
    output = tmp_path / 'campaign'
    report = energy_campaign.run_study(campaign['config'], output)
    assert report['decisions']['accepted_runs'] == [4]
    assert report['production_adopted'] is False
    assert report['qualification']['status'] == 'insufficient_evidence'
    assert report['closure'][0]['counts']['recovered_pol_events'] == event_count
    assert not report['closure'][0]['projection_failures']
    saved = json.loads((output / 'report.json').read_text())
    assert saved['decisions'] == report['decisions']
    study = json.loads((output / 'study.json').read_text())
    assert study['feature_count'] == 12
    assert {p['method'] for p in study['predictions']} == {'linear', 'extra_trees_hybrid'}
    draws = json.loads((output / 'uncertainty.json').read_text())
    assert draws['requested_replicas'] == 8
    assert draws['combination'] == 'calibrated_total_residual_only'
    assert len(draws['draws']) == 8
    assert all(d['group'][-1] == 'POL1' for d in saved['coverage'])



def test_run_baseline_counts_pol_only_admission_and_publishes_measured_comparison(tmp_path, monkeypatch):
    import json
    from flux_studies import energy_campaign
    campaign, loaded, event_count = _campaign_fixture(monkeypatch)
    output = tmp_path / 'baseline'
    report = energy_campaign.run_baseline(campaign['config'], output)
    assert report['counts']['selected_events'] == 2 * event_count
    assert report['counts']['recovered_without_ml_events'] == 2 * event_count
    assert report['counts']['recovered_ml_events'] == 0
    assert report['sigma']['uv']['counts'] == dict(unique_selected_events=2 * event_count,
        before_events=0, after_events=2 * event_count, recovered_events=2 * event_count)
    assert report['sigma']['uv']['measured_oracle_available'] is False
    assert report['comparison_kind'] == 'measured POL admission only; no ML validation'
    saved = json.loads((output / 'baseline.json').read_text())
    assert saved['counts'] == report['counts']
    assert saved['production_adopted'] is False


def test_run_application_missing_pol_is_projected_without_rewriting_measured_states(tmp_path, monkeypatch):
    import json
    from flux_studies import energy_campaign, energy_closure, energy_protocol
    campaign, loaded, event_count = _campaign_fixture(monkeypatch, missing_states={(4, 'POL1')})
    assert not any(r['run'] == 4 and r['state'] == 'POL1' for r in campaign['dataset']['records'])
    assert not any(r['run'] == 4 and r['state'] == 'POL1' for r in campaign['dataset']['diagnostic_records'])
    assert {key[0] for key in loaded['native']} == {1}
    protocol, verification = tmp_path / 'protocol.json', tmp_path / 'verification.json'
    protocol.write_text('{}')
    verification.write_text('{}')
    monkeypatch.setattr(energy_protocol, 'load_protocol',
        lambda path: dict(config=campaign['config'], sha256='synthetic authenticated protocol'))
    monkeypatch.setattr(energy_protocol, 'load_verified_result',
        lambda *args: dict(closure=[], coverage=[dict(period='p', state='POL1')]))
    monkeypatch.setattr(energy_protocol, 'qualify_energy', lambda *args, **kwargs: {'status': 'qualified', 'qualified_domains': [['p', 'POL1']]})
    observed = []
    def consuming_extractor(**kwargs):
        observed.append(kwargs['exposures'])
        return _small_extraction(**kwargs)
    monkeypatch.setattr(energy_closure, 'extract_sample', consuming_extractor)
    output = tmp_path / 'application'
    report = energy_campaign.run_application(protocol, verification, output)
    accepted = {(r['run'], r['state']) for r in report['decisions']['state_decisions'] if r['accepted']}
    assert accepted == {(4, 'POL1')}
    comparison = report['comparisons']['uv']
    assert comparison['counts'] == dict(unique_selected_events=2 * event_count,
        before_events=event_count, after_events=2 * event_count, recovered_events=event_count)
    assert comparison['measured_oracle_available'] is False
    assert set(comparison['scenarios']) == {'A', 'B'}
    assert all(row['reference'] == 'A' and row['scenario'] == 'B' for row in comparison['comparisons'])
    assert comparison['projection_audit']['4']['states']['POL1']['status'] == 'projected'
    assert comparison['projection_audit']['4']['states']['POL2']['status'] == 'measured_valid'
    measured_pol2 = next(r for r in campaign['dataset']['records'] if r['run'] == 4 and r['state'] == 'POL2')
    recovered_maps = [m for m in observed if (4, 17) in m]
    assert recovered_maps
    assert all(m[4, 17].flux_horizontal == measured_pol2['native_values'][16] for m in recovered_maps)
    assert all(m[1, 17] == loaded['native'][1, 17] for m in observed)
    candidates = json.loads((output / 'energy_candidates.json').read_text())
    assert not candidates['projection_failures']
    assert all('truth' not in p and 'metrics' not in p for p in candidates['predictions'])
    assert candidates['production_adopted'] is False
    assert report['production_adopted'] is False
    assert comparison['uncertainty']['requested_replicas'] == 8
    assert comparison['uncertainty']['flux_propagated'] is True
    assert json.loads((output / 'report.json').read_text())['comparisons']['uv']['counts'] == comparison['counts']



def test_run_application_brem_only_missing_stays_explicit_without_pol_event_gain(tmp_path, monkeypatch):
    import json
    from flux_studies import energy_campaign, energy_protocol
    campaign, loaded, event_count = _campaign_fixture(monkeypatch)
    protocol, verification = tmp_path / 'protocol.json', tmp_path / 'verification.json'
    protocol.write_text('{}')
    verification.write_text('{}')
    monkeypatch.setattr(energy_protocol, 'load_protocol',
        lambda path: dict(config=campaign['config'], sha256='synthetic authenticated protocol'))
    monkeypatch.setattr(energy_protocol, 'load_verified_result',
        lambda *args: dict(closure=[], coverage=[dict(period='p', state='POL1')]))
    monkeypatch.setattr(energy_protocol, 'qualify_energy',
        lambda *args, **kwargs: {'status': 'qualified', 'qualified_domains': [['p', 'POL1']]})
    output = tmp_path / 'brem-only'
    report = energy_campaign.run_application(protocol, verification, output)
    assert report['decisions']['accepted_runs'] == []
    assert report['decisions']['state_decisions']
    assert all(r['state'] == 'BREM' and r['reasons'] == ['domain_not_qualified']
               for r in report['decisions']['state_decisions'])
    comparison = report['comparisons']['uv']
    assert comparison['counts'] == dict(unique_selected_events=2 * event_count,
        before_events=2 * event_count, after_events=2 * event_count, recovered_events=0)
    assert comparison['measured_oracle_available'] is False
    assert set(comparison['scenarios']) == {'A', 'B'}
    candidates = json.loads((output / 'energy_candidates.json').read_text())
    assert candidates['predictions'] == []
    assert report['production_adopted'] is False
