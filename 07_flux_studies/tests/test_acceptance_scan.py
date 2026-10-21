"""Inference-only acceptance and whole-run safety invariants."""
from copy import deepcopy

import numpy as np
import pytest


def fixture(states=('POL1',)):
    records, predictions, keys = [], [], []
    for state in states:
        for run, count, position in ((1, 90, 0.), (2, 110, 20.), (3, 100, 10.)):
            records.append(dict(period='p', run=run, state=state,
                                group=('p', 'P', 'UV', state), count=count,
                                position=position, values=np.ones(128) * count))
        for method in ('linear', 'extra_trees_hybrid', 'kernel_ridge_hybrid'):
            predictions.append(dict(period='p', run=3, state=state, role='test',
                                    method=method, donors=[1, 2], count=100,
                                    estimate=np.ones(128) * 100,
                                    truth=np.ones(128) * 100, coverage95=1.))
        keys.append(dict(period='p', run=3, state=state, method='extra_trees_hybrid'))
    splits = [dict(run=1, role='train', block=0), dict(run=2, role='train', block=1),
              dict(run=3, role='test', block=2)]
    splits.extend(dict(run=r, role='validation', block=3 + (r - 10) // 2) for r in range(10, 18))
    study = dict(predictions=predictions, splits={'p': splits})
    uncertainty = dict(keys=keys, draws=np.full((40, len(keys), 128), 101.),
                       requested_replicas=40,
                       residual_support=[dict(period='p', paired_validation_runs=list(range(10, 18)),
                                              validation_blocks=[3, 4, 5, 6], states=list(states))])
    return records, study, uncertainty


def test_acceptance_cannot_read_test_truth_or_coverage():
    from flux_studies.acceptance_scan import POLICIES, decide_runs, state_diagnostics
    records, study, uncertainty = fixture()
    first = state_diagnostics(records, study, uncertainty)
    for row in records:
        if row['run'] == 3:
            del row['values']
    for row in study['predictions']:
        row.update(truth=object(), coverage95=object(), relative_l1=object(), true_integral=object())
    uncertainty['target_summary'] = object()
    second = state_diagnostics(records, study, uncertainty)
    assert first == second
    assert decide_runs(second, POLICIES[0])['accepted_runs'] == [3]
    assert second[0]['metrics']['predicted_l1_uncertainty95'] == pytest.approx(.01)


def test_ladder_is_nested_and_a_single_bad_state_rejects_whole_run():
    from flux_studies.acceptance_scan import POLICIES, decide_runs, state_diagnostics
    records, study, uncertainty = fixture(('POL1', 'POL2'))
    # 16% predicted uncertainty passes only policies 3–5.
    uncertainty['draws'][:, 1] = 116.
    diagnostics = state_diagnostics(records, study, uncertainty)
    accepted = [decide_runs(diagnostics, p)['accepted_runs'] for p in POLICIES]
    assert accepted == [[], [], [3], [3], [3]]
    assert all(set(a) <= set(b) for a, b in zip(accepted, accepted[1:]))
    assert decide_runs(diagnostics, POLICIES[-1], excluded_runs=[3])['accepted_runs'] == []
    assert decide_runs(diagnostics, POLICIES[-1], excluded_runs=[1])['accepted_runs'] == []


@pytest.mark.parametrize('missing', ['extra_trees_hybrid', 'kernel_ridge_hybrid', 'uncertainty'])
def test_missing_method_or_uncertainty_preserves_rejected_target(missing):
    from flux_studies.acceptance_scan import POLICIES, decide_runs, state_diagnostics
    records, study, uncertainty = fixture()
    if missing == 'uncertainty':
        uncertainty = None
    else:
        study['predictions'] = [p for p in study['predictions'] if p['method'] != missing]
    diagnostics = state_diagnostics(records, study, uncertainty)
    assert len(diagnostics) == 1
    assert diagnostics[0]['blockers']
    assert decide_runs(diagnostics, POLICIES[-1])['rejected_runs'] == [3]


@pytest.mark.parametrize('failure', ['replicas', 'fraction', 'support', 'count', 'bracket', 'excluded'])
def test_hard_safeguards_cannot_be_relaxed(failure):
    from flux_studies.acceptance_scan import POLICIES, decide_runs, state_diagnostics
    records, study, uncertainty = fixture()
    excluded = []
    if failure == 'replicas':
        uncertainty['requested_replicas'] = 31
        uncertainty['draws'] = uncertainty['draws'][:31]
    elif failure == 'fraction':
        uncertainty['draws'][:5] = np.nan
    elif failure == 'support':
        uncertainty['residual_support'][0]['paired_validation_runs'].pop()
    elif failure == 'count':
        records[-1]['count'] = 200
    elif failure == 'bracket':
        records[-1]['position'] = 30.
    else:
        excluded = [1]
    diagnostics = state_diagnostics(records, study, uncertainty, excluded_runs=excluded)
    assert diagnostics[0]['blockers']
    assert decide_runs(diagnostics, POLICIES[-1])['rejected_runs'] == [3]


@pytest.mark.parametrize('bad', ['record', 'prediction', 'replica_key', 'split', 'shape', 'requested'])
def test_ambiguous_ids_and_malformed_draw_alignment_raise(bad):
    from flux_studies.acceptance_scan import state_diagnostics
    records, study, uncertainty = fixture()
    if bad == 'record':
        records.append(deepcopy(records[0]))
    elif bad == 'prediction':
        study['predictions'].append(deepcopy(study['predictions'][0]))
    elif bad == 'replica_key':
        uncertainty['keys'].append(deepcopy(uncertainty['keys'][0]))
    elif bad == 'split':
        study['splits']['p'].append(deepcopy(study['splits']['p'][0]))
    elif bad == 'shape':
        uncertainty['draws'] = uncertainty['draws'][:, :, :127]
    else:
        uncertainty['requested_replicas'] += 1
    with pytest.raises(ValueError):
        state_diagnostics(records, study, uncertainty)


def test_duplicate_diagnostics_raise_instead_of_overwriting():
    from flux_studies.acceptance_scan import POLICIES, decide_runs, state_diagnostics
    diagnostics = state_diagnostics(*fixture())
    with pytest.raises(ValueError, match='duplicate'):
        decide_runs(diagnostics + diagnostics, POLICIES[0])


@pytest.mark.parametrize('change', ['distance', 'normalization', 'shape', 'count'])
def test_each_observable_cut_can_reject_a_well_supported_target(change):
    from flux_studies.acceptance_scan import POLICIES, decide_runs, state_diagnostics
    records, study, uncertainty = fixture()
    if change == 'distance':
        records[0]['position'] = -10.
    elif change == 'normalization':
        records[0]['values'] *= 1.15
    elif change == 'shape':
        study['predictions'][-1]['estimate'][:64] = 96.
        study['predictions'][-1]['estimate'][64:] = 104.
    else:
        records[-1]['count'] = 91.5
    diagnostics = state_diagnostics(records, study, uncertainty)
    assert not diagnostics[0]['blockers']
    assert decide_runs(diagnostics, POLICIES[0])['accepted_runs'] == []
    assert decide_runs(diagnostics, POLICIES[1])['accepted_runs'] == [3]


@pytest.mark.parametrize('bad', [np.nan, np.inf, -1., 0.])
def test_invalid_prediction_spectra_never_accept(bad):
    from flux_studies.acceptance_scan import POLICIES, decide_runs, state_diagnostics
    records, study, uncertainty = fixture()
    study['predictions'][-1]['estimate'][:] = bad
    diagnostics = state_diagnostics(records, study, uncertainty)
    assert 'invalid_kernel_ridge_hybrid' in diagnostics[0]['blockers']
    assert decide_runs(diagnostics, POLICIES[-1])['accepted_runs'] == []


def test_validation_spectra_and_target_count_never_expand_training_count_support():
    from flux_studies.acceptance_scan import POLICIES, decide_runs, state_diagnostics
    records, study, uncertainty = fixture()
    records.append({**records[-1], 'run': 10, 'count': 100000})
    records[-2]['count'] = 200.
    diagnostics = state_diagnostics(records, study, uncertainty)
    assert 'count_outside_training_range' in diagnostics[0]['blockers']
    assert decide_runs(diagnostics, POLICIES[-1])['accepted_runs'] == []


def test_invalid_run_id_and_nontraining_donor_fail_closed():
    from flux_studies.acceptance_scan import POLICIES, decide_runs, state_diagnostics
    records, study, uncertainty = fixture()
    records[0]['run'] = '1'
    with pytest.raises(ValueError, match='integers'):
        state_diagnostics(records, study, uncertainty)
    records[0]['run'] = 1
    study['splits']['p'][0]['role'] = 'validation'
    diagnostics = state_diagnostics(records, study, uncertainty)
    assert 'invalid_training_bracket' in diagnostics[0]['blockers']
    assert decide_runs(diagnostics, POLICIES[-1])['accepted_runs'] == []


def test_mask_placeholder_preserves_target_with_no_model_predictions():
    from flux_studies.acceptance_scan import POLICIES, decide_runs, state_diagnostics
    records, study, _ = fixture()
    study['predictions'] = [dict(period='p', run=3, state='POL1', role='test',
                                method='masked_reference_only', donors=[])]
    diagnostics = state_diagnostics(records, study, None)
    assert len(diagnostics) == 1
    assert 'missing_extra_trees_hybrid' in diagnostics[0]['blockers']
    assert 'missing_kernel_ridge_hybrid' in diagnostics[0]['blockers']
    assert decide_runs(diagnostics, POLICIES[-1])['rejected_runs'] == [3]
