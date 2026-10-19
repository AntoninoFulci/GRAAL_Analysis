"""Isolation and dependence invariants for native neighbor uncertainty."""
import copy
import numpy as np

from flux_studies.tests.test_calibrated_neighbors import records
from flux_studies.neighbor_validation import evaluate_neighbors


def example():
    rows = records(120)
    for r in rows:
        r['values'] *= 1 + .05 * np.sin(r['run'])
    study = evaluate_neighbors(rows, block_size=3, seed=42, models=())
    return rows, study


def test_replicas_do_not_read_test_truth_and_keep_state_draws_paired():
    from flux_studies.flux_uncertainty import neighbor_replicas
    rows, study = example()
    a = neighbor_replicas(rows, study, methods=('linear',), n_replicas=8, seed=7)
    assert all(s['status'] == 'available' for s in a['residual_support'])
    assert np.isfinite(a['draws']).any()
    changed = copy.deepcopy(study)
    for p in changed['predictions']:
        if p['role'] == 'test':
            p['truth'][:] = 1e30
    held = {p['run'] for p in changed['predictions'] if p['role'] == 'test'}
    altered = [{**r, 'values': np.full(128, 1e30) if r['run'] in held else r['values']} for r in rows]
    b = neighbor_replicas(altered, changed, methods=('linear',), n_replicas=8, seed=7)
    np.testing.assert_array_equal(a['draws'], b['draws'])
    assert a['draws'].shape[0] == 8
    for i, key in enumerate(a['keys']):
        matching = [j for j, other in enumerate(a['keys']) if key['run'] == other['run']]
        for j in matching:
            np.testing.assert_array_equal(a['draws'][:, i], a['draws'][:, j])
    assert all(set(x['sampled_runs']) <= set(x['training_runs']) for x in a['bootstrap_audit'])


def test_invalid_replicas_preserve_requested_denominator():
    from flux_studies.flux_uncertainty import neighbor_replicas, closure_replicas
    rows, study = example()
    result = neighbor_replicas(rows, study, methods=('linear',), n_replicas=5, seed=4)
    output = closure_replicas(result)
    assert len(output['linear']['p']) == 5
    for index, row in enumerate(result['keys']):
        assert result['target_summary'][index]['requested_replicas'] == 5
        assert result['target_summary'][index]['valid_replicas'] <= 5
    result['draws'][0, 0] = np.nan
    assert np.isnan(closure_replicas(result)['linear']['p'][0][(result['keys'][0]['run'], result['keys'][0]['state'])]).all()


def test_missing_validation_pairs_are_unavailable_not_zero_uncertainty():
    from flux_studies.flux_uncertainty import neighbor_replicas
    rows, study = example()
    study['predictions'] = [p for p in study['predictions'] if p['role'] != 'validation']
    result = neighbor_replicas(rows, study, methods=('linear',), n_replicas=3, seed=0)
    assert np.isnan(result['draws']).all()
    assert all(r['valid_replicas'] == 0 for r in result['target_summary'])


def test_bootstrap_shared_donors_share_the_actual_residual_innovation():
    from flux_studies.flux_uncertainty import neighbor_replicas, _clusters
    rows, study = example()
    result = neighbor_replicas(rows, study, methods=('linear',), n_replicas=32, seed=7)
    original = [p for p in study['predictions'] if p['role'] == 'test' and p['method'] == 'linear']
    blocks = {a['run']: a['block'] for a in study['splits']['p']}
    original_clusters = _clusters(original, blocks)
    residuals = {(p['run'], p['state'], p['method']):
                 (p['truth'] - p['estimate']) / p['estimate'].sum()
                 for p in study['predictions'] if p['role'] == 'validation'}
    newly_shared = 0
    for audit in result['bootstrap_audit']:
        targets = audit['targets']
        for index, target in enumerate(targets):
            if not target['donors']:
                assert target['status'] == 'no_training_bracket'
                continue
            source = target['residual_run']
            assert source in result['residual_support'][0]['paired_validation_runs']
            i = target['prediction_index']
            estimate = result['model_draws'][audit['replica'], i]
            expected = np.maximum(estimate + estimate.sum() * residuals[
                source, target['state'], target['method']], 0.)
            np.testing.assert_array_equal(result['draws'][audit['replica'], i], expected)
            for other in targets[index + 1:]:
                if set(target['donors']) & set(other['donors']):
                    assert source == other['residual_run']
                    if original_clusters[target['run']] != original_clusters[other['run']]:
                        newly_shared += 1
    assert newly_shared > 0, 'fixture must exercise donors shared only after bootstrap'
    complete = np.isfinite(result['draws']).all(axis=(1, 2))
    assert 0 < complete.sum() < 32, 'failed full-period draws must remain in the denominator'
