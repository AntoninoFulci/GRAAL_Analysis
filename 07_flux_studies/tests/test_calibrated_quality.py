import numpy as np
import uproot

from calibration.run_manifest import RunRecord, write_manifest
from flux_studies.calibrated_data import load_calibrated_dataset


def test_quality_exclusion_preserves_original_eligible_split_universe(tmp_path):
    manifest = tmp_path / 'manifest.csv'
    write_manifest([RunRecord(run, '1998_uv', 'P', 'UV', 'P_UV', 'manual', f'uv/run{run}.root')
                    for run in (1321, 1322, 1323, 1441, 1454, 1988, 2055, 2064)], manifest)
    flux = tmp_path / 'flux.root'
    counts = {}
    with uproot.recreate(flux) as output:
        for run in (1321, 1322, 1323, 1441, 1454, 1988, 2055, 2064):
            for state in ('POL1', 'POL2', 'BREM'):
                counts[run, state] = 10
                if run != 1323 or state != 'BREM':
                    output[f'run{run}_{state}'] = np.ones(128), np.linspace(.5, 2., 129)
    dataset = load_calibrated_dataset(manifest, flux, counts)
    assert {row['run'] for row in dataset['records']} == {1321}
    assert dataset['split_runs_by_period'] == {'1998_uv': [1321, 1322, 1441, 1454, 1988, 2055, 2064]}
    excluded = {row['run']: row for row in dataset['exclusions']}
    assert all(excluded[run]['category'] == 'run_quality'
               for run in (1322, 1441, 1454, 1988, 2055, 2064))
    assert excluded[1322]['reasons']
    assert 'BREM:missing_or_duplicate_calibrated' in excluded[1323]['reasons']
    assert len(dataset['run_quality']['sha256']) == 64
