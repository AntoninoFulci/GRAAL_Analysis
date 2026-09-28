from __future__ import annotations

import sys
from pathlib import Path

import pytest


def test_python_stages_inherit_orchestrator_interpreter_by_default():
    from graal_pipeline.config import load_config
    from graal_pipeline.registry import build_stage_invocation

    config = load_config()
    selection = build_stage_invocation("event_selection", config)

    assert selection.commands[0][0] == sys.executable


def test_python_stage_interpreter_can_be_overridden_explicitly(tmp_path):
    from graal_pipeline.config import load_config
    from graal_pipeline.registry import build_stage_invocation

    root = tmp_path / "repo"
    root.mkdir()
    config_path = root / "pipeline.toml"
    config_path.write_text(
        '[runtime]\npython_executable = "/opt/graal/python"\n'
    )
    config = load_config(config_path, repo_root=root)
    selection = build_stage_invocation("event_selection", config)

    assert selection.commands[0][0] == "/opt/graal/python"


def test_every_stage_declares_command_outputs_validator_scope_and_code():
    from graal_pipeline.config import load_config
    from graal_pipeline.registry import STAGES, build_stage_invocation

    config = load_config()
    for key, stage in STAGES.items():
        invocation = build_stage_invocation(key, config, final_state="eta_pi0")
        assert invocation.commands, key
        assert all(isinstance(command, tuple) and command for command in invocation.commands)
        assert invocation.working_directory.is_absolute()
        assert invocation.outputs, key
        assert invocation.scope is stage.scope
        assert invocation.validator == stage.validator
        assert invocation.responsible_paths == stage.responsible_paths


def test_canonical_result_paths_are_namespaced_by_final_state():
    from graal_pipeline.config import load_config
    from graal_pipeline.registry import pipeline_paths

    config = load_config()
    paths = pipeline_paths(config, "eta_pi0")
    results = config.paths.results_dir

    assert paths["calibration_dir"] == results / "shared/strip_energy_flux"
    assert paths["reconstruction_dir"] == results / "eta_pi0/reconstruction"
    assert paths["reco_chi2_raw"] == (
        results / "eta_pi0/reconstruction/reco_eta_pi0_chi2_raw.root"
    )
    assert paths["beam_asymmetry_first_dir"] == (
        results / "eta_pi0/observables/beam_asymmetry/first_pass"
    )
    assert paths["beam_asymmetry_dir"] == (
        results / "eta_pi0/observables/beam_asymmetry"
    )
    assert config.paths.model_dir == config.repository_root / "04_bdt_training/artifacts/stage1"


def test_preanalysis_selection_and_calibration_argv_are_exact():
    from graal_pipeline.config import load_config
    from graal_pipeline.registry import build_stage_invocation, pipeline_paths

    config = load_config()
    root = config.repository_root
    paths = pipeline_paths(config, "eta_pi0")

    preanalysis = build_stage_invocation("preanalysis", config)
    selection = build_stage_invocation("event_selection", config)
    calibration = build_stage_invocation("flux_calibration", config)

    expression = (
        f'gROOT->ProcessLine(".L {root / "01_pre_analysis/PreAnalysis.C"}"); '
        f'AnalyzeAll("{config.paths.raw_dir}", "{config.paths.preanalysis_dir}", '
        f'"{root / "01_pre_analysis/cuts"}");'
    )
    assert preanalysis.commands == (
        (config.runtime.root_executable, "-l", "-b", "-q", "-e", expression),
    )
    assert selection.commands == (
        (
            config.runtime.python_executable,
            "-u",
            "-m",
            "event_selector.select_events",
            "--input-dir",
            str(config.paths.preanalysis_dir),
            "--output-dir",
            str(config.paths.selected_dir),
            "--threads",
            str(config.runtime.threads),
        ),
    )
    assert calibration.commands == (
        (
            config.runtime.python_executable,
            str(root / "scripts/build_strip_energy_flux.py"),
            "--preanalysis-dir",
            str(config.paths.preanalysis_dir),
            "--manifest",
            str(config.paths.run_manifest),
            "--flux",
            str(config.paths.external_flux),
            "--output-dir",
            str(paths["calibration_dir"]),
            "--progress-every-events",
            str(config.runtime.flux_progress_every_events),
            "--samples-per-run-strip",
            str(config.runtime.flux_samples_per_run_strip),
            "--threads",
            str(config.runtime.threads),
        ),
    )


def test_training_commands_and_optional_grid_parameters_are_exact():
    from graal_pipeline.config import load_config
    from graal_pipeline.registry import build_stage_invocation

    config = load_config()
    python = config.runtime.python_executable

    beam = build_stage_invocation("beam_spectrum", config)
    features = build_stage_invocation("feature_build", config)
    grid = build_stage_invocation("grid_search", config)
    training = build_stage_invocation("bdt_training", config)

    assert beam.commands == (
        (
            python,
            "-u",
            "-m",
            "bdt_training.beam_spectrum",
            "--selected-dir",
            str(config.paths.selected_dir),
            "--tree",
            config.runtime.input_tree,
            "--output",
            str(config.paths.beam_spectrum_file),
        ),
    )
    assert features.commands == (
        (
            python,
            "-u",
            "-m",
            "bdt_training.build_background_features",
            "--mc-dir",
            str(config.paths.mc_data_dir),
            "--signal-channel",
            config.runtime.signal_channel,
            "--signal-prior",
            str(config.runtime.signal_prior),
            "--beam-spectrum",
            str(config.paths.beam_spectrum_file),
            "--output",
            str(config.paths.features_file),
        ),
    )
    assert "--n-iter" in grid.commands[0]
    assert training.commands[0][-2:] == (
        "--hyperparams",
        str(config.paths.model_dir / "best_hyperparams.json"),
    )


def test_reconstruction_and_observable_commands_are_exact():
    from graal_pipeline.config import load_config
    from graal_pipeline.registry import build_stage_invocation, pipeline_paths

    config = load_config()
    paths = pipeline_paths(config, "eta_pi0")
    python = config.runtime.python_executable

    raw = build_stage_invocation("reco_chi2_raw", config)
    bdt = build_stage_invocation("reco_bdt_raw", config)
    fit = build_stage_invocation("reco_bdt_fit", config)
    sideband = build_stage_invocation("reco_data_sideband", config)
    adapter = build_stage_invocation("signal_mc_adapter", config)
    signal_reco = build_stage_invocation("reco_signal_mc_sideband", config)
    first_pass = build_stage_invocation("beam_asymmetry_first_pass", config)
    full = build_stage_invocation("beam_asymmetry_full", config)

    assert raw.commands[0] == (
        python,
        "-m",
        "reconstruction.reconstruct_eta_pi0_chi2",
        "--input-dir",
        str(config.paths.selected_dir),
        "--input-tree",
        config.runtime.input_tree,
        "--partner",
        config.runtime.partner,
        "--no-fit",
        "--output-file",
        str(paths["reco_chi2_raw"]),
    )
    assert "--no-fit" in bdt.commands[0]
    assert "--model-dir" in bdt.commands[0]
    assert "--no-fit" not in fit.commands[0]
    assert sideband.commands[0][2] == "reconstruction.reconstruct_eta_pi0_bdt_sideband"
    assert adapter.commands[0][2] == "reconstruction.prepare_signal_mc_selected"
    assert signal_reco.commands[0][4] == str(paths["signal_mc_selected_dir"])
    assert first_pass.commands[0] == (
        python,
        "-m",
        "observable_extraction.beam_asymmetry",
        "--raw-bdt",
        str(paths["reco_bdt_raw"]),
        "--calibration-dir",
        str(paths["calibration_dir"]),
        "--output-dir",
        str(paths["beam_asymmetry_first_dir"]),
    )
    assert full.commands[0] == (
        python,
        "-m",
        "observable_extraction.beam_asymmetry",
        "--raw",
        str(paths["reco_chi2_raw"]),
        "--raw-bdt",
        str(paths["reco_bdt_raw"]),
        "--raw-bdt-fit",
        str(paths["reco_bdt_fit"]),
        "--sideband",
        str(paths["reco_data_sideband"]),
        "--signal-mc",
        str(paths["reco_signal_mc_sideband"]),
        "--calibration-dir",
        str(paths["calibration_dir"]),
        "--output-dir",
        str(paths["beam_asymmetry_dir"]),
        "--estimator",
        config.runtime.estimator,
        "--bootstrap-replicas",
        str(config.runtime.bootstrap_replicas),
        "--bootstrap-seed",
        str(config.runtime.bootstrap_seed),
    )


def test_mc_generation_uses_one_root_argv_per_registered_channel():
    from graal_common.physics.channels import CHANNEL_NAMES
    from graal_pipeline.config import load_config
    from graal_pipeline.registry import build_stage_invocation

    config = load_config()
    invocation = build_stage_invocation("mc_generation", config)
    background_channels = tuple(
        channel for channel in CHANNEL_NAMES if channel != "eta_pi0"
    )

    assert len(invocation.commands) == len(background_channels)
    for channel, command in zip(background_channels, invocation.commands):
        assert command == (
            config.runtime.root_executable,
            "-l",
            "-b",
            "-q",
            str(
                config.repository_root
                / f"03_mc_simulation/generators/generate_{channel}_dataset.C"
            )
            + f"({config.runtime.mc_events})",
        )
    assert invocation.working_directory == config.paths.mc_data_dir


def test_signal_mc_has_single_owner_shared_by_training_and_extraction():
    from graal_pipeline.config import load_config
    from graal_pipeline.registry import STAGES, build_stage_invocation

    config = load_config()
    background = build_stage_invocation("mc_generation", config)
    signal = build_stage_invocation("signal_mc_generation", config)
    signal_path = config.paths.mc_data_dir / "eta_pi0_mc.root"

    assert signal_path not in background.outputs
    assert signal.outputs == (signal_path,)
    assert "signal_mc_generation" in STAGES["feature_build"].dependencies


def test_result_path_rejects_parent_and_symlink_escape(tmp_path):
    from graal_pipeline.config import ConfigError, load_config
    from graal_pipeline.registry import result_path

    root = tmp_path / "repo"
    root.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    config_file = root / "pipeline.toml"
    config_file.write_text('[paths]\nresults_dir = "results"\n')
    config = load_config(config_file, repo_root=root)

    with pytest.raises(ConfigError, match="escapes result root"):
        result_path(config, "..", "escape")

    config.paths.results_dir.mkdir()
    (config.paths.results_dir / "linked").symlink_to(outside, target_is_directory=True)
    with pytest.raises(ConfigError, match="escapes result root"):
        result_path(config, "linked", "escape")
