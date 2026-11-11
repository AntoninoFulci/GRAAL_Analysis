"""State availability and conservative common-energy contracts."""
import numpy as np
import pytest
import uproot

from calibration.run_manifest import RunRecord, write_manifest
from flux_studies.calibrated_data import load_calibrated_dataset


def test_state_inventory_keeps_pol_without_brem_and_absent_cohort(tmp_path):
    manifest = tmp_path / 'manifest.csv'
    write_manifest([RunRecord(run, '1998_uv', 'P', 'UV', 'P_UV', 'manual', f'uv/run{run}.root')
                    for run in (1321, 1322, 1323, 1324)], manifest)
    flux = tmp_path / 'flux.root'
    counts = {(run, state): 10 for run in (1321, 1322, 1323)
              for state in ('BREM', 'POL1', 'POL2')}
    with uproot.recreate(flux) as output:
        for run in (1321, 1322, 1323):
            for state in ('POL1', 'POL2'):
                output[f'run{run}_{state}'] = np.zeros(128), np.linspace(.5, 2., 129)
        output['run1323_POL1'] = np.ones(128), np.linspace(.5, 2., 129)
    data = load_calibrated_dataset(manifest, flux, counts, state_wise=True,
                                   edges=np.linspace(.5, 2., 18))
    assert {(r['run'], r['state']) for r in data['records']} == {
        (1321, 'POL1'), (1321, 'POL2'), (1323, 'POL2')}
    assert all(len(r['values']) == 17 for r in data['records'])
    assert all(r['native_values'].shape == (128,) for r in data['records'])
    inventory = {(r['run'], r['state']): r for r in data['inventory']}
    assert len(inventory) == 12
    assert inventory[1321, 'POL1']['measurement_status'] == 'measured_valid'
    assert inventory[1321, 'BREM']['measurement_status'] == 'missing_histogram'
    assert inventory[1323, 'POL1']['measurement_status'] == 'duplicate_histogram'
    assert 'run_quality' in inventory[1322, 'POL1']['reasons']
    assert 'missing_inclusive_count' in inventory[1324, 'POL1']['reasons']
    assert 'insufficient_independent_axis' in inventory[1321, 'POL1']['reasons']
    assert data['input_audit']['calibrated_flux']['uuid']
    assert len(data['input_audit']['manifest']['sha256']) == 64


@pytest.mark.parametrize('problem, expected', [
    ('negative', 'invalid_values'), ('nan', 'invalid_values'),
    ('axis', 'invalid_axis'), ('count_zero', 'invalid_inclusive_count'),
    ('count_missing', 'missing_inclusive_count')])
def test_inventory_distinguishes_defective_measurement_and_missing_inputs(tmp_path, problem, expected):
    manifest = tmp_path / 'manifest.csv'
    write_manifest([RunRecord(1321, '1998_uv', 'P', 'UV', 'P_UV', 'manual', 'uv/run1321.root')], manifest)
    values, edges = np.ones(128), np.linspace(.5, 2., 129)
    count = 10
    if problem == 'negative':
        values[4] = -1
    elif problem == 'nan':
        values[4] = np.nan
    elif problem == 'axis':
        edges[3] = edges[2]
    elif problem == 'count_zero':
        count = 0
    flux = tmp_path / 'flux.root'
    with uproot.recreate(flux) as output:
        output['run1321_POL1'] = values, edges
    counts = {} if problem == 'count_missing' else {(1321, 'POL1'): count}
    result = load_calibrated_dataset(manifest, flux, counts, state_wise=True)
    row = next(r for r in result['inventory'] if r['state'] == 'POL1')
    assert expected in row['reasons']
    assert not row['measured_eligible']
    assert result['records'] == []


def test_enclosing_grid_preserves_measured_support_without_requiring_identical_axes(tmp_path):
    manifest = tmp_path / 'manifest.csv'
    write_manifest([RunRecord(1321, '1998_uv', 'P', 'UV', 'P_UV', 'manual', 'uv/run1321.root')], manifest)
    flux = tmp_path / 'flux.root'
    with uproot.recreate(flux) as output:
        output['run1321_POL1'] = np.ones(128), np.linspace(.6, 1.9, 129)
    data = load_calibrated_dataset(manifest, flux, {(1321, 'POL1'): 10}, state_wise=True)
    assert len(data['records']) == 1
    assert data['records'][0]['values'].sum() == pytest.approx(128)
    assert not data['records'][0]['transfer_audit']['destination_covered']
    assert data['records'][0]['measured_energy_support'] == [.6, 1.9]


def test_transfer_accounts_tails_flow_and_uncovered_domain():
    from flux_studies.energy_recovery import conservative_transfer
    result = conservative_transfer([2., 4.], [0., 1., 2.], [.5, 1., 1.5],
                                   underflow=3., overflow=5.)
    np.testing.assert_allclose(result['values'], [1., 2.])
    assert result['audit']['lower_tail'] == 1.
    assert result['audit']['upper_tail'] == 2.
    assert result['audit']['source_total_including_flow'] == 14.
    assert result['audit']['accounted_total'] == 14.
    assert result['audit']['destination_covered']
    outside = conservative_transfer([2.], [0., 1.], [-1., .5, 2.])
    assert not outside['audit']['destination_covered']
    np.testing.assert_allclose(outside['audit']['coverage_fraction'], [1 / 3, 1 / 3])


def test_enclosing_transfer_does_not_invent_floating_point_tail():
    from flux_studies.energy_recovery import conservative_transfer
    values=np.random.default_rng(7).random(128)
    result=conservative_transfer(values,np.linspace(.6,1.9,129),np.linspace(.5,2.,129))
    assert result['audit']['lower_tail']==0
    assert result['audit']['upper_tail']==0



def test_strip_mapping_rejects_uncovered_axis_and_preserves_strip_identity():
    from flux_studies.energy_recovery import IndependentStripAxis, map_energy_to_strips
    axis = IndependentStripAxis(run=1321, state='POL1', edges=np.linspace(.5, 2., 129),
                                provenance={'kind': 'inclusive_h80_calibration', 'sha256': 'a' * 64})
    result = map_energy_to_strips(np.ones(16), np.linspace(.5, 2., 17), axis)
    assert result['run'] == 1321 and result['state'] == 'POL1'
    np.testing.assert_array_equal(result['strip_indices'], np.arange(1, 129))
    assert sum(result['values']) == pytest.approx(16)
    with pytest.raises(ValueError, match='uncovered'):
        map_energy_to_strips(np.ones(16), np.linspace(.6, 1.9, 17), axis)


def test_independent_axis_reads_authenticated_fit_without_flux_histogram(tmp_path):
    from calibration.calibration_qa import sha256_file, write_calibration_qa
    from flux_studies.energy_recovery import load_independent_axes
    root = pytest.importorskip('ROOT')
    manifest, h80 = tmp_path / 'manifest.csv', tmp_path / 'h80.root'
    write_manifest([RunRecord(1321, '1998_uv', 'P', 'UV', 'P_UV', 'manual', 'uv/run1321.root')], manifest)
    with uproot.recreate(h80) as source:
        source['h80'] = {'RunNumber': np.array([1321]), 'Polarization': np.array([1])}
    product = tmp_path / 'calibration.root'
    output = root.TFile.Open(str(product), 'RECREATE')
    output.mkdir('calibration').cd()
    fit = root.TF1('run1321_POL1_fit', 'pol4', .5, 128.5)
    fit.SetParameters(.5, .01, 0., 0., 0.)
    fit.Write()
    output.Close()
    qa = tmp_path / 'calibration.qa.json'
    write_calibration_qa(qa, product,
        inputs={'manifest': sha256_file(manifest),
                'h80': [[str(h80), h80.stat().st_size, h80.stat().st_mtime_ns, sha256_file(h80)]]},
        coverage=[dict(run_number=1321, state='POL1', accepted=True,
                       strip_coverage=dict(observed_strip_count=5, first_strip=1, last_strip=128))],
        diagnostics={})
    axes = load_independent_axes(product, qa, manifest=manifest, h80_paths=[h80])
    np.testing.assert_allclose(axes[1321, 'POL1'].edges, .5 + .01 * (np.arange(129) + .5))
    assert axes[1321, 'POL1'].provenance['object'] == 'calibration/run1321_POL1_fit'
    assert axes[1321, 'POL1'].provenance['h80'][0]['uuid']
    with uproot.update(h80) as source:
        source['extra'] = 'changed'
    with pytest.raises(ValueError, match='h80.*identity'):
        load_independent_axes(product, qa, manifest=manifest, h80_paths=[h80])
