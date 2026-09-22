"""Contract for failure-tolerant overnight beam-asymmetry runner."""

from pathlib import Path
import os
import subprocess


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/run_beam_asymmetry_overnight.sh"


def _fake_python(tmp_path: Path) -> Path:
    executable = tmp_path / "fake-python"
    executable.write_text(
        """#!/usr/bin/env bash
set -u
printf '%s\n' "$*" >> "${OVERNIGHT_TEST_CALLS:?}"
all_args="$*"
if [[ "$*" == *"${OVERNIGHT_FAIL_MATCH:-never-match}"* ]]; then
    echo "synthetic overnight failure" >&2
    exit 42
fi
output_file=""
output_dir=""
while [[ $# -gt 0 ]]; do
    case "$1" in
        --output-file) output_file="$2"; shift 2 ;;
        --output-dir) output_dir="$2"; shift 2 ;;
        *) shift ;;
    esac
done
if [[ -n "$output_file" ]]; then
    mkdir -p "$(dirname "$output_file")"
    touch "$output_file"
fi
if [[ -n "$output_dir" ]]; then
    mkdir -p "$output_dir"
    if [[ "$all_args" == *"build_strip_energy_flux.py"* ]]; then
        touch "$output_dir/strip_energy_flux_qa.json"
    else
        touch "$output_dir/beam_asymmetry.root"
    fi
fi
exit 0
"""
    )
    executable.chmod(0o755)
    return executable


def _environment(tmp_path: Path, fake_python: Path) -> dict[str, str]:
    env = os.environ.copy()
    env.update(
        PYTHON_BIN=str(fake_python),
        PREANALYSIS_DIR=str(tmp_path / "preanalysis"),
        MANIFEST_FILE=str(tmp_path / "run_manifest.csv"),
        FLUX_FILE=str(tmp_path / "flux.root"),
        FLUX_PROGRESS_EVERY_EVENTS="123",
        SELECTED_DIR=str(tmp_path / "selected"),
        SIGNAL_MC_SELECTED_DIR=str(tmp_path / "signal_mc_selected"),
        RECO_DIR=str(tmp_path / "reco"),
        CALIBRATION_DIR=str(tmp_path / "calibration"),
        ASYMMETRY_FIRST_DIR=str(tmp_path / "asymmetry_first"),
        ASYMMETRY_DIR=str(tmp_path / "asymmetry"),
        LOG_DIR=str(tmp_path / "logs"),
        RUN_STAMP="test-run",
        BOOTSTRAP_REPLICAS="7",
        OVERNIGHT_TEST_CALLS=str(tmp_path / "calls.log"),
    )
    return env


def test_runner_continues_independent_steps_and_summarizes_failure(tmp_path):
    fake_python = _fake_python(tmp_path)
    env = _environment(tmp_path, fake_python)
    env["OVERNIGHT_FAIL_MATCH"] = "reco_eta_pi0_bdt_raw.root"

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "FAILED  raw_bdt" in combined
    assert "SKIPPED first_pass" in combined
    assert "SKIPPED full_extraction" in combined
    calls = (tmp_path / "calls.log").read_text()
    assert "reconstruction.reconstruct_eta_pi0_chi2" in calls
    assert "reco_eta_pi0_bdt_fit.root" in calls
    assert "reconstruction.reconstruct_eta_pi0_bdt_sideband" in calls
    assert "reco_eta_pi0_signal_mc.root" in calls


def test_runner_executes_full_chain_and_writes_step_logs(tmp_path):
    fake_python = _fake_python(tmp_path)
    env = _environment(tmp_path, fake_python)

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK      full_extraction" in result.stdout
    calls = (tmp_path / "calls.log").read_text()
    assert "scripts/build_strip_energy_flux.py" in calls
    assert "--progress-every-events 123" in calls
    assert "--bootstrap-replicas 7" in calls
    assert len(calls.splitlines()) == 8
    logs = sorted((tmp_path / "logs").glob("test-run_*.log"))
    assert len(logs) == 8


def test_calibration_failure_does_not_stop_reconstruction(tmp_path):
    fake_python = _fake_python(tmp_path)
    env = _environment(tmp_path, fake_python)
    env["OVERNIGHT_FAIL_MATCH"] = "build_strip_energy_flux.py"

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "FAILED  flux_calibration" in combined
    assert "OK      raw" in combined
    assert "OK      raw_bdt" in combined
    assert "OK      sideband" in combined
    assert "SKIPPED first_pass" in combined
    assert "SKIPPED full_extraction" in combined
