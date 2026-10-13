"""Comparison invariants: weights, operating points and artifact round-trip."""
from dataclasses import replace

import numpy as np
import pytest

from bdt_training.tests.test_grouped_stage1 import identified_dataset


def profile_data(name):
    data = identified_dataset()
    data.rows.profile[:] = name
    bounds = (1.1, 1.5) if name == "uv" else (.9313, 1.1)
    return replace(data, metadata=replace(data.metadata, beam_profile=name,
                                         energy_min_gev=bounds[0], energy_max_gev=bounds[1]),
                   rows=replace(data.rows, origin_id=np.char.add(name + ":", data.rows.origin_id)))


def test_comparison_balances_profiles_and_preserves_baseline_splits():
    from scripts.compare_shared_bdt import comparison_datasets
    uv, vis = profile_data("uv"), profile_data("vis")
    vis.w[:] *= 100
    datasets = comparison_datasets(uv, vis)
    shared = datasets["shared"]
    for split in (0, 1, 2):
        mask = shared.rows.split == split
        for profile in ("uv", "vis"):
            assert shared.w[mask & (shared.rows.profile == profile)].sum() == pytest.approx(mask.sum() / 2)
    np.testing.assert_array_equal(datasets["uv"].rows.split, uv.rows.split)
    np.testing.assert_array_equal(datasets["vis"].rows.origin_id, vis.rows.origin_id)
    with pytest.raises(ValueError, match="identity"):
        comparison_datasets(replace(uv, rows=None), vis)


def test_comparison_rejects_cross_profile_leakage():
    from scripts.compare_shared_bdt import comparison_datasets
    uv, vis = profile_data("uv"), profile_data("vis")
    vis.rows.origin_id[36] = uv.rows.origin_id[0]
    with pytest.raises(ValueError, match="origin.*split"):
        comparison_datasets(uv, vis)


def test_weighted_metrics_and_equal_efficiency_threshold():
    from scripts.compare_shared_bdt import metrics, efficiency_threshold
    y = np.array([0, 0, 1, 1])
    score = np.array([.1, .7, .5, .9])
    weight = np.array([1., 3., 1., 3.])
    value = metrics(y, score, weight, .6)
    assert value["signal_efficiency"] == .75
    assert value["background_rejection"] == .25
    assert value["precision"] == .5
    assert value["auc"] == .8125
    assert efficiency_threshold(y, score, weight, target=.8) == .5
    assert metrics(np.zeros(4), score, weight, .6)["auc"] is None


def test_three_bundles_load_and_test_rows_never_enter_fit(tmp_path):
    from scripts.compare_shared_bdt import comparison_datasets, train_comparison
    from bdt_training.training.stage1_training import TrainingConfig
    from reconstruction.runtime.stage1_gate import Stage1Gate
    from graal_common.physics.beam_profiles import UV_PROFILE, VIS_PROFILE
    datasets = comparison_datasets(profile_data("uv"), profile_data("vis"))
    results = train_comparison(datasets, tmp_path, TrainingConfig(n_estimators=3, nthread=1, verbose=False))
    assert results["shared"].n_train == 144
    assert results["shared"].n_val == 48
    gate = Stage1Gate.load(tmp_path / "shared")
    gate.check_profile(UV_PROFILE)
    gate.check_profile(VIS_PROFILE)
    with pytest.raises(ValueError):
        Stage1Gate.load(tmp_path / "uv").check_profile(VIS_PROFILE)
    assert (tmp_path / "protocol.json").is_file()
    assert (tmp_path / "split_audit.json").is_file()
