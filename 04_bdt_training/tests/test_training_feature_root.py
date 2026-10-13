"""Conservation and provenance contracts for training-feature diagnostics."""
from dataclasses import replace
import importlib
import json
from pathlib import Path

import numpy as np
import pytest

from bdt_training.dataset.stage1_dataset import (
    Stage1Dataset, Stage1DatasetMetadata, save_stage1_dataset,
)
from graal_common.physics.channels import HYPOTHESES
from graal_common.stage1.features import feature_names


def _reporting():
    # A missing implementation is an assertion failure during the initial RED run.
    assert importlib.util.find_spec('bdt_training.training.feature_reporting'), (
        'training-feature exporter is missing'
    )
    return importlib.import_module('bdt_training.training.feature_reporting')


def _dataset(profile='vis', hypothesis='eta_pi0'):
    X = np.zeros((6, 26), dtype=np.float32)
    X[:, 6] = [0, 1, 6, 2, 2, 2]
    X[:, 23] = [-2, -1, 1, 0, 2, np.nan]
    bounds = {'vis': (.9313, 1.1), 'uv': (1.1, 1.5), None: (None, None)}[profile]
    return Stage1Dataset(
        X, np.array([1, 1, 1, 0, 0, 0]), np.array([2., 3., 4., 5., 6., 7.]),
        Stage1DatasetMetadata(tuple(feature_names(HYPOTHESES[hypothesis])),
                              'eta_pi0', hypothesis, .5, True, profile, *bounds),
    )


def _save(tmp_path, dataset=None, name='features.npz'):
    path = tmp_path / name
    save_stage1_dataset(path, _dataset() if dataset is None else dataset)
    return path


def test_dictionary_covers_hypotheses_units_and_common_integer_bins():
    reporting = _reporting()
    for hypothesis in HYPOTHESES.values():
        specs = reporting.feature_definitions(hypothesis)
        assert [s.name for s in specs] == feature_names(hypothesis)
        assert len(specs) == 26
        assert len(set(s.name for s in specs)) == 26
        assert specs[6].kind == 'discrete'
        np.testing.assert_array_equal(specs[6].edges, np.arange(-.5, 7., 1.))
        assert specs[18].unit == 'rad'
        assert specs[23].unit == specs[24].unit == specs[25].unit == '1'
        assert 'beam + target - proton' in specs[9].formula
        assert 'cos' in specs[25].formula
        assert all(s.formula and s.family and s.domain for s in specs)


def test_root_round_trip_conserves_yield_sumw2_entries_flows_and_nan(tmp_path):
    reporting = _reporting()
    ROOT = pytest.importorskip('ROOT')
    source = _save(tmp_path)
    out = tmp_path / 'diagnostics'
    reporting.export_training_features([source], out)
    metadata = json.loads((out / 'training_features.json').read_text())
    assert len(metadata['features']) == 26
    assert metadata['inputs'][0]['sha256']
    assert metadata['inputs'][0]['shape'] == [6, 26]
    assert metadata['inputs'][0]['training_seed'] is None
    assert metadata['inputs'][0]['photon_loss'] is None
    assert metadata['inputs'][0]['split_status'] == 'unavailable; full dataset only'
    assert metadata['inputs'][0]['channel_status'] == 'unavailable; binary classes only'
    assert (out / 'training_features.pdf').read_bytes().startswith(b'%PDF-')
    with ROOT.TFile.Open(str(out / 'training_features.root')) as root:
        embedded = json.loads(root.Get('training_features_metadata').GetTitle())
        assert embedded == metadata
        h = root.Get('vis/all/signal/proton_costheta/weighted_yield')
        n = h.GetNbinsX()
        assert h.GetEntries() == 3
        assert h.Integral(0, n + 1) == pytest.approx(9)
        assert sum(h.GetBinError(i)**2 for i in range(n + 2)) == pytest.approx(29)
        assert h.GetBinContent(0) == 2
        assert h.GetBinContent(n + 1) == 0  # +1 is physical, not overflow
        shape = root.Get('vis/all/signal/proton_costheta/weighted_shape')
        assert shape.Integral(0, n + 1) == pytest.approx(1)
        assert shape.GetBinError(0) == pytest.approx(2/9)
        u = root.Get('vis/all/signal/proton_costheta/unweighted_yield')
        assert u.Integral(0, n + 1) == 3
        assert sum(u.GetBinError(i)**2 for i in range(n + 2)) == pytest.approx(3)
        b = root.Get('vis/all/background/proton_costheta/weighted_yield')
        assert b.GetEntries() == 2
        assert b.Integral(0, n + 1) == 11
        assert b.GetBinContent(n + 1) == 6
        audit = metadata['histograms']['vis/all/background/proton_costheta']['weighted']
        assert audit['nan'] == {'entries': 1, 'sumw': 7., 'sumw2': 49.}
        assert audit['total'] == {'entries': 3, 'sumw': 18., 'sumw2': 110.}
        constant = root.Get('vis/all/signal/missing_mass/weighted_yield')
        assert constant.GetBinContent(1) == 9
        assert constant.GetEntries() == 3
        count = root.Get('vis/all/signal/n_pairs_near_pi0/weighted_yield')
        assert count.GetNbinsX() == 7
        assert count.GetBinCenter(1) == 0
        assert count.GetBinCenter(7) == 6
        assert count.GetBinContent(7) == 4


def test_profiles_use_identical_edges_and_unknown_profile_is_not_guessed(tmp_path):
    reporting = _reporting()
    uv = _save(tmp_path, _dataset('uv'), 'uv.npz')
    vis = _save(tmp_path, _dataset('vis'), 'vis.npz')
    legacy = _save(tmp_path, _dataset(None), 'legacy_vis.npz')
    report = reporting.build_feature_report([uv, vis, legacy])
    assert set(report.histograms) == {'uv', 'vis', 'unknown'}
    for profile in report.histograms:
        hist = report.histograms[profile]['signal'][6]['weighted']
        np.testing.assert_array_equal(hist.edges, np.arange(-.5, 7., 1.))


@pytest.mark.parametrize('mutation,match', [
    ('order', 'feature names/order'), ('width', '26 feature'),
    ('weights', 'weights'), ('labels', 'labels'), ('inf', 'infinite'),
    ('nonnumeric', 'numeric'), ('fractional_counter', 'integer'),
])
def test_invalid_input_fails_without_publishing_outputs(tmp_path, mutation, match):
    reporting = _reporting()
    source = _save(tmp_path)
    with np.load(source) as stored:
        values = {k: stored[k] for k in stored.files}
    if mutation == 'order':
        values['feature_names'] = values['feature_names'][::-1]
    elif mutation == 'width':
        values['X'] = values['X'][:, :-1]
    elif mutation == 'weights':
        values['w'][0] = np.nan
    elif mutation == 'labels':
        values['y'][0] = 3
    elif mutation == 'inf':
        values['X'][0, 0] = np.inf
    elif mutation == 'nonnumeric':
        values['X'] = values['X'].astype(str)
    elif mutation == 'fractional_counter':
        values['X'][0, 6] = .5
    np.savez(source, **values)
    out = tmp_path / 'invalid'
    with pytest.raises(ValueError, match=match):
        reporting.export_training_features([source], out)
    assert not (out / 'training_features.root').exists()


def test_missing_duplicate_or_mixed_hypothesis_inputs_are_rejected(tmp_path):
    reporting = _reporting()
    with pytest.raises(FileNotFoundError):
        reporting.build_feature_report([tmp_path / 'absent.npz'])
    source = _save(tmp_path)
    with pytest.raises(ValueError, match='profile'):
        reporting.build_feature_report([source, source])
    other = _save(tmp_path, _dataset('uv', '2pi0'), 'two_pi0.npz')
    with pytest.raises(ValueError, match='hypothesis'):
        reporting.build_feature_report([source, other])


def test_zero_weight_shape_is_explicitly_undefined_and_signed_yields_survive(tmp_path):
    reporting = _reporting()
    dataset = _dataset()
    source = _save(tmp_path, replace(dataset, w=np.array([1., -1., 0., 0., 0., 0.])))
    report = reporting.build_feature_report([source])
    h = report.histograms['vis']['signal'][0]['weighted']
    assert h.sumw.sum() == 0
    assert h.sumw2.sum() == 2
    assert h.entries == 3
    assert h.normalization is None


def test_export_never_overwrites_existing_artifact(tmp_path):
    reporting = _reporting()
    source = _save(tmp_path)
    out = tmp_path / 'occupied'
    out.mkdir()
    target = out / 'training_features.root'
    target.write_bytes(b'preserve')
    with pytest.raises(FileExistsError):
        reporting.export_training_features([source], out)
    assert target.read_bytes() == b'preserve'


def test_training_opt_in_exports_without_changing_model_or_threshold(tmp_path):
    pytest.importorskip('ROOT')
    from bdt_training.train_bdt_stage1 import train
    import inspect
    assert 'feature_diagnostics_dir' in inspect.signature(train).parameters
    dataset = _dataset()
    dataset = replace(dataset, X=np.tile(dataset.X, (8, 1)),
                      y=np.tile(dataset.y, 8), w=np.tile(dataset.w, 8))
    source = _save(tmp_path, dataset)
    common = dict(features_path=str(source), n_estimators=2, nthread=1, verbose=False)
    train(**common, out_dir=str(tmp_path / 'plain'))
    train(**common, out_dir=str(tmp_path / 'with_diagnostics'),
          feature_diagnostics_dir=str(tmp_path / 'report'))
    for name in ('bdt_stage1.json', 'stage1_threshold.txt', 'stage1_provenance.json'):
        assert (tmp_path / 'plain' / name).read_bytes() == (tmp_path / 'with_diagnostics' / name).read_bytes()
    metadata = json.loads((tmp_path / 'report' / 'training_features.json').read_text())
    assert metadata['inputs'][0]['training_seed'] == 42
    assert metadata['inputs'][0]['split_status'] == 'unavailable; full dataset only'
    assert not (tmp_path / 'with_diagnostics' / 'training_features.root').exists()


def test_training_diagnostics_cannot_share_bundle_directory(tmp_path):
    from bdt_training.train_bdt_stage1 import train
    import inspect
    assert 'feature_diagnostics_dir' in inspect.signature(train).parameters
    source = _save(tmp_path)
    with pytest.raises(ValueError, match='separate'):
        train(str(source), out_dir=str(tmp_path / 'model'),
              feature_diagnostics_dir=str(tmp_path / 'model'))
    assert not (tmp_path / 'model').exists()


def test_export_metadata_does_not_require_git_executable(tmp_path, monkeypatch):
    reporting = _reporting()
    source = _save(tmp_path)
    monkeypatch.setenv('PATH', '')
    report = reporting.build_feature_report([source])
    assert report.metadata['code_revision'] is None
    assert report.metadata['source_sha256']


def test_source_hashes_follow_installed_modules_not_repository_layout(tmp_path, monkeypatch):
    reporting = _reporting()
    source = _save(tmp_path)
    installed = tmp_path / 'site-packages' / 'bdt_training' / 'training' / 'feature_reporting.py'
    installed.parent.mkdir(parents=True)
    installed.write_bytes(Path(reporting.__file__).read_bytes())
    monkeypatch.setattr(reporting, '__file__', str(installed))
    report = reporting.build_feature_report([source])
    assert report.metadata['source_sha256']['bdt_training.training.feature_reporting']
    assert report.metadata['source_sha256']['graal_common.stage1.features']


@pytest.mark.parametrize('persist_split', [False, True])
def test_identified_input_reports_persisted_row_provenance(tmp_path, persist_split):
    from bdt_training.dataset.stage1_dataset import Stage1Rows

    dataset = _dataset()
    rows = Stage1Rows(
        origin_id=np.array([f'source:{i}' for i in range(6)]),
        channel=np.where(dataset.y == 1, 'eta_pi0', 'pi0pi0'),
        profile=np.full(6, 'vis'),
        detector_variant=np.full(6, 'LossParams=stored;seed=17'),
        split=np.tile([0, 1, 2], 2) if persist_split else None,
    )
    source = _save(tmp_path, replace(dataset, X=np.nan_to_num(dataset.X), rows=rows))

    metadata = _reporting().build_feature_report([source]).metadata['inputs'][0]

    assert metadata['channel_status'] == 'persisted per row; full dataset histograms only'
    assert metadata['channels'] == ['eta_pi0', 'pi0pi0']
    assert metadata['detector_variants'] == ['LossParams=stored;seed=17']
    assert metadata['photon_loss_status'] == 'detector variants persisted verbatim; parameters not inferred'
    assert metadata['photon_loss'] is None
    if persist_split:
        assert metadata['split_status'] == 'persisted and audited; full dataset histograms only'
        assert metadata['split_audit']['rows'] == {'train': 2, 'validation': 2, 'test': 2}
        assert metadata['split_audit']['unique_origins'] == 6
    else:
        assert metadata['split_status'] == 'not persisted; full dataset histograms only'
        assert metadata['split_audit'] is None
