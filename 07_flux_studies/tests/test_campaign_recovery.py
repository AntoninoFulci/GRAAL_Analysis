"""Campaign anomalies must never become truth or donors for their own recovery."""
from types import SimpleNamespace
import json

import numpy as np
import uproot

from calibration.run_manifest import RunRecord, write_manifest
from calibration.run_quality import load_run_quality
from flux_studies.calibrated_data import load_calibrated_dataset
from flux_studies.realistic_gaps import gap_inventory
from flux_studies.tests.test_calibrated_neighbors import records


def test_diagnostic_records_include_excluded_and_incomplete_runs(tmp_path):
    manifest = tmp_path / 'manifest.csv'
    write_manifest([RunRecord(r, '1998_uv', 'P', 'UV', 'P_UV', 'manual', f'uv/run{r}.root')
                    for r in (1321, 1322, 1323)], manifest)
    flux = tmp_path / 'flux.root'
    counts = {(r, s): 10 for r in (1321, 1322, 1323) for s in ('POL1', 'POL2', 'BREM')}
    with uproot.recreate(flux) as f:
        for r, s in counts:
            if (r, s) != (1323, 'BREM'):
                f[f'run{r}_{s}'] = np.ones(128), np.linspace(.5, 2, 129)
    data = load_calibrated_dataset(manifest, flux, counts, representation='native_strip')
    assert {r['run'] for r in data['records']} == {1321}
    assert {(r['run'], r['state']) for r in data['diagnostic_records']} == set(counts) - {(1323, 'BREM')}


def test_factor100_policy_freezes_new_findings_preserves_manual_exclusions(tmp_path):
    from flux_studies.prepare_native_recovery import campaign_quality
    base = load_run_quality()
    rows = [dict(run=r, period='p', state='POL1', count=10, values=np.array([v]))
            for r, v in enumerate([100., 100., 100., 100., 10001.], 1)]
    policy, findings = campaign_quality(rows, base, {'full_counts.json': 'b' * 64})
    path = tmp_path / 'quality.json'
    path.write_text(json.dumps(policy))
    loaded = load_run_quality(path)
    assert {r['run'] for r in findings} == {5}
    assert {r['run'] for r in loaded['excluded_runs']} == {5, 1322, 1441, 1454, 1482, 1970, 1988, 2055, 2064, 2607, 2804, 3585, 3776}
    assert next(r for r in loaded['excluded_runs'] if r['run'] == 5)['decision_basis'] == 'flux_per_event_factor_100'
    assert next(r for r in loaded['excluded_runs'] if r['run'] == 1441)['decision_basis'] == 'user_requested_development_benchmark_errors'
    assert len(base['excluded_runs']) == 12


def test_anomalous_run_never_becomes_candidate_or_donor():
    manifest = [SimpleNamespace(run_number=i, source_period='p', target='P', beam_type='UV') for i in range(1, 8)]
    audit = {'rows': [dict(run_number=i, state=s, calibrated_keys=[] if i in (3, 4) else [{}], problems=[])
                      for i in range(1, 8) for s in ('POL1', 'POL2', 'BREM')]}
    data = [{**r, 'position': r['position'] - 15} for r in records(7)]
    counts = {(r['run'], r['state']): r['count'] for r in data}
    inv = gap_inventory(manifest, audit, counts, data, excluded_runs={3})
    assert all(r['status'] == 'quality_excluded' for r in inv['missing'] if r['run'] == 3)
    assert all(3 not in r['donors'] for r in inv['missing'])
    assert all(r['status'] == 'candidate' for r in inv['missing'] if r['run'] == 4)


def test_campaign_policy_applies_to_dataset_and_rejects_closure_truth(tmp_path):
    from copy import deepcopy
    from flux_studies.flux_observable_closure import run_observable_closure
    import pytest
    base = load_run_quality()
    policy = {k: deepcopy(v) for k, v in base.items() if k not in ('path', 'sha256')}
    extra = deepcopy(policy['excluded_runs'][0])
    extra.update(run=1321, period='1998_uv')
    policy['excluded_runs'].append(extra)
    quality = tmp_path / 'policy.json'
    quality.write_text(json.dumps(policy))
    manifest = tmp_path / 'manifest.csv'
    write_manifest([RunRecord(1321, '1998_uv', 'P', 'UV', 'P_UV', 'manual', 'uv/run1321.root')], manifest)
    flux = tmp_path / 'flux.root'
    with uproot.recreate(flux) as f:
        for state in ('POL1', 'POL2', 'BREM'):
            f[f'run1321_{state}'] = np.ones(128), np.linspace(.5, 2, 129)
    data = load_calibrated_dataset(manifest, flux, {(1321, s): 10 for s in ('POL1', 'POL2', 'BREM')},
                                   run_quality_path=quality)
    assert data['records'] == []
    assert data['run_quality']['sha256'] == load_run_quality(quality)['sha256']
    with pytest.raises(ValueError, match='quality-excluded'):
        run_observable_closure([dict(run=1321, state='POL1', period='1998_uv', role='test', method='linear',
                                    truth=np.ones(128), estimate=np.ones(128))],
                              flux_path=flux, manifest_path=manifest, reco_paths={},
                              output_dir=tmp_path / 'closure', representation='native_strip',
                              methods=('linear',), run_quality_path=quality)


def test_preparation_counts_full_fixture_and_freezes_recovery_inputs(tmp_path, monkeypatch):
    from flux_studies.prepare_native_recovery import main
    from flux_studies.study_native_recovery import load_cached_counts
    manifest = tmp_path / 'manifest.csv'
    runs = list(range(4001, 4021))
    write_manifest([RunRecord(r, 'period_uv', 'P', 'UV', 'P_UV', 'manual', f'uv/run{r}.root')
                    for r in runs], manifest)
    h80 = tmp_path / 'pre_analisi_period_uv.root'
    with uproot.recreate(h80) as f:
        f['h80'] = {'RunNumber': np.repeat(runs, 3), 'Polarization': np.tile([0, 1, 2], len(runs))}
    flux, raw = tmp_path / 'flux.root', tmp_path / 'raw.root'
    with uproot.recreate(flux) as f, uproot.recreate(raw) as g:
        for run in runs:
            for state in ('POL1', 'POL2', 'BREM'):
                values = np.full(128, 10000. if (run, state) == (4010, 'BREM') else 1.)
                f[f'run{run}_{state}'] = values, np.linspace(.5, 2, 129)
                g[f'run{run}_{state}'] = values, np.arange(129)
    output = tmp_path / 'prepared'
    assert main(['--manifest', str(manifest), '--raw-flux', str(raw), '--calibrated-flux', str(flux),
                 '--h80-dir', str(tmp_path), '--output-dir', str(output)]) == 0
    counts, _ = load_cached_counts(output / 'h80_counts.json')
    assert sum(counts.values()) == 60
    preparation = json.loads((output / 'preparation.json').read_text())
    assert preparation['current_factor100_runs'] == [4010]
    assert preparation['clean_runs'] == 19
    inv = json.loads((output / 'gap_inventory.json').read_text())
    assert inv['missing'] == []
    assert preparation['recover_quality_runs'] == []
    design = json.loads((output / 'realistic_design.json').read_text())
    assert not design['test_masks']
    assert all(r['run'] != 4010 for r in design['split_plan']['period_uv'])
    assert json.loads((output / 'input_integrity.json').read_text())['unchanged']
    import flux_studies.prepare_native_recovery as producer
    def forbidden(*args, **kwargs):
        raise AssertionError('reused count manifest must not rescan h80 entries')
    monkeypatch.setattr(producer, 'count_h80', forbidden)
    reused = tmp_path / 'prepared-reused'
    assert main(['--manifest', str(manifest), '--raw-flux', str(raw), '--calibrated-flux', str(flux),
                 '--h80-dir', str(tmp_path), '--output-dir', str(reused),
                 '--counts-cache', str(output / 'h80_counts.json')]) == 0
    assert load_cached_counts(reused / 'h80_counts.json')[0] == counts
