"""Hybrid/model-search contracts independent of the publication layer."""
import numpy as np

from flux_studies.tests.test_calibrated_neighbors import records


def test_hybrid_preserves_baseline_integral_and_rejects_missing_shape():
    from flux_studies.neighbor_models import hybrid_prediction
    np.testing.assert_allclose(hybrid_prediction(np.array([-2., 1., 3.]), 20.), [0., 5., 15.])
    assert hybrid_prediction(np.zeros(128), 20.) is None


def test_all_models_grid_defaults_determinism_and_test_isolation():
    from flux_studies.neighbor_validation import evaluate_neighbors, split_runs
    rows = records(45)[::3]
    for row in rows:
        row['values'] *= 1 + .2 * np.sin(np.linspace(0, 6, 128) + row['run'] / 8)
    roles, _ = split_runs(range(1, 46), block_size=1, seed=42)
    models = ('ridge', 'kernel_ridge', 'extra_trees')
    first = evaluate_neighbors(rows, block_size=1, seed=42, models=models)
    changed = [{**r, 'values': r['values'] * (20 if roles[r['run']] == 'test' else 1)} for r in rows]
    second = evaluate_neighbors(changed, block_size=1, seed=42, models=models)
    expected = {'nearest', 'linear_unscaled', 'linear'}
    expected.update(f'{family}{suffix}' for family in models
                    for suffix in ('', '_hybrid', '_default', '_default_hybrid'))
    assert {p['method'] for p in first['predictions']} == expected
    linear = {(p['run'], p['role']): p for p in first['predictions'] if p['method'] == 'linear'}
    for a, b in zip(first['predictions'], second['predictions'], strict=True):
        np.testing.assert_array_equal(a['estimate'], b['estimate'])
        if a['lower95'] is not None:
            np.testing.assert_array_equal(a['lower95'], b['lower95'])
        if a['method'].endswith('_hybrid'):
            np.testing.assert_allclose(a['predicted_integral'], linear[a['run'], a['role']]['predicted_integral'], rtol=1e-14)
    for family, size in [('ridge', 7), ('kernel_ridge', 9), ('extra_trees', 6)]:
        model = first['fits'][0]['models'][family]
        assert len(model['candidates']) == size
        assert model == second['fits'][0]['models'][family]
        for candidate in model['candidates']:
            assert len(candidate['folds']) == 3
            assert candidate['direct']['n'] > 0
            assert candidate['hybrid']['n'] > 0
            assert candidate['direct']['shape_l1'] is not None
            assert candidate['direct']['absolute_relative_integral_error'] is not None
        for kind in ('direct', 'hybrid'):
            chosen = next(c for c in model['candidates'] if c['parameters'] == model['selected'][kind])
            assert chosen[kind]['relative_l1'] == min(c[kind]['relative_l1'] for c in model['candidates'])
        for fold in model['folds']:
            fit_runs, held_runs = set(fold['fit_runs']), set(fold['held_runs'])
            assert not fit_runs & held_runs
            for example in fold['training_examples'] + fold['held_examples']:
                assert set(example['donors']) <= fit_runs
                assert not set(example['donors']) & held_runs
    assert first['fits'][0]['intervals']['extra_trees_hybrid']['n'] >= 5


def test_inner_fold_features_do_not_read_held_truth():
    from flux_studies.neighbor_validation import _inner_folds
    rows = records(45)[::3]
    blocks = {r['run']: (r['run'] - 1) // 3 for r in rows}
    first = _inner_folds(rows, blocks)[0]
    held_runs = set(first[2]['held_runs'])
    changed = [{**r, 'values': r['values'] * (100 if r['run'] in held_runs else 1)} for r in rows]
    second = _inner_folds(changed, blocks)[0]
    for a, b in zip(first[0] + first[1], second[0] + second[1], strict=True):
        np.testing.assert_array_equal(a[1]['features'], b[1]['features'])
    for a, b in zip(first[0], second[0], strict=True):
        np.testing.assert_array_equal(a[0]['values'], b[0]['values'])


def test_zero_model_shape_is_reported_as_unavailable():
    from flux_studies.neighbor_validation import evaluate_neighbors
    rows = records(30)[::3]
    for row in rows:
        row['values'][:] = 0
    study = evaluate_neighbors(rows, block_size=1, seed=42)
    assert not any(p['method'].endswith('_hybrid') for p in study['predictions'])
    assert any(e.get('method') == 'ridge_default_hybrid' and e['reason'] == 'zero_predicted_shape'
               for e in study['exclusions'])


def test_supplied_split_universe_retains_assignments_but_never_excluded_donors():
    from flux_studies.neighbor_validation import evaluate_neighbors, split_runs
    rows = records(45)[::3]
    excluded = {4, 11, 30}
    rows = [r for r in rows if r['run'] not in excluded]
    study = evaluate_neighbors(rows, block_size=3, seed=42,
                               split_runs_by_period={'p': list(range(1, 46))})
    roles, blocks = split_runs(range(1, 46), block_size=3, seed=42)
    assert study['splits']['p'] == [dict(run=r, role=roles[r], block=blocks[r]) for r in sorted(roles)]
    for prediction in study['predictions']:
        assert prediction['run'] not in excluded
        assert not set(prediction['donors']) & excluded
        assert prediction['role'] == roles[prediction['run']]
