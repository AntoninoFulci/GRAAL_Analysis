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
    elif [[ "$all_args" == *"event_selector.select_events"* ]]; then
        touch "$output_dir/selected_test.root"
    elif [[ "$all_args" == *"prepare_signal_mc_selected"* ]]; then
        touch "$output_dir/eta_pi0_mc_selected.root"
    else
        touch "$output_dir/beam_asymmetry.root"
    fi
fi
exit 0
"""
    )
    executable.chmod(0o755)
    return executable


def _fake_root(tmp_path: Path) -> Path:
    executable = tmp_path / "fake-root"
    executable.write_text(
        """#!/usr/bin/env bash
set -u
printf '%s\n' "$*" >> "${OVERNIGHT_TEST_ROOT_CALLS:?}"
if [[ "$*" == *"${OVERNIGHT_ROOT_FAIL_MATCH:-never-match}"* ]]; then
    echo "synthetic ROOT failure" >&2
    exit 43
fi
mkdir -p "$(dirname "${SIGNAL_MC_INPUT:?}")"
touch "${SIGNAL_MC_INPUT:?}"
"""
    )
    executable.chmod(0o755)
    return executable


def _environment(tmp_path: Path, fake_python: Path) -> dict[str, str]:
    selected_dir = tmp_path / "selected"
    selected_dir.mkdir()
    (selected_dir / "selected_2000.root").touch()
    signal_mc_input = tmp_path / "eta_pi0_mc.root"
    signal_mc_input.touch()
    fake_root = _fake_root(tmp_path)
    env = os.environ.copy()
    env.update(
        PYTHON_BIN=str(fake_python),
        ROOT_BIN=str(fake_root),
        PREANALYSIS_DIR=str(tmp_path / "preanalysis"),
        MANIFEST_FILE=str(tmp_path / "run_manifest.csv"),
        FLUX_FILE=str(tmp_path / "flux.root"),
        FLUX_PROGRESS_EVERY_EVENTS="123",
        FLUX_THREADS="3",
        SELECTED_DIR=str(selected_dir),
        SIGNAL_MC_INPUT=str(signal_mc_input),
        SIGNAL_MC_SELECTED_DIR=str(tmp_path / "signal_mc_selected"),
        RECO_DIR=str(tmp_path / "reco"),
        CALIBRATION_DIR=str(tmp_path / "calibration"),
        ASYMMETRY_FIRST_DIR=str(tmp_path / "asymmetry_first"),
        ASYMMETRY_DIR=str(tmp_path / "asymmetry"),
        LOG_DIR=str(tmp_path / "logs"),
        RUN_STAMP="test-run",
        BOOTSTRAP_REPLICAS="7",
        OVERNIGHT_LOCK_DIR=str(tmp_path / "runner.lock"),
        OVERNIGHT_TEST_CALLS=str(tmp_path / "calls.log"),
        OVERNIGHT_TEST_ROOT_CALLS=str(tmp_path / "root_calls.log"),
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
    assert "reconstruction.prepare_signal_mc_selected" in calls
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
    assert "OK      signal_mc_source" in result.stdout
    calls = (tmp_path / "calls.log").read_text()
    assert "scripts/build_strip_energy_flux.py" in calls
    assert "event_selector.select_events" in calls
    assert "--progress-every-events 123" in calls
    assert "--threads 3" in calls
    assert "--bootstrap-replicas 7" in calls
    assert "--input-file " + env["SIGNAL_MC_INPUT"] in calls
    lines = calls.splitlines()
    assert len(lines) == 10
    assert next(i for i, line in enumerate(lines) if "event_selector" in line) < next(
        i for i, line in enumerate(lines) if "reconstruct_eta_pi0_chi2" in line
    )
    logs = sorted((tmp_path / "logs").glob("test-run_*.log"))
    assert len(logs) == 11
    assert not (tmp_path / "root_calls.log").exists()
    assert not Path(env["OVERNIGHT_LOCK_DIR"]).exists()


def test_runner_defaults_to_one_million_event_progress_interval(tmp_path):
    fake_python = _fake_python(tmp_path)
    env = _environment(tmp_path, fake_python)
    env.pop("FLUX_PROGRESS_EVERY_EVENTS")

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    calls = (tmp_path / "calls.log").read_text()
    assert "--progress-every-events 1000000" in calls


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


def test_missing_signal_mc_is_generated_before_adapter(tmp_path):
    fake_python = _fake_python(tmp_path)
    env = _environment(tmp_path, fake_python)
    Path(env["SIGNAL_MC_INPUT"]).unlink()

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "OK      signal_mc_source" in result.stdout
    assert Path(env["SIGNAL_MC_INPUT"]).is_file()
    root_calls = (tmp_path / "root_calls.log").read_text()
    assert "generate_eta_pi0_dataset.C(1000000)" in root_calls
    calls = (tmp_path / "calls.log").read_text()
    assert "reconstruction.prepare_signal_mc_selected" in calls
    assert "reco_eta_pi0_signal_mc.root" in calls


def test_signal_mc_generation_failure_skips_only_mc_dependents(tmp_path):
    fake_python = _fake_python(tmp_path)
    env = _environment(tmp_path, fake_python)
    Path(env["SIGNAL_MC_INPUT"]).unlink()
    env["OVERNIGHT_ROOT_FAIL_MATCH"] = "generate_eta_pi0_dataset.C"

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "FAILED  signal_mc_source" in combined
    assert "SKIPPED signal_mc_adapter" in combined
    assert "SKIPPED signal_mc" in combined
    assert "OK      raw" in combined
    assert "SKIPPED full_extraction" in combined
    calls = (tmp_path / "calls.log").read_text()
    assert "reconstruction.prepare_signal_mc_selected" not in calls


def test_existing_lock_stops_before_any_command(tmp_path):
    fake_python = _fake_python(tmp_path)
    env = _environment(tmp_path, fake_python)
    lock_dir = Path(env["OVERNIGHT_LOCK_DIR"])
    lock_dir.mkdir()
    (lock_dir / "pid").write_text(f"{os.getpid()}\n")

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 73
    assert "already running or stale lock" in result.stderr
    assert not (tmp_path / "calls.log").exists()
    assert lock_dir.is_dir()


def test_failed_event_selection_skips_only_data_dependent_steps(tmp_path):
    fake_python = _fake_python(tmp_path)
    env = _environment(tmp_path, fake_python)
    env["OVERNIGHT_FAIL_MATCH"] = "event_selector.select_events"
    selected_dir = Path(env["SELECTED_DIR"])
    for path in selected_dir.iterdir():
        path.unlink()

    result = subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
    )

    assert result.returncode == 1
    combined = result.stdout + result.stderr
    assert "FAILED  event_selection" in combined
    assert "SKIPPED raw" in combined
    assert "SKIPPED raw_bdt" in combined
    assert "SKIPPED raw_bdt_fit" in combined
    assert "SKIPPED sideband" in combined
    assert "OK      signal_mc_adapter" in combined
    assert "OK      signal_mc" in combined
    calls = (tmp_path / "calls.log").read_text()
    assert "reconstruction.prepare_signal_mc_selected" in calls
    assert "reconstruction.reconstruct_eta_pi0_chi2" not in calls
