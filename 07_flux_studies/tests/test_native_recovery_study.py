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


def test_content_bound_counts_exact_cohort_and_relocation_without_entry_scan(tmp_path, monkeypatch):
    from calibration.calibration_qa import sha256_file
    from pathlib import Path
    import shutil
    path, data = cache_file(tmp_path)
    root = Path(data['sources'][0]['path'])
    data['sources'][0].update(root='checkout', path=root.name, sha256=sha256_file(root))
    path.write_text(json.dumps(data))
    # Loader may read ROOT headers, but must not scan entry arrays.
    monkeypatch.setattr(uproot.behaviors.TBranch.HasBranches, 'iterate', lambda *a, **kw: pytest.fail('entry rescan'))
    monkeypatch.setattr(uproot.behaviors.TBranch.HasBranches, 'arrays', lambda *a, **kw: pytest.fail('entry rescan'))
    counts, _ = load_cached_counts(path, expected_paths=[root], checkout=tmp_path, require_content=True)
    assert counts == {(1, 'POL1'): 2}
    relocated = tmp_path / 'moved'; relocated.mkdir()
    shutil.copyfile(root, relocated / root.name)
    assert load_cached_counts(path, expected_paths=[relocated / root.name], checkout=relocated, require_content=True)[0] == counts
    with pytest.raises(ValueError, match='cohort'):
        load_cached_counts(path, expected_paths=[], checkout=tmp_path, require_content=True)
    with root.open('ab') as stream:
        stream.write(b'changed')
    with pytest.raises(ValueError, match='content'):
        load_cached_counts(path, expected_paths=[root], checkout=tmp_path, require_content=True)


def test_common_counts_require_content_identity(tmp_path):
    path, data = cache_file(tmp_path)
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='content identity'):
        load_cached_counts(path, require_content=True)


def test_portable_count_provenance_roundtrips_to_campaign_cache(tmp_path):
    from calibration.calibration_qa import sha256_file
    from pathlib import Path
    path, data = cache_file(tmp_path)
    root = Path(data['sources'][0]['path'])
    data['sources'][0].update(root='checkout', path=root.name, sha256=sha256_file(root))
    path.write_text(json.dumps(data))
    counts, sources = load_cached_counts(path, expected_paths=[root], checkout=tmp_path, require_content=True)
    campaign = tmp_path / 'campaign.json'
    campaign.write_text(json.dumps(dict(counts=data['counts'], sources=sources)))
    assert load_cached_counts(campaign, expected_paths=[root], require_content=True)[0] == counts


@pytest.mark.parametrize('kind', ['file', 'directory'])
def test_portable_counts_follow_external_data_links_with_exact_cohort(tmp_path, monkeypatch, kind):
    from calibration.calibration_qa import sha256_file
    from pathlib import Path
    path, data = cache_file(tmp_path)
    source = Path(data['sources'][0]['path'])
    checkout = tmp_path / 'checkout'
    (checkout / 'data').mkdir(parents=True)
    if kind == 'file':
        relative = 'data/h80.root'
        (checkout / relative).symlink_to(source)
    else:
        relative = 'data/farm/h80.root'
        (checkout / 'data/farm').symlink_to(tmp_path, target_is_directory=True)
    original = source.read_bytes()
    data['sources'][0].update(root='checkout', path=relative, sha256=sha256_file(source))
    path.write_text(json.dumps(data))
    monkeypatch.setattr(uproot.behaviors.TBranch.HasBranches, 'arrays', lambda *a, **kw: pytest.fail('entry rescan'))
    counts, sources = load_cached_counts(path, expected_paths=[checkout / relative], checkout=checkout, require_content=True)
    assert counts == {(1, 'POL1'): 2}
    assert sources[0]['path'] == str(source)
    assert sources[0]['reference'] == dict(root='checkout', path=relative)
    with pytest.raises(ValueError, match='cohort mismatch'):
        load_cached_counts(path, expected_paths=[], checkout=checkout, require_content=True)
    data['sources'][0]['sha256'] = '0' * 64
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='content mismatch'):
        load_cached_counts(path, expected_paths=[source], checkout=checkout, require_content=True)
    assert source.read_bytes() == original
