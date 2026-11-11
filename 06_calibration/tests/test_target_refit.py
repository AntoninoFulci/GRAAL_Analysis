import json
from pathlib import Path
from zipfile import ZipFile,ZIP_DEFLATED

import numpy as np
import pytest

from calibration.target_database import _analyze_run,_sha256
from calibration.target_fit import fit_length,observed_xy
from calibration.target_archive import write_run,finish_archive
from calibration.target_periods import aggregate_periods
from calibration.target_refit import refit_archive,reaggregate_products


def test_refit_preserves_events_and_skips_and_rebuilds_xy_from_new_edges(tmp_path):
    rng=np.random.default_rng(912)
    truth=rng.uniform(-5.4,6.2,30000)
    truth=truth[rng.random(len(truth))<1-.65*(2*(truth-.4)/11.6)**2]
    z=truth+rng.normal(0,.15,len(truth));n=len(z)
    arrays=dict(run=np.ones(n,dtype=int),status=np.zeros(n,dtype=int),n_charged=np.full(n,2),
                source_file=np.zeros(n,dtype=int),source_entry=np.arange(n),dca_cm=rng.uniform(0,.4,n),
                x_cm=rng.normal(0,.4,n),y_cm=rng.normal(0,.3,n),z_cm=z)
    report=dict(schema=2,dca_max_cm=.4,coordinate_frame='native_h70_detector',selection='fixture',runs={})
    catalog=tmp_path/'catalog.csv'
    catalog.write_text('run_number,source_period,target,beam_type,group,classification_source,source_file\n'
                       '1,1998_uv,P,UV,P_UV,manual,1998_uv/run1.root\n'
                       '2,1998_uv,P,UV,P_UV,manual,1998_uv/run2.root\n')
    report['catalog']={'sha256':_sha256(catalog)}
    source=tmp_path/'source';source.mkdir()
    with ZipFile(source/'run_plots.npz','w',compression=ZIP_DEFLATED) as archive:
        for run,data in [(1,arrays),(2,{k:v[:0] for k,v in arrays.items()})]:
            record,xyz,mask=_analyze_run(run,data,{'events_read':len(data['run'])},0)
            record['length_fit']=fit_length(data['z_cm'],bootstrap=0)
            fit=record['length_fit']
            inside=(xyz[:,2]>=fit['z_min_cm'])&(xyz[:,2]<=fit['z_max_cm']) if fit['length_cm'] else np.zeros(len(xyz),dtype=bool)
            record['observed_xy']={**observed_xy(xyz[inside,:2]),'outside_z_selection':int((~inside).sum()),'z_selection':'old edges'}
            record.update(catalog=dict(target='P',beam_type='UV',source_period='1998_uv',classification_source='manual'),
                          raw_source_files=[f'run{run}.root'],reconstruction_status='completed' if run==1 else 'no_chamber_tracks',
                          reconstruction_note='' if run==1 else 'No chamber tracks')
            report['runs'][str(run)]=record
            write_run(archive,run,xyz,data,mask,record)
        report['periods']=aggregate_periods(report['runs'],{'1998_uv':[1,2]})
        finish_archive(archive,report)
    (source/'checksums.json').write_text(json.dumps({'run_plots.npz':_sha256(source/'run_plots.npz')}))
    output=tmp_path/'refitted'
    output.mkdir()  # Recover an interrupted merge's empty output reservation.
    pending=tmp_path/'.refitted.interrupted'
    pending.mkdir()
    (pending/'partial.npz').write_bytes(b'partial')
    updated=refit_archive(source/'run_plots.npz',catalog,output,work=tmp_path/'work',workers=2,bootstrap=0)
    row=updated['runs']['1']
    assert not pending.exists()
    assert row['length_fit']['length_cm']==pytest.approx(11.6,abs=.15)
    assert row['previous_length_cm']<row['length_fit']['length_cm']-.5
    assert row['observed_xy']['events']>report['runs']['1']['observed_xy']['events']
    assert updated['runs']['2']['reconstruction_status']=='no_chamber_tracks'
    assert updated['periods']['1998_uv']['excluded_runs']==[2]
    with np.load(output/'run_plots.npz',allow_pickle=False) as archive:
        np.testing.assert_array_equal(archive['run_1_source_entry'],arrays['source_entry'])
        np.testing.assert_array_equal(archive['run_1_xyz_cm'][:,2],z)
        assert archive['period_1998_uv_xy_probability'].sum()==pytest.approx(1.)
        assert np.isnan(archive['period_1998_uv_z_model_probability']).any()
    with pytest.raises(FileExistsError):
        refit_archive(source/'run_plots.npz',catalog,output,work=tmp_path/'work',workers=2,bootstrap=0)
    # Period-policy updates preserve existing fit results and all selected events.
    final=tmp_path/'reaggregated'
    final.mkdir()
    rebuilt=reaggregate_products(output/'run_plots.npz',catalog,final)
    assert rebuilt['runs']['1']['length_fit']['length_cm']==row['length_fit']['length_cm']
    assert rebuilt['periods']['1998_uv']['included_runs']==[1]
    with np.load(final/'run_plots.npz',allow_pickle=False) as archive:
        np.testing.assert_array_equal(archive['run_1_xyz_cm'][:,2],z)
    # A later policy update must not relabel the fit's original source code.
    metadata=json.loads((final/'metadata.json').read_text())
    original_hashes=metadata['fit_code_hashes']
    assert rebuilt['fit_code_hashes']==updated['code_hashes']
    from unittest.mock import patch
    with patch('calibration.target_refit.source_hashes',return_value={'aggregation_revision':'new'}):
        again=reaggregate_products(final/'run_plots.npz',catalog,tmp_path/'again')
    assert again['fit_code_hashes']==original_hashes


def test_fit_exception_preserves_observed_histograms(tmp_path,monkeypatch):
    from calibration import target_refit as module
    rng=np.random.default_rng(5)
    n=2000
    xyz=np.column_stack([rng.normal(0,.3,n),rng.normal(0,.3,n),rng.uniform(-3,3,n)])
    source={'run_1_xyz_cm':xyz,'run_1_dca_cm':np.full(n,.2),
            'run_1_source_file':np.zeros(n,dtype=int),'run_1_source_entry':np.arange(n)}
    previous=dict(run=1,selected_events=n,raw_events=n,saved_pairs=n,
                  reconstruction_status='completed',length_fit={'length_cm':6.,'status':'approximate'})
    original=module._analyze_run
    def fail_nonempty(run,data,counts,bootstrap):
        if len(data['run']):raise RuntimeError('fixture optimizer error')
        return original(run,data,counts,bootstrap)
    monkeypatch.setattr(module,'_SOURCE',source)
    monkeypatch.setattr(module,'_METADATA',{'runs':{'1':previous}})
    monkeypatch.setattr(module,'_analyze_run',fail_nonempty)
    module._refit_one('1',tmp_path,0,{})
    record=json.loads((tmp_path/'run_1/record.json').read_text())['record']
    assert record['length_fit']['status']=='fit_failed'
    assert sum(record['length_fit']['counts'])==n
    assert record['observed_xy']['events']==n
    with np.load(tmp_path/'run_1/plots.npz',allow_pickle=False) as archive:
        assert archive['run_1_z_counts'].sum()==n
        np.testing.assert_array_equal(archive['run_1_xyz_cm'],xyz)
