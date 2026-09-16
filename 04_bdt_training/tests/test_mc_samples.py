"""Tests for Monte Carlo decoding and per-channel feature sampling."""

import numpy as np

import bdt_training.dataset.mc_samples as mc_samples
from bdt_training.photon_loss import LossParams
from graal_common.physics.channels import get_channel
from graal_common.stage1.features import compute_stage1_features


def _make_photons(rng, n_events, n_photons=4):
    energy = rng.uniform(0.1, 0.8, (n_events, n_photons))
    theta = rng.uniform(0.1, 2.8, (n_events, n_photons))
    phi = rng.uniform(0, 2 * np.pi, (n_events, n_photons))
    px = energy * np.sin(theta) * np.cos(phi)
    py = energy * np.sin(theta) * np.sin(phi)
    pz = energy * np.cos(theta)
    return np.stack([px, py, pz, energy], axis=-1)


def _make_proton(rng, n_events):
    momentum = rng.uniform(0.1, 1.5, n_events)
    theta = rng.uniform(0.05, 1.0, n_events)
    phi = rng.uniform(0, 2 * np.pi, n_events)
    px = momentum * np.sin(theta) * np.cos(phi)
    py = momentum * np.sin(theta) * np.sin(phi)
    pz = momentum * np.cos(theta)
    energy = np.sqrt(momentum**2 + 0.938272**2)
    return np.stack([px, py, pz, energy], axis=1)


def _make_beam(rng, n_events):
    energy = rng.uniform(0.5, 1.5, n_events)
    return np.stack(
        [np.zeros(n_events), np.zeros(n_events), energy, energy], axis=1
    )


class TestShufflePhotons:
    def test_every_event_keeps_its_own_four_photons(self):
        rng = np.random.default_rng(11)
        photons = _make_photons(rng, 200)
        out = mc_samples.shuffle_photons(photons, np.random.default_rng(3))

        for before, after in zip(photons, out):
            assert sorted(before[:, 3].tolist()) == sorted(after[:, 3].tolist())

    def test_it_actually_reorders(self):
        rng = np.random.default_rng(12)
        photons = _make_photons(rng, 500)
        out = mc_samples.shuffle_photons(photons, np.random.default_rng(4))

        moved = (photons[:, 0, 3] != out[:, 0, 3]).mean()
        assert moved > 0.5

    def test_order_invariant_features_survive_it(self):
        rng = np.random.default_rng(13)
        photons = _make_photons(rng, 100)
        proton = _make_proton(rng, 100)
        beam = _make_beam(rng, 100)

        original = compute_stage1_features(photons, proton, beam)
        shuffled = compute_stage1_features(
            mc_samples.shuffle_photons(photons, np.random.default_rng(5)),
            proton,
            beam,
        )

        for column in (8, 19, 20):
            np.testing.assert_allclose(
                original[:, column], shuffled[:, column], rtol=1e-5
            )


class _Branch:
    def __init__(self, value):
        self.value = value

    def array(self, library):
        return self.value


class _Tree:
    def __init__(self, values):
        self.values = values

    def __getitem__(self, name):
        return _Branch(self.values[name])


def _vectors(energies):
    energies = np.asarray(energies, dtype=float)
    return {
        "fP": {
            "fX": energies,
            "fY": np.zeros_like(energies),
            "fZ": np.zeros_like(energies),
        },
        "fE": energies,
    }


def test_seeded_channel_sampling_preserves_selection_and_photon_order(monkeypatch):
    tree = _Tree(
        {
            "eta_gamma1": _vectors([0.11, 0.21, 0.31]),
            "eta_gamma2": _vectors([0.12, 0.22, 0.32]),
            "pi0_gamma1": _vectors([0.13, 0.23, 0.33]),
            "pi0_gamma2": _vectors([0.14, 0.24, 0.34]),
            "proton": _vectors([0.91, 0.92, 0.93]),
            "beam": _vectors([1.11, 1.22, 1.33]),
        }
    )
    channel = get_channel("eta_pi0")
    assert channel.hypothesis is not None

    def encode_photon_order(photons, _protons, _beams, _hypothesis):
        features = np.zeros((len(photons), 26), dtype=np.float32)
        features[:, :4] = photons[:, :, 3]
        return features

    monkeypatch.setattr(
        mc_samples, "compute_stage1_features", encode_photon_order
    )
    monkeypatch.setattr(
        mc_samples,
        "beam_reweight",
        lambda beam_energy, _target: beam_energy.copy(),
    )

    sample = mc_samples.build_channel_features(
        tree,
        channel,
        channel.hypothesis,
        np.random.default_rng(17),
        LossParams(
            E_thr=-1.0,
            sigma_E=0.01,
            theta_min_acc=-1.0,
            theta_max_acc=4.0,
            sigma_theta=0.01,
        ),
        object(),
    )

    expected = np.array(
        [
            [0.14, 0.11, 0.13, 0.12],
            [0.23, 0.24, 0.21, 0.22],
            [0.31, 0.34, 0.32, 0.33],
        ],
        dtype=np.float32,
    )
    assert sample.X.shape == (3, 26)
    np.testing.assert_array_equal(sample.X[:, :4], expected)
    np.testing.assert_array_equal(sample.X[:, 4:], np.zeros((3, 22), np.float32))
    np.testing.assert_array_equal(sample.beam_E, np.array([1.11, 1.22, 1.33]))
    np.testing.assert_array_equal(sample.w_beam, sample.beam_E)
    assert sample.p_surv == 1.0
    assert sample.n_gen == 3
