"""Channel workers preserve seeded samples, ordering and dataset provenance."""
from dataclasses import fields
from pathlib import Path
import sys

import numpy as np
import pytest
import uproot

from bdt_training import build_background_features as builder
from bdt_training.beam_spectrum import BeamSpectrum
from bdt_training.dataset.mc_samples import build_channel_features
from bdt_training.dataset.stage1_dataset import load_stage1_dataset
from bdt_training.photon_loss import LossParams
from graal_common.physics.channels import ETA_PI0_HYP, get_channel


@pytest.fixture(scope="module")
def mc_inputs(tmp_path_factory):
    ROOT = pytest.importorskip("ROOT")
    directory = tmp_path_factory.mktemp("parallel-feature-mc")
    generators = Path(__file__).resolve().parents[2] / "03_mc_simulation/generators"
    for name, seed in (("eta_pi0", 71), ("pi0pi0", 72)):
        macro = generators / f"generate_{name}_dataset.C"
        if not hasattr(ROOT, macro.stem):
            assert ROOT.gROOT.LoadMacro(str(macro)) == 0
        getattr(ROOT, macro.stem)(5000, .98, 1.08, str(directory / f"{name}_mc.root"), seed)
    target = BeamSpectrum(np.array([.9313, 1.1]), np.array([1 / (1.1 - .9313)]))
    return directory, target


def _build(directory, target, *, workers=1, seed_policy="channel-v1", names=("eta_pi0", "pi0pi0")):
    assert hasattr(builder, "build_channel_samples"), "parallel channel preparation is missing"
    return builder.build_channel_samples(
        [get_channel(name) for name in names], directory, ETA_PI0_HYP,
        LossParams(), target, loss_seed=42, workers=workers, seed_policy=seed_policy,
    )


def _assert_sample_equal(left, right):
    for field in fields(left):
        expected, actual = getattr(left, field.name), getattr(right, field.name)
        if isinstance(expected, np.ndarray):
            np.testing.assert_array_equal(actual, expected, err_msg=field.name)
        else:
            assert actual == expected


def test_channel_seed_samples_identical_in_serial_parallel_and_reordered_input(mc_inputs):
    directory, target = mc_inputs
    serial = _build(directory, target)
    parallel = _build(directory, target, workers=2)
    reordered = _build(directory, target, workers=2, names=("pi0pi0", "eta_pi0"))
    assert list(parallel) == ["eta_pi0", "pi0pi0"]
    assert list(reordered) == ["pi0pi0", "eta_pi0"]
    for name in serial:
        assert len(serial[name].X) > 200
        _assert_sample_equal(serial[name], parallel[name])
        _assert_sample_equal(serial[name], reordered[name])


def test_default_legacy_policy_keeps_the_original_serial_rng_stream(mc_inputs):
    directory, target = mc_inputs
    actual = _build(directory, target, seed_policy="legacy")
    rng = np.random.default_rng(42)
    for name, sample in actual.items():
        channel = get_channel(name)
        with uproot.open(directory / channel.mc_filename) as source:
            expected = build_channel_features(
                source["mc"], channel, ETA_PI0_HYP, rng, LossParams(), target,
            )
        _assert_sample_equal(sample, expected)


@pytest.mark.parametrize("workers,policy,match", [
    (0, "channel-v1", "workers"),
    (2, "legacy", "channel-v1"),
    (1, "unknown", "seed.policy"),
])
def test_invalid_parallel_configuration_fails_before_opening_inputs(tmp_path, workers, policy, match):
    target = BeamSpectrum(np.array([0., 1.]), np.ones(1))
    with pytest.raises(ValueError, match=match):
        _build(tmp_path, target, workers=workers, seed_policy=policy)


def test_parallel_worker_error_is_propagated_for_corrupt_input(mc_inputs, tmp_path):
    directory, target = mc_inputs
    import shutil
    shutil.copyfile(directory / "eta_pi0_mc.root", tmp_path / "eta_pi0_mc.root")
    (tmp_path / "pi0pi0_mc.root").write_bytes(b"not a ROOT file")
    with pytest.raises((OSError, ValueError), match="ROOT|bytes|expected"):
        _build(tmp_path, target, workers=2)


def test_cli_parallel_dataset_matches_serial_and_records_seed_policy(mc_inputs, tmp_path, monkeypatch):
    directory, target = mc_inputs
    spectrum = tmp_path / "spectrum.npz"
    target.save(spectrum)
    outputs = [tmp_path / "serial.npz", tmp_path / "parallel.npz"]
    for workers, output in zip((1, 2), outputs):
        monkeypatch.setattr(sys, "argv", [
            "build_background_features", "--mc-dir", str(directory),
            "--background-channels", "pi0pi0", "--beam-spectrum", str(spectrum),
            "--profile", "vis", "--record-origins", "--loss-seed", "42",
            "--workers", str(workers), "--seed-policy", "channel-v1", "--output", str(output),
        ])
        builder.main()
    serial, parallel = map(load_stage1_dataset, outputs)
    for key in ("X", "y", "w"):
        np.testing.assert_array_equal(getattr(serial, key), getattr(parallel, key))
    for key in ("origin_id", "channel", "profile", "detector_variant"):
        np.testing.assert_array_equal(getattr(serial.rows, key), getattr(parallel.rows, key))
    assert serial.metadata == parallel.metadata
    assert serial.metadata.loss_seed == 42
    assert serial.metadata.loss_seed_policy == "channel-v1"
    assert np.all(np.char.find(serial.rows.detector_variant, "seed_policy=channel-v1") >= 0)
