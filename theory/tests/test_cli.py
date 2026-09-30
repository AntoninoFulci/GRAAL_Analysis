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
