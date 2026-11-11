import copy

import numpy as np
import pytest

from calibration.target_periods import aggregate_periods
from calibration.target_database import _geant4_candidates


def record(run, length, counts, *, period='1998_uv', events=100):
    return dict(run=run, selected_events=events, catalog={'source_period':period,'target':'P','beam_type':'UV'},
                length_fit={'status':'approximate','length_cm':length,'center_cm':.1,
                            'length_stat_error_cm':.1,'edges_cm':[-10,0,10],
                            'counts':[events//2,events-events//2],'expected_counts':[events/2,events/2],
                            'model_check':'no_large_deviance'},
                observed_xy={'x_edges_cm':[-2,0,2],'y_edges_cm':[-1,1],
                             'counts':counts,'outside_xy_window':0})


def test_period_gives_equal_weight_to_runs_and_includes_beam_drift():
    records={'1':record(1,6.,[[100],[0]]), '2':record(2,6.2,[[0],[900]],events=900)}
    result=aggregate_periods(records,{'1998_uv':[1,2,3]})['1998_uv']
    assert result['length_cm']==pytest.approx(6.1)
    assert result['length_run_std_cm']==pytest.approx(np.sqrt(.02))
    assert result['xy_probability']==pytest.approx(np.array([[.5],[.5]]))
    assert result['spot_mean_cm']==pytest.approx([0,0])
    assert result['spot_rms_cm'][0]>=1  # Includes between-run beam displacement.
    assert result['coverage_status']=='partial'
    assert result['missing_runs']==[3]


def test_mixed_geometries_and_failed_runs_remain_explicit():
    rows={'1':record(1,3.,[[100],[0]]),'2':record(2,6.,[[0],[100]])}
    rows['3']=copy.deepcopy(rows['1']);rows['3']['run']=3
    rows['3']['length_fit']['status']='fit_failed'
    result=aggregate_periods(rows,{'1998_uv':[1,2,3]})['1998_uv']
    assert result['geometry_status']=='heterogeneous_lengths'
    assert result['length_cm']==pytest.approx(4.5)  # descriptive mean, not exported geometry
    assert not result['geometry_candidate_available']
    assert result['excluded_runs']==[3]
    candidate=_geant4_candidates({'periods':{'1998_uv':result}})['periods']['1998_uv']
    assert candidate['target']['length_mm'] is None
    assert candidate['target']['center_z_mm'] is None


def test_period_with_no_valid_fit_preserves_exclusions_and_exports_no_geometry():
    row=record(1,6.,[[100],[0]])
    row['length_fit']['status']='fit_failed'
    result=aggregate_periods({'1':row},{'1998_uv':[1]})['1998_uv']
    assert result['length_cm'] is None
    assert result['n_runs']==0
    assert result['excluded_runs']==[1]
    assert np.sum(result['xy_probability'])==0
    assert not result['geometry_candidate_available']
    candidate=_geant4_candidates({'periods':{'1998_uv':result}})['periods']['1998_uv']
    assert not candidate['photon_beam_proxy']['available']
    assert candidate['photon_beam_proxy']['sampling'] is None


def test_cannot_silently_mix_materials_or_different_histogram_bins():
    rows={'1':record(1,6.,[[100],[0]]),'2':record(2,6.,[[0],[100]])}
    rows['2']['catalog']['target']='D'
    assert aggregate_periods(rows,{'1998_uv':[1,2]})['1998_uv']['geometry_status']=='mixed_target_labels'
    rows['2']['observed_xy']['x_edges_cm']=[-3,0,3]
    with pytest.raises(ValueError,match='bin'):
        aggregate_periods(rows,{'1998_uv':[1,2]})


def test_local_edge_models_keep_full_profile_scale_and_missing_interior():
    rows={'1':record(1,6.,[[100],[0]]),'2':record(2,6.,[[0],[900]],events=900)}
    for row in rows.values():
        row['length_fit']['model_scope']='local_edges'
        row['length_fit']['halfwidth_effective_cm']=1.6
        row['length_fit']['expected_counts']=[None,.4*sum(row['length_fit']['counts'])]
        row['dca_variations_cm']={'0.3':{'status':'approximate'}}
        row['window_variations_cm']={'1.2':{'status':'approximate','halfwidth_effective_cm':1.2}}
    result=aggregate_periods(rows,{'1998_uv':[1,2]})['1998_uv']
    assert result['z_model_probability']==[None,pytest.approx(.4)]
    assert result['z_model_coverage_runs']==[0,2]


def test_nominal_local_fit_without_crosscheck_is_not_period_calibration():
    row=record(1,6.,[[100],[0]])
    row['length_fit']['model_scope']='local_edges'
    row['dca_variations_cm']={'0.3':{'status':'insufficient_statistics'}}
    row['window_variations_cm']={'1.2':{'status':'approximate'}}
    result=aggregate_periods({'1':row},{'1998_uv':[1]})['1998_uv']
    assert result['n_runs']==0
    assert result['exclusion_reasons']=={'1':'edge_robustness_unavailable'}


def test_capped_identical_windows_do_not_count_as_independent_check():
    row=record(1,3.,[[100],[0]])
    row['length_fit'].update(model_scope='local_edges',halfwidth_effective_cm=1.1)
    row['dca_variations_cm']={'0.3':{'status':'approximate'}}
    row['window_variations_cm']={'1.2':{'status':'approximate','halfwidth_effective_cm':1.1}}
    result=aggregate_periods({'1':row},{'1998_uv':[1]})['1998_uv']
    assert result['exclusion_reasons']=={'1':'edge_robustness_unavailable'}
    row['window_variations_cm']['1.0']={'status':'approximate','halfwidth_effective_cm':1.0}
    assert aggregate_periods({'1':row},{'1998_uv':[1]})['1998_uv']['included_runs']==[1]
