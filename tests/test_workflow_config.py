"""YAML and CLI must resolve to the same validated launch configuration."""
from pathlib import Path
import subprocess
import sys

import pytest

from graal_workflow import cli, models, paths, planning, resources


def test_yaml_and_cli_build_identical_plans_from_another_cwd(tmp_path, monkeypatch):
    config = tmp_path / "campaign.yaml"
    config.write_text(
        "mode: production\noutput_dir: results/new-campaign\n"
        "preanalysis_dir: inputs\ncpus: 4\nextraction_workers: 2\n"
        "seed: 71\nphi_bins: 16\nflux_study: off\nforce_mc: true\n"
    )
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    monkeypatch.chdir(elsewhere)
    yaml_args = cli.parse_args([str(config)])
    cli_args = cli.parse_args([
        "--mode", "production", "--output-dir", str(tmp_path / "results/new-campaign"),
        "--preanalysis-dir", str(tmp_path / "inputs"), "--cpus", "4",
        "--extraction-workers", "2", "--seed", "71", "--phi-bins", "16", "--force-mc",
    ])
    assert yaml_args.output_dir == tmp_path / "results/new-campaign"
    assert yaml_args.preanalysis_dir == tmp_path / "inputs"
    assert yaml_args.force_mc is True
    assert yaml_args.flux_study == "off"
    assert yaml_args.best_binning is False

    def plan(args):
        mode = paths.mode_config(args.mode, tmp_path)
        locations = paths.build_paths(mode, args.output_dir)
        stages = planning.build_pipeline_plan(
            mode, locations, models.PreflightResult("/usr/bin/root"), phi_bins=args.phi_bins,
        )
        return resources.configure_resources(
            stages, cpus=args.cpus, seed=args.seed, extraction_workers=args.extraction_workers,
        )

    assert plan(yaml_args) == plan(cli_args)


def test_explicit_cli_overrides_yaml_including_false_and_default_values(tmp_path, monkeypatch):
    config = tmp_path / "campaign.yaml"
    config.write_text(
        "mode: production\ncpus: 8\nphi_bins: 16\nseed: 71\n"
        "force_mc: true\nbest_binning: true\nrequire_current_preanalysis: true\n"
        "output_dir: yaml-results\n"
    )
    monkeypatch.chdir(tmp_path)
    args = cli.parse_args([
        str(config), "--mode", "test_data", "--cpus", "2", "--phi-bins", "12",
        "--seed", "42", "--no-force-mc", "--no-best-binning",
        "--no-require-current-preanalysis", "--output-dir", "cli-results",
    ])
    assert (args.mode, args.cpus, args.phi_bins, args.seed) == ("test_data", 2, 12, 42)
    assert not args.force_mc and not args.best_binning and not args.require_current_preanalysis
    assert args.output_dir == Path("cli-results")


@pytest.mark.parametrize("option", ["repo_root", "output_dir", "preanalysis_dir", "energy_config", "flux_study_metadata"])
def test_all_yaml_paths_are_relative_to_config_directory(tmp_path, option):
    config = tmp_path / "campaign.yaml"
    config.write_text(f"mode: production\n{option}: folder with spaces/input\n")
    args = cli.parse_args([str(config)])
    assert getattr(args, option) == tmp_path / "folder with spaces/input"


def test_yaml_expands_home_but_does_not_expand_environment_variables(tmp_path):
    config = tmp_path / "campaign.yaml"
    config.write_text("mode: test_data\npreanalysis_dir: ~/inputs\noutput_dir: $HOME/output\n")
    args = cli.parse_args([str(config)])
    assert args.preanalysis_dir == Path.home() / "inputs"
    assert args.output_dir == tmp_path / "$HOME/output"


@pytest.mark.parametrize("content, error", [
    ("", "mapping"),
    ("[]", "mapping"),
    ("mode: [production", "YAML"),
    ("mode: production\nmode: test_data\n", "duplicate"),
    ("mode: production\ncpuss: 4\n", "cpuss"),
    ("mode: production\nconfig_file: other.yaml\n", "config_file"),
    ("mode: production\n1: value\n", "string"),
    ("mode: farm\n", "mode"),
    ("mode: production\ncpus: '4'\n", "cpus"),
    ("mode: production\ncpus: true\n", "cpus"),
    ("mode: production\nseed: 4.5\n", "seed"),
    ("mode: production\nforce_bdt: 'false'\n", "force_bdt"),
    ("mode: production\noutput_dir: null\n", "output_dir"),
    ("mode: production\noutput_dir: ''\n", "output_dir"),
    ("mode: production\nenergy_config: {uv: [1.1, 1.5]}\n", "energy_config"),
    ("mode: production\nextraction_workers: 0\n", "extraction_workers"),
    ("mode: production\nphi_bins: 10\n", "phi_bins"),
    ("mode: production\nflux_study: automatic\n", "flux_study"),
    ("mode: production\ncolor: blue\n", "color"),
    ("mode: production\n---\nmode: test_data\n", "YAML"),
    ("!!python/object/apply:os.system ['echo unsafe']\n", "YAML"),
])
def test_invalid_yaml_fails_before_execution_even_with_cli_override(tmp_path, capsys, content, error):
    config = tmp_path / "campaign.yaml"
    config.write_text(content)
    with pytest.raises(SystemExit) as caught:
        cli.main([str(config), "--mode", "test_data", "--cpus", "2"])
    assert caught.value.code == 2
    diagnostic = capsys.readouterr().err
    assert str(config) in diagnostic
    assert error in diagnostic
    assert not (tmp_path / "results").exists()


def test_missing_config_is_reported_without_traceback(tmp_path, capsys):
    absent = tmp_path / "absent.yaml"
    with pytest.raises(SystemExit) as caught:
        cli.main([str(absent)])
    assert caught.value.code == 2
    diagnostic = capsys.readouterr().err
    assert str(absent) in diagnostic and "Traceback" not in diagnostic


def test_mode_required_after_merging_and_no_defaults_leak_between_calls(tmp_path):
    config = tmp_path / "campaign.yaml"
    config.write_text("cpus: 4\n")
    assert cli.parse_args([str(config), "--mode", "production"]).cpus == 4
    for arguments in ([], [str(config)]):
        with pytest.raises(SystemExit) as caught:
            cli.parse_args(arguments)
        assert caught.value.code == 2
    assert cli.parse_args(["--mode", "test_data"]).force_mc is False


@pytest.mark.parametrize("cli_root", [False, True])
def test_script_loads_yaml_and_reaches_existing_repo_validation(tmp_path, cli_root):
    config = tmp_path / "campaign.yaml"
    config.write_text("mode: test_data\nrepo_root: missing-checkout\noutput_dir: blocked-output\n")
    script = Path(__file__).resolve().parents[1] / "scripts/run_pipeline.py"
    overrides = ["--repo-root", str(tmp_path)] if cli_root else []
    result = subprocess.run([
        sys.executable, "-B", str(script), str(config), *overrides,
    ], cwd=tmp_path, capture_output=True, text=True)
    assert result.returncode == 1
    assert "invalid repository root" in result.stderr
    assert "Traceback" not in result.stderr


def test_shipped_yaml_example_resolves_checkout_and_production_output():
    root = Path(__file__).resolve().parents[1]
    args = cli.parse_args([str(root / "config/pipeline.yaml")])
    assert args.mode == "production"
    assert args.repo_root == root
    assert args.output_dir == root / "results/production"
    assert args.flux_study == "off"
