from __future__ import annotations

from pathlib import Path
import json
import os
import subprocess
import sys

import pytest


ROOT = Path(__file__).parents[1]


def test_module_help_works_outside_repository(tmp_path):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)

    result = subprocess.run(
        [sys.executable, "-m", "graal_pipeline", "--help"],
        cwd=tmp_path,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr
    assert "GRAAL pipeline orchestrator" in result.stdout
    assert "--config" in result.stdout
    assert "--profile" in result.stdout


def test_pyproject_registers_console_command_and_python_310_tomli():
    try:
        import tomllib
    except ModuleNotFoundError:  # pragma: no cover - exercised on Python 3.10
        import tomli as tomllib

    metadata = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert metadata["project"]["scripts"]["graal-pipeline"] == "graal_pipeline.cli:main"
    assert "tomli>=2; python_version < '3.11'" in metadata["project"]["dependencies"]
    assert "graal_pipeline" in metadata["tool"]["setuptools"]["packages"]


@pytest.mark.parametrize(
    ("argv", "command", "operation"),
    [
        (["resume"], "resume", None),
        (["prepare", "--final-state", "eta_pi0"], "prepare", None),
        (["reconstruct", "--final-state", "eta_pi0"], "reconstruct", None),
        (["status", "--final-state", "eta_pi0"], "status", None),
        (
            ["plan", "extract", "beam-asymmetry", "--final-state", "eta_pi0"],
            "plan",
            "extract",
        ),
        (
            ["extract", "beam-asymmetry", "--final-state", "eta_pi0"],
            "extract",
            "beam-asymmetry",
        ),
        (
            [
                "validate",
                "beam-asymmetry",
                "--final-state",
                "eta_pi0",
                "--profile",
                "smoke",
            ],
            "validate",
            "beam-asymmetry",
        ),
        (
            ["validate", "full", "--final-state", "eta_pi0"],
            "validate",
            "full",
        ),
    ],
)
def test_cli_parses_supported_command_tree(argv, command, operation):
    from graal_pipeline.cli import build_parser

    args = build_parser().parse_args(argv)

    assert args.command == command
    if operation is not None:
        assert args.operation == operation


def test_leaf_help_lists_every_common_option(capsys):
    from graal_pipeline.cli import main

    with pytest.raises(SystemExit) as error:
        main(["extract", "beam-asymmetry", "--help"])

    assert error.value.code == 0
    help_text = capsys.readouterr().out
    for option in (
        "--config",
        "--profile",
        "--state-dir",
        "--dry-run",
        "--non-interactive",
        "--yes",
        "--force-stage",
        "--old-policy",
        "--stale-policy",
        "--untracked-policy",
        "--verify",
        "--keep-failed-work",
    ):
        assert option in help_text


def test_disabled_cli_capability_fails_before_discovery(capsys):
    from graal_pipeline.cli import main

    exit_code = main(
        [
            "plan",
            "extract",
            "beam-asymmetry",
            "--final-state",
            "2pi0",
            "--non-interactive",
        ]
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "2pi0 / beam_asymmetry is disabled" in captured.err


def test_status_and_plan_use_stable_english_tokens(tmp_path, capsys):
    from graal_pipeline.cli import main

    config = tmp_path / "pipeline.toml"
    config.write_text(f'[paths]\nresults_dir = "{tmp_path / "results"}"\n')

    status_code = main(
        ["status", "--final-state", "eta_pi0", "--config", str(config)]
    )
    status_output = capsys.readouterr().out
    plan_code = main(
        [
            "plan",
            "extract",
            "beam-asymmetry",
            "--final-state",
            "eta_pi0",
                "--config",
                str(config),
                "--non-interactive",
                "--old-policy",
                "reuse",
                "--stale-policy",
                "rebuild",
                "--untracked-policy",
                "rebuild",
            ]
        )
    plan_output = capsys.readouterr().out

    assert status_code == 0
    assert "MISSING" in status_output
    assert plan_code == 0
    assert "RUN" in plan_output


def test_module_and_console_help_are_equivalent():
    module = subprocess.run(
        [sys.executable, "-m", "graal_pipeline", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )
    console = subprocess.run(
        ["graal-pipeline", "--help"],
        cwd=ROOT,
        text=True,
        capture_output=True,
    )

    assert module.returncode == console.returncode == 0
    assert module.stdout == console.stdout


def test_common_options_work_before_or_after_subcommand():
    from graal_pipeline.cli import build_parser

    before = build_parser().parse_args(
        ["--profile", "farm", "--config", "farm.toml", "status"]
    )
    after = build_parser().parse_args(
        ["status", "--profile", "farm", "--config", "farm.toml"]
    )

    assert before.profile == after.profile == "farm"
    assert before.config == after.config == "farm.toml"


def test_toml_checkpoint_policies_apply_when_cli_does_not_override():
    from graal_pipeline.cli import _planning_policies_from_args, build_parser
    from graal_pipeline.config import load_config

    args = build_parser().parse_args(["status"])
    config = load_config(
        cli_overrides={
            "checkpoint.old_policy": "reuse",
            "checkpoint.stale_policy": "fail",
            "checkpoint.untracked_policy": "adopt",
        }
    )

    policies = _planning_policies_from_args(args, config)

    assert (policies.old, policies.stale, policies.untracked) == (
        "reuse",
        "fail",
        "adopt",
    )


def test_first_pass_flag_selects_first_pass_target():
    from graal_pipeline.cli import _target_from_args, build_parser

    args = build_parser().parse_args(
        ["extract", "beam-asymmetry", "--first-pass", "--final-state", "eta_pi0"]
    )

    assert _target_from_args(args) == (
        "beam_asymmetry_first_pass",
        "eta_pi0",
        "beam_asymmetry",
    )


def test_resume_farm_profile_reopens_latest_isolated_validation_run(tmp_path, capsys):
    from graal_pipeline.cli import main

    results = tmp_path / "validation/farm"
    profile_run = results / "20260928T120000000000Z"
    state = profile_run / ".pipeline"
    attempt = "initial-attempt"
    (state / "runs" / attempt).mkdir(parents=True)
    (state / "runs" / attempt / "plan.json").write_text(
        json.dumps(
            {
                "target": "beam_asymmetry_first_pass",
                "final_state": "eta_pi0",
                "observable": "beam_asymmetry",
                "items": [],
            }
        )
    )
    (state / "latest.json").write_text(
        json.dumps({"run_id": attempt, "status": "FAILED"})
    )
    config = tmp_path / "pipeline.toml"
    config.write_text(
        f"""
[profiles.farm.paths]
results_dir = "{results}"

[profiles.farm.profile_settings]
claim = "full farm validation"
isolated_results = true
requires_real_fixture = false
"""
    )

    code = main(
        [
            "resume",
            "--profile",
            "farm",
            "--config",
            str(config),
            "--dry-run",
            "--non-interactive",
            "--old-policy",
            "rebuild",
            "--stale-policy",
            "rebuild",
            "--untracked-policy",
            "rebuild",
        ]
    )

    captured = capsys.readouterr()
    assert code == 0, captured.err
    assert "beam_asymmetry_first_pass" in captured.out
    assert "no previous run is available to resume" not in captured.err


def test_isolated_profile_does_not_reuse_output_run_id_for_execution_attempt(
    tmp_path, monkeypatch
):
    from types import SimpleNamespace

    from graal_pipeline.cli import main

    results = tmp_path / "validation/farm"
    config = tmp_path / "pipeline.toml"
    config.write_text(
        f"""
[profiles.farm.paths]
results_dir = "{results}"

[profiles.farm.profile_settings]
claim = "full farm validation"
isolated_results = true
requires_real_fixture = false
"""
    )
    captured = {}

    def record_run(*args, **kwargs):
        captured["run_id"] = kwargs["run_id"]
        captured["state_directory"] = Path(kwargs["state_directory"])
        return SimpleNamespace(exit_code=0)

    monkeypatch.setattr("graal_pipeline.cli.run_plan", record_run)

    code = main(
        [
            "validate",
            "full",
            "--profile",
            "farm",
            "--config",
            str(config),
            "--non-interactive",
            "--yes",
            "--old-policy",
            "rebuild",
            "--stale-policy",
            "rebuild",
            "--untracked-policy",
            "rebuild",
        ]
    )

    assert code == 0
    assert captured["run_id"] is None
    assert captured["state_directory"].parent.parent == results


def test_status_farm_profile_inspects_latest_isolated_validation_run(
    tmp_path, monkeypatch
):
    import graal_pipeline.cli as cli

    results = tmp_path / "validation/farm"
    older = results / "20260928T110000000000Z"
    latest = results / "20260928T120000000000Z"
    for index, profile_run in enumerate((older, latest)):
        state = profile_run / ".pipeline"
        state.mkdir(parents=True)
        (state / "latest.json").write_text(
            json.dumps({"run_id": f"attempt-{index}", "status": "FAILED"})
        )
        os.utime(state / "latest.json", ns=(index + 1, index + 1))
    config = tmp_path / "pipeline.toml"
    config.write_text(
        f"""
[profiles.farm.paths]
results_dir = "{results}"

[profiles.farm.profile_settings]
claim = "full farm validation"
isolated_results = true
requires_real_fixture = false
"""
    )
    real_builder = cli.build_stage_invocation
    invoked_results = set()

    def record_results(stage, pipeline_config, **kwargs):
        invoked_results.add(pipeline_config.paths.results_dir)
        return real_builder(stage, pipeline_config, **kwargs)

    monkeypatch.setattr(cli, "build_stage_invocation", record_results)

    code = cli.main(
        [
            "status",
            "--profile",
            "farm",
            "--config",
            str(config),
            "--final-state",
            "eta_pi0",
        ]
    )

    assert code == 0
    assert invoked_results == {latest}


def test_status_state_dir_selects_requested_isolated_validation_run(
    tmp_path, monkeypatch
):
    import graal_pipeline.cli as cli

    results = tmp_path / "validation/farm"
    requested = results / "20260928T110000000000Z"
    newer = results / "20260928T120000000000Z"
    for profile_run in (requested, newer):
        state = profile_run / ".pipeline"
        state.mkdir(parents=True)
        (state / "latest.json").write_text(
            json.dumps({"run_id": "attempt", "status": "FAILED"})
        )
    config = tmp_path / "pipeline.toml"
    config.write_text(
        f"""
[profiles.farm.paths]
results_dir = "{results}"

[profiles.farm.profile_settings]
claim = "full farm validation"
isolated_results = true
requires_real_fixture = false
"""
    )
    real_builder = cli.build_stage_invocation
    invoked_results = set()

    def record_results(stage, pipeline_config, **kwargs):
        invoked_results.add(pipeline_config.paths.results_dir)
        return real_builder(stage, pipeline_config, **kwargs)

    monkeypatch.setattr(cli, "build_stage_invocation", record_results)

    code = cli.main(
        [
            "status",
            "--profile",
            "farm",
            "--config",
            str(config),
            "--state-dir",
            str(requested / ".pipeline"),
        ]
    )

    assert code == 0
    assert invoked_results == {requested}
