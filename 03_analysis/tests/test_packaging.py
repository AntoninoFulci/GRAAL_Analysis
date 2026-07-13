"""The numbered pipeline dirs must be importable under clean package names."""


def test_analysis_bdt_importable():
    from analysis_bdt import physics

    assert hasattr(physics, "invariant_mass")


def test_stage1_feature_builder_importable():
    from analysis_bdt.build_background_features import (
        FEATURE_NAMES_S1,
        compute_stage1_features,
    )

    assert len(FEATURE_NAMES_S1) == 24
    assert callable(compute_stage1_features)
