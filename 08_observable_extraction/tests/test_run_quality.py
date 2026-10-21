"""All observable entry points share these event/exposure selection boundaries."""
from dataclasses import fields

import numpy as np
import pytest

from calibration.run_manifest import RunRecord, write_manifest
from observable_extraction.calibration.flux_v2 import load_exposures
from observable_extraction.core.models import FluxExposure
from observable_extraction.core.periods import selection_audit
from observable_extraction.io.reconstructed_events import EventArrays, select_sigma_events, select_brem_control
from observable_extraction.tests.test_calibration_io import _write_flux_root, _write_rows, _row


def _events():
    runs = np.repeat([811, 1322, 1441, 1454, 1482, 1970, 1988, 2055, 2064, 2607, 2804, 3585, 3776], 3)
    values = {field.name: np.zeros(len(runs)) for field in fields(EventArrays)}
    values.update(run_number=runs, xstrip=np.full(len(runs), 17),
                  polarization=np.tile([0, 1, 2], len(runs) // 3), beam_energy_gev=np.full(len(runs), 1.25))
    return EventArrays(**values)


@pytest.mark.parametrize('format', ['csv', 'root'])
def test_quality_removes_entire_runs_from_exposure_and_data_with_reasoned_audit(tmp_path, format):
    runs = [811, 1322, 1441, 1454, 1482, 1970, 1988, 2055, 2064, 2607, 2804, 3585, 3776]
    manifest = tmp_path / 'manifest.csv'
    write_manifest([RunRecord(run, 'p', 'P', 'UV', 'P_UV', 'manual', f'uv/run{run}.root') for run in runs], manifest)
    path = tmp_path / f'flux.{format}'
    if format == 'root':
        _write_flux_root(path, {run: ('POL1', 'POL2', 'BREM') for run in runs})
    else:
        _write_rows(path, [_row(run_number=run, source_period='p') for run in runs])
    audit = {}
    exposures = load_exposures(path, manifest_path=manifest, run_numbers=runs,
                              polarization_model=lambda _: .5, audit=audit, energy_range=(.5, 2.))
    assert {run for run, _ in exposures} == {811}
    assert audit['1322']['status'] == 'quality_excluded'
    assert audit['1322']['problems']
    assert len(audit['_run_quality']['sha256']) == 64
    assert select_sigma_events(_events(), exposures).run_number.tolist() == [811, 811]
    assert select_brem_control(_events(), exposures).run_number.tolist() == [811]
    counts = selection_audit(_events(), exposures, (1.1, 1.5))
    assert counts['quality_excluded'] == 36
    assert counts['missing_exposure'] == 0
    assert counts['input'] == counts['selected'] + counts['brem'] + counts['excluded']


def test_event_boundary_also_rejects_quality_runs_in_legacy_in_memory_exposures():
    exposures = {(run, 17): FluxExposure(run, 17, 1.25, 120, 80, 25, .5, .5)
                 for run in (811, 1322, 1441, 1454, 1482, 1970, 1988, 2055, 2064, 2607, 2804, 3585, 3776)}
    assert select_sigma_events(_events(), exposures).run_number.tolist() == [811, 811]
    assert select_brem_control(_events(), exposures).run_number.tolist() == [811]


def test_period_audit_carries_shared_policy_identity():
    from observable_extraction.beam_asymmetry import _period_metadata
    from graal_common.physics.beam_profiles import get_beam_profile
    profile = get_beam_profile('uv')
    metadata = _period_metadata('p', [1322], {'data': _events()}, {},
                                {'_run_quality': {'sha256': 'frozen'}}, {}, profile, profile)
    assert metadata['run_quality']['sha256'] == 'frozen'
