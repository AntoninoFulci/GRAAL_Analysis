#!/usr/bin/env bash
# ============================================================
# GRAAL full MC + BDT pipeline
#
# Usage:
#   ./run_pipeline.sh [--nevents N] [--out-dir DIR] [--skip-mc]
#                     [--skip-features] [--skip-train] [--help]
#
# Steps:
#   1. Generate ROOT MC (signal + 5 background channels)
#   2. Build stage-1 BDT features  (build_background_features.py)
#   3. Train stage-1 BDT           (train_bdt_stage1.py)
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

# ---- parse args ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        --nevents)     NEVENTS="$2";       shift 2 ;;
        --out-dir)     OUT_DIR="$2";       shift 2 ;;
        --skip-mc)     SKIP_MC=1;          shift   ;;
        --skip-features) SKIP_FEATURES=1; shift   ;;
        --skip-train)  SKIP_TRAIN=1;       shift   ;;
        --help|-h)
            sed -n '2,12p' "$0"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

PYTHON="${PYTHON:-python}"
ROOT_EXEC="${ROOT_EXEC:-root}"

echo "=================================================="
echo "  GRAAL pipeline  (N=${NEVENTS})"
echo "=================================================="

# ---- Step 1: MC generation ----
if [[ $SKIP_MC -eq 0 ]]; then
    echo ""
    echo "=== Step 1: MC generation ==="
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
    echo "  MC generation done."
else
    echo "=== Step 1: MC generation skipped ==="
fi

# ---- Step 2: build features ----
if [[ $SKIP_FEATURES -eq 0 ]]; then
    echo ""
    echo "=== Step 2: build stage-1 features ==="

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

    ${PYTHON} -m analysis.ml.build_background_features \
        --signal        "$SIG" \
        --backgrounds   "${BG_FILES[@]}" \
        --cs-csv        "$CS_CSV" \
        --output        "$FEATURES_FILE"

    echo "  Features saved to ${FEATURES_FILE}."
else
    echo "=== Step 2: feature building skipped ==="
fi

# ---- Step 3: train BDT ----
if [[ $SKIP_TRAIN -eq 0 ]]; then
    echo ""
    echo "=== Step 3: train stage-1 BDT ==="

    if [[ ! -f "$FEATURES_FILE" ]]; then
        echo "ERROR: ${FEATURES_FILE} not found (run step 2 first)"
        exit 1
    fi

    ${PYTHON} -m analysis.ml.train_bdt_stage1 \
        --features  "$FEATURES_FILE" \
        --out-dir   "$OUT_DIR"

    echo "  Model saved to ${OUT_DIR}/bdt_stage1.json"
    echo "  Threshold : $(cat ${OUT_DIR}/stage1_threshold.txt)"
    echo ""
    echo "  Metrics:"
    cat "${OUT_DIR}/stage1_metrics.txt"
else
    echo "=== Step 3: BDT training skipped ==="
fi

echo ""
echo "=================================================="
echo "  Pipeline complete."
echo "  Next: python analysis/reconstruct_eta_pi0.py"
echo "=================================================="
