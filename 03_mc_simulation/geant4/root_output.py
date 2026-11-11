"""Read the compressed ROOT transport contract without loading CERN ROOT."""
import json
from pathlib import Path

import uproot


def read_text(path, key):
    with uproot.open(Path(path)) as root:
        return str(root[key])


def read_json(path, key="summary"):
    return json.loads(read_text(path, key))


def read_transport_summary(root):
    """Validate storage semantics for event-only consumers, without reading steps.

    Detector response readers separately validate stored rows and per-event
    counts. This gate preserves schema 2 inputs and requires the complete
    compact contract before event ledgers accept schema 3.
    """
    from mc_simulation.geant4.trigger import _strict_json

    summary = _strict_json(root, 'summary')
    version = summary.get('hit_schema_version')
    if type(version) is not int or version not in (2, 3):
        raise ValueError('Unsupported transport hit schema')
    if version == 2:
        if summary.get('storage_mode', 'full') != 'full':
            raise ValueError('Schema 2 requires full storage mode')
        return summary
    if (summary.get('storage_mode') != 'compact' or
            summary.get('hit_policy') != 'compact_response_inputs_v1'):
        raise ValueError('Invalid compact storage contract')
    for key in ('detector_steps', 'stored_detector_steps'):
        if type(summary.get(key)) is not int or not 0 <= summary[key] <= 2**64-1:
            raise ValueError(f'Invalid compact storage count: {key}')
    if summary['stored_detector_steps'] > summary['detector_steps']:
        raise ValueError('Compact stored count exceeds original detector steps')
    metadata = _strict_json(root, 'storage_metadata')
    expected = dict(mode='compact', bgo='sum_per_crystal_float64',
                    source_index='original_sensitive_step',
                    response_scope='current_response_no_step_quenching')
    if (type(metadata.get('schema_version')) is not int or metadata['schema_version'] != 1
            or any(metadata.get(key) != value for key, value in expected.items())):
        raise ValueError('Unsupported compact storage metadata')
    return summary


def read_table(path, name):
    """Small diagnostic tables; use uproot.iterate for large step datasets."""
    with uproot.open(Path(path)) as root:
        columns = root[name].arrays(library="np")
    return [{key: value.item() if hasattr(value, "item") else value
             for key, value in zip(columns, row)} for row in zip(*columns.values())]
