#!/usr/bin/env bash
# ============================================================
# GRAAL full pipeline, from raw detector files to reconstructed events.
#
# Usage:
#   ./run_pipeline.sh [--test-data] [--nevents N] [--input-tree NOME]
#                     [--skip-preanalysis] [--force-preanalysis]
#                     [--skip-selection]
#                     [--skip-mc] [--force-mc]
#                     [--skip-features] [--skip-grid-search]
#                     [--grid-search-niter N] [--skip-train]
#                     [--skip-reco] [--help]
#
# Stages:
#   1. Pre-analisi         raw/          -> pre_analyzed/  (albero h80)
#   2. Selezione eventi    pre_analyzed/ -> selected/      (albero h85)
#   3. MC generation       (saltata se i 6 canali esistono gia')
#   4. Build features stage-1
#   5. Grid search iper-parametri
#   6. Training BDT stage-1
#   7. Ricostruzione       selected/     -> analyzed/      (chi2 e BDT)
#
# La ricostruzione e' in fondo perche' il run BDT ha bisogno del modello,
# che esiste solo dopo lo stage 6.
#
# --test-data ridirige le cartelle dei dati del rivelatore su test_data/.
# Il Monte Carlo e il modello restano quelli veri.
#
# --input-tree serve per una selected/ prodotta da una versione precedente del
# codice, quando la preselezione lasciava all'albero il nome h80 ereditato dalla
# pre-analisi. Sui dati nuovi non serve: il default e' gia' h85. Esempio, per
# ricostruire e basta una selected/ vecchia:
#   ./run_pipeline.sh --input-tree h80 --skip-preanalysis --skip-selection \
#                     --skip-mc --skip-features --skip-grid-search --skip-train
# ============================================================

set -euo pipefail

# ---- defaults ----
NEVENTS=1000000

# The tree the reconstruction reads out of selected/. The preselection writes
# h85; an older selected/ may still carry the h80 name it inherited from the
# pre-analysis, and --input-tree is how you point at it.
INPUT_TREE="h85"

MC_DIR="04_mc_simulation"
MC_DATA_DIR="${MC_DIR}/data"
BDT_DIR="05_analysis_bdt"
MODEL_DIR="${BDT_DIR}/model"
FEATURES_FILE="${BDT_DIR}/data/features_stage1.npz"
CS_CSV="${MC_DIR}/cross_sections/cross_sections.csv"
CUTS_DIR="01_pre_analysis/cuts"
PREANALYSIS_MACRO="01_pre_analysis/PreAnalysis.C"

# Detector-data directories. --test-data moves all four under test_data/.
RAW_DIR="graal_data"
PRE_DIR="pre_analyzed"
SELECTED_DIR="selected"
ANALYZED_DIR="analyzed"

TEST_DATA=0
SKIP_PREANALYSIS=0
FORCE_PREANALYSIS=0
SKIP_SELECTION=0
SKIP_MC=0
FORCE_MC=0
SKIP_FEATURES=0
SKIP_GRID_SEARCH=0
SKIP_TRAIN=0
SKIP_RECO=0
GRID_SEARCH_NITER=30

# ---- parse args ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        --test-data)          TEST_DATA=1;            shift   ;;
        --nevents)            NEVENTS="$2";           shift 2 ;;
        --input-tree)         INPUT_TREE="$2";        shift 2 ;;
        --skip-preanalysis)   SKIP_PREANALYSIS=1;     shift   ;;
        --force-preanalysis)  FORCE_PREANALYSIS=1;    shift   ;;
        --skip-selection)     SKIP_SELECTION=1;       shift   ;;
        --skip-mc)            SKIP_MC=1;              shift   ;;
        --force-mc)           FORCE_MC=1;             shift   ;;
        --skip-features)      SKIP_FEATURES=1;        shift   ;;
        --skip-grid-search)   SKIP_GRID_SEARCH=1;     shift   ;;
        --grid-search-niter)  GRID_SEARCH_NITER="$2"; shift 2 ;;
        --skip-train)         SKIP_TRAIN=1;           shift   ;;
        --skip-reco)          SKIP_RECO=1;            shift   ;;
        --help|-h)
            # Print the header block between the two ==== delimiters. Bound to the
            # delimiter rather than a line number, which silently truncated the
            # help every time the header grew.
            sed -n '3,/^# =\{10,\}$/{/^# =\{10,\}$/d; p;}' "$0"
            exit 0 ;;
        *) echo "Unknown option: $1"; exit 1 ;;
    esac
done

if [[ $TEST_DATA -eq 1 ]]; then
    RAW_DIR="test_data/raw"
    PRE_DIR="test_data/pre_analyzed"
    SELECTED_DIR="test_data/selected"
    ANALYZED_DIR="test_data/analyzed"
fi

PYTHON="${PYTHON:-python}"
ROOT_EXEC="${ROOT_EXEC:-root}"

TOTAL_STAGES=7
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
if [[ $TEST_DATA -eq 1 ]]; then
    echo "  MODALITA' TEST: dati del rivelatore sotto test_data/"
fi
echo "=================================================="

# ---- Preflight: the pipeline packages must be importable ----
# A bare `python` (the default for $PYTHON) that has not run `pip install -e .`
# fails every `python -m ...` call with ModuleNotFoundError. Fail here, loudly,
# before anything expensive runs.
if ! ${PYTHON} -c "import mc_simulation, analysis, analysis_bdt, event_selector" 2>/dev/null; then
    echo "ERROR: i pacchetti della pipeline non sono importabili."
    echo "       Esegui:  pip install -e ."
    echo "       (oppure passa il tuo interprete:  PYTHON=.venv/bin/python ./run_pipeline.sh ...)"
    exit 1
fi

# ---- Stage 1: pre-analisi (raw -> h80) ----
if [[ $SKIP_PREANALYSIS -eq 0 ]]; then
    stage 1 "Pre-analisi (raw -> h80)"

    # Reuse what is already there: on real data this stage is long, and it must
    # not restart by accident. Same policy as the MC in stage 3.
    n_pre=0
    if [[ -d "${PRE_DIR}" ]]; then
        n_pre=$(find "${PRE_DIR}" -maxdepth 1 -name 'pre_*.root' | wc -l | tr -d ' ')
    fi

    if [[ $n_pre -gt 0 && $FORCE_PREANALYSIS -eq 0 ]]; then
        echo "  -> ${n_pre} file gia' in ${PRE_DIR}/: pre-analisi SALTATA"
        echo "     (--force-preanalysis per rifarla)"
    else
        if [[ ! -d "${RAW_DIR}" ]]; then
            echo "ERROR: la cartella dei dati grezzi non esiste: ${RAW_DIR}/"
            if [[ $TEST_DATA -eq 1 ]]; then
                echo "       Copiaci 1-2 run da /data/graal/graal_data/ — vedi test_data/README.md"
            fi
            exit 1
        fi

        mkdir -p "${PRE_DIR}"
        ${ROOT_EXEC} -l -b -q -e \
            "gROOT->ProcessLine(\".L ${PREANALYSIS_MACRO}\"); AnalyzeAll(\"${RAW_DIR}\", \"${PRE_DIR}\", \"${CUTS_DIR}\");"

        stage_done
    fi
else
    echo "[1/${TOTAL_STAGES}] Pre-analisi — saltata"
fi

# ---- Stage 2: selezione eventi (h80 -> h85) ----
if [[ $SKIP_SELECTION -eq 0 ]]; then
    stage 2 "Selezione eventi (h80 -> h85)"

    ${PYTHON} -u -m event_selector.select_events \
        --input-dir  "${PRE_DIR}" \
        --output-dir "${SELECTED_DIR}"

    stage_done
else
    echo "[2/${TOTAL_STAGES}] Selezione eventi — saltata"
fi

# ---- Stage 3: MC generation ----
stage 3 "MC generation"

# mc_status exits 0 when all six channels are on disk, 1 when any is missing,
# 2 on an internal error. set -e is guarded off for this one call so we can
# inspect the exit code; anything outside {0,1} is fatal and must NEVER be
# silently read as "MC missing" (that would trigger hours of regeneration).
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

# ---- Stage 4: build features ----
if [[ $SKIP_FEATURES -eq 0 ]]; then
    stage 4 "Build features stage-1"

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
    echo "[4/${TOTAL_STAGES}] Build features — saltato"
fi

# ---- Stage 5: grid search ----
if [[ $SKIP_TRAIN -eq 0 && $SKIP_GRID_SEARCH -eq 0 ]]; then
    stage 5 "Grid search iper-parametri (n_iter=${GRID_SEARCH_NITER})"

    if [[ ! -f "$FEATURES_FILE" ]]; then
        echo "ERROR: ${FEATURES_FILE} not found (run stage 4 first)"
        exit 1
    fi

    ${PYTHON} -u -m analysis_bdt.grid_search_stage1 \
        --features "$FEATURES_FILE" \
        --out-dir  "$MODEL_DIR" \
        --n-iter   "$GRID_SEARCH_NITER"

    stage_done
else
    echo "[5/${TOTAL_STAGES}] Grid search — saltato"
fi

# ---- Stage 6: train stage-1 BDT ----
if [[ $SKIP_TRAIN -eq 0 ]]; then
    stage 6 "Training BDT stage-1"

    if [[ ! -f "$FEATURES_FILE" ]]; then
        echo "ERROR: ${FEATURES_FILE} not found (run stage 4 first)"
        exit 1
    fi

    HYPERPARAMS_FLAG=()
    if [[ -f "${MODEL_DIR}/best_hyperparams.json" ]]; then
        HYPERPARAMS_FLAG=("--hyperparams" "${MODEL_DIR}/best_hyperparams.json")
        echo "  Usando iper-parametri da ${MODEL_DIR}/best_hyperparams.json"
    fi

    ${PYTHON} -u -m analysis_bdt.train_bdt_stage1 \
        --features "$FEATURES_FILE" \
        --out-dir  "$MODEL_DIR" \
        "${HYPERPARAMS_FLAG[@]}"

    stage_done
    echo ""
    echo "  Threshold : $(cat "${MODEL_DIR}/stage1_threshold.txt")"
    echo "  Metrics:"
    cat "${MODEL_DIR}/stage1_metrics.txt"
else
    echo "[6/${TOTAL_STAGES}] BDT training — saltato"
fi

# ---- Stage 7: ricostruzione, chi2 e BDT ----
if [[ $SKIP_RECO -eq 0 ]]; then
    stage 7 "Ricostruzione eta pi0 (chi2 + BDT)"

    mkdir -p "${ANALYZED_DIR}"

    echo "  -> analisi standard (chi2)"
    ${PYTHON} -u -m analysis.reconstruct_eta_pi0_chi2 \
        --input-dir   "${SELECTED_DIR}" \
        --input-tree  "${INPUT_TREE}" \
        --output-file "${ANALYZED_DIR}/reco_eta_pi0_chi2.root"

    echo "  -> analisi con gate BDT stage-1"
    ${PYTHON} -u -m analysis.reconstruct_eta_pi0_bdt \
        --input-dir   "${SELECTED_DIR}" \
        --input-tree  "${INPUT_TREE}" \
        --output-file "${ANALYZED_DIR}/reco_eta_pi0_bdt.root" \
        --model-dir   "${MODEL_DIR}"

    stage_done
else
    echo "[7/${TOTAL_STAGES}] Ricostruzione — saltata"
fi

echo ""
echo "=================================================="
echo "  Pipeline complete."
echo "=================================================="
