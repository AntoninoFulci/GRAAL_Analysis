from dataclasses import fields, replace
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import ROOT

from calibration.run_manifest import RunRecord, write_manifest
from observable_extraction import period_workflow, workflow
from observable_extraction import beam_asymmetry
from observable_extraction.extraction import ExtractionBundle
from observable_extraction.core.models import FluxExposure
from observable_extraction.io.reconstructed_events import EventArrays
from observable_extraction.io.root_input import read_output_points, read_output_uncertainties, read_output_contract
from observable_extraction.tests.test_beam_asymmetry_cli import _synthetic_events
from observable_extraction.tests.test_calibration_io import _write_flux_root


def test_runtime_source_provenance_covers_new_modules_and_changes_with_their_bytes(tmp_path):
    (tmp_path / 'beam_asymmetry.py').write_text('entrypoint = 1\n')
    (tmp_path / 'core').mkdir()
    (tmp_path / 'core/ratio_fit.py').write_text('ratio = 1\n')
    first = period_workflow._source_identities(tmp_path)
    added = tmp_path / 'new_runtime_module.py'
    added.write_text('algorithm = 1\n')
    second = period_workflow._source_identities(tmp_path)
    added.write_text('algorithm = 2\n')
    third = period_workflow._source_identities(tmp_path)
    assert {Path(row['path']).name for row in first} == {'beam_asymmetry.py', 'ratio_fit.py'}
    assert {Path(row['path']).name for row in second} == {
        'beam_asymmetry.py', 'ratio_fit.py', 'new_runtime_module.py'}
    previous = next(row for row in second if row['path'] == str(added.resolve()))
    current = next(row for row in third if row['path'] == str(added.resolve()))
    assert previous['sha256'] != current['sha256']
    assert current['sha256'] == hashlib.sha256(added.read_bytes()).hexdigest()
    assert [row for row in second if row['path'] != str(added.resolve())] == first


def _records():
    return [RunRecord(run, period, 'P', 'UV', 'P_UV', 'manual', f'{period}/run{run}.root')
            for run, period in [(811, '1998_uv'), (812, '1999_uv'),
                                (813, '2000_uv1'), (814, '2000_uv2'), (815, '2001_uv')]]


def _join(*samples):
    return EventArrays(**{field.name: np.concatenate([getattr(x, field.name) for x in samples])
                          for field in fields(EventArrays)})


def test_partition_requires_exact_manifest_join_and_safe_periods(tmp_path):
    from observable_extraction.core.periods import partition_runs
    records = _records()
    groups = partition_runs(records, {811, 812, 814}, target='P', beam_type='UV')
    assert groups == {'1998_uv': [811], '1999_uv': [812], '2000_uv2': [814]}
    with pytest.raises(ValueError, match='unknown'):
        partition_runs(records, {999}, target='P', beam_type='UV')
    with pytest.raises(ValueError, match='duplicate'):
        partition_runs(records + [records[0]], {811}, target='P', beam_type='UV')
    with pytest.raises(ValueError, match='period'):
        partition_runs([replace(records[0], source_period='../escape')], {811}, target='P', beam_type='UV')
    with pytest.raises(ValueError, match='period'):
        partition_runs([replace(records[0], source_period='pooled')], {811}, target='P', beam_type='UV')
    with pytest.raises(ValueError, match='profile'):
        partition_runs([replace(records[0], target='D')], {811}, target='P', beam_type='UV')


def test_inclusive_universe_from_reconstruction_cutflow_keeps_zero_yield(tmp_path):
    from observable_extraction.io.reconstructed_events import read_run_universe
    path = tmp_path / 'input.root'
    output = ROOT.TFile(str(path), 'RECREATE')
    ROOT.TNamed('reconstruction_provenance', json.dumps({'counts_by_run_state': [
        {'run': 811, 'polarization': 1, 'input': 30, 'written': 10},
        {'run': 812, 'polarization': 2, 'input': 40, 'written': 0},
    ]})).Write()
    output.Close()
    runs, cutflow = read_run_universe(path)
    assert runs == {811, 812}
    assert cutflow[1]['written'] == 0


def test_flux_audit_records_missing_state_and_all_missing_is_representable(tmp_path):
    from observable_extraction.calibration.flux_v2 import load_exposures
    path, manifest = tmp_path / 'flux.root', tmp_path / 'manifest.csv'
    write_manifest(_records(), manifest)
    _write_flux_root(path, {813: ('POL1', 'BREM')})
    audit = {}
    result = load_exposures(path, manifest_path=manifest, run_numbers={813},
                            audit=audit, allow_empty=True)
    assert result == {}
    assert audit['813']['problems'] == ['missing POL2']
    assert audit['813']['status'] == 'missing_flux'


@pytest.mark.parametrize("best_binning", [False, True])
@pytest.mark.parametrize("workers", [1, 2])
def test_period_workflow_shares_engine_preserves_empty_periods_and_closes(tmp_path, monkeypatch, best_binning, workers):
    # This test mocks input ROOT I/O; real energy-domain guards have dedicated tests.
    monkeypatch.setattr(period_workflow, "_validate_energy_inputs", lambda args: None)
    nominal = tmp_path / 'nominal.root'
    nominal.write_bytes(b'test input identity')
    flux = tmp_path / 'flux.root'
    flux.write_bytes(b'test flux identity')
    manifest = tmp_path / 'manifest.csv'
    write_manifest(_records(), manifest)
    first = _synthetic_events(sigma=.4)
    second = _synthetic_events(sigma=-.25)
    second = replace(second, run_number=np.full(len(second), 812))
    missing = replace(first, run_number=np.full(len(first), 813))
    # Unequal yields: the aggregate is not an arithmetic mean of fitted Sigmas.
    events = _join(first, first, second, missing)
    exposures = {(run, 17): FluxExposure(run, 17, 1.15, 1.2, .9, .2, .6, .55)
                 for run in (811, 812, 814)}
    monkeypatch.setattr(period_workflow, 'read_reconstructed', lambda *a, **k: events)
    monkeypatch.setattr(period_workflow, 'read_run_universe',
                        lambda path: ({811, 812, 813, 814}, []))

    def load(path, **kwargs):
        assert set(kwargs['run_numbers']) == {811, 812, 813, 814}
        kwargs['audit'].update({str(run): {'status': 'valid', 'problems': []}
                                 for run in (811, 812, 814)})
        kwargs['audit']['813'] = {'status': 'missing_flux', 'problems': ['missing POL2']}
        return exposures

    monkeypatch.setattr(period_workflow, 'load_exposures', load)
    output = tmp_path / 'output'
    assert beam_asymmetry.main([
        '--by-period', '--raw-bdt', str(nominal), '--raw', str(tmp_path / 'absent.root'),
        '--flux-file', str(flux), '--run-manifest', str(manifest), '--output-dir', str(output),
        '--estimator', 'ratio',
        '--workers', str(workers),
        *(['--best-binning'] if best_binning else []),
    ]) == 0
    index = json.loads((output / 'periods/index.json').read_text())
    assert {'extraction.py', 'samples.py', 'workflow.py', 'period_workflow.py',
            'extraction_background.py', 'extraction_systematics.py'} <= {
        Path(record['path']).name for record in index['source_files']}
    entries = {row['period']: row for row in index['periods']}
    assert entries['1998_uv']['status'] == 'estimable'
    assert entries['1999_uv']['status'] == 'estimable'
    assert entries['2000_uv1']['status'] == 'not_estimable'
    assert entries['2000_uv2']['status'] == 'not_estimable'
    assert entries['2001_uv']['status'] == 'not_available'
    assert index['closure']['same_estimable_bins'] is True
    assert index['closure']['max_abs_sigma_difference'] < 1e-10
    assert index['aggregate']['run_universe'] == [811, 812, 813, 814]
    assert index['aggregate']['exposed_runs'] == [811, 812, 814]
    assert entries['2000_uv2']['samples']['raw_bdt']['input'] == 0
    assert all(row['status'] == 'not_estimable' for row in entries['2000_uv2']['bins'])
    assert entries['2000_uv1']['samples']['raw_bdt']['missing_exposure'] == len(missing)
    all_points = read_output_points(output / 'beam_asymmetry.root')
    per_points = [read_output_points(output / f'periods/{name}/beam_asymmetry.root')
                  for name in ('1998_uv', '1999_uv')]
    if not best_binning:
        assert per_points[0][0].point.sigma == pytest.approx(.4 / .9549, abs=.01)
        assert per_points[1][0].point.sigma == pytest.approx(-.25 / .9549, abs=.01)
    else:
        assert all(p.phi_bins in (8, 12, 16) for group in per_points for p in group)
    assert abs(all_points[0].point.sigma - np.mean([p[0].point.sigma for p in per_points])) > .05
    for name in ('2000_uv1', '2000_uv2'):
        path = output / f'periods/{name}/beam_asymmetry.root'
        assert read_output_points(path) == ()
        assert read_output_uncertainties(path).matrices == {}
        assert read_output_contract(path).phi_bin_divisor == (None if best_binning else .9549)
        source = ROOT.TFile.Open(str(path))
        metadata = json.loads(source.Get('extraction_metadata').GetTitle())
        assert metadata['status'] == 'not_estimable'
        assert metadata['estimable_points'] == 0
        assert metadata['point_keys'] == []
        assert source.Get('sigma_points').GetEntries() == 0
        source.Close()
    assert (output / 'period_stability.pdf').is_file()
    assert index['shared_nuisances']['polarization_scale_3pct']['correlation'] == 'shared_across_periods'
    assert len(index['period_differences']) == 3
    if not best_binning:
        assert index['period_differences'][0]['sigma_difference'] == pytest.approx(.65 / .9549, abs=.02)


def test_period_mode_rejects_unknown_input_before_writing(tmp_path, monkeypatch):
    # This test mocks input ROOT I/O; real energy-domain guards have dedicated tests.
    monkeypatch.setattr(period_workflow, "_validate_energy_inputs", lambda args: None)
    nominal = tmp_path / 'nominal.root'
    nominal.touch()
    manifest = tmp_path / 'manifest.csv'
    write_manifest(_records(), manifest)
    events = _synthetic_events()
    events = replace(events, run_number=np.full(len(events), 999))
    monkeypatch.setattr(period_workflow, 'read_reconstructed', lambda *a, **k: events)
    monkeypatch.setattr(period_workflow, 'read_run_universe', lambda path: ({999}, []))
    output = tmp_path / 'result'
    with pytest.raises(ValueError, match='unknown'):
        beam_asymmetry.main(['--by-period', '--raw-bdt', str(nominal),
                             '--run-manifest', str(manifest), '--output-dir', str(output)])
    assert not output.exists()


def test_csv_period_must_agree_with_canonical_manifest(tmp_path):
    from observable_extraction.calibration.flux_v2 import load_exposures
    from observable_extraction.tests.test_calibration_io import _write_rows, _row
    path, manifest = tmp_path / 'flux.csv', tmp_path / 'manifest.csv'
    write_manifest(_records(), manifest)
    _write_rows(path, [_row(source_period='1999_uv')])
    with pytest.raises(ValueError, match='manifest'):
        load_exposures(path, manifest_path=manifest, run_numbers={811})


def test_sideband_requires_same_inclusive_universe(tmp_path, monkeypatch):
    # This test mocks input ROOT I/O; real energy-domain guards have dedicated tests.
    monkeypatch.setattr(period_workflow, "_validate_energy_inputs", lambda args: None)
    nominal, sideband, mc = [tmp_path / name for name in ('nominal.root', 'sideband.root', 'mc.root')]
    for path in (nominal, sideband, mc):
        path.touch()
    manifest = tmp_path / 'manifest.csv'
    write_manifest(_records(), manifest)
    monkeypatch.setattr(period_workflow, 'read_reconstructed', lambda *a, **k: _synthetic_events())
    monkeypatch.setattr(period_workflow, 'read_run_universe',
                        lambda path: ({811} if path == sideband else {811, 812}, []))
    with pytest.raises(ValueError, match='sideband.*universe'):
        beam_asymmetry.main(['--by-period', '--raw-bdt', str(nominal),
                             '--sideband', str(sideband), '--signal-mc', str(mc),
                             '--run-manifest', str(manifest), '--flux-file', str(tmp_path / 'absent.root'),
                             '--output-dir', str(tmp_path / 'output')])


def test_period_audit_energy_boundaries_match_selector():
    from observable_extraction.core.periods import selection_audit
    first = _synthetic_events()
    events = first.take(np.arange(len(first)) < 6)
    events = replace(events, beam_energy_gev=np.array([1.1, 1.2, 1.5, 1.099, 1.501, 1.2]),
                     polarization=np.array([1, 2, 0, 1, 2, 99]))
    exposures = {(811, 17): FluxExposure(811, 17, 1.2, 1., 1., .2, .6, .6)}
    audit = selection_audit(events, exposures, (1.1, 1.5))
    assert audit['selected'] == 2
    assert audit['brem'] == 1
    assert audit['outside_energy'] == 2
    assert audit['other_state'] == 1
    assert audit['input'] == audit['selected'] + audit['brem'] + audit['excluded']


def test_unconverged_period_fit_is_recorded_but_not_published(tmp_path, monkeypatch):
    from observable_extraction.tests.test_root_output import _point
    point = _point()
    failed = replace(point, sample='raw_bdt', estimator='likelihood',
                     point=replace(point.point, diagnostics=replace(point.point.diagnostics, converged=False)))
    monkeypatch.setattr(workflow, 'extract_sample',
                        lambda **kwargs: ExtractionBundle((failed,), ()))
    args = beam_asymmetry.build_parser().parse_args([
        '--raw-bdt', str(tmp_path / 'input.root'), '--raw', str(tmp_path / 'absent.root'),
        '--estimator', 'likelihood', '--output-dir', str(tmp_path / 'result')])
    events = _synthetic_events()
    inputs = {(args.raw_bdt, 'reco_eta_pi0_bdt'): events}
    exposures = {(811, 17): FluxExposure(811, 17, 1.15, 1., 1., .2, .6, .6)}
    payload = workflow._run_single(args, prepared=(inputs, exposures),
                                         period='1998_uv', metadata={}, campaign='toy')
    assert payload.points == ()
    assert payload.extraction_metadata['status'] == 'not_estimable'
    assert payload.extraction_metadata['failed_fit_keys'][0]['mass_bin'] == 0
