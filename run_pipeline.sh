#!/usr/bin/env bash
# ============================================================
# GRAAL full MC + BDT pipeline
#
# Usage:
#   ./run_pipeline.sh [--nevents N] [--out-dir DIR] [--skip-mc]
#                     [--skip-features] [--skip-grid-search]
#                     [--grid-search-niter N] [--skip-train] [--help]
#
# Steps:
#   1. Generate ROOT MC (signal + 5 background channels)
#   2. Build stage-1 BDT features  (build_background_features.py)
#   3. Grid search iper-parametri  (grid_search_stage1.py)
#   4. Train stage-1 BDT           (train_bdt_stage1.py)
# ============================================================

set -euo pipefail

# ---- defaults ----
NEVENTS=1000000
SIM_DIR="simulation"
OUT_DIR="analysis/ml/model"
FEATURES_FILE="features_stage1.npz"
CS_CSV="${SIM_DIR}/cross_sections.csv"

SKIP_MC=0
SKIP_FEATURES=0
SKIP_TRAIN=0
SKIP_GRID_SEARCH=0
GRID_SEARCH_NITER=30

# ---- parse args ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        --nevents)     NEVENTS="$2";       shift 2 ;;
        --out-dir)     OUT_DIR="$2";       shift 2 ;;
        --skip-mc)     SKIP_MC=1;          shift   ;;
        --skip-features) SKIP_FEATURES=1; shift   ;;
        --skip-train)  SKIP_TRAIN=1;       shift   ;;
        --skip-grid-search)   SKIP_GRID_SEARCH=1;           shift   ;;
        --grid-search-niter)  GRID_SEARCH_NITER="$2";       shift 2 ;;
        --help|-h)
            sed -n '2,12p' "$0"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

PYTHON="${PYTHON:-python}"
ROOT_EXEC="${ROOT_EXEC:-root}"

# ---- helpers ----
_STAGE_T0=0

stage() {
    local n=$1 total=$2 desc=$3
    _STAGE_T0=$(date +%s)
    echo ""
    echo "[${n}/${total}] ${desc}  ($(date '+%H:%M:%S'))"
}

stage_done() {
    local T1
    T1=$(date +%s)
    echo "    -> completato in $((T1 - _STAGE_T0))s"
}

TOTAL_STAGES=4

echo "=================================================="
echo "  GRAAL pipeline  (N=${NEVENTS})"
echo "=================================================="

# ---- Step 1: MC generation ----
if [[ $SKIP_MC -eq 0 ]]; then
    stage 1 $TOTAL_STAGES "MC generation (${NEVENTS} eventi per canale)"
    cd "$SIM_DIR"

    channels=(
        "generate_eta_pi0_dataset.C"
        "generate_pi0pi0_dataset.C"
        "generate_3pi0_dataset.C"
        "generate_eta_2pi0_dataset.C"
        "generate_omega_pi0_dataset.C"
        "generate_etaprime_dataset.C"
    )
    for macro in "${channels[@]}"; do
        name="${macro%.C}"
        echo "  -> ${name} (N=${NEVENTS})"
        ${ROOT_EXEC} -l -b -q "${macro}(${NEVENTS})"
    done

    cd ..
    stage_done
else
    echo "[1/${TOTAL_STAGES}] MC generation — saltato"
fi

# ---- Step 2: build features ----
if [[ $SKIP_FEATURES -eq 0 ]]; then
    stage 2 $TOTAL_STAGES "Build features stage-1"

    SIG="${SIM_DIR}/eta_pi0_mc.root"
    BG_FILES=(
        "${SIM_DIR}/pi0pi0_mc.root"
        "${SIM_DIR}/3pi0_mc.root"
        "${SIM_DIR}/eta_2pi0_mc.root"
        "${SIM_DIR}/omega_pi0_mc.root"
        "${SIM_DIR}/etaprime_mc.root"
    )

    for f in "$SIG" "${BG_FILES[@]}"; do
        if [[ ! -f "$f" ]]; then
            echo "ERROR: missing file $f (run with --skip-mc=0 first)"
            exit 1
        fi
    done

    python -u -m analysis.ml.build_background_features \
        --signal        "$SIG" \
        --backgrounds   "${BG_FILES[@]}" \
        --cs-csv        "$CS_CSV" \
        --output        "$FEATURES_FILE"

    stage_done
else
    echo "[2/${TOTAL_STAGES}] Feature building — saltato"
fi

# ---- Step 3: grid search (opzionale) ----
if [[ $SKIP_TRAIN -eq 0 && $SKIP_GRID_SEARCH -eq 0 ]]; then
    stage 3 $TOTAL_STAGES "Grid search iper-parametri (n_iter=${GRID_SEARCH_NITER})"

    if [[ ! -f "$FEATURES_FILE" ]]; then
        echo "ERROR: ${FEATURES_FILE} not found (run step 2 first)"
        exit 1
    fi

    python -u -m analysis.ml.grid_search_stage1 \
        --features  "$FEATURES_FILE" \
        --out-dir   "$OUT_DIR" \
        --n-iter    "$GRID_SEARCH_NITER"

    stage_done
elif [[ $SKIP_TRAIN -eq 0 ]]; then
    echo "[3/${TOTAL_STAGES}] Grid search — saltato"
fi

# ---- Step 4: train BDT ----
if [[ $SKIP_TRAIN -eq 0 ]]; then
    stage 4 $TOTAL_STAGES "Training BDT stage-1"

    if [[ ! -f "$FEATURES_FILE" ]]; then
        echo "ERROR: ${FEATURES_FILE} not found (run step 2 first)"
        exit 1
    fi

    HYPERPARAMS_FLAG=""
    if [[ -f "${OUT_DIR}/best_hyperparams.json" ]]; then
        HYPERPARAMS_FLAG="--hyperparams ${OUT_DIR}/best_hyperparams.json"
        echo "  Usando iper-parametri da ${OUT_DIR}/best_hyperparams.json"
    fi

    python -u -m analysis.ml.train_bdt_stage1 \
        --features  "$FEATURES_FILE" \
        --out-dir   "$OUT_DIR" \
        ${HYPERPARAMS_FLAG}

    stage_done
    echo ""
    echo "  Threshold : $(cat "${OUT_DIR}/stage1_threshold.txt")"
    echo ""
    echo "  Metrics:"
    cat "${OUT_DIR}/stage1_metrics.txt"
else
    echo "[4/${TOTAL_STAGES}] BDT training — saltato"
fi

echo ""
echo "=================================================="
echo "  Pipeline complete."
echo "  Next: python analysis/reconstruct_eta_pi0.py"
echo "=================================================="
