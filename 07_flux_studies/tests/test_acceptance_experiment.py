"""Frozen outer blocks never enter development or uncertainty calibration."""
import numpy as np
import pytest

from flux_studies.tests.test_calibrated_neighbors import records


def test_outer_reservation_and_development_are_disjoint_reproducible():
    from flux_studies.acceptance_experiment import reserve_outer, trial_partition
    rows = records(90)
    outer = reserve_outer(rows, seed=701)
    assert outer == reserve_outer(rows, seed=701)
    held = {r['run'] for r in outer['p'] if r['role'] == 'test'}
    assert held
    plan, usable = trial_partition(rows, outer, phase='development', seed=17, block_size=3)
    assert held.isdisjoint(r['run'] for r in usable)
    assert held.isdisjoint(r['run'] for r in plan['p'])
    changed = [{**r, 'values': np.full(128, 999999.)} if r['run'] in held else r for r in rows]
    again, usable_again = trial_partition(changed, outer, phase='development', seed=17, block_size=3)
    assert again == plan
    for a, b in zip(usable, usable_again, strict=True):
        np.testing.assert_array_equal(a['values'], b['values'])


def test_confirmation_uses_exactly_outer_test_and_disjoint_calibration():
    from flux_studies.acceptance_experiment import reserve_outer, trial_partition
    rows = records(90)
    outer = reserve_outer(rows, seed=701)
    plan, usable = trial_partition(rows, outer, phase='confirmation', seed=17, block_size=3)
    expected = {r['run'] for r in outer['p'] if r['role'] == 'test'}
    assert {r['run'] for r in plan['p'] if r['role'] == 'test'} == expected
    assert {r['run'] for r in usable} == set(range(1, 91))
    blocks = {}
    for row in plan['p']:
        assert blocks.setdefault(row['block'], row['role']) == row['role']
    with pytest.raises(ValueError, match='phase'):
        trial_partition(rows, outer, phase='new_phase', seed=17, block_size=3)


def test_real_mask_templates_ignore_anomalies_and_assign_whole_held_runs():
    from flux_studies.acceptance_experiment import mask_templates, trial_masks
    inventory = {'missing': [
        dict(run=1, period='p', state='BREM', missing_reason='missing_calibrated'),
        dict(run=2, period='p', state='POL1', missing_reason='quality_excluded_as_missing')]}
    templates = mask_templates(inventory, excluded_runs={2})
    assert templates == {'p': [['BREM']]}
    plan = {'p': [dict(run=3, role='test', block=1), dict(run=4, role='train', block=2)]}
    assert trial_masks(plan, templates, seed=5) == [dict(period='p', run=3, state='BREM')]


def test_unpredictable_mask_stays_in_closure_and_is_rejected_by_acceptance():
    from flux_studies.acceptance_experiment import _masked_reference_rows
    from flux_studies.acceptance_scan import state_diagnostics, decide_runs, POLICIES
    rows = records(5)
    study = dict(predictions=[], splits={'p': [
        dict(run=r, block=r, role='test' if r == 1 else 'train') for r in range(1, 6)]})
    masks = [dict(period='p', run=1, state='POL1')]
    augmented = _masked_reference_rows(study, masks, rows)
    assert len(augmented['predictions']) == 1
    assert augmented['predictions'][0]['run'] == 1
    uncertainty = dict(keys=[], requested_replicas=32, draws=np.empty((32, 0, 128)), residual_support=[])
    diagnostics = state_diagnostics(rows, augmented, uncertainty)
    assert [r['run'] for r in diagnostics] == [1]
    assert decide_runs(diagnostics, POLICIES[-1])['accepted_runs'] == []
