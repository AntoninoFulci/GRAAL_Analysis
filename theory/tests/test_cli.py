import json
import os
from pathlib import Path
import subprocess
import sys


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
    )


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
