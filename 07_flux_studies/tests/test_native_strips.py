"""Native strip identity, independent calibration metadata, and target isolation."""
import numpy as np
import pytest
import uproot

from calibration.run_manifest import RunRecord, write_manifest
from flux_studies.calibrated_data import load_calibrated_dataset


def inputs(tmp_path):
    manifest = tmp_path / 'manifest.csv'
    write_manifest([RunRecord(run, '1998_uv', 'P', 'UV', 'P_UV', 'manual', f'uv/run{run}.root')
                    for run in (1321, 1324, 1325)], manifest)
    calibrated, raw = tmp_path / 'calibrated.root', tmp_path / 'raw.root'
    counts, values, axes = {}, {}, {}
    with uproot.recreate(calibrated) as output, uproot.recreate(raw) as original:
        for i, run in enumerate((1321, 1324, 1325)):
            for j, state in enumerate(('BREM', 'POL1', 'POL2')):
                name = f'run{run}_{state}'
                counts[run, state] = 100
                values[run, state] = np.arange(128, dtype=float) + i + j
                axes[run, state] = np.linspace(.6 + .001 * i, 1.9 + .001 * j, 129)
                output[name] = values[run, state], axes[run, state]
                original[name] = values[run, state], np.arange(129, dtype=float)
                output[f'calibration/{name}_profile'] = np.linspace(.6, 1.9, 128), np.arange(129) + .5
    return manifest, calibrated, raw, counts, values, axes


def test_native_values_are_exact_and_calibration_axes_remain_per_record(tmp_path):
    manifest, calibrated, _, counts, values, axes = inputs(tmp_path)
    dataset = load_calibrated_dataset(manifest, calibrated, counts, representation='native_strip')
    assert dataset['representation'] == 'native_strip'
    assert dataset['energy_edges'] is None
    np.testing.assert_array_equal(dataset['strip_indices'], np.arange(1, 129))
    for record in dataset['records']:
        key = record['run'], record['state']
        np.testing.assert_array_equal(record['values'], values[key])
        np.testing.assert_array_equal(record['calibration_edges'], axes[key])
        assert record['axis_source']['histogram'] == f'run{key[0]}_{key[1]}'
    legacy = load_calibrated_dataset(manifest, calibrated, counts)
    assert legacy['representation'] == 'common_energy'
    assert not np.array_equal(legacy['records'][0]['values'], dataset['records'][0]['values'])
    assert legacy['split_runs_by_period'] == dataset['split_runs_by_period']


def test_native_axis_outside_common_energy_range_is_valid(tmp_path):
    manifest, calibrated, _, counts, _, _ = inputs(tmp_path)
    with uproot.recreate(calibrated) as output:
        for run, state in counts:
            output[f'run{run}_{state}'] = np.ones(128), np.linspace(2., 3., 129)
    native = load_calibrated_dataset(manifest, calibrated, counts, representation='native_strip')
    assert len(native['records']) == 9
    assert load_calibrated_dataset(manifest, calibrated, counts)['records'] == []


def test_unknown_representation_rejected_before_io():
    with pytest.raises(ValueError, match='representation'):
        load_calibrated_dataset('absent', 'absent', {}, representation='misspelled')


def test_native_predictors_never_read_target_truth_or_axis():
    from flux_studies.neighbor_validation import neighbor_example
    class HiddenTarget(dict):
        def __getitem__(self, key):
            if key in ('values', 'calibration_edges', 'axis_source', 'xstrips'):
                raise AssertionError(f'target leakage: {key}')
            return super().__getitem__(key)
    base = dict(group=('1998_uv', 'P', 'UV', 'POL1'), count=100)
    target = HiddenTarget(base, run=2, position=15.)
    donors = [dict(base, run=run, position=pos, values=np.ones(128) * value)
              for run, pos, value in [(1, 0., 2.), (3, 30., 4.)]]
    result = neighbor_example(target, donors)
    np.testing.assert_array_equal(result['linear'], np.ones(128) * 3.)


def test_audit_checks_index_identity_and_accepts_different_energy_axes(tmp_path):
    from flux_studies.strip_audit import audit_native_strips
    manifest, calibrated, raw, _, _, _ = inputs(tmp_path)
    result = audit_native_strips(manifest, calibrated, raw)
    assert result['status'] == 'verified'
    assert result['periods']['1998_uv']['histograms_checked'] == 9
    assert result['periods']['1998_uv']['unique_energy_axes'] > 1
    assert result['periods']['1998_uv']['content_mismatches'] == 0
    with uproot.update(raw) as source:
        source['run1321_POL1'] = np.ones(128), np.arange(129)
    assert audit_native_strips(manifest, calibrated, raw)['status'] == 'failed'


@pytest.mark.parametrize('axis', [np.r_[np.arange(128), 127.], np.r_[np.nan, np.arange(128)]])
def test_native_rejects_invalid_calibration_axes_for_entire_run(tmp_path, axis):
    manifest, calibrated, _, counts, _, _ = inputs(tmp_path)
    with uproot.recreate(calibrated) as output:
        for run, state in counts:
            output[f'run{run}_{state}'] = np.ones(128), axis
    result = load_calibrated_dataset(manifest, calibrated, counts, representation='native_strip')
    assert result['records'] == []
    assert len(result['exclusions']) == 3


def test_audit_detects_moved_content_and_wrong_raw_strip_axis(tmp_path):
    from flux_studies.strip_audit import audit_native_strips
    manifest, calibrated, raw, counts, values, _ = inputs(tmp_path)
    with uproot.recreate(raw) as output:
        for run, state in counts:
            output[f'run{run}_{state}'] = np.roll(values[run, state], 1), np.arange(129) + .5
    result = audit_native_strips(manifest, calibrated, raw)
    assert result['status'] == 'failed'
    assert result['periods']['1998_uv']['content_mismatches'] == 9
    assert result['periods']['1998_uv']['raw_axis_mismatches'] == 9


def test_native_keeps_all_twelve_frozen_whole_run_exclusions(tmp_path):
    from calibration.run_quality import load_run_quality
    quality = load_run_quality()
    excluded = {row['run']: row for row in quality['excluded_runs']}
    assert len(excluded) == 12
    runs = [(1321, '1998_uv')] + [(run, row['period']) for run, row in excluded.items()]
    manifest = tmp_path / 'manifest.csv'
    write_manifest([RunRecord(run, period, 'P', 'UV', 'P_UV', 'manual', f'{period}/run{run}.root')
                    for run, period in runs], manifest)
    counts = {(run, state): 100 for run, _ in runs for state in ('BREM', 'POL1', 'POL2')}
    calibrated = tmp_path / 'calibrated.root'
    with uproot.recreate(calibrated) as output:
        for run, state in counts:
            output[f'run{run}_{state}'] = np.ones(128), np.linspace(.5, 2., 129)
    dataset = load_calibrated_dataset(manifest, calibrated, counts, representation='native_strip')
    assert {r['run'] for r in dataset['records']} == {1321}
    assert {r['run'] for r in dataset['exclusions'] if r.get('category') == 'run_quality'} == set(excluded)
    assert {run for runs in dataset['split_runs_by_period'].values() for run in runs} == set(excluded) | {1321}
