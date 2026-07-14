#!/usr/bin/env bash
# ============================================================
# GRAAL full pipeline: MC -> stage-1 BDT -> preselection -> reconstruction
#
# Usage:
#   ./run_pipeline.sh [--nevents N] [--force-mc] [--skip-mc]
#                     [--skip-features] [--skip-grid-search]
#                     [--grid-search-niter N] [--skip-train]
#                     [--skip-selection] [--skip-reco] [--help]
#
# Stages:
#   1. MC generation      (skipped automatically if all 6 channels exist)
#   2. Stage-1 features   (build_background_features)
#   3. Grid search        (grid_search_stage1)
#   4. Train stage-1 BDT  (train_bdt_stage1)
#   5. Event preselection (h80 -> h85)
#   6. Reconstruction     (chi2 and BDT-gated, both)
#
# Stages 5-6 need real pre-analysed data in pre_analyzed/. Without it they are
# skipped and the MC + BDT half of the pipeline still runs.
# ============================================================

set -euo pipefail

# ---- defaults ----
NEVENTS=1000000
MC_DIR="04_mc_simulation"
MC_DATA_DIR="${MC_DIR}/data"
BDT_DIR="05_analysis_bdt"
OUT_DIR="${BDT_DIR}/model"
FEATURES_FILE="${BDT_DIR}/data/features_stage1.npz"
CS_CSV="${MC_DIR}/cross_sections/cross_sections.csv"

PRE_DIR="pre_analyzed"
SELECTED_DIR="selected"
RECO_DIR="03_analysis/data"

FORCE_MC=0
SKIP_MC=0
SKIP_FEATURES=0
SKIP_TRAIN=0
SKIP_GRID_SEARCH=0
SKIP_SELECTION=0
SKIP_RECO=0
GRID_SEARCH_NITER=30

# ---- parse args ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        --nevents)            NEVENTS="$2";           shift 2 ;;
        --force-mc)           FORCE_MC=1;             shift   ;;
        --skip-mc)            SKIP_MC=1;              shift   ;;
        --skip-features)      SKIP_FEATURES=1;        shift   ;;
        --skip-train)         SKIP_TRAIN=1;           shift   ;;
        --skip-grid-search)   SKIP_GRID_SEARCH=1;     shift   ;;
        --grid-search-niter)  GRID_SEARCH_NITER="$2"; shift 2 ;;
        --skip-selection)     SKIP_SELECTION=1;       shift   ;;
        --skip-reco)          SKIP_RECO=1;            shift   ;;
        --help|-h)
            sed -n '2,22p' "$0"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

PYTHON="${PYTHON:-python}"
ROOT_EXEC="${ROOT_EXEC:-root}"

TOTAL_STAGES=6
_STAGE_T0=0

stage() {
    local n=$1 desc=$2
    _STAGE_T0=$(date +%s)
    echo ""
    echo "[${n}/${TOTAL_STAGES}] ${desc}  ($(date '+%H:%M:%S'))"
}

stage_done() {
    local T1
    T1=$(date +%s)
    echo "    -> completato in $((T1 - _STAGE_T0))s"
}

echo "=================================================="
echo "  GRAAL pipeline  (N=${NEVENTS})"
echo "=================================================="

# ---- Preflight: the pipeline packages must be importable ----
# A bare `python` (the default for $PYTHON) that has not run `pip install -e .`
# fails every `python -m mc_simulation...` / `python -m analysis...` call with
# ModuleNotFoundError. mc_status.py used to exit 1 on that crash too, which is
# indistinguishable from "an MC channel is missing" -- the pipeline would then
# regenerate six channels at full statistics (hours) while the real files sat
# untouched on disk, and stage 2 would die with the same ModuleNotFoundError
# anyway. Fail loud here, before anything expensive runs.
if ! ${PYTHON} -c "import mc_simulation, analysis, analysis_bdt" 2>/dev/null; then
    echo "ERROR: i pacchetti della pipeline non sono importabili."
    echo "       Esegui:  pip install -e ."
    echo "       (oppure passa il tuo interprete:  PYTHON=.venv/bin/python ./run_pipeline.sh ...)"
    exit 1
fi

# ---- Stage 1: MC generation ----
stage 1 "MC generation"

# mc_status exits 0 when all six channels are on disk, 1 when any is missing,
# 2 on an internal error. set -e is guarded off for this one call so we can
# inspect the exit code ourselves; anything outside {0,1} is fatal and must
# NEVER be silently treated as "MC missing" (that is what used to trigger
# hours of needless regeneration).
MC_ALL_PRESENT=0
set +e
${PYTHON} -m mc_simulation.mc_status --data-dir "${MC_DATA_DIR}"
mc_status_rc=$?
set -e

case "$mc_status_rc" in
    0) MC_ALL_PRESENT=1 ;;
    1) MC_ALL_PRESENT=0 ;;
    *)
        echo "ERROR: mc_simulation.mc_status ha fallito internamente (exit ${mc_status_rc})."
        echo "       Non e' un 'MC mancante': controlla l'errore sopra prima di rigenerare."
        exit 1
        ;;
esac

NEED_MC=1
if [[ $SKIP_MC -eq 1 ]]; then
    echo "    -> --skip-mc: generazione saltata"
    NEED_MC=0
elif [[ $FORCE_MC -eq 1 ]]; then
    echo "    -> --force-mc: rigenero comunque"
elif [[ $MC_ALL_PRESENT -eq 1 ]]; then
    NEED_MC=0
fi

if [[ $NEED_MC -eq 1 ]]; then
    mkdir -p "${MC_DATA_DIR}"

    channels=(
        "generate_eta_pi0_dataset.C"
        "generate_pi0pi0_dataset.C"
        "generate_3pi0_dataset.C"
        "generate_eta_2pi0_dataset.C"
        "generate_omega_pi0_dataset.C"
        "generate_etaprime_dataset.C"
    )
    # The macros write their .root file into the current directory, so run them
    # from the data dir and reach back up for the macro itself.
    pushd "${MC_DATA_DIR}" > /dev/null
    for macro in "${channels[@]}"; do
        echo "  -> ${macro%.C} (N=${NEVENTS})"
        ${ROOT_EXEC} -l -b -q "../${macro}(${NEVENTS})"
    done
    popd > /dev/null

    stage_done
fi

# ---- Stage 2: build features ----
if [[ $SKIP_FEATURES -eq 0 ]]; then
    stage 2 "Build features stage-1"

    SIG="${MC_DATA_DIR}/eta_pi0_mc.root"
    BG_FILES=(
        "${MC_DATA_DIR}/pi0pi0_mc.root"
        "${MC_DATA_DIR}/3pi0_mc.root"
        "${MC_DATA_DIR}/eta_2pi0_mc.root"
        "${MC_DATA_DIR}/omega_pi0_mc.root"
        "${MC_DATA_DIR}/etaprime_mc.root"
    )

    for f in "$SIG" "${BG_FILES[@]}"; do
        if [[ ! -f "$f" ]]; then
            echo "ERROR: missing MC file $f (run without --skip-mc)"
            exit 1
        fi
    done

    mkdir -p "$(dirname "${FEATURES_FILE}")"

    ${PYTHON} -u -m analysis_bdt.build_background_features \
        --signal      "$SIG" \
        --backgrounds "${BG_FILES[@]}" \
        --cs-csv      "$CS_CSV" \
        --output      "$FEATURES_FILE"

    stage_done
else
    echo "[2/${TOTAL_STAGES}] Build features — saltato"
fi

# ---- Stage 3: grid search ----
if [[ $SKIP_TRAIN -eq 0 && $SKIP_GRID_SEARCH -eq 0 ]]; then
    stage 3 "Grid search iper-parametri (n_iter=${GRID_SEARCH_NITER})"

    if [[ ! -f "$FEATURES_FILE" ]]; then
        echo "ERROR: ${FEATURES_FILE} not found (run stage 2 first)"
        exit 1
    fi

    ${PYTHON} -u -m analysis_bdt.grid_search_stage1 \
        --features "$FEATURES_FILE" \
        --out-dir  "$OUT_DIR" \
        --n-iter   "$GRID_SEARCH_NITER"

    stage_done
else
    echo "[3/${TOTAL_STAGES}] Grid search — saltato"
fi

# ---- Stage 4: train stage-1 BDT ----
if [[ $SKIP_TRAIN -eq 0 ]]; then
    stage 4 "Training BDT stage-1"

    if [[ ! -f "$FEATURES_FILE" ]]; then
        echo "ERROR: ${FEATURES_FILE} not found (run stage 2 first)"
        exit 1
    fi

    HYPERPARAMS_FLAG=()
    if [[ -f "${OUT_DIR}/best_hyperparams.json" ]]; then
        HYPERPARAMS_FLAG=("--hyperparams" "${OUT_DIR}/best_hyperparams.json")
        echo "  Usando iper-parametri da ${OUT_DIR}/best_hyperparams.json"
    fi

    ${PYTHON} -u -m analysis_bdt.train_bdt_stage1 \
        --features "$FEATURES_FILE" \
        --out-dir  "$OUT_DIR" \
        "${HYPERPARAMS_FLAG[@]}"

    stage_done
    echo ""
    echo "  Threshold : $(cat "${OUT_DIR}/stage1_threshold.txt")"
    echo "  Metrics:"
    cat "${OUT_DIR}/stage1_metrics.txt"
else
    echo "[4/${TOTAL_STAGES}] BDT training — saltato"
fi

# ---- Stage 5: event preselection (h80 -> h85) ----
if [[ $SKIP_SELECTION -eq 0 ]]; then
    if [[ ! -d "${PRE_DIR}" ]]; then
        echo ""
        echo "[5/${TOTAL_STAGES}] Preselezione — saltata: ${PRE_DIR}/ non esiste"
        echo "    (dati reali pre-analizzati assenti su questa macchina)"
        SKIP_RECO=1
    else
        stage 5 "Preselezione eventi (h80 -> h85)"
        ${PYTHON} -u -m event_selector.select_events \
            --input-dir  "${PRE_DIR}" \
            --output-dir "${SELECTED_DIR}"
        stage_done
    fi
else
    echo "[5/${TOTAL_STAGES}] Preselezione — saltata"
fi

# ---- Stage 6: reconstruction, chi2 and BDT ----
if [[ $SKIP_RECO -eq 0 ]]; then
    stage 6 "Ricostruzione eta pi0 (chi2 + BDT)"

    echo "  -> analisi standard (chi2)"
    ${PYTHON} -u -m analysis.reconstruct_eta_pi0_chi2 \
        --input-dir   "${SELECTED_DIR}" \
        --output-file "${RECO_DIR}/reco_eta_pi0_chi2.root"

    echo "  -> analisi con gate BDT stage-1"
    ${PYTHON} -u -m analysis.reconstruct_eta_pi0_bdt \
        --input-dir   "${SELECTED_DIR}" \
        --output-file "${RECO_DIR}/reco_eta_pi0_bdt.root" \
        --model-dir   "${OUT_DIR}"

    stage_done
else
    echo "[6/${TOTAL_STAGES}] Ricostruzione — saltata"
fi

echo ""
echo "=================================================="
echo "  Pipeline complete."
echo "=================================================="
