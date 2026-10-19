"""Real gaps determine masks without consulting held-out spectra."""
from types import SimpleNamespace
import numpy as np

from flux_studies.tests.test_calibrated_neighbors import records


def test_inventory_distinguishes_exclusion_counts_and_brackets():
    from flux_studies.realistic_gaps import gap_inventory
    manifest=[SimpleNamespace(run_number=i,source_period='p',target='P',beam_type='UV') for i in range(1,7)]
    audit={'rows':[dict(run_number=i,state=s,calibrated_keys=[] if i in (1,3,5) and s=='BREM' else [{}], problems=[])
                   for i in range(1,7) for s in ('POL1','POL2','BREM')]}
    data=records(6)
    good=[r for r in data if r['run'] not in (1,3,5)]
    for r in good:r['position']-=15
    counts={(r['run'],r['state']):r['count'] for r in data}
    result=gap_inventory(manifest,audit,counts,good,excluded_runs={5})
    missing={r['run']:r for r in result['missing']}
    assert missing[1]['status']=='no_two_sided_donors'
    assert missing[3]['status']=='candidate'
    assert missing[3]['donors']==[2,4]
    assert missing[5]['status']=='quality_excluded'
    assert len(result['patterns'])==1
    assert result['patterns'][0]['masks']==[['BREM']]


def test_realistic_masks_are_run_disjoint_separated_and_truth_independent():
    from flux_studies.realistic_gaps import realistic_split
    data=records(80)
    patterns=[dict(period='p',runs=[100,101],masks=[['POL1'],['BREM']],positions=[5,6])]
    a=realistic_split(data,patterns,seed=42)
    b=realistic_split([{**r,'values':r['values']*999} for r in data],patterns,seed=42)
    assert a==b
    plan=a['split_plan']['p']; roles={r['run']:r['role'] for r in plan}
    assert set(roles.values())=={'train','validation','test'}
    for gap in a['placements']:
        assert len(gap['runs'])==2
        lo,hi=gap['runs'][0],gap['runs'][-1]
        assert roles[lo-1]==roles[hi+1]=='train'
        assert all(roles[r]==gap['role'] for r in gap['runs'])
        assert gap['masks']==[['POL1'],['BREM']]
    held={r['run'] for r in plan if r['role']=='test'}
    assert set(r['run'] for r in a['test_masks'])==held


def test_patterns_without_supported_period_are_not_invented():
    from flux_studies.realistic_gaps import realistic_split
    result=realistic_split(records(20),[],seed=42)
    assert result['test_masks']==[]
    assert result['unsupported']==[dict(period='p',reason='no_supported_real_gap_pattern')]


def test_unavailable_adjacent_donor_is_part_of_mask_geometry():
    from flux_studies.realistic_gaps import gap_inventory, realistic_split
    manifest=[SimpleNamespace(run_number=i,source_period='p',target='P',beam_type='UV') for i in range(1,9)]
    audit={'rows':[dict(run_number=i,state=s,calibrated_keys=[] if i==5 and s=='BREM' else [{}], problems=[])
                   for i in range(1,9) for s in ('POL1','POL2','BREM')]}
    data=records(8)
    good=[{**r,'position':r['position']-15} for r in data if r['run'] not in (4,5)]
    counts={(r['run'],r['state']):r['count'] for r in data}
    inv=gap_inventory(manifest,audit,counts,good,excluded_runs={4})
    assert inv['missing'][0]['gap']==45
    pattern=inv['patterns'][0]
    assert pattern['runs']==[4,5]
    assert pattern['masks']==[[],['BREM']]
    design=realistic_split(records(60),[pattern],seed=42)
    assert all(len(g['runs'])==2 for g in design['placements'])
    assert len(design['test_masks'])==sum(g['role']=='test' for g in design['placements'])


def test_candidate_support_matches_offsets_not_just_total_span():
    from flux_studies.study_realistic_gaps import candidate_support
    rec=records(6)
    pred=dict(run=3,state='POL1',period='p',method='linear',role='missing',donors=[1,4],gap=45,count=109)
    val=dict(run=2,state='POL1',period='p',method='linear',role='test',donors=[1,4],gap=45,count=106)
    row=candidate_support([pred],[val],rec,targets=[])[0]
    assert not row['gap_within_validation_support']
    assert row['production_adopted'] is False


def test_closure_cannot_silently_drop_unpredicted_masks():
    import pytest
    from flux_studies.study_realistic_gaps import require_mask_coverage
    with pytest.raises(ValueError,match='unpredicted'):
        require_mask_coverage([], [dict(period='p',run=3,state='POL1')])
