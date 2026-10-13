"""Origin grouping, persistence and a genuinely untouched test partition."""
from dataclasses import replace

import numpy as np
import pytest

from bdt_training.dataset import stage1_dataset as storage
from bdt_training.training.stage1_training import TrainingConfig, fit_stage1
from graal_common.stage1.features import FEATURE_NAMES_S1


def identified_dataset():
    rng = np.random.default_rng(31)
    n = 120
    y = np.repeat([0, 1], n // 2)
    X = rng.normal(size=(n, 26)).astype(np.float32)
    X[:, 0] += y * 2
    rows = storage.Stage1Rows(
        origin_id=np.array([f"source:{i}" for i in range(n)]),
        channel=np.where(y == 1, "eta_pi0", "pi0pi0"),
        profile=np.tile(["uv", "vis"], n // 2),
        detector_variant=np.full(n, "loss-v1"),
        split=np.tile(np.repeat([0, 1, 2], [36, 12, 12]), 2),
    )
    return storage.Stage1Dataset(
        X, y, np.ones(n),
        storage.Stage1DatasetMetadata(tuple(FEATURE_NAMES_S1), "eta_pi0", "eta_pi0", .5, True),
        rows=rows,
    )


def test_grouped_split_keeps_profile_and_detector_copies_together():
    from bdt_training.dataset.grouped_split import assign_group_splits, audit_group_splits
    data = identified_dataset()
    rows = data.rows
    origins = np.tile(rows.origin_id, 3)
    channels = np.tile(rows.channel, 3)
    profiles = np.concatenate([rows.profile, np.full(120, "uv"), np.full(120, "vis")])
    split = assign_group_splits(origins, channels, profiles, seed=7)
    np.testing.assert_array_equal(split[:120], split[120:240])
    np.testing.assert_array_equal(split[:120], split[240:])
    np.testing.assert_array_equal(split, assign_group_splits(origins, channels, profiles, seed=7))
    assert set(split) == {0, 1, 2}
    audit = audit_group_splits(origins, split)
    assert audit["intersections"] == {"train_validation": 0, "train_test": 0, "validation_test": 0}
    assert audit["unique_origins"] == 120
    order = np.random.default_rng(8).permutation(len(split))
    np.testing.assert_array_equal(assign_group_splits(origins[order], channels[order], profiles[order], seed=7), split[order])


def test_persistence_retains_origin_and_splits_and_rejects_leakage(tmp_path):
    data = identified_dataset()
    path = tmp_path / "features.npz"
    storage.save_stage1_dataset(path, data)
    restored = storage.load_stage1_dataset(path)
    for key in ("origin_id", "channel", "profile", "detector_variant", "split"):
        np.testing.assert_array_equal(getattr(restored.rows, key), getattr(data.rows, key))
    data.rows.origin_id[36] = data.rows.origin_id[0]
    with pytest.raises(ValueError, match="origin.*split"):
        storage.save_stage1_dataset(path, data)


def test_grouping_rejects_inconsistent_channel_and_small_strata():
    from bdt_training.dataset.grouped_split import assign_group_splits
    with pytest.raises(ValueError, match="channel"):
        assign_group_splits(np.array(["same", "same"]), np.array(["eta_pi0", "pi0pi0"]), np.array(["uv", "vis"]))
    with pytest.raises(ValueError, match="insufficient.*groups"):
        assign_group_splits(np.array(["a", "b"]), np.array(["eta_pi0"] * 2), np.array(["uv"] * 2))


def test_changing_test_data_does_not_change_fit_or_threshold():
    data = identified_dataset()
    cfg = TrainingConfig(n_estimators=6, max_depth=2, nthread=1, verbose=False)
    first = fit_stage1(data, cfg)
    changed = replace(data, X=data.X.copy(), w=data.w.copy())
    test = data.rows.split == 2
    changed.X[test] = 1000
    changed.w[test] = 100000
    second = fit_stage1(changed, cfg)
    assert first.n_train == 72
    assert first.n_val == 24
    assert first.threshold == second.threshold
    np.testing.assert_array_equal(first.scores_val, second.scores_val)


@pytest.mark.parametrize("bad", [-1, np.nan, np.inf])
def test_identified_dataset_rejects_invalid_weights(tmp_path, bad):
    data = identified_dataset()
    data.w[0] = bad
    with pytest.raises(ValueError, match="weights"):
        storage.save_stage1_dataset(tmp_path / "bad.npz", data)


def test_reweight_reference_is_frozen_against_evaluation_distribution():
    from bdt_training.beam_spectrum import BeamSpectrum, reweight
    spectrum = BeamSpectrum(np.array([0., 1., 2.]), np.array([.5, .5]))
    reference = np.array([.2, .3, .4, 1.2])
    observed = np.array([.5, 1.5])
    weights = reweight(observed, spectrum, min_mc_per_bin=1, reference_E=reference)
    np.testing.assert_allclose(weights, [2/3, 2])
    enlarged = np.concatenate([observed, np.full(100, 1.5)])
    np.testing.assert_array_equal(reweight(enlarged, spectrum, min_mc_per_bin=1, reference_E=reference)[:2], weights)


def test_origin_cannot_change_background_channel_within_same_split(tmp_path):
    data = identified_dataset()
    data.rows.origin_id[1] = data.rows.origin_id[0]
    data.rows.channel[1] = "3pi0"
    with pytest.raises(ValueError, match="origin.*channel"):
        storage.save_stage1_dataset(tmp_path / "bad.npz", data)
