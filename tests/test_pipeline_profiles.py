from __future__ import annotations

from pathlib import Path

import pytest


def test_all_profiles_share_exactly_one_stage_graph():
    from graal_pipeline.config import load_config
    from graal_pipeline.registry import STAGES, stage_graph_for_profile

    for profile in ("production", "smoke", "farm"):
        config = load_config(profile=profile)
        graph = stage_graph_for_profile(config)
        assert graph is STAGES
        assert tuple(graph) == tuple(STAGES)


def test_production_keeps_canonical_paths_and_fast_verification():
    from graal_pipeline.config import load_config

    config = load_config(profile="production")

    assert config.paths.selected_dir == config.repository_root / "data/03_selected"
    assert config.paths.results_dir == config.repository_root / "results"
    assert config.checkpoint.verification == "fast"
    assert config.profile_settings.isolated_results is False
    assert config.profile_settings.claim == "physics production"


def test_smoke_requires_real_reduced_root_fixture_with_copy_instructions(tmp_path):
    from graal_pipeline.config import ProfileInputError, load_config, validate_profile_inputs

    config = load_config(profile="smoke")

    with pytest.raises(ProfileInputError) as error:
        validate_profile_inputs(config)

    message = str(error.value)
    assert "test_data/raw" in message
    assert "copy" in message.casefold()
    assert "synthetic physics input is not accepted" in message.casefold()


def test_smoke_run_materializes_every_writable_path_under_run_root(tmp_path):
    from graal_pipeline.config import (
        load_config,
        materialize_profile_run,
        validate_profile_inputs,
    )

    root = tmp_path / "repo"
    fixture = root / "test_data/raw/1998_uv"
    fixture.mkdir(parents=True)
    (fixture / "run1321.root").write_bytes(b"real fixture placeholder")
    config_path = root / "pipeline.toml"
    config_path.write_text(
        """
[profiles.smoke.paths]
raw_dir = "test_data/raw"
results_dir = "results/validation/smoke"

[profiles.smoke.checkpoint]
verification = "full"

[profiles.smoke.profile_settings]
claim = "integration only"
isolated_results = true
requires_real_fixture = true
"""
    )
    config = load_config(config_path, profile="smoke", repo_root=root)
    validate_profile_inputs(config)

    run = materialize_profile_run(config, "smoke-001")
    run_root = root / "results/validation/smoke/smoke-001"

    assert run.paths.results_dir == run_root
    for path in (
        run.paths.preanalysis_dir,
        run.paths.selected_dir,
        run.paths.mc_data_dir,
        run.paths.model_dir,
        run.paths.features_file,
        run.paths.beam_spectrum_file,
    ):
        assert path.resolve().is_relative_to(run_root.resolve())
    assert run.paths.raw_dir == root / "test_data/raw"


def test_smoke_and_farm_profiles_define_claims_and_runtime_overrides():
    from graal_pipeline.config import load_config

    smoke = load_config(profile="smoke")
    farm = load_config(profile="farm")

    assert smoke.checkpoint.verification == "full"
    assert smoke.runtime.mc_events < farm.runtime.mc_events
    assert smoke.runtime.bootstrap_replicas < farm.runtime.bootstrap_replicas
    assert smoke.profile_settings.claim == "integration only"
    assert farm.checkpoint.verification == "full"
    assert farm.profile_settings.claim == "full farm validation"
    assert farm.profile_settings.isolated_results is True


def test_cli_smoke_stops_before_planning_when_fixture_is_missing(tmp_path, capsys):
    from graal_pipeline.cli import main

    config_path = tmp_path / "pipeline.toml"
    config_path.write_text(
        f"""
[profiles.smoke.paths]
raw_dir = "{tmp_path / 'missing-real-fixture'}"
results_dir = "{tmp_path / 'results'}"

[profiles.smoke.profile_settings]
claim = "integration only"
isolated_results = true
requires_real_fixture = true
"""
    )

    code = main(
        [
            "validate",
            "beam-asymmetry",
            "--profile",
            "smoke",
            "--config",
            str(config_path),
            "--non-interactive",
            "--dry-run",
        ]
    )

    assert code == 2
    assert "copy one or more representative detector runs" in capsys.readouterr().err
    assert not (tmp_path / "results").exists()
