"""Metadata gates for event-only consumers of compact transport."""
import json

import pytest
import uproot

from mc_simulation.geant4 import root_output


def mark_compact(path, *, summary_changes=None, metadata_changes=None, metadata=True):
    with uproot.open(path) as root:
        summary = json.loads(str(root['summary']))
    summary.update(hit_schema_version=3, storage_mode='compact',
                   hit_policy='compact_response_inputs_v1',
                   detector_steps=summary.get('detector_steps', 0), stored_detector_steps=0)
    summary.update(summary_changes or {})
    storage = dict(schema_version=1, mode='compact', bgo='sum_per_crystal_float64',
                   source_index='original_sensitive_step',
                   response_scope='current_response_no_step_quenching')
    storage.update(metadata_changes or {})
    with uproot.update(path) as root:
        del root['summary']
        root['summary'] = json.dumps(summary)
        if metadata:
            root['storage_metadata'] = json.dumps(storage)


def test_compact_summary_accepts_sparse_storage_without_reading_steps(tmp_path):
    path = tmp_path/'transport.root'
    with uproot.recreate(path) as root:
        root['summary'] = json.dumps(dict(hit_schema_version=2))
    mark_compact(path, summary_changes=dict(detector_steps=9, stored_detector_steps=2))
    with uproot.open(path) as root:
        summary = root_output.read_transport_summary(root)
    assert summary['detector_steps'] == 9
    assert summary['stored_detector_steps'] == 2


@pytest.mark.parametrize('summary_changes,metadata_changes,metadata', [
    ({'hit_schema_version': 4}, {}, True),
    ({'hit_schema_version': 3.0}, {}, True),
    ({'storage_mode': 'full'}, {}, True),
    ({'hit_policy': 'all_steps_in_sensitive_volumes_no_response_cuts'}, {}, True),
    ({'stored_detector_steps': -1}, {}, True),
    ({'stored_detector_steps': True}, {}, True),
    ({'stored_detector_steps': 0.0}, {}, True),
    ({'stored_detector_steps': 1}, {}, True),
    ({'detector_steps': False}, {}, True),
    ({}, {}, False),
    ({}, {'schema_version': True}, True),
    ({}, {'mode': 'full'}, True),
    ({}, {'bgo': 'sum_per_crystal_float32'}, True),
    ({}, {'source_index': 'stored_row'}, True),
    ({}, {'response_scope': 'step_quenching'}, True),
])
def test_compact_summary_rejects_incompatible_storage(tmp_path, summary_changes, metadata_changes, metadata):
    path = tmp_path/'transport.root'
    with uproot.recreate(path) as root:
        root['summary'] = json.dumps(dict(hit_schema_version=2))
    mark_compact(path, summary_changes=summary_changes, metadata_changes=metadata_changes, metadata=metadata)
    with uproot.open(path) as root, pytest.raises(ValueError, match='[Ss]torage|[Cc]ompact|schema'):
        root_output.read_transport_summary(root)


@pytest.mark.parametrize('mode', [None, 'full'])
def test_schema2_without_new_metadata_remains_readable(tmp_path, mode):
    path = tmp_path/'transport.root'
    summary = dict(hit_schema_version=2)
    if mode:
        summary['storage_mode'] = mode
    with uproot.recreate(path) as root:
        root['summary'] = json.dumps(summary)
    with uproot.open(path) as root:
        assert root_output.read_transport_summary(root) == summary
