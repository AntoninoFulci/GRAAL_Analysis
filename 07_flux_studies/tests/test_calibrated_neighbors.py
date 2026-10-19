"""Scientific invariants for the calibrated-neighbor pilot."""
from pathlib import Path

import numpy as np
import pytest


def test_rebin_preserves_fractional_bin_counts():
    from flux_studies.calibrated_data import rebin_counts
    got = rebin_counts([10., 30.], [0., 1., 3.], [0., .5, 2., 3.])
    np.testing.assert_allclose(got, [5., 20., 15.])
    with pytest.raises(ValueError, match='range'):
        rebin_counts([10., 30.], [0., 1., 3.], [.5, 2.])
    with pytest.raises(ValueError):
        rebin_counts([-1.], [0., 1.], [0., 1.])


def test_h80_counts_all_events_and_rejects_duplicate_coverage(tmp_path):
    import uproot
    from flux_studies.calibrated_data import count_h80
    path = tmp_path / 'events.root'
    with uproot.recreate(path) as f:
        f['h80'] = {'RunNumber': np.array([10, 10, 10, 11]),
                    'Polarization': np.array([1, 1, 2, 0])}
    counts, sources = count_h80([path])
    assert counts == {(10, 'POL1'): 2, (10, 'POL2'): 1, (11, 'BREM'): 1}
    assert sources[0]['entries'] == 4
    with pytest.raises(ValueError, match='duplicate'):
        count_h80([path, path])


def records(n=60):
    result = []
    shape = np.linspace(1., 2., 128)
    for run in range(1, n + 1):
        for state in ('POL1', 'POL2', 'BREM'):
            count = 100 + run * 3
            result.append(dict(run=run, state=state, period='p', group=('p', 'P', 'UV', state),
                               position=15. * run, count=count,
                               values=shape * (1. + .002 * run) * count))
    return result


def test_neighbor_interpolation_uses_target_count_but_not_target_flux():
    from flux_studies.neighbor_validation import neighbor_example
    rows = records(5)[::3]
    example = neighbor_example(rows[2], [rows[0], rows[4]])
    np.testing.assert_allclose(example['linear'], rows[2]['values'], rtol=1e-12)
    changed = {**rows[2], 'values': rows[2]['values'] * 50}
    second = neighbor_example(changed, [rows[0], rows[4]])
    np.testing.assert_array_equal(example['features'], second['features'])
    np.testing.assert_array_equal(example['linear'], second['linear'])
    assert example['donors'] == [1, 5]
    assert neighbor_example(rows[0], [rows[4]]) is None


def test_split_is_run_disjoint_and_keeps_blocks_together():
    from flux_studies.neighbor_validation import split_runs
    roles, blocks = split_runs(range(1, 61), block_size=3, seed=42)
    assert set(roles.values()) == {'train', 'validation', 'test'}
    for block in set(blocks.values()):
        assert len({roles[r] for r in roles if blocks[r] == block}) == 1
    assert (roles, blocks) == split_runs(range(1, 61), block_size=3, seed=42)


def test_final_test_truth_cannot_change_predictions_or_intervals():
    from flux_studies.neighbor_validation import evaluate_neighbors, split_runs
    rows = records(60)
    roles, _ = split_runs(range(1, 61), block_size=3, seed=42)
    first = evaluate_neighbors(rows, block_size=3, seed=42)
    modified = [{**r, 'values': r['values'] * (20 if roles[r['run']] == 'test' else 1)} for r in rows]
    second = evaluate_neighbors(modified, block_size=3, seed=42)
    assert first['predictions']
    for a, b in zip(first['predictions'], second['predictions'], strict=True):
        np.testing.assert_allclose(a['estimate'], b['estimate'])
        if a['lower95'] is not None:
            np.testing.assert_allclose(a['lower95'], b['lower95'])
        assert all(roles[d] == 'train' for d in a['donors'])
        assert a['run'] not in a['donors']
    for fit in first['fits']:
        for check in fit['training_examples']:
            assert all(check['block'] != b for b in check['donor_blocks'])


def test_zero_truth_shape_is_not_invented():
    from flux_studies.neighbor_validation import score_prediction
    score = score_prediction(np.zeros(128), np.ones(128))
    assert score['shape_l1'] is None
    assert score['relative_integral_error'] is None


def test_inner_selection_uses_all_three_blocked_folds():
    from flux_studies.neighbor_validation import _choose_alpha
    rows = records(60)[::3]
    blocks = {r['run']: (r['run'] - 1) // 3 for r in rows}
    alpha, curve = _choose_alpha(rows, blocks)
    assert alpha is not None
    assert all(len(item.get('fold_counts', {})) == 3 for item in curve)


def test_cli_detects_input_change_during_computation(tmp_path, monkeypatch):
    from flux_studies import study_calibrated_neighbors as cli
    source = tmp_path / 'source'
    source.write_text('original input')
    monkeypatch.setattr(cli, 'count_h80', lambda paths: ({}, []))
    monkeypatch.setattr(cli, 'load_calibrated_dataset', lambda *args: dict(records=[], exclusions=[], energy_edges=np.linspace(.5, 2, 129)))
    def altered(*args, **kwargs):
        source.write_text('changed during computation')
        return dict(predictions=[], exclusions=[], fits=[], splits={}, block_size=1, status='insufficient_data')
    monkeypatch.setattr(cli, 'evaluate_neighbors', altered)
    monkeypatch.setattr(cli, '_write_benchmark', lambda *args, **kwargs: None, raising=False)
    monkeypatch.setattr('flux_studies.neighbor_plots.plot_benchmark', lambda *args: None)
    output = tmp_path / 'output'
    result = cli.main(['--manifest', str(source), '--calibrated-flux', str(source),
                       '--h80', str(source), '--output-dir', str(output), '--block-size', '1'])
    assert result == 1
    assert not output.exists()


def test_publication_writes_every_test_overlay_and_preserves_input(tmp_path):
    from flux_studies.neighbor_validation import evaluate_neighbors
    from flux_studies.study_calibrated_neighbors import publish_benchmark
    from flux_studies.calibrated_data import ENERGY_EDGES
    rows = [r for r in records(30) if r['state'] == 'POL1']
    study = evaluate_neighbors(rows, block_size=1, seed=42)
    source = tmp_path / 'input.txt'
    source.write_text('measured inputs')
    output = tmp_path / 'out'
    publish_benchmark(output, dict(records=rows, exclusions=[], energy_edges=ENERGY_EDGES),
                      [study], sources=[], inputs=[source])
    assert source.read_text() == 'measured inputs'
    assert (output / 'summary.json').is_file()
    assert (output / 'block_1' / 'spectra.npz').is_file()
    assert (output / 'block_1' / 'diagnostics.pdf').is_file()
    import json
    index = json.loads((output / 'block_1' / 'overlay_index.json').read_text())
    expected = {p['run'] for p in study['predictions'] if p['role'] == 'test'}
    assert {p['run'] for p in index} == expected
    assert all((output / 'block_1' / p['atlas']).is_file() for p in index)
    with pytest.raises(FileExistsError):
        publish_benchmark(output, dict(records=rows, exclusions=[], energy_edges=ENERGY_EDGES),
                          [study], sources=[], inputs=[source])
