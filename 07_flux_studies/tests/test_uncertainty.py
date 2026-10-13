import numpy as np
from flux_studies.tests.helpers import study_audit


def test_failed_predictions_remain_in_denominator():
    from flux_studies.uncertainty import paired_metrics
    truth=np.full(128,1/128)
    rows=[dict(target_key=(run,'POL1'),method=method,status='ok',truth=truth,estimate=truth.copy(),domain='shape') for run in (7,8) for method in ('nearest','ridge')]
    rows[-1].update(status='not_reconstructible',estimate=None)
    result=paired_metrics(rows)
    assert result['coverage']['ridge']['eligible']==2
    assert result['coverage']['ridge']['success']==1
    assert result['coverage']['nearest']['success']==2
    assert result['pairs'][0]['common_targets']==1


def test_shared_exposure_draws_generate_joint_covariance():
    from flux_studies.uncertainty import joint_replicas
    from flux_studies.validation import _predict
    audit=study_audit(4)
    for key,row in audit['metadata'].items():
        row['exposure']=dict(value=10.,error=0.,unit='s',definition='live',uncertainty_group=None)
        audit['histograms'][key]=np.ones(128)*10
    for run,value in [(3,10.),(4,20.)]:
        audit['metadata'][(run,'POL1')]['exposure'].update(value=value,error=value*.1,uncertainty_group='shared')
    context=dict(audit=audit,runs=[1,2],pattern=('POL1',),mode='offline',domain='absolute',alpha=1.,residuals={'nearest':[dict(run_number=1,block=0,values=np.zeros(128)),dict(run_number=2,block=1,values=np.zeros(128))]})
    predictions=[]
    for run in (3,4):
        p=_predict(audit,[1,2],(run,'POL1'),('POL1',),'offline','absolute','nearest',1.)
        p.update(run_number=run,state='POL1',method='nearest',context_id=(0,),domain='absolute',truth=np.ones(128),target_key=(run,'POL1'))
        predictions.append(p)
    evaluation=dict(predictions=predictions,contexts={(0,):context})
    result=joint_replicas(evaluation,seed=42,n_replicas=30)
    values=result['mean_replicas']
    np.testing.assert_allclose(values[:,1],values[:,0]*2)
    assert values[:,0,0].std()>0
    again=joint_replicas(evaluation,seed=42,n_replicas=30)
    np.testing.assert_allclose(again['replicas'],result['replicas'])


def test_predictive_coverage_on_independent_noisy_holdouts():
    from flux_studies.validation import evaluate_holdouts
    from flux_studies.uncertainty import joint_replicas, paired_metrics
    audit=study_audit(36)
    rng=np.random.default_rng(817)
    for key in audit['histograms']:
        audit['histograms'][key]=np.maximum(1+rng.normal(0,.1,128),.01)
    evaluation=evaluate_holdouts(audit,mode='offline',n_splits=3,mask_patterns=(('POL1',),),seed=42)
    evaluation['predictions']=[p for p in evaluation['predictions'] if p['method']=='mean']
    joint_replicas(evaluation,seed=42,n_replicas=100)
    result=paired_metrics(evaluation['predictions'])['metrics']['mean']['shape']
    assert result['interval95_targets']==36
    assert .80 < result['coverage95'] < .995


def _exposure_evaluation(*,different_contexts=False,unknown_donor=False):
    from flux_studies.validation import _predict
    audit=study_audit(4)
    for key,row in audit['metadata'].items():
        row['exposure']=dict(value=10.,error=0.,unit='s',definition='live',uncertainty_group=None)
        audit['histograms'][key]=np.ones(128)*(100 if unknown_donor and key[0]==1 else 10)
    for run,value in [(3,10.),(4,20.)]:
        audit['metadata'][(run,'POL1')]['exposure'].update(value=value,error=0 if unknown_donor else value*.1,uncertainty_group='shared')
    if unknown_donor:audit['metadata'][(1,'POL1')]['exposure']['error']=None
    context=dict(audit=audit,runs=[1,2],pattern=('POL1',),mode='offline',domain='absolute',alpha=1.,residuals={'nearest':[dict(run_number=1,block=0,values=np.zeros(128)),dict(run_number=2,block=1,values=np.zeros(128))]})
    predictions=[]
    for run in (3,4):
        p=_predict(audit,[1,2],(run,'POL1'),('POL1',),'offline','absolute','nearest',1.)
        p.update(run_number=run,state='POL1',method='nearest',context_id=(run if different_contexts else 0,),domain='absolute',truth=np.ones(128),target_key=(run,'POL1'))
        predictions.append(p)
    return dict(predictions=predictions,contexts={(0,):context,(3,):context,(4,):context})


def test_shared_exposure_correlates_across_different_folds():
    from flux_studies.uncertainty import joint_replicas
    result=joint_replicas(_exposure_evaluation(different_contexts=True),seed=42,n_replicas=100)
    np.testing.assert_allclose(result['mean_replicas'][:,1],result['mean_replicas'][:,0]*2)


def test_bootstrap_substitution_with_unknown_exposure_error_is_invalid():
    from flux_studies.uncertainty import joint_replicas
    result=joint_replicas(_exposure_evaluation(unknown_donor=True),seed=42,n_replicas=100)
    valid=result['valid'][:,0]
    assert not valid.all()
    np.testing.assert_allclose(result['replicas'][valid,0],10.)


def test_bootstrap_blocks_follow_acquisition_time_and_preserve_overlap():
    from flux_studies.uncertainty import bootstrap_blocks
    audit=study_audit(4)
    for key,row in audit['metadata'].items():
        if key[0]==3:row['start']-=300;row['end']-=300
    audit['metadata'][(1,'POL1')]['start']=20.
    blocks=bootstrap_blocks(audit['metadata'],[1,2,3,4])
    assert blocks==[[3,1],[2],[4]]


def test_bootstrap_respects_each_configuration_overlap(monkeypatch):
    import collections
    from flux_studies import uncertainty
    from flux_studies.validation import _predict
    audit=study_audit(4)
    for key,row in audit['metadata'].items():
        if key[1]=='POL2':row['configuration_id']='B'
    audit['metadata'][(2,'POL2')]['start']=audit['metadata'][(1,'POL2')]['start']
    contexts={};predictions=[]
    for state in ('POL1','POL2'):
        cid=('candidate',state)
        contexts[cid]=dict(audit=audit,runs=[1,2,3],pattern=('POL1','POL2','BREM'),mode='offline',domain='shape',alpha=1.,residuals={'mean':[dict(run_number=1,block=0,values=np.zeros(128)),dict(run_number=3,block=1,values=np.zeros(128))]})
        p=_predict(audit,[1,2,3],(4,state),('POL1','POL2','BREM'),'offline','shape','mean',1.)
        p.update(run_number=4,state=state,method='mean',domain='shape',context_id=cid,target_key=(4,state))
        predictions.append(p)
    observed=[]
    def trace(audit,runs,key,*args,**kwargs):
        if key[1]=='POL2':observed.append(collections.Counter(runs))
        return _predict(audit,runs,key,*args,**kwargs)
    monkeypatch.setattr(uncertainty,'_predict',trace)
    uncertainty.joint_replicas(dict(predictions=predictions,contexts=contexts),seed=42,n_replicas=30)
    assert observed and all(c[1]==c[2] for c in observed)
