"""The numbered pipeline dirs must be importable under clean package names."""


def test_graal_common_importable():
    from graal_common.channels import CHANNELS, M_ETA

    assert M_ETA > 0
    assert "eta_pi0" in CHANNELS


def test_bdt_training_importable():
    from bdt_training import photon_loss

    assert hasattr(photon_loss, "sample_surviving_photons")


def test_stage1_feature_builder_importable():
    from bdt_training.build_background_features import (
        FEATURE_NAMES_S1,
        compute_stage1_features,
    )

    assert len(FEATURE_NAMES_S1) == 24
    assert callable(compute_stage1_features)
