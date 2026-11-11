import json
import csv
from pathlib import Path
import subprocess
import sys

import numpy as np
import pytest
import uproot

from calibration.target_database import build_database, render_archived_run


def test_database_groups_runs_preserves_unknown_diameter_and_refuses_overwrite(tmp_path):
    campaign = tmp_path/'vertices'
    campaign.mkdir()
    rng = np.random.default_rng(17)
    n = 3000  # Enough events in each local edge window, not just the whole cell.
    data = dict(run=np.repeat([1321,1324], n), event=np.arange(2*n),
                source_file=np.zeros(2*n, dtype=int), source_entry=np.arange(2*n),
                n_charged=np.full(2*n, 2), status=np.zeros(2*n, dtype=int),
                dca_cm=np.full(2*n,.2), x_cm=rng.normal(.5,.4,2*n),
                y_cm=rng.normal(.1,.25,2*n), z_cm=rng.uniform(-3,3,2*n)+rng.normal(0,.2,2*n))
    with uproot.recreate(campaign/'vertices.root') as f:
        f.mktree('vertices',data)
    (campaign/'summary.json').write_text(json.dumps({'schema':1,'diagnostic':'central_pair_target_vertex',
        'units':'cm, native h70 detector frame; no alignment shift',
        'files':[{'index':0,'path':'fixture.root'}],
        'runs':{'1321':{'events_read':n},'1324':{'events_read':n}}}))
    catalog=tmp_path/'catalog.csv'
    catalog.write_text('run_number,source_period,target,beam_type,group,classification_source,source_file\n'
                       '1321,1998_uv,P,UV,P_UV,manual,1998_uv/run1321.root\n'
                       '1324,1998_uv,P,UV,P_UV,manual,1998_uv/run1324.root\n')
    out = tmp_path/'database'
    report = build_database(campaign,out,bootstrap=0,plots=True,catalog=catalog)
    assert len(report['runs']) == 2
    with (out/'target_runs.csv').open() as stream:
        rows=list(csv.DictReader(stream))
    assert [(r['run'],int(r['selected_events']),r['target_diameter_cm']) for r in rows]==[('1321',n,''),('1324',n,'')]
    assert all(r['source_period']=='1998_uv' for r in rows)
    assert not list(out.glob('*.sqlite'))
    candidate = json.loads((out/'geant4_candidates.json').read_text())['periods']['1998_uv']
    assert candidate['status'] == 'diagnostic_approximation_not_applied'
    assert candidate['target']['diameter_mm'] == 50
    assert candidate['target']['diameter_source'] == 'historical_reference_assumption_not_run_measurement'
    assert candidate['weighting']=='equal_weight_per_valid_run'
    profile = np.load(out/'run_plots.npz',allow_pickle=False)
    spot = report['runs']['1321']['observed_xy']
    assert profile['run_1321_xy_counts'].sum() + spot['outside_z_selection'] + spot['outside_xy_window'] == n
    assert profile['run_1321_xyz_cm'].shape==(n,3)
    np.testing.assert_allclose(profile['run_1321_xyz_cm'][:,0],data['x_cm'][:n])
    assert profile['period_1998_uv_x_edges_mm'][0] == -50
    assert profile['period_1998_uv_xy_probability'].sum()==pytest.approx(1)
    assert (out/'period_1998_uv_target_spot.png').is_file()
    assert not (out/'run_1321_target_spot.png').exists()
    restored=render_archived_run(out/'run_plots.npz',1321,tmp_path/'restored')
    assert restored.stat().st_size>1000
    with pytest.raises(FileExistsError):
        build_database(campaign,out,bootstrap=0,plots=False,catalog=catalog)
    cli_out = tmp_path/'cli_output'
    script = Path(__file__).resolve().parents[1]/'target_database.py'
    cli = subprocess.run([sys.executable,'-B',str(script),str(campaign),'--output',str(cli_out),
                          '--bootstrap','0','--no-plots','--catalog',str(catalog)],capture_output=True,text=True)
    assert cli.returncode == 0, cli.stderr
    assert json.loads((cli_out/'metadata.json').read_text())['runs']['1324']['selected_events'] == n
    metadata = json.loads((campaign/'summary.json').read_text())
    del metadata['runs']['1324']
    (campaign/'summary.json').write_text(json.dumps(metadata))
    with pytest.raises(ValueError, match='run coverage'):
        build_database(campaign,tmp_path/'missing_run',bootstrap=0,plots=False,catalog=catalog)
    assert not (tmp_path/'missing_run').exists()


def test_missing_manifest_cannot_be_interpreted_as_vertex_campaign(tmp_path):
    with pytest.raises((ValueError,FileNotFoundError)):
        build_database(tmp_path,tmp_path/'out',bootstrap=0,plots=False)
    assert not (tmp_path/'out').exists()
