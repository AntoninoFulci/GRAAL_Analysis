#!/usr/bin/env bash
# Run beam-asymmetry reconstruction/extraction chain without stopping after errors.
#
# Typical server launch:
#   nohup bash scripts/run_beam_asymmetry_overnight.sh \
#     >> results/beam_asymmetry_overnight.out 2>&1 &
#
# Every path can be overridden through environment variables defined below.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT" || exit 1

PYTHON_BIN="${PYTHON_BIN:-python}"
PREANALYSIS_DIR="${PREANALYSIS_DIR:-data/02_pre_analyzed/pre_analisi}"
MANIFEST_FILE="${MANIFEST_FILE:-config/run_manifest.csv}"
FLUX_FILE="${FLUX_FILE:-data/00_external/flux.root}"
FLUX_PROGRESS_EVERY_EVENTS="${FLUX_PROGRESS_EVERY_EVENTS:-100000}"
FLUX_THREADS="${FLUX_THREADS:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || echo 1)}"
FLUX_SAMPLES_PER_RUN_STRIP="${FLUX_SAMPLES_PER_RUN_STRIP:-256}"
SELECTED_DIR="${SELECTED_DIR:-/data/graal/selected}"
SIGNAL_MC_INPUT="${SIGNAL_MC_INPUT:-03_mc_simulation/data/eta_pi0_mc.root}"
SIGNAL_MC_SELECTED_DIR="${SIGNAL_MC_SELECTED_DIR:-data/signal_mc_selected}"
RECO_DIR="${RECO_DIR:-results/reco}"
CALIBRATION_DIR="${CALIBRATION_DIR:-results/strip_energy_flux}"
ASYMMETRY_FIRST_DIR="${ASYMMETRY_FIRST_DIR:-results/beam_asymmetry_first_pass}"
ASYMMETRY_DIR="${ASYMMETRY_DIR:-results/beam_asymmetry}"
LOG_DIR="${LOG_DIR:-results/logs/beam_asymmetry_overnight}"
BOOTSTRAP_REPLICAS="${BOOTSTRAP_REPLICAS:-500}"
BOOTSTRAP_SEED="${BOOTSTRAP_SEED:-1208}"
RUN_STAMP="${RUN_STAMP:-$(date +%Y%m%d_%H%M%S)}"
OVERNIGHT_LOCK_DIR="${OVERNIGHT_LOCK_DIR:-results/locks/beam_asymmetry_overnight.lock}"

LOCK_ACQUIRED=0
cleanup_lock() {
    if [[ $LOCK_ACQUIRED -eq 1 && -f "$OVERNIGHT_LOCK_DIR/pid" ]]; then
        local owner
        owner="$(<"$OVERNIGHT_LOCK_DIR/pid")"
        if [[ "$owner" == "$$" ]]; then
            rm -f "$OVERNIGHT_LOCK_DIR/pid"
            rmdir "$OVERNIGHT_LOCK_DIR" 2>/dev/null || true
        fi
    fi
}
trap cleanup_lock EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

mkdir -p "$(dirname "$OVERNIGHT_LOCK_DIR")"
if ! mkdir "$OVERNIGHT_LOCK_DIR" 2>/dev/null; then
    lock_owner="unknown"
    [[ -f "$OVERNIGHT_LOCK_DIR/pid" ]] && lock_owner="$(<"$OVERNIGHT_LOCK_DIR/pid")"
    echo "ERROR: overnight runner already running or stale lock exists: $OVERNIGHT_LOCK_DIR (owner PID: $lock_owner)" >&2
    echo "Inspect the owner process; remove only a confirmed stale lock." >&2
    exit 73
fi
printf '%s\n' "$$" > "$OVERNIGHT_LOCK_DIR/pid"
LOCK_ACQUIRED=1

mkdir -p "$LOG_DIR" "$RECO_DIR"

STEP_NAMES=()
STEP_STATES=()
STEP_DETAILS=()
FAILED_ANY=0

record_result() {
    STEP_NAMES+=("$1")
    STEP_STATES+=("$2")
    STEP_DETAILS+=("$3")
}

run_step() {
    local key="$1"
    local title="$2"
    local expected_output="$3"
    shift 3
    local log_file="$LOG_DIR/${RUN_STAMP}_${key}.log"
    local command_status

    {
        echo "============================================================"
        echo "STEP: $title"
        echo "START: $(date --iso-8601=seconds 2>/dev/null || date)"
        printf 'COMMAND:'
        printf ' %q' "$@"
        printf '\n'
        echo "LOG: $log_file"
        echo "============================================================"
        "$@"
    } 2>&1 | tee "$log_file"
    command_status=${PIPESTATUS[0]}

    if [[ $command_status -eq 0 && ! -f "$expected_output" ]]; then
        command_status=98
        echo "ERROR: command returned 0 but expected output is missing: $expected_output" \
            | tee -a "$log_file" >&2
    fi

    if [[ $command_status -eq 0 ]]; then
        echo "OK: $key -> $expected_output" | tee -a "$log_file"
        record_result "$key" "OK" "$log_file"
    else
        echo "ERROR: $key failed with exit code $command_status; continuing." \
            | tee -a "$log_file" >&2
        record_result "$key" "FAILED" "exit=$command_status log=$log_file"
        FAILED_ANY=1
    fi
    return "$command_status"
}

skip_step() {
    local key="$1"
    local reason="$2"
    local log_file="$LOG_DIR/${RUN_STAMP}_${key}.log"
    echo "SKIPPED: $key — $reason" | tee "$log_file" >&2
    record_result "$key" "SKIPPED" "$reason"
}

RAW_FILE="$RECO_DIR/reco_eta_pi0_chi2_raw.root"
RAW_BDT_FILE="$RECO_DIR/reco_eta_pi0_bdt_raw.root"
FIT_FILE="$RECO_DIR/reco_eta_pi0_bdt_fit.root"
SIDEBAND_FILE="$RECO_DIR/reco_eta_pi0_bdt_sideband.root"
SIGNAL_MC_FILE="$RECO_DIR/reco_eta_pi0_signal_mc.root"
SIGNAL_MC_SELECTED_FILE="$SIGNAL_MC_SELECTED_DIR/eta_pi0_mc_selected.root"

raw_ok=0
raw_bdt_ok=0
fit_ok=0
sideband_ok=0
signal_mc_ok=0
signal_mc_adapter_ok=0
calibration_ok=0
selected_input_ok=0

if [[ -d "$SELECTED_DIR" ]] && compgen -G "$SELECTED_DIR/*.root" >/dev/null; then
    selected_input_ok=1
    echo "Selected data input: $SELECTED_DIR"
else
    selected_log="$LOG_DIR/${RUN_STAMP}_selected_input.log"
    echo "ERROR: no selected ROOT files found in $SELECTED_DIR" \
        | tee "$selected_log" >&2
    record_result selected_input FAILED "$selected_log"
    FAILED_ANY=1
fi

run_step \
    flux_calibration \
    "Strip-energy and final-flux calibration" \
    "$CALIBRATION_DIR/strip_energy_flux_qa.json" \
    "$PYTHON_BIN" scripts/build_strip_energy_flux.py \
    --preanalysis-dir "$PREANALYSIS_DIR" \
    --manifest "$MANIFEST_FILE" \
    --flux "$FLUX_FILE" \
    --output-dir "$CALIBRATION_DIR" \
    --progress-every-events "$FLUX_PROGRESS_EVERY_EVENTS" \
    --samples-per-run-strip "$FLUX_SAMPLES_PER_RUN_STRIP" \
    --threads "$FLUX_THREADS"
[[ $? -eq 0 ]] && calibration_ok=1

if [[ $selected_input_ok -eq 1 ]]; then
    run_step \
        raw \
        "Raw chi2 reconstruction" \
        "$RAW_FILE" \
        "$PYTHON_BIN" -m reconstruction.reconstruct_eta_pi0_chi2 \
        --input-dir "$SELECTED_DIR" \
        --no-fit \
        --output-file "$RAW_FILE"
    [[ $? -eq 0 ]] && raw_ok=1

    run_step \
        raw_bdt \
        "Raw plus BDT reconstruction" \
        "$RAW_BDT_FILE" \
        "$PYTHON_BIN" -m reconstruction.reconstruct_eta_pi0_bdt \
        --input-dir "$SELECTED_DIR" \
        --no-fit \
        --output-file "$RAW_BDT_FILE"
    [[ $? -eq 0 ]] && raw_bdt_ok=1

    run_step \
        raw_bdt_fit \
        "Raw plus BDT plus kinematic-fit reconstruction" \
        "$FIT_FILE" \
        "$PYTHON_BIN" -m reconstruction.reconstruct_eta_pi0_bdt \
        --input-dir "$SELECTED_DIR" \
        --output-file "$FIT_FILE"
    [[ $? -eq 0 ]] && fit_ok=1
else
    skip_step raw "selected data input is unavailable"
    skip_step raw_bdt "selected data input is unavailable"
    skip_step raw_bdt_fit "selected data input is unavailable"
fi

if [[ $calibration_ok -eq 1 && $raw_bdt_ok -eq 1 ]]; then
    run_step \
        first_pass \
        "First raw plus BDT asymmetry extraction" \
        "$ASYMMETRY_FIRST_DIR/beam_asymmetry.root" \
        "$PYTHON_BIN" -m observable_extraction.beam_asymmetry \
        --raw-bdt "$RAW_BDT_FILE" \
        --calibration-dir "$CALIBRATION_DIR" \
        --output-dir "$ASYMMETRY_FIRST_DIR"
else
    skip_step first_pass "flux_calibration or raw_bdt failed in this run"
fi

if [[ $selected_input_ok -eq 1 ]]; then
    run_step \
        sideband \
        "Broad sideband reconstruction on data" \
        "$SIDEBAND_FILE" \
        "$PYTHON_BIN" -m reconstruction.reconstruct_eta_pi0_bdt_sideband \
        --input-dir "$SELECTED_DIR" \
        --output-file "$SIDEBAND_FILE"
    [[ $? -eq 0 ]] && sideband_ok=1
else
    skip_step sideband "selected data input is unavailable"
fi

run_step \
    signal_mc_adapter \
    "Adapt generated signal MC to detector-like h85" \
    "$SIGNAL_MC_SELECTED_FILE" \
    "$PYTHON_BIN" -m reconstruction.prepare_signal_mc_selected \
    --input-file "$SIGNAL_MC_INPUT" \
    --output-dir "$SIGNAL_MC_SELECTED_DIR" \
    --threads "$FLUX_THREADS"
[[ $? -eq 0 ]] && signal_mc_adapter_ok=1

if [[ $signal_mc_adapter_ok -eq 1 ]]; then
    run_step \
        signal_mc \
        "Broad sideband reconstruction on signal MC" \
        "$SIGNAL_MC_FILE" \
        "$PYTHON_BIN" -m reconstruction.reconstruct_eta_pi0_bdt_sideband \
        --input-dir "$SIGNAL_MC_SELECTED_DIR" \
        --output-file "$SIGNAL_MC_FILE"
    [[ $? -eq 0 ]] && signal_mc_ok=1
else
    skip_step signal_mc "signal_mc_adapter failed in this run"
fi

if [[ $calibration_ok -eq 1 && $raw_ok -eq 1 && $raw_bdt_ok -eq 1 && $fit_ok -eq 1 \
      && $sideband_ok -eq 1 && $signal_mc_ok -eq 1 ]]; then
    run_step \
        full_extraction \
        "Full corrected beam-asymmetry extraction" \
        "$ASYMMETRY_DIR/beam_asymmetry.root" \
        "$PYTHON_BIN" -m observable_extraction.beam_asymmetry \
        --raw "$RAW_FILE" \
        --raw-bdt "$RAW_BDT_FILE" \
        --raw-bdt-fit "$FIT_FILE" \
        --sideband "$SIDEBAND_FILE" \
        --signal-mc "$SIGNAL_MC_FILE" \
        --calibration-dir "$CALIBRATION_DIR" \
        --output-dir "$ASYMMETRY_DIR" \
        --estimator both \
        --bootstrap-replicas "$BOOTSTRAP_REPLICAS" \
        --bootstrap-seed "$BOOTSTRAP_SEED"
else
    skip_step full_extraction \
        "calibration or one or more required reconstruction/sideband steps failed"
fi

echo
echo "================ OVERNIGHT SUMMARY ================"
for index in "${!STEP_NAMES[@]}"; do
    printf '%-7s %-24s %s\n' \
        "${STEP_STATES[$index]}" \
        "${STEP_NAMES[$index]}" \
        "${STEP_DETAILS[$index]}"
done
echo "Logs: $LOG_DIR"

if [[ $FAILED_ANY -ne 0 ]]; then
    echo "One or more steps failed. Inspect FAILED logs." >&2
    exit 1
fi

echo "All requested steps completed."
exit 0
