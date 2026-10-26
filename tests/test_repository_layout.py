def test_responsibility_packages_are_importable():
    from graal_common.physics import channels
    from graal_common.io import trees
    from calibration import run_manifest
    from graal_common.stage1 import features
    from bdt_training.dataset import stage1_dataset
    from bdt_training.training import stage1_training
    from reconstruction.core import event_logic
    from reconstruction.runtime import reco_core
    from plots.core import reconstruction_data

    assert channels.CHANNEL_NAMES
    assert trees.AUTO == "auto"
    assert run_manifest.RunRecord
    assert features.N_FEATURES_S1 == 26
    assert stage1_dataset.Stage1Dataset
    assert stage1_training.TrainingConfig
    assert event_logic.EventInput
    assert reco_core.RecoConfig
    assert reconstruction_data.ReconstructionArrays


def test_stage1_runtime_bundle_has_dedicated_artifact_directory():
    from pathlib import Path

    from reconstruction.runtime.stage1_gate import DEFAULT_MODEL_DIR

    expected = Path(__file__).parents[1] / "04_bdt_training" / "artifacts" / "stage1"
    assert DEFAULT_MODEL_DIR == expected
    assert (DEFAULT_MODEL_DIR / "bdt_stage1.json").is_file()
    assert (DEFAULT_MODEL_DIR / "stage1_threshold.txt").is_file()
    assert (DEFAULT_MODEL_DIR / "stage1_provenance.json").is_file()


def test_retired_theory_keeps_references_and_experimental_extraction():
    from pathlib import Path

    from graal_common.physics.cross_sections import sigma_at
    from observable_extraction.beam_asymmetry import build_parser

    root = Path(__file__).parents[1]
    assert not (root / "09_theory").exists()
    references = root / "docs/reference/theory"
    assert (references / "sources.json").is_file()
    assert (references / "eta_pi0_literature_audit.json").is_file()
    assert not list(references.rglob("*.py"))
    assert "--phi-bins" in build_parser()._option_string_actions
    assert callable(sigma_at)
