import json
from pathlib import Path
from types import SimpleNamespace
import numpy as np
import pytest


def _rule():
    return dict(max_gap=90., min_count=1, min_replicas=3, min_groups=2,
                max_relative_integral_std=.2, min_valid_replica_fraction=.75)


def _limits():
    return dict(max_abs_shift_stat=.2, max_representation_shift_stat=.1,
                max_model_shift_stat=.1, max_shift_std_stat=.2,
                max_combined_precision_ratio=.95, max_missing_fraction=0.,
                min_complete_replicas=3, min_coverage_groups=2,
                min_coverage68=.6, min_coverage95=.9, max_coverage_interval_width=.2)


def _config(tmp_path):
    from calibration.calibration_qa import sha256_file
    source = tmp_path / 'source'
    source.write_text('declared input')
    development = tmp_path / 'development-report.json'
    development.write_text(json.dumps(dict(phase='development',tried_rules=[_rule()])))
    return dict(inputs={'manifest': str(source)}, input_sha256={str(source): sha256_file(source)},
        cohort_runs=[1], energy_edges=[.5, 1., 2.],
        assignments=[dict(run=1,period='uv',block='b',role='final')],
        masks=[[1,'POL1']], seed=1, replicas=3, min_groups=2, coverage_resamples=10,
        parameters=[dict(group=['uv','P','UV','POL1'],parameters={'min_samples_leaf':2,'max_features':1.})],
        rule=_rule(), normalization_domains=[dict(period='uv',state='POL1',qualified=True,evidence='report')],
        limits=_limits(), history={'previously_used_runs':[], 'final_interpretation':'internal confirmation'},
        point_universe=[['uv','ratio','p_eta',0,0]],
        selection=dict(candidate_rules=[_rule()],objective='minimum combined uncertainty within declared bounds',
                       stopping_rule='stop after all declared candidate rules are evaluated',
                       development_reports=[dict(path=str(development),sha256=sha256_file(development))]),
        systematics=dict(status='qualified',evidence='declared budget',scope='declared domain'))


def test_protocol_is_immutable_authenticated_and_final_attempt_single_use(tmp_path):
    from flux_studies.energy_protocol import freeze_protocol, load_protocol, claim_final
    path = tmp_path / 'protocol.json'
    frozen = freeze_protocol(_config(tmp_path), path)
    assert load_protocol(path) == frozen
    assert claim_final(path)['protocol_sha256'] == frozen['sha256']
    with pytest.raises(FileExistsError):
        claim_final(path)
    with pytest.raises(FileExistsError):
        freeze_protocol(frozen['config'], path)
    altered = json.loads(path.read_text())
    altered['config']['seed'] = 20
    path.write_text(json.dumps(altered))
    with pytest.raises(ValueError, match='digest'):
        load_protocol(path)


def test_protocol_requires_explicit_limits_and_rejects_input_drift(tmp_path):
    from flux_studies.energy_protocol import freeze_protocol, load_protocol
    config = _config(tmp_path)
    config['limits'].pop('max_abs_shift_stat')
    with pytest.raises(ValueError, match='max_abs_shift_stat'):
        freeze_protocol(config,tmp_path/'incomplete.json')
    config['limits'] = _limits()
    path = tmp_path / 'protocol.json'
    freeze_protocol(config,path)
    (tmp_path/'source').write_text('changed')
    with pytest.raises(ValueError, match='input.*identity'):
        load_protocol(path)


@pytest.mark.parametrize('change,match',[
    ('missing','selection'),('outside','candidate'),('empty_objective','objective'),
    ('empty_stopping','stopping_rule'),('invalid_candidate','min_count'),
    ('no_reports','development_reports')])
def test_freeze_requires_bounded_documented_development_selection(tmp_path,change,match):
    from flux_studies.energy_protocol import freeze_protocol
    config=_config(tmp_path)
    if change=='missing':
        config.pop('selection')
    elif change=='outside':
        config['rule']['max_gap']=120.
    elif change=='empty_objective':
        config['selection']['objective']='  '
    elif change=='empty_stopping':
        config['selection']['stopping_rule']=''
    elif change=='invalid_candidate':
        config['selection']['candidate_rules'][0]['min_count']=None
    else:
        config['selection']['development_reports']=[]
    with pytest.raises(ValueError,match=match):
        freeze_protocol(config,tmp_path/'protocol.json')


def test_development_evidence_identity_checked_on_freeze_and_load(tmp_path):
    from flux_studies.energy_protocol import freeze_protocol,load_protocol
    config=_config(tmp_path)
    path=tmp_path/'protocol.json'
    frozen=freeze_protocol(config,path)
    development=Path(config['selection']['development_reports'][0]['path'])
    assert str(development) not in frozen['config']['input_sha256']
    development.write_text('modified development evidence')
    with pytest.raises(ValueError,match='development report identity'):
        load_protocol(path)
    with pytest.raises(ValueError,match='development report identity'):
        freeze_protocol(config,tmp_path/'second.json')


def test_completed_verification_binds_report_path_content_and_original_attempt(tmp_path):
    from flux_studies.energy_protocol import (freeze_protocol, claim_final,
        complete_verification, load_verified_result)
    path=tmp_path/'protocol.json'
    frozen=freeze_protocol(_config(tmp_path),path)
    report_path=tmp_path/'report.json'
    report=dict(phase='verification',protocol_sha256=frozen['sha256'],
                input_sha256=frozen['config']['input_sha256'],qualification={'status':'failed'})
    report_path.write_text(json.dumps(report))
    with pytest.raises(FileNotFoundError):
        complete_verification(path,report_path)
    claim_final(path)
    receipt=complete_verification(path,report_path)
    assert receipt['report_path']==str(report_path.resolve())
    assert load_verified_result(path,report_path)==report
    with pytest.raises(FileExistsError):
        complete_verification(path,report_path)
    relocated=tmp_path/'copy.json'
    relocated.write_text(report_path.read_text())
    with pytest.raises(ValueError,match='verification.*identity'):
        load_verified_result(path,relocated)
    report['qualification']['status']='qualified'
    report_path.write_text(json.dumps(report))
    with pytest.raises(ValueError,match='verification.*identity'):
        load_verified_result(path,report_path)


def test_development_report_cannot_complete_final_attempt(tmp_path):
    from flux_studies.energy_protocol import freeze_protocol,claim_final,complete_verification
    path=tmp_path/'protocol.json'
    frozen=freeze_protocol(_config(tmp_path),path)
    claim_final(path)
    report_path=tmp_path/'report.json'
    report_path.write_text(json.dumps(dict(phase='development',protocol_sha256=frozen['sha256'],
                                           input_sha256=frozen['config']['input_sha256'])))
    with pytest.raises(ValueError,match='verification.*protocol'):
        complete_verification(path,report_path)
    assert not Path(str(path)+'.final-result.json').exists()


def test_real_acceptance_uses_metadata_only_and_requires_all_polarized_states():
    from flux_studies.energy_protocol import decide_energy_runs
    class NoTruth(dict):
        def __getitem__(self,key):
            if key in ('truth','metrics','sigma'):
                raise AssertionError('truth leakage')
            return super().__getitem__(key)
        def get(self,key,*args):
            if key in ('truth','metrics','sigma'):
                raise AssertionError('truth leakage')
            return super().get(key,*args)
    prediction=NoTruth(run=1,state='POL1',period='uv',method='extra_trees_hybrid',
        group=['uv','P','UV','POL1'],status='available',count=100,gap=30,donors=[0,2],
        estimate=np.ones(2),energy_support=[.5,2.])
    inventory=[dict(run=1,state='POL1',measurement_status='missing_histogram',reasons=[]),
               dict(run=1,state='POL2',measurement_status='measured_valid',reasons=[])]
    uncertainty=dict(target_summary=[dict(run=1,state='POL1',method='extra_trees_hybrid',
        valid_replicas=4,requested_replicas=4,relative_integral_uncertainty=.1)],
        residual_support=[dict(period='uv',domain=['uv','P','UV'],state='POL1',n_groups=2,status='available'),
                          dict(period='uv',domain=['uv','P','UV'],state='BREM',n_groups=0,status='insufficient_groups'),
                          dict(period='uv',domain=['uv','P','VIS'],n_groups=0,status='insufficient_groups')])
    axes={(1,'POL1'):SimpleNamespace(edges=np.linspace(.5,2.,129))}
    domains=[dict(period='uv',state='POL1',qualified=True,evidence='verified stability')]
    result=decide_energy_runs([prediction],uncertainty,inventory,axes,_rule(),domains)
    assert result['accepted_runs']==[1]
    prediction['energy_support']=[.6,1.9]
    result=decide_energy_runs([prediction],uncertainty,inventory,axes,_rule(),domains)
    assert result['accepted_runs']==[]
    assert 'uncovered_donor_energy_support' in result['state_decisions'][0]['reasons']
    prediction['energy_support']=None
    result=decide_energy_runs([prediction],uncertainty,inventory,axes,_rule(),domains)
    assert result['accepted_runs']==[]
    assert 'missing_donor_energy_support' in result['state_decisions'][0]['reasons']
    prediction['energy_support']=[.5,2.]
    inventory[1]['measurement_status']='invalid_values'
    result=decide_energy_runs([prediction],uncertainty,inventory,axes,_rule(),domains)
    assert result['accepted_runs']==[]


def test_qualification_no_recovery_or_missing_evidence_cannot_pass():
    from flux_studies.energy_protocol import qualify_energy
    result=qualify_energy({'accepted_runs':[]},[],_limits())
    assert result['status']=='no_recovery'
    result=qualify_energy({'accepted_runs':[1]},[],_limits())
    assert result['status']=='insufficient_evidence'


def _evidence():
    key=['ratio','p_eta',0,0]
    comparisons=[dict(reference=a,scenario=b,estimator='ratio',pair='p_eta',energy_bin=0,mass_bin=0,
                      delta_over_nominal_stat=.01,nominal_stat=1.)
                 for a,b in [('C','B'),('C','D'),('D','B')]]
    paired={f'{b}-{a}':dict(points=[dict(key=key,shift_std=.02,successful=3)])
            for a,b in [('C','B'),('C','D'),('D','B')]}
    replicas=[dict(scenarios={name:[dict(key=key,sigma=value)]
                            for name,value in [('A',x),('B',x/2)]}) for x in (-1,0,1)]
    closure=dict(period='uv',accepted_runs=[1],masked_states=[dict(run=1,state='POL1')],
        counts={'recovered_pol_events':10},comparisons=comparisons,
        uncertainty=dict(paired=paired,scenario_replicas=replicas,flux_propagated=True))
    coverage=dict(period='uv',state='POL1',n_groups=2,expected_targets=3,
        levels={str(level):dict(bin_coverage=[1.,1.],integral_coverage=1.,unavailable=0,
        grouped_diagnostic_interval95=[[.9,.9,.9],[1.,1.,1.]]) for level in (68,95)})
    return closure,coverage


def test_qualification_requires_joint_precision_systematics_and_matching_domain():
    from flux_studies.energy_protocol import qualify_energy
    closure,coverage=_evidence()
    kwargs=dict(point_universe=[['uv','ratio','p_eta',0,0]],
                systematics=dict(status='qualified',evidence='budget',scope='uv'))
    for row in coverage['levels'].values():
        row['grouped_diagnostic_interval95'][0].extend([0.,0.])
        row['grouped_diagnostic_interval95'][1].extend([1.,1.])
    assert qualify_energy([closure],[coverage],_limits(),**kwargs)['status']=='qualified'
    coverage['period']='another_period'
    assert qualify_energy([closure],[coverage],_limits(),**kwargs)['status']=='insufficient_evidence'
    coverage['period']='uv'
    closure['uncertainty']['flux_propagated']=False
    assert qualify_energy([closure],[coverage],_limits(),**kwargs)['status']=='insufficient_evidence'


def test_brem_only_admission_is_not_recovery_qualification():
    from flux_studies.energy_protocol import qualify_energy
    closure,coverage=_evidence()
    closure['counts']['recovered_pol_events']=0
    assert qualify_energy([closure],[coverage],_limits())['status']=='no_recovery'


def test_qualified_domains_require_accepted_pol_and_frozen_observable_points():
    from flux_studies.energy_protocol import qualify_energy
    import copy
    closure,coverage=_evidence()
    extra_closure=copy.deepcopy(closure)
    extra_closure['period']='vis'
    extra_coverage=copy.deepcopy(coverage)
    extra_coverage['period']='vis'
    result=qualify_energy([closure,extra_closure],[coverage,extra_coverage],_limits(),
        point_universe=[['uv','ratio','p_eta',0,0]],
        systematics=dict(status='qualified',evidence='budget',scope='uv'))
    assert result['status']=='qualified'
    assert result['qualified_domains']==[dict(period='uv',state='POL1')]
    closure['counts']['recovered_pol_events']=0
    result=qualify_energy([closure],[coverage],_limits())
    assert result['qualified_domains']==[]


def test_joint_polarized_recovery_requires_supported_cross_state_errors():
    from flux_studies.energy_protocol import decide_energy_runs
    states=('POL1','POL2')
    predictions=[dict(run=1,state=s,period='uv',group=['uv','P','UV',s],method='extra_trees_hybrid',
        status='available',count=100,gap=30,donors=[0,2],estimate=np.ones(2),energy_support=[.5,2.]) for s in states]
    inventory=[dict(run=1,state=s,measurement_status='missing_histogram',reasons=[]) for s in states]
    axes={(1,s):SimpleNamespace(edges=np.linspace(.5,2.,129)) for s in states}
    uncertainty=dict(target_summary=[dict(run=1,state=s,method='extra_trees_hybrid',valid_replicas=4,
        requested_replicas=4,relative_integral_uncertainty=.1) for s in states],
        residual_support=[dict(period='uv',domain=['uv','P','UV'],state=s,n_groups=2,status='available') for s in states],
        joint_state_support=[dict(period='uv',domain=['uv','P','UV'],states=list(states),
                                 n_groups=0,status='insufficient_groups')])
    domains=[dict(period='uv',state=s,qualified=True,evidence='verified stability') for s in states]
    result=decide_energy_runs(predictions,uncertainty,inventory,axes,_rule(),domains)
    assert result['accepted_runs']==[]
    assert all('insufficient_joint_polarized_support' in r['reasons'] for r in result['state_decisions'])
    uncertainty['joint_state_support'][0].update(n_groups=2,status='available')
    assert decide_energy_runs(predictions,uncertainty,inventory,axes,_rule(),domains)['accepted_runs']==[1]
