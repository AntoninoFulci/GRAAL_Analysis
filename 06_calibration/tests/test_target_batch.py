import csv
import json
from pathlib import Path

import numpy as np
import awkward as ak
import pytest
import uproot

from calibration.target_batch import run_campaign


def write_raw(path, run, mode='good'):
    n = 2000  # Local edge fits require 200 events per edge window.
    rng = np.random.default_rng(run)
    z = rng.uniform(-3, 3, n) + rng.normal(0, .3, n)
    tracks = 0 if mode == 'off' else 2
    data = dict(Idrun=np.full(n, run), Idevt=np.arange(n), Nass_3=np.full(n, tracks),
                Nb_traces_cyl=np.full(n, tracks),
                Iass_3=np.tile(np.array([[[1, 1, 1], [2, 2, 2]]]), (n, 1, 1))[:, :tracks],
                Itipo_track=np.zeros((n, tracks), dtype=np.int32))
    for side, radius in [('int', 5.), ('ext', 8.)]:
        data[f'X_trace_{side}'] = np.tile([radius, 0.], (n, 1))[:, :tracks]
        data[f'Y_trace_{side}'] = np.tile([0., radius], (n, 1))[:, :tracks]
        data[f'Z_trace_{side}'] = np.column_stack([z, z])[:, :tracks]
    if mode == 'missing':
        del data['X_trace_int']
    if mode == 'off':
        for name in ['Iass_3', 'Itipo_track'] + [f'{axis}_trace_{side}' for side in ('int', 'ext') for axis in 'XYZ']:
            flat = np.empty((0, 3), dtype=np.int32) if name == 'Iass_3' else np.empty(0)
            data[name] = ak.unflatten(flat, np.zeros(n, dtype=int))
    with uproot.recreate(path) as f:
        f.mktree('h70', data)


def test_batch_skips_bad_runs_continues_merges_and_resumes(tmp_path, caplog):
    raw = tmp_path/'raw'/'1998_uv'
    raw.mkdir(parents=True)
    for run, mode in [(1321, 'missing'), (1322, 'off'), (1324, 'good')]:
        write_raw(raw/f'run{run}.root', run, mode)
    catalog = tmp_path/'catalog.csv'
    catalog.write_text('run_number,source_period,target,beam_type,group,classification_source,source_file\n'+
                       ''.join(f'{r},1998_uv,P,UV,P_UV,manual,1998_uv/run{r}.root\n'
                               for r in [1321,1322,1323,1324]))
    output = tmp_path/'campaign'
    with caplog.at_level('WARNING'):
        products = run_campaign(raw.parent, catalog, output, workers=2, bootstrap=0, plots=False)
    rows = {int(r['run']): r for r in csv.DictReader((products/'target_runs.csv').open())}
    assert rows[1321]['reconstruction_status'] == 'missing_geometry_branches'
    assert rows[1322]['reconstruction_status'] == 'no_chamber_tracks'
    assert rows[1323]['reconstruction_status'] == 'missing_input'
    assert rows[1324]['reconstruction_status'] == 'completed'
    assert rows[1322]['events_with_chamber_tracks'] == '0'
    assert rows[1324]['selected_events'] == '2000'
    assert '1321' in caplog.text and '1322' in caplog.text and '1323' in caplog.text
    meta = json.loads((products/'metadata.json').read_text())
    period = meta['periods']['1998_uv']
    assert period['coverage_status'] == 'complete'
    assert period['included_runs'] == [1324]
    assert period['exclusion_reasons']['1322'] == 'no_chamber_tracks'
    with np.load(products/'run_plots.npz', allow_pickle=False) as archive:
        assert archive['run_1321_xyz_cm'].shape == (0, 3)
        assert archive['run_1324_xyz_cm'].shape == (2000, 3)
        assert archive['period_1998_uv_xy_probability'].sum() == pytest.approx(1)
    before = (output/'runs/run_1324/plots.npz').stat().st_mtime_ns
    # Remove only disposable merged test output to exercise shard resume.
    import shutil
    shutil.rmtree(products)
    run_campaign(raw.parent, catalog, output, workers=2, bootstrap=0, plots=False)
    assert (output/'runs/run_1324/plots.npz').stat().st_mtime_ns == before
    assert run_campaign(raw.parent, catalog, output, workers=2, bootstrap=0, plots=False) == products
    with pytest.raises(ValueError, match='fingerprint'):
        run_campaign(raw.parent, catalog, output, workers=2, bootstrap=1, plots=False)


def test_run_identity_mismatch_is_flagged_and_not_accepted(tmp_path):
    from calibration.target_batch import process_run, source_hashes
    write_raw(tmp_path/'run1321.root', 9999)
    row = dict(run_number=1321, source_file='run1321.root', source_period='1998_uv',
               target='P', beam_type='UV', classification_source='manual')
    record, resumed = process_run(row, tmp_path, tmp_path/'shards', 0, source_hashes())
    assert not resumed
    assert record['reconstruction_status'] == 'reconstruction_failed'
    assert 'identity' in record['reconstruction_note']
    assert record['selected_events'] == 0


def test_interrupted_empty_reservation_can_resume(tmp_path):
    from calibration.target_batch import process_run, source_hashes
    shards = tmp_path/'shards'
    (shards/'run_1321').mkdir(parents=True)
    stale = shards/'.run_1321.interrupted'
    stale.mkdir()
    (stale/'partial.root').write_bytes(b'partial')
    write_raw(tmp_path/'run1321.root', 1321)
    row = dict(run_number=1321, source_file='run1321.root', source_period='1998_uv',
               target='P', beam_type='UV', classification_source='manual')
    record, _ = process_run(row, tmp_path, shards, 0, source_hashes())
    assert record['reconstruction_status'] == 'completed'
    assert not stale.exists()


def test_stat_permission_error_is_a_run_failure_not_campaign_abort(tmp_path, monkeypatch):
    from calibration.target_batch import process_run, source_hashes
    raw = tmp_path/'run1321.root'
    write_raw(raw, 1321)
    real_stat = Path.stat

    def denied(path, *args, **kwargs):
        if path == raw:
            raise PermissionError(13, 'fixture access denied', str(path))
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(Path, 'stat', denied)
    row = dict(run_number=1321, source_file='run1321.root', source_period='1998_uv',
               target='P', beam_type='UV', classification_source='manual')
    record, _ = process_run(row, tmp_path, tmp_path/'shards', 0, source_hashes())
    # Explicit stat error is not usable scientific provenance even if open succeeds.
    assert record['reconstruction_status'] == 'reconstruction_failed'
    assert 'PermissionError' in record['reconstruction_note']


def test_publication_checks_hashes_and_relocates_profile_paths(tmp_path):
    from calibration.target_batch import _sha256
    from calibration.target_publish import publish_support
    products = tmp_path/'results'/'products'
    products.mkdir(parents=True)
    for name in ['target_runs.csv', 'target_periods.csv']:
        (products/name).write_text('run,plot_archive\n1,run_plots.npz\n')
    (products/'run_plots.npz').write_bytes(b'fixture')
    (products/'metadata.json').write_text(json.dumps(dict(periods={'p':{'coverage_status':'complete'}}, catalog={}, code_hashes={})))
    (products/'geant4_candidates.json').write_text(json.dumps(dict(periods={'p':{'photon_beam_proxy':{'profile_file':'run_plots.npz'}}})))
    (products/'checksums.json').write_text(json.dumps({p.name:_sha256(p) for p in products.iterdir()}))
    support = tmp_path/'config'/'support'/'conditions'
    support.mkdir(parents=True)  # Interrupted empty publication reservation.
    stale = support.parent/'.conditions.interrupted'
    stale.mkdir()
    (stale/'partial.csv').write_text('partial')
    publish_support(products, support)
    assert not stale.exists()
    candidate = json.loads((support/'geant4_candidates.json').read_text())
    profile = support/candidate['periods']['p']['photon_beam_proxy']['profile_file']
    assert profile.resolve() == products/'run_plots.npz'
    assert publish_support(products, support) == support
    (products/'run_plots.npz').write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='checksum'):
        publish_support(products, tmp_path/'bad')
