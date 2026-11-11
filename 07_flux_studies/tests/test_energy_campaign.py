import json
from pathlib import Path

import numpy as np
import pytest

from calibration.run_manifest import RunRecord, write_manifest


def _config(tmp_path):
    import uproot
    manifest = tmp_path / 'manifest.csv'
    write_manifest([RunRecord(811, 'uv_a', 'P', 'UV', 'P_UV', 'manual', 'uv/run811.root')], manifest)
    flux, h80 = tmp_path / 'flux.root', tmp_path / 'h80.root'
    with uproot.recreate(flux) as output:
        for state in ('POL1', 'POL2'):
            output[f'run811_{state}'] = (np.ones(128), np.linspace(.8, 1.6, 129))
    with uproot.recreate(h80) as output:
        output['h80'] = dict(RunNumber=np.full(12, 811), Polarization=np.tile([1, 2], 6))
    quality = tmp_path / 'quality.json'
    from calibration.run_quality import DEFAULT_RUN_QUALITY_PATH
    quality.write_bytes(DEFAULT_RUN_QUALITY_PATH.read_bytes())
    return dict(inputs=dict(manifest=str(manifest), calibrated_flux=str(flux),
        run_quality=str(quality), h80=[str(h80)], reco={}), cohort_runs=[811],
        energy_edges=np.linspace(.5, 2., 65).tolist())


def test_inventory_is_statewise_authenticated_and_never_invents_cohort_events(tmp_path):
    from flux_studies.energy_campaign import run_inventory
    config = _config(tmp_path)
    destination = tmp_path / 'inventory'
    result = run_inventory(config, destination)
    assert result['counts']['measured_pol_pair_runs'] == [811]
    assert result['counts']['measured_pol_without_brem_runs'] == [811]
    assert result['counts']['selected_events'] is None
    assert result['production_adopted'] is False
    assert result['input_sha256']
    assert (destination / 'inventory.json').is_file()
    assert not (destination / 'recovered.root').exists()
    with pytest.raises(FileExistsError):
        run_inventory(config, destination)


def test_declared_input_hash_mismatch_blocks_reuse(tmp_path):
    from flux_studies.energy_campaign import load_campaign
    config = _config(tmp_path)
    config['input_sha256'] = {config['inputs']['calibrated_flux']: '0' * 64}
    with pytest.raises(ValueError, match='identity'):
        load_campaign(config)


def test_duplicate_cohort_runs_rejected_before_scanning(tmp_path):
    from flux_studies.energy_campaign import load_campaign
    config = _config(tmp_path)
    config['cohort_runs'] *= 2
    with pytest.raises(ValueError, match='cohort'):
        load_campaign(config)


def test_defective_measured_state_remains_present_for_overlay_protection():
    from flux_studies.energy_campaign import measured_states
    dataset = dict(diagnostic_records=[], run_quality={'excluded_runs': []}, inventory=[
        dict(run=811, state='POL1', measurement_status='invalid_values'),
        dict(run=811, state='POL2', measurement_status='missing_histogram')])
    states = measured_states(dataset, {811})
    assert states[811, 'POL1']['status'] == 'invalid_values'
    assert (811, 'POL2') not in states


def test_original_axis_control_uses_energy_bins_not_false_strip_indices():
    from flux_studies.energy_campaign import original_axis_control
    from observable_extraction.core.models import FluxExposure
    native = {(811, 17): FluxExposure(811, 17, 1.15, 1.2, .9, .2, .6, .55)}
    measured = {(811, 'POL1'): dict(calibration_edges=np.linspace(1., 1.6, 129))}
    rows = [dict(run=811, state='POL1', method='extra_trees_hybrid', truth=np.full(32, 4.8))]
    control, audit = original_axis_control(native, measured, rows, np.linspace(1., 1.6, 33))
    assert control[811, 17].flux_vertical == pytest.approx(1.2)
    assert control[811, 17].polarization_vertical == .6
    assert control[811, 17].energy_gev == 1.15
    assert audit[0]['projected_integral'] == pytest.approx(153.6)


def test_accepted_coverage_keeps_failed_replicas_and_remaps_dependencies():
    from flux_studies.energy_campaign import accepted_uncertainty
    keys = [dict(run=r, state='POL1', method='extra_trees_hybrid', period='p') for r in (1, 2)]
    values = np.ones((3, 2, 4))
    values[1, 1] = np.nan
    uncertainty = dict(keys=keys, draws=values, bootstrap_audit=[dict(replica=0, targets=[
        dict(prediction_index=0, donors=[10, 20]), dict(prediction_index=1, donors=[20, 30])])])
    decisions = dict(accepted_runs=[2], state_decisions=[dict(run=1, state='POL1', accepted=False),
                                                       dict(run=2, state='POL1', accepted=True)])
    selected = accepted_uncertainty(uncertainty, decisions)
    assert selected['keys'] == [keys[1]]
    assert selected['draws'].shape == (3, 1, 4)
    assert np.isnan(selected['draws'][1, 0]).all()
    assert selected['bootstrap_audit'][0]['targets'] == [dict(prediction_index=0, donors=[20, 30])]
