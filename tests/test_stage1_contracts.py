"""Cross-module contracts for the stage-1 training and inference boundary."""

import json
from pathlib import Path
import sys
from types import SimpleNamespace

import numpy as np

import bdt_training.build_background_features as feature_builder
import bdt_training.dataset.channel_weights as channel_weights
import bdt_training.dataset.mc_samples as mc_samples
import bdt_training.train_bdt_stage1 as trainer
import graal_common.stage1.features as shared_features
from graal_common.physics.channels import get_channel
from graal_common.stage1.artifacts import METRICS_FILE
from reconstruction.runtime.stage1_gate import MODEL_FILE, PROVENANCE_FILE, THRESHOLD_FILE


FEATURE_NAMES = [
    "m_gg_01",
    "m_gg_02",
    "m_gg_03",
    "m_gg_12",
    "m_gg_13",
    "m_gg_23",
    "n_pairs_near_pi0",
    "n_pairs_near_eta",
    "best_chi2_eta_pi0",
    "missing_mass",
    "missing_E",
    "missing_pz",
    "missing_pt",
    "total_gamma_E",
    "beam_E",
    "max_gamma_E",
    "min_gamma_E",
    "gamma_E_rms",
    "sum_opening_angles",
    "min_pair_mass",
    "max_pair_mass",
    "total_pt_gamma",
    "proton_p",
    "proton_costheta",
    "eta_E_asym",
    "eta_pi0_angle",
]

FEATURE_VECTOR = np.array(
    [
        0.35034412145614624,
        0.3412857949733734,
        0.31499364972114563,
        0.32095015048980713,
        0.10413452982902527,
        0.25850531458854675,
        1.0,
        0.0,
        30.37286949157715,
        0.7628103494644165,
        1.3432719707489014,
        1.100000023841858,
        0.11180339753627777,
        1.4859999418258667,
        1.399999976158142,
        0.44999998807907104,
        0.296999990940094,
        0.05422407388687134,
        4.6728901863098145,
        0.10413452982902527,
        0.35034412145614624,
        0.6898563504219055,
        0.3201562166213989,
        0.9370425939559937,
        0.09223300963640213,
        0.7148410677909851,
    ],
    dtype=np.float32,
)

DATASET_KEYS = {
    "X",
    "y",
    "w",
    "feature_names",
    "signal_channel",
    "hypothesis",
    "signal_prior",
    "beam_reweighted",
}

PROVENANCE_KEYS = {
    "signal_channel",
    "hypothesis",
    "signal_prior",
    "beam_reweighted",
    "phase_space_sampling",
    "tagger_resolution_fwhm_gev",
    "tagger_resolution_sigma_gev",
    "detector_covariance_status",
    "feature_names",
}


def test_stage1_feature_vector_is_a_stable_ordered_float32_contract():
    photons = np.array(
        [
            [
                [0.20, 0.10, 0.30, 0.374],
                [-0.15, 0.05, 0.25, 0.297],
                [0.05, -0.20, 0.40, 0.450],
                [-0.10, 0.02, 0.35, 0.365],
            ]
        ]
    )
    proton = np.array([[0.10, -0.05, 0.30, 0.995]])
    beam = np.array([[0.0, 0.0, 1.4, 1.4]])

    actual = feature_builder.compute_stage1_features(photons, proton, beam)

    assert feature_builder.FEATURE_NAMES_S1 == FEATURE_NAMES
    assert actual.dtype == np.float32
    assert actual.shape == (1, 26)
    np.testing.assert_allclose(actual[0], FEATURE_VECTOR, rtol=0.0, atol=1e-7)


def test_legacy_feature_builder_imports_remain_available():
    assert feature_builder.N_FEATURES_S1 == 26
    assert callable(feature_builder.feature_names)
    assert callable(feature_builder.compute_stage1_features)


def test_shared_feature_api_is_the_legacy_feature_api():
    assert feature_builder.N_FEATURES_S1 == shared_features.N_FEATURES_S1
    assert feature_builder.FEATURE_NAMES_S1 is shared_features.FEATURE_NAMES_S1
    assert feature_builder.feature_names is shared_features.feature_names
    assert (
        feature_builder.compute_stage1_features
        is shared_features.compute_stage1_features
    )


def test_feature_builder_reexports_moved_sampling_and_weighting_api():
    assert feature_builder._load_4vec is mc_samples._load_4vec
    assert feature_builder.load_photons is mc_samples.load_photons
    assert feature_builder._extract_E_theta is mc_samples._extract_E_theta
    assert feature_builder.shuffle_photons is mc_samples.shuffle_photons
    assert feature_builder.ChannelSample is mc_samples.ChannelSample
    assert feature_builder.build_channel_features is mc_samples.build_channel_features
    assert feature_builder.ChannelYield is channel_weights.ChannelYield
    assert feature_builder.channel_yield is channel_weights.channel_yield
    assert feature_builder.compute_shares is channel_weights.compute_shares


class _FakeRootFile:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def __getitem__(self, name):
        assert name == "mc"
        return object()


def test_feature_builder_writes_exact_npz_schema(tmp_path, monkeypatch):
    mc_dir = tmp_path / "mc"
    mc_dir.mkdir()
    for name in ("eta_pi0", "pi0pi0"):
        (mc_dir / get_channel(name).mc_filename).touch()

    output = tmp_path / "features_stage1.npz"
    beam_spectrum = tmp_path / "beam_spectrum.npz"

    monkeypatch.setattr(
        feature_builder,
        "BeamSpectrum",
        SimpleNamespace(load=lambda _path: object()),
    )
    monkeypatch.setattr(feature_builder.uproot, "open", lambda _path: _FakeRootFile())

    def fake_sample(_tree, channel, _hypothesis, _rng, _params, _beam_target):
        value = 1.0 if channel.name == "eta_pi0" else 2.0
        return feature_builder.ChannelSample(
            X=np.full((2, 26), value, dtype=np.float32),
            w_beam=np.ones(2),
            beam_E=np.full(2, 1.4),
            p_surv=0.5,
            n_gen=4,
        )

    monkeypatch.setattr(feature_builder, "build_channel_features", fake_sample)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "build_background_features",
            "--mc-dir",
            str(mc_dir),
            "--signal-channel",
            "eta_pi0",
            "--background-channels",
            "pi0pi0",
            "--beam-spectrum",
            str(beam_spectrum),
            "--output",
            str(output),
        ],
    )

    feature_builder.main()

    with np.load(output) as data:
        assert set(data.files) == DATASET_KEYS
        np.testing.assert_array_equal(
            data["X"],
            np.concatenate(
                [
                    np.ones((2, 26), dtype=np.float32),
                    np.full((2, 26), 2.0, dtype=np.float32),
                ]
            ),
        )
        np.testing.assert_array_equal(data["y"], np.array([1, 1, 0, 0]))
        np.testing.assert_array_equal(data["w"], np.ones(4, dtype=np.float32))
        assert list(data["feature_names"]) == FEATURE_NAMES
        assert str(data["signal_channel"]) == "eta_pi0"
        assert str(data["hypothesis"]) == "eta_pi0"
        assert float(data["signal_prior"]) == 0.5
        assert bool(data["beam_reweighted"]) is True


class _FakeClassifier:
    feature_importances_ = np.zeros(26)

    def __init__(self, **_kwargs):
        pass

    def fit(self, *_args, **_kwargs):
        return self

    def predict_proba(self, X):
        scores = np.where(X[:, 0] > 0.5, 0.9, 0.1)
        return np.column_stack([1.0 - scores, scores])

    def save_model(self, path):
        Path(path).write_text("{}\n")


def test_trainer_publishes_exact_runtime_artifact_bundle(tmp_path, monkeypatch):
    features = tmp_path / "features_stage1.npz"
    labels = np.tile(np.array([0, 1], dtype=np.int8), 10)
    X = np.zeros((len(labels), 26), dtype=np.float32)
    X[:, 0] = labels
    np.savez(
        features,
        X=X,
        y=labels,
        w=np.ones(len(labels), dtype=np.float32),
        feature_names=np.array(FEATURE_NAMES),
        signal_channel=np.array("eta_pi0"),
        hypothesis=np.array("eta_pi0"),
        signal_prior=np.array(0.5),
        beam_reweighted=np.array(True),
    )

    monkeypatch.setattr(trainer.xgb, "XGBClassifier", _FakeClassifier)
    monkeypatch.setattr(trainer, "_HAVE_MPL", False)
    output = tmp_path / "model"

    trainer.train(str(features), str(output), n_estimators=1, verbose=False)

    expected_files = {
        MODEL_FILE,
        THRESHOLD_FILE,
        PROVENANCE_FILE,
        METRICS_FILE,
    }
    assert {path.name for path in output.iterdir()} == expected_files
    provenance = json.loads((output / PROVENANCE_FILE).read_text())
    assert set(provenance) == PROVENANCE_KEYS
    assert provenance["feature_names"] == FEATURE_NAMES
    assert (output / THRESHOLD_FILE).read_text().endswith("\n")
    assert (output / METRICS_FILE).read_text().endswith("\n")
