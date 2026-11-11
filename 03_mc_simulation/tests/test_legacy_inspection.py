import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
import uproot


@pytest.fixture
def inspector():
    path = Path(__file__).parents[1] / 'geant4/inspect_legacy.py'
    assert path.is_file(), 'legacy input inspection command is missing'
    spec = importlib.util.spec_from_file_location('inspect_legacy', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def root_control(path, runs, missing=None):
    columns = {name: np.zeros(len(runs), dtype=np.float32) for name in (
        'Dedx_track', 'Eclusc_track', 'Tof_trf', 'De_trf') if name != missing}
    columns['Idrun'] = np.asarray(runs, dtype=np.int32)
    with uproot.recreate(path) as output:
        output.mktree('h70', columns)


def test_control_inventory_reads_run_identity_and_observables(inspector, tmp_path):
    path = tmp_path / 'control.root'
    root_control(path, [1321, 1321, 1325])
    result = inspector.inspect_control(path)
    assert result['events_by_run'] == {1321: 2, 1325: 1}
    assert result['missing_branches'] == []
    assert len(result['sha256']) == 64


def test_missing_observable_never_becomes_ready_control(inspector, tmp_path):
    path = tmp_path / 'incomplete.root'
    root_control(path, [1321], missing='Dedx_track')
    result = inspector.inspect_control(path)
    assert result['missing_branches'] == ['Dedx_track']
    assert result['status'] == 'missing_observables'


def test_one_run_cannot_supply_independent_validation(inspector):
    result = inspector.propose_controls({1321: 100}, {1321}, set())
    assert result['tuning_runs'] == [1321]
    assert result['validation_runs'] == []
    assert result['status'] == 'needs_independent_runs'


def test_control_split_respects_policy_calibration_and_run_disjointness(inspector):
    result = inspector.propose_controls({1321: 10, 1322: 20, 1325: 30, 1326: 40},
                                       {1321, 1322, 1325}, {1322})
    assert result['tuning_runs'] == [1321]
    assert result['validation_runs'] == [1325]
    assert result['status'] == 'proposed_unvalidated'


def test_existing_output_refused_before_reading_inputs(inspector, tmp_path):
    sentinel = tmp_path / 'preserved'
    sentinel.write_text('keep')
    with pytest.raises(FileExistsError):
        inspector.write_inspection(tmp_path / 'absent', tmp_path / 'absent.csv',
                                   tmp_path / 'absent.json', [], tmp_path)
    assert sentinel.read_text() == 'keep'
