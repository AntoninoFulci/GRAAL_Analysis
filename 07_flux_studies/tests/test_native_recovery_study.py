"""Provenance boundary for reuse of previously scanned inclusive counts."""
import json
import numpy as np
import pytest
import uproot

from flux_studies.study_native_recovery import load_cached_counts


def cache_file(tmp_path):
    root = tmp_path / 'h80.root'
    with uproot.recreate(root) as f:
        f['h80'] = {'RunNumber': np.array([1, 1]), 'Polarization': np.array([1, 1])}
    with uproot.open(root) as f:
        source = dict(path=str(root), uuid=str(f.file.uuid), entries=2)
    data = dict(counts=[dict(run=1, state='POL1', count=2)], sources=[source])
    return tmp_path / 'cache.json', data


@pytest.mark.parametrize('defect', ['uuid', 'entries', 'sum', 'duplicate', 'fractional', 'state'])
def test_cached_counts_reject_invalid_provenance_or_content(tmp_path, defect):
    path, data = cache_file(tmp_path)
    if defect in ('uuid', 'entries'):
        data['sources'][0][defect] = 'wrong' if defect == 'uuid' else 3
    elif defect == 'sum':
        data['counts'][0]['count'] = 3
    elif defect == 'duplicate':
        data['counts'].append(data['counts'][0].copy())
    elif defect == 'fractional':
        data['counts'][0]['count'] = 2.5
    else:
        data['counts'][0]['state'] = 'OTHER'
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        load_cached_counts(path)


def test_cached_counts_reuse_verified_complete_inclusive_sample(tmp_path):
    path, data = cache_file(tmp_path)
    path.write_text(json.dumps(data))
    counts, sources = load_cached_counts(path)
    assert counts == {(1, 'POL1'): 2}
    assert sources == data['sources']
