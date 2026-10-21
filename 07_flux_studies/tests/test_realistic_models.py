"""Truth-free missing targets and externally fixed whole-run holdouts."""
import numpy as np
import pytest

from flux_studies.tests.test_calibrated_neighbors import records
from flux_studies import neighbor_validation as nv


def explicit_plan(n):
    return {'p': [dict(run=r, role='test' if r in (10, 11) else
                       'validation' if r in (20, 21) else 'train', block=(r - 1) // 2)
                  for r in range(1, n + 1)]}


def test_explicit_holdouts_never_contribute_donors_or_fits():
    rows = records(36)
    plan = explicit_plan(36)
    # Choose whole blocks with consistent roles.
    for item in plan['p']:
        item['role'] = 'test' if item['block'] == 5 else 'validation' if item['block'] == 10 else 'train'
    result = nv.evaluate_neighbors(rows, block_size=2, seed=1, split_plan=plan, models=('extra_trees',))
    held = {r['run'] for r in plan['p'] if r['role'] != 'train'}
    assert result['splits'] == plan
    assert {p['state'] for p in result['predictions'] if p['role'] == 'test'} == {'POL1', 'POL2', 'BREM'}
    for p in result['predictions']:
        assert not held.intersection(p['donors'])
    for fit in result['fits']:
        assert not held.intersection(e['run'] for e in fit['training_examples'])
    changed = [{**r, 'values': r['values'] * (99 if r['run'] in held else 1)} for r in rows]
    again = nv.evaluate_neighbors(changed, block_size=2, seed=1, split_plan=plan, models=('extra_trees',))
    for a, b in zip(result['predictions'], again['predictions'], strict=True):
        np.testing.assert_array_equal(a['estimate'], b['estimate'])
    assert result['fits'][0]['models'] == again['fits'][0]['models']


@pytest.mark.parametrize('defect', ['missing', 'extra', 'duplicate', 'role', 'mixed_block', 'period'])
def test_split_plan_rejects_ambiguous_or_incomplete_universe(defect):
    plan = {'p': [dict(run=r, role='train', block=r) for r in range(1, 9)]}
    if defect == 'missing':
        plan['p'].pop()
    elif defect == 'extra':
        plan['p'].append(dict(run=99, role='train', block=99))
    elif defect == 'duplicate':
        plan['p'].append(plan['p'][0].copy())
    elif defect == 'role':
        plan['p'][0]['role'] = 'holdout'
    elif defect == 'mixed_block':
        plan['p'][1].update(block=1, role='test')
    else:
        plan['other'] = []
    with pytest.raises(ValueError):
        nv.evaluate_neighbors(records(8), block_size=1, seed=0, split_plan=plan, models=())


def test_explicit_plan_can_cover_prepolicy_runs_without_training_on_them():
    plan = {'p': [dict(run=r, role='train', block=r) for r in range(1, 9)]}
    result = nv.evaluate_neighbors(records(7), block_size=1, seed=0, models=(),
                                   split_plan=plan, split_runs_by_period={'p': range(1, 9)})
    assert result['splits'] == plan
    assert all(8 not in p['donors'] for p in result['predictions'])


def test_missing_target_truth_and_axis_are_irrelevant_and_grid_is_training_only():
    rows = records(30)[::3]
    target = {k: v for k, v in rows[14].items() if k != 'values'}
    rows = [r for r in rows if r['run'] != target['run']]
    models = ('extra_trees', 'kernel_ridge')
    first = nv.predict_missing_neighbors(rows, [target], models=models, seed=7)
    second = nv.predict_missing_neighbors(rows, [{**target, 'values': object(), 'axis': object()}],
                                          models=models, seed=7)
    assert first['methods'] == ['linear', 'extra_trees', 'extra_trees_hybrid', 'kernel_ridge', 'kernel_ridge_hybrid']
    assert len(first['predictions']) == 5
    for a, b in zip(first['predictions'], second['predictions'], strict=True):
        np.testing.assert_array_equal(a['estimate'], b['estimate'])
        assert a['donors'] == [14, 16]
        assert 'truth' not in a and 'relative_l1' not in a and 'true_integral' not in a
        assert a['lower95'] is None and a['uncertainty_status'].startswith('unavailable')
        if a['method'].endswith('_hybrid'):
            np.testing.assert_allclose(a['predicted_integral'], first['predictions'][0]['predicted_integral'])
    for family in models:
        metadata = first['fits'][0]['models'][family]
        assert metadata == second['fits'][0]['models'][family]
        for kind in ('direct', 'hybrid'):
            selected = next(c for c in metadata['candidates'] if c['parameters'] == metadata['selected'][kind])
            eligible = [c for c in metadata['candidates'] if c[kind]['n'] == c[kind]['expected'] and c[kind]['n']]
            assert selected[kind]['relative_l1'] == min(c[kind]['relative_l1'] for c in eligible)
        for fold in metadata['folds']:
            assert target['run'] not in fold['fit_runs'] + fold['held_runs']
            for example in fold['held_examples'] + fold['training_examples']:
                assert not set(example['donors']).intersection(fold['held_runs'])


def test_missing_candidates_require_brackets_and_never_invent_zero_shape():
    rows = records(12)[::3]
    for row in rows:
        row['values'][:] = 0
    targets = [{k: v for k, v in r.items() if k != 'values'} for r in (rows[0], rows[5])]
    rows = [r for r in rows if r['run'] not in (1, 6)]
    result = nv.predict_missing_neighbors(rows, targets, models=('extra_trees',), seed=0)
    assert any(e['run'] == 1 and e['reason'] == 'no_training_bracket' for e in result['exclusions'])
    assert not any(p['run'] == 1 or p['method'].endswith('_hybrid') for p in result['predictions'])
    assert len(result['predictions']) == 1
    np.testing.assert_array_equal(result['predictions'][0]['estimate'], np.zeros(128))
    assert any(e['run'] == 6 and e['method'] == 'extra_trees_hybrid' for e in result['exclusions'])
