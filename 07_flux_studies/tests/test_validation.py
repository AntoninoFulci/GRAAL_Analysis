import copy
import numpy as np
from flux_studies.tests.helpers import study_audit


def test_folds_do_not_split_runs_or_overlap_intervals():
    from flux_studies.validation import blocked_folds
    metadata=study_audit(18)['metadata']
    metadata[(2,'POL1')]['start']=100.
    folds=blocked_folds(metadata,mode='offline',n_splits=3)
    for fold in folds:
        assert set(fold['train_runs']).isdisjoint(fold['test_runs'])
        assert ((1 in fold['test_runs'])==(2 in fold['test_runs']))
    for fold in blocked_folds(metadata,mode='causal',n_splits=3):
        assert max(fold['train_runs'])<min(fold['test_runs'])


def test_hidden_truth_changes_residual_not_prediction():
    from flux_studies.validation import evaluate_holdouts
    audit=study_audit(18)
    kwargs=dict(mode='offline',n_splits=3,mask_patterns=(('POL1',),),seed=42)
    before=evaluate_holdouts(audit,**kwargs)
    target=next(p for p in before['predictions'] if p['method']=='ridge' and p['status']=='ok')
    changed=copy.deepcopy(audit)
    changed['histograms'][(target['run_number'],'POL1')][0]*=1000
    after=evaluate_holdouts(changed,**kwargs)
    match=next(p for p in after['predictions'] if p['target_key']==target['target_key'] and p['method']=='ridge')
    np.testing.assert_allclose(match['estimate'],target['estimate'])
    assert match['alpha']==target['alpha']
    assert not np.array_equal(match['truth'],target['truth'])
    assert target['run_number'] not in target['training_runs']


def test_causal_donors_are_past_and_groups_never_mix():
    from flux_studies.validation import evaluate_holdouts
    audit=study_audit(18)
    for key,row in audit['metadata'].items():
        if key[0]>12:row['source_period']='1999_uv'
    result=evaluate_holdouts(audit,mode='causal',n_splits=3,mask_patterns=(('POL1','POL2'),),seed=42)
    for p in result['predictions']:
        assert all(run<p['run_number'] for run in p['training_runs'])
        assert all((run>12)==(p['run_number']>12) for run in p['training_runs'])


def test_incomplete_target_metadata_is_excluded_at_all_nesting_levels():
    from flux_studies.validation import evaluate_holdouts
    audit=study_audit(18)
    audit['metadata'][(1,'POL1')]['end']=None
    result=evaluate_holdouts(audit,mode='offline',n_splits=3,mask_patterns=(('POL1',),),seed=42)
    assert result['predictions']
    assert all(p['run_number']!=1 for p in result['predictions'])


def test_target_is_evaluated_only_in_its_own_configuration_fold():
    from flux_studies.validation import evaluate_holdouts
    audit=study_audit(12)
    for key,row in audit['metadata'].items():
        if key[1]=='POL1':row['configuration_id']='B'
    result=evaluate_holdouts(audit,mode='offline',n_splits=3,mask_patterns=(('POL1',),),seed=42)
    folds={f['fold_id']:f for f in result['folds']}
    assert len(result['predictions'])==12*5
    assert all(folds[p['fold_id']]['group'][3]=='B' for p in result['predictions'])
