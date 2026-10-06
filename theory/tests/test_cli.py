import json
import os
import subprocess
import sys
from pathlib import Path

THEORY_ROOT = Path(__file__).resolve().parents[1]


def _run_cli(*args):
    env = os.environ.copy()
    env["PYTHONPATH"] = str(THEORY_ROOT / "src")
    return subprocess.run(
        [sys.executable, "-m", "graal_theory.cli", *args],
        cwd=THEORY_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_figure4_full_command_dispatches_explicit_numerical_settings(tmp_path, monkeypatch):
    from graal_theory import cli
    observed = []
    def fake(args):
        observed.append((args.output, args.energy_order, args.sobol_power,
                         args.replicas, args.workers, args.mode))
        return 2
    monkeypatch.setattr(cli, "_figure4_full", fake, raising=False)
    result = cli.main(["figure4-full", "--output", str(tmp_path/"run"),
                       "--energy-order", "4", "--sobol-power", "6",
                       "--replicas", "8", "--workers", "4", "--mode", "grid"])
    assert result == 2
    assert observed == [(tmp_path/"run", 4, 6, 8, 4, "grid")]


def test_figure4_bin_task_keeps_replica_checks_for_panel_assembly(monkeypatch):
    from types import SimpleNamespace
    from graal_theory import cli

    class FlatModel:
        masses = (.547862, .1349768, .93827208816)
        parameters = SimpleNamespace(proton_mass_gev=masses[2])

        def polarized_matrix_element_squared(self, sample, epsilon):
            import numpy as np
            return np.ones(len(sample.initial))

    monkeypatch.setattr(cli, "_figure4_model", lambda *args: FlatModel(), raising=False)
    key, checks = cli._figure4_bin_task((THEORY_ROOT/"references", 3, "p_eta", 5,
        1, 4, tuple(range(2026, 2034)), "direct", 64, 48))
    assert key == (3, "p_eta", 5)
    assert max(abs(a-b) for a, b in zip(checks[0].mass_range_gev, (1.6, 1.64))) < 1e-12
    assert len(checks[3]) == 8


def test_predict_cli_writes_partial_bundle(tmp_path):
    result = _run_cli(
        "predict", "--energy", "1.2", "--sobol-power", "8",
        "--output", str(tmp_path / "run"),
    )
    assert result.returncode == 0, result.stderr
    assert "partial" in result.stdout
    manifest = json.loads((tmp_path / "run" / "manifest.json").read_text())
    assert manifest["scope"] == "partial:delta1700_eta_delta_tree_eq43"


def test_predict_cli_rejects_duplicate_energies(tmp_path):
    result = _run_cli(
        "predict", "--energy", "1.2", "--energy", "1.2",
        "--output", str(tmp_path / "run"),
    )
    assert result.returncode != 0
    assert "duplicate" in result.stderr.lower()
    assert not (tmp_path / "run").exists()


def test_validate_cli_reports_scientific_failure_with_artifacts(tmp_path):
    run = tmp_path / "run"
    predicted = _run_cli(
        "predict", "--energy", "1.2", "--energy", "1.202", "--sobol-power", "8",
        "--output", str(run),
    )
    assert predicted.returncode == 0, predicted.stderr
    validated = _run_cli("validate", "--bundle", str(run))
    assert validated.returncode == 2, validated.stderr
    comparison = json.loads((run / "validation" / "comparison.json").read_text())
    assert comparison["status"] == "failed"
    assert set(comparison) >= {"figure14_tree", "factor_two_1202", "phase_space", "convergence"}
    assert (run / "validation" / "invariant_masses.pdf").is_file()
    assert (run / "validation" / "total_cross_section.pdf").is_file()
    manifest = json.loads((run / "manifest.json").read_text())
    assert manifest["validation_state"] == "failed"


def test_validate_cli_requires_both_reference_energies(tmp_path):
    run = tmp_path / "run"
    predicted = _run_cli("predict", "--energy", "1.2", "--sobol-power", "8", "--output", str(run))
    assert predicted.returncode == 0, predicted.stderr
    validated = _run_cli("validate", "--bundle", str(run))
    assert validated.returncode == 1
    assert "1.202" in validated.stderr
    assert json.loads((run / "manifest.json").read_text())["validation_state"] == "pending"


def test_validate_cli_accepts_extra_below_threshold_energy(tmp_path):
    run = tmp_path / "run"
    predicted = _run_cli(
        "predict", "--energy", "0.5", "--energy", "1.2", "--energy", "1.202",
        "--sobol-power", "8", "--output", str(run),
    )
    assert predicted.returncode == 0, predicted.stderr
    validated = _run_cli("validate", "--bundle", str(run))
    assert validated.returncode == 2, validated.stderr
    phase = json.loads((run / "validation" / "comparison.json").read_text())["phase_space"]
    assert phase["passed"]
    assert phase["energies"][0]["quadrature_volume_gev2"] == 0.0


def test_validate_cli_rejects_bundle_with_missing_source_locator(tmp_path):
    run = tmp_path / "run"
    predicted = _run_cli(
        "predict", "--energy", "1.2", "--energy", "1.202", "--sobol-power", "8",
        "--output", str(run),
    )
    assert predicted.returncode == 0, predicted.stderr
    path = run / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["parameters"]["eta_mass"]["locator"] = ""
    path.write_text(json.dumps(manifest))
    validated = _run_cli("validate", "--bundle", str(run))
    assert validated.returncode == 1
    assert "locator" in validated.stderr
    assert json.loads(path.read_text())["validation_state"] == "pending"


def test_pilot_panel5_cli_writes_labeled_partial_overlay(tmp_path):
    published = THEORY_ROOT.parent / "test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv"
    output = tmp_path / "panel5"
    result = _run_cli(
        "pilot-panel5", "--published-csv", str(published),
        "--sobol-power", "14", "--energy-nodes", "9", "--output", str(output),
    )
    assert result.returncode == 0, result.stderr
    assert (output / "panel5.pdf").is_file()
    prediction = json.loads((output / "prediction.json").read_text())
    assert prediction["scope"] == "partial:delta1700_eta_delta_tree_eq43"
    assert prediction["energy_weighting"] == "uniform"
    assert prediction["beam_asymmetry_sign"] == "vertical_minus_horizontal"
    assert len(prediction["sigma"]) == 10
    assert prediction["sigma"][:2] == [None, None]
    assert len(prediction["published_points"]) == 4
    assert len(prediction["theory_parameters_sha256"]) == 64
    assert "g1_prime" in prediction["theory_parameters"]
    assert prediction["code_revision"]["commit"]
    assert prediction["published_source"]["doi"] == "10.1103/PhysRevLett.100.052003"
    assert prediction["published_source"]["uncertainties"] == "statistical only"


def test_pilot_panel5_cli_rejects_unreliable_resolution(tmp_path):
    published = THEORY_ROOT.parent / "test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv"
    output = tmp_path / "panel5"
    result = _run_cli(
        "pilot-panel5", "--published-csv", str(published),
        "--sobol-power", "8", "--energy-nodes", "3", "--output", str(output),
    )
    assert result.returncode == 1
    assert "sobol-power" in result.stderr
    assert not output.exists()


def test_pilot_panel5_flux_option_requires_manifest(tmp_path):
    published = THEORY_ROOT.parent / "test_data/beam_asymmetry/ajaka2008_figure4_digitized.csv"
    result = _run_cli(
        "pilot-panel5", "--published-csv", str(published),
        "--flux-root", str(tmp_path / "flux.root"),
        "--output", str(tmp_path / "panel5"),
    )
    assert result.returncode == 1
    assert "run-manifest" in result.stderr
    assert not (tmp_path / "panel5").exists()
