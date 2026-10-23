import importlib
import numpy as np
import pytest


def test_reserves_strips_and_topologies_deterministically():
    sample = importlib.import_module('scripts.prepare_test_sample')
    strips = np.tile([1, 2, 3, 4, 128, 8, 8, 8, 8, 8], 3)
    states = np.repeat([0, 1, 2], 10)
    chosen = sample.choose_entries('a' * 64, strips, states, np.array([9, 19, 29]), 24)
    assert set([9, 19, 29]) <= set(chosen)
    for state in [0, 1, 2]:
        kept = set(strips[chosen[states[chosen] == state]])
        assert {1, 128} <= kept and len(kept) >= 5
    assert np.array_equal(chosen, sample.choose_entries('a' * 64, strips, states, np.array([9, 19, 29]), 24))


def test_incomplete_coverage_is_rejected():
    sample = importlib.import_module('scripts.prepare_test_sample')
    with pytest.raises(ValueError, match='coverage'):
        sample.choose_entries('a' * 64, np.tile([1, 2, 3, 4, 5], 3), np.repeat([0, 1, 2], 5), np.array([], dtype=int), 15)


def test_failed_sample_publication_preserves_inputs_and_cleans_staging(tmp_path, monkeypatch):
    sample = importlib.import_module('scripts.prepare_test_sample')
    uv = tmp_path / 'uv.root'; vis = tmp_path / 'vis.root'
    uv.write_bytes(b'original UV'); vis.write_bytes(b'original VIS')
    strips = np.tile([1, 2, 3, 4, 128], 3)
    monkeypatch.setattr(sample, 'read_cohort', lambda *_: (strips, np.repeat([0, 1, 2], 5), np.array([], dtype=int), 15))
    def fail(*_): raise RuntimeError('clone failure')
    monkeypatch.setattr(sample, 'clone_sample', fail)
    with pytest.raises(RuntimeError, match='clone failure'):
        sample.prepare(uv, vis, tmp_path / 'sample')
    assert uv.read_bytes() == b'original UV' and vis.read_bytes() == b'original VIS'
    assert not (tmp_path / 'sample').exists()
    assert not list(tmp_path.glob('.sample-*'))


def test_sample_refuses_existing_destination(tmp_path):
    sample = importlib.import_module('scripts.prepare_test_sample')
    destination = tmp_path / 'sample'; destination.mkdir()
    with pytest.raises(FileExistsError):
        sample.prepare(tmp_path / 'uv', tmp_path / 'vis', destination)
