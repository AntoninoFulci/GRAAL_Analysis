"""Truth isolation, statistical grouping and dynamic-grid recovery contracts."""
import copy

import numpy as np
import pytest


def cohort():
    rows, assignments = [], []
    for run in range(36):
        role = ('train', 'train', 'train', 'calibration', 'development', 'final')[run % 6]
        assignments.append(dict(run=run, period='p', block=run, role=role))
        for state in ('POL1', 'POL2'):
            rows.append(dict(run=run, period='p', state=state, group=('p', 'P', 'UV', state),
                             position=run * 15., count=10., measured_energy_support=[1.1, 1.5], values=np.array([1., 2., 3.]) * (10 + run)))
    return rows, assignments


def api():
    from flux_studies import energy_validation
    return energy_validation


def test_dynamic_features_statewise_donors_and_no_extrapolation():
    engine = api()
    rows, assignments = cohort()
    targets = [r for r in rows if r['run'] in (4, 35)]
    result = engine.predict_energy(rows, targets, assignments=assignments, seed=0,
        parameters={('p', 'P', 'UV', s): dict(min_samples_leaf=1, max_features=1.)
                    for s in ('POL1', 'POL2')})
    first = next(p for p in result['predictions'] if p['run'] == 4 and p['method'] == 'linear')
    np.testing.assert_allclose(first['estimate'], [14., 28., 42.])
    assert first['donors'] == [2, 6]
    assert result['feature_count'] == 12
    assert all(p['status'] == 'no_training_bracket' for p in result['predictions'] if p['run'] == 35)
    assert result['summary']['expected'] == 8
    assert result['summary']['failed'] == 4


def test_truth_mutation_cannot_change_models_predictions_or_donors():
    engine = api()
    rows, assignments = cohort()
    masks = [(r['run'], r['state']) for r in rows if r['run'] % 6 in (3, 4)]
    one = engine.evaluate_energy(rows, assignments=assignments, masks=masks, seed=1)
    changed = copy.deepcopy(rows)
    for row in changed:
        if row['run'] % 6 in (3, 4, 5):
            row['values'][:] = 1e30
    two = engine.evaluate_energy(changed, assignments=assignments, masks=masks, seed=1)
    assert one['fits'] == two['fits']
    for a, b in zip(one['predictions'], two['predictions'], strict=True):
        np.testing.assert_array_equal(a['estimate'], b['estimate'])
        assert a['donors'] == b['donors']
    assert {p['method'] for p in one['predictions']} == {'linear', 'extra_trees_hybrid'}
    for fit in one['fits']:
        for fold in fit['tuning']['folds']:
            assert not set(fold['fit_runs']) & set(fold['held_runs'])
            assert all(r % 6 < 3 for r in fold['fit_runs'] + fold['held_runs'])


def test_partition_leak_and_unfrozen_final_are_rejected():
    engine = api()
    rows, assignments = cohort()
    assignments[3]['block'] = assignments[2]['block']
    with pytest.raises(ValueError, match='block'):
        engine.validate_partitions(rows, assignments)
    rows, assignments = cohort()
    with pytest.raises(ValueError, match='frozen'):
        engine.evaluate_energy(rows, assignments=assignments, masks=[(5, 'POL1')], seed=0)


def test_replicas_separate_integral_shape_and_never_read_target_truth():
    engine = api()
    rows, assignments = cohort()
    masks = [(r['run'], r['state']) for r in rows if r['run'] % 6 in (3, 4)]
    study = engine.evaluate_energy(rows, assignments=assignments, masks=masks, seed=0)
    calibration = engine.calibrate_energy_uncertainty(study, min_groups=1)
    one = engine.energy_replicas(rows, study, calibration, roles=('development',),
                                  n_replicas=4, seed=3, min_groups=1)
    altered = copy.deepcopy(study)
    for prediction in altered['predictions']:
        if prediction['role'] == 'development':
            prediction['truth'][:] = 1e30
    for row in rows:
        if row['run'] % 6 in (4, 5):
            row['values'][:] = 1e30
    two = engine.energy_replicas(rows, altered, calibration, roles=('development',),
                                  n_replicas=4, seed=3, min_groups=1)
    assert one['draws'].shape == (4, 24, 3)
    np.testing.assert_array_equal(one['draws'], two['draws'])
    assert np.isfinite(one['draws']).any()
    assert one['combination'] == 'calibrated_total_residual_only'
    for audit in one['bootstrap_audit']:
        for target in audit['targets']:
            for other in audit['targets']:
                if set(target['donors']) & set(other['donors']):
                    assert target['residual_run'] == other['residual_run']
    insufficient = engine.calibrate_energy_uncertainty(study, min_groups=100)
    failed = engine.energy_replicas(rows, study, insufficient, roles=('development',),
                                    n_replicas=3, seed=3, min_groups=100)
    assert np.isnan(failed['draws']).all()
    assert all(p['requested_replicas'] == 3 for p in failed['target_summary'])
    report = engine.grouped_energy_coverage(study, one, min_groups=100, n_resamples=10, seed=1)
    assert report['status'] == 'insufficient_groups'
    assert report['expected_targets'] == 24
    assert len(report['domains']) == 4
    assert all(d['expected_targets'] == 6 and d['status'] == 'insufficient_groups'
               for d in report['domains'])


def test_state_eligibility_whole_run_mask_and_missing_truth_application():
    engine = api()
    rows, assignments = cohort()
    # POL1 can donate although this run has no valid POL2/BREM.
    rows = [r for r in rows if not (r['run'] == 2 and r['state'] == 'POL2')]
    target = next(r for r in rows if r['run'] == 4 and r['state'] == 'POL1').copy()
    del target['values']
    parameters = {('p', 'P', 'UV', s): dict(min_samples_leaf=1, max_features=1.)
                  for s in ('POL1', 'POL2')}
    result = engine.predict_energy(rows, [target], assignments=assignments, seed=0, parameters=parameters)
    assert result['predictions'][0]['donors'] == [2, 6]
    np.testing.assert_allclose(result['predictions'][0]['estimate'], [14., 28., 42.])
    # A quality exclusion is whole-run even if only one state carries the flag.
    next(r for r in rows if r['run'] == 2)['quality_excluded'] = True
    result = engine.predict_energy(rows, [target], assignments=assignments, seed=0, parameters=parameters)
    assert result['predictions'][0]['donors'] == [1, 6]
    # Masking a training run removes its other state from every training example.
    target = next(r for r in rows if r['run'] == 7 and r['state'] == 'POL1').copy()
    del target['values']
    result = engine.predict_energy(rows, [target], assignments=assignments, seed=0, parameters=parameters)
    assert 7 not in result['predictions'][0]['donors']
    assert 'truth' not in result['predictions'][0]


def test_quality_flag_is_whole_run_and_target_metadata_must_match():
    engine = api()
    rows, assignments = cohort()
    next(r for r in rows if r['run'] == 2 and r['state'] == 'POL1')['quality_excluded'] = True
    target = next(r for r in rows if r['run'] == 4 and r['state'] == 'POL2').copy()
    parameters = {('p', 'P', 'UV', s): dict(min_samples_leaf=1, max_features=1.)
                  for s in ('POL1', 'POL2')}
    result = engine.predict_energy(rows, [target], assignments=assignments, seed=0, parameters=parameters)
    assert result['predictions'][0]['donors'] == [1, 6]
    target['position'] = 55.
    with pytest.raises(ValueError, match='metadata'):
        engine.predict_energy(rows, [target], assignments=assignments, seed=0, parameters=parameters)


def test_replica_uncertainty_summary_and_beam_domains_are_separate():
    engine = api()
    rows, assignments = cohort()
    extra = []
    for row in rows:
        extra.append({**row, 'run': row['run'] + 100, 'position': row['position'] + 1000,
                      'group': ('p', 'P', 'VIS', row['state'])})
    assignments += [{**a, 'run': a['run']+100, 'block': a['block']+100} for a in assignments.copy()]
    rows += extra
    masks = [(r['run'], r['state']) for r in rows if (r['run'] % 100) % 6 in (3, 4)]
    study = engine.evaluate_energy(rows, assignments=assignments, masks=masks, seed=0)
    calibration = engine.calibrate_energy_uncertainty(study, min_groups=1)
    result = engine.energy_replicas(rows, study, calibration, roles=('development',),
                                    n_replicas=4, seed=3, min_groups=1)
    assert np.isfinite(result['draws'][:, :24]).any()
    assert np.isfinite(result['draws'][:, 24:]).any()
    assert all('relative_integral_uncertainty' in r for r in result['target_summary'])
    for replica in range(4):
        samples = [a['sampled_blocks'] for a in result['bootstrap_audit'] if a['replica'] == replica]
        assert samples[0] == samples[1]
    for audit in result['bootstrap_audit']:
        for target in audit['targets']:
            if target['residual_run'] is not None:
                assert (target['residual_run'] >= 100) == (target['run'] >= 100)


def test_quality_excluded_target_is_failed_across_all_states_and_keeps_denominator():
    engine = api()
    rows, assignments = cohort()
    next(r for r in rows if r['run'] == 4 and r['state'] == 'POL1')['quality_excluded'] = True
    study = engine.evaluate_energy(rows, assignments=assignments, masks=[(4, 'POL2')], seed=0)
    assert study['summary'] == {'expected': 2, 'available': 0, 'failed': 2}
    assert all(p['status'] == 'ineligible_target' for p in study['predictions'])


def test_frozen_final_keeps_config_and_obeys_minimum_support_per_domain():
    engine = api()
    rows, assignments = cohort()
    params = {('p', 'P', 'UV', s): dict(min_samples_leaf=3, max_features=.5)
              for s in ('POL1', 'POL2')}
    study = engine.evaluate_energy(rows, assignments=assignments, masks=[(5, 'POL1')],
                                   seed=1, parameters=params)
    assert all(f['tuning'] is None and f['parameters']['min_samples_leaf'] == 3 for f in study['fits'])
    assert all(p['role'] == 'final' for p in study['predictions'])
    assert all(p['donors'] == [2, 6] for p in study['predictions'])
    calibration = engine.calibrate_energy_uncertainty(study, min_groups=2)
    result = engine.energy_replicas(rows, study, calibration, roles=('final',),
                                    n_replicas=3, seed=1, min_groups=2)
    assert np.isnan(result['draws']).all()
    assert all(r['relative_integral_uncertainty'] is None for r in result['target_summary'])


def test_calibration_keeps_integral_and_shape_distinct_after_json_roundtrip():
    engine = api()
    study = dict(assignments=[dict(period='p', run=1, block=1, role='calibration'),
                              dict(period='p', run=2, block=2, role='development')],
        predictions=[dict(period='p', run=1, state='POL1', method='extra_trees_hybrid',
                          group=['p', 'P', 'UV', 'POL1'], role='calibration', status='available',
                          donors=[0, 3], estimate=[40., 60.], truth=[160., 40.]),
                     dict(period='p', run=2, state='POL1', method='extra_trees_hybrid',
                          group=['p', 'P', 'UV', 'POL1'], role='development', status='available',
                          donors=[0, 3], estimate=[1., 1.], truth=[1e30, 1e30])])
    calibration = engine.calibrate_energy_uncertainty(study, min_groups=1)
    assert len(calibration['residuals']) == 1
    residual = calibration['residuals'][0]
    assert residual['log_integral'] == pytest.approx(np.log(2.))
    np.testing.assert_allclose(residual['shape'], [.4, -.4])


def test_actual_missing_training_role_can_receive_truth_free_replicas():
    engine = api()
    rows, assignments = cohort()
    params = {('p', 'P', 'UV', s): dict(min_samples_leaf=1, max_features=1.)
              for s in ('POL1', 'POL2')}
    calibration_study = engine.evaluate_energy(rows, assignments=assignments,
        masks=[(r['run'], r['state']) for r in rows if r['run'] % 6 == 3], seed=0, parameters=params)
    calibration = engine.calibrate_energy_uncertainty(calibration_study, min_groups=1)
    target = next(r for r in rows if r['run'] == 7 and r['state'] == 'POL1').copy()
    del target['values']
    study = engine.predict_energy(rows, [target], assignments=assignments, seed=0, parameters=params)
    replicas = engine.energy_replicas(rows, study, calibration, roles=('train',),
                                     n_replicas=5, seed=3, min_groups=1)
    assert np.isfinite(replicas['draws']).any()
    assert all(7 not in a['sampled_runs'] for a in replicas['bootstrap_audit'])


def test_energy_support_is_the_donor_intersection_never_target_truth_axis():
    engine = api()
    rows, assignments = cohort()
    for row in rows:
        if row['run'] == 2:
            row['measured_energy_support'] = [1.15, 1.5]
        if row['run'] == 6:
            row['measured_energy_support'] = [1.1, 1.45]
    target = next(r for r in rows if r['run'] == 4 and r['state'] == 'POL1')
    parameters = {('p', 'P', 'UV', 'POL1'): dict(min_samples_leaf=1, max_features=1.)}
    result = engine.predict_energy(rows, [target], assignments=assignments, seed=0, parameters=parameters)
    assert all(p['energy_support'] == [1.15, 1.45] for p in result['predictions'])
    next(r for r in rows if r['run'] == 2 and r['state'] == 'POL1').pop('measured_energy_support')
    result = engine.predict_energy(rows, [target], assignments=assignments, seed=0, parameters=parameters)
    assert all(p['energy_support'] is None for p in result['predictions'])


def test_empty_training_uses_declared_grid_and_keeps_attempted_denominator():
    engine = api()
    rows, assignments = cohort()
    for assignment in assignments:
        if assignment['role'] == 'train':
            assignment['role'] = 'development'
    target = next(r for r in rows if r['run'] == 4 and r['state'] == 'POL1').copy()
    target.pop('values')
    params = {('p', 'P', 'UV', 'POL1'): dict(min_samples_leaf=1, max_features=1.)}
    study = engine.predict_energy(rows, [target], assignments=assignments, seed=0, parameters=params, n_bins=3)
    assert study['summary'] == {'expected': 2, 'available': 0, 'failed': 2}
    assert all(p['status'] == 'no_training_bracket' for p in study['predictions'])
    calibration = engine.calibrate_energy_uncertainty(study, min_groups=1)
    replicas = engine.energy_replicas(rows, study, calibration, roles=('development',),
                                     n_replicas=3, seed=0, min_groups=1)
    assert replicas['draws'].shape == (3, 2, 3)
    assert np.isnan(replicas['draws']).all()
    evaluated = engine.evaluate_energy(rows, assignments=assignments, masks=[(4, 'POL1')], seed=0, n_bins=3)
    assert evaluated['summary']['failed'] == 2


def test_unsupported_brem_or_other_pol_state_does_not_veto_supported_state():
    engine = api()
    rows, assignments = cohort()
    rows += [{**r, 'state': 'BREM', 'group': ('p', 'P', 'UV', 'BREM')}
             for r in rows.copy() if r['state'] == 'POL1']
    params = {('p', 'P', 'UV', s): dict(min_samples_leaf=1, max_features=1.)
              for s in ('POL1', 'POL2', 'BREM')}
    calibration_masks = [(r['run'], 'POL1') for r in rows if r['state'] == 'POL1' and r['run'] % 6 == 3]
    baseline = engine.evaluate_energy(rows, assignments=assignments, masks=calibration_masks+[(4, 'POL1')],
                                      seed=0, parameters=params)
    study = engine.evaluate_energy(rows, assignments=assignments,
        masks=calibration_masks+[(4, 'POL1'), (4, 'POL2'), (4, 'BREM')], seed=0, parameters=params)
    calibration = engine.calibrate_energy_uncertainty(study, min_groups=1)
    before = engine.energy_replicas(rows, baseline, calibration, roles=('development',),
                                    n_replicas=5, seed=3, min_groups=1)
    after = engine.energy_replicas(rows, study, calibration, roles=('development',),
                                   n_replicas=5, seed=3, min_groups=1)
    for i, key in enumerate(after['keys']):
        if key['state'] == 'POL1':
            original = next(j for j, other in enumerate(before['keys']) if other == key)
            np.testing.assert_array_equal(after['draws'][:, i], before['draws'][:, original])
            assert np.isfinite(after['draws'][:, i]).any()
        else:
            assert np.isnan(after['draws'][:, i]).all()
    support = {r['state']: r for r in after['residual_support']}
    assert support['POL1']['status'] == 'available'
    assert support['POL2']['status'] == support['BREM']['status'] == 'insufficient_groups'
