#!/usr/bin/env bash
# ============================================================
# GRAAL full pipeline, from raw detector files to reconstructed events.
#
# Usage:
#   ./run_pipeline.sh [--test-data] [--nevents N] [--input-tree NOME]
#                     [--signal-channel CANALE] [--signal-prior F]
#                     [--skip-preanalysis] [--force-preanalysis]
#                     [--skip-selection]
#                     [--skip-mc] [--force-mc]
#                     [--skip-features] [--skip-grid-search]
#                     [--grid-search-niter N] [--skip-train]
#                     [--skip-reco] [--skip-plots] [--help]
#
# Stages:
#   1. Pre-analisi         data/graal_data/   -> data/pre_analyzed/ (albero h80)
#   2. Selezione eventi    data/pre_analyzed/ -> data/selected/     (albero h85)
#   3. MC generation       (saltata se i 9 canali esistono gia')
#   4. Build features stage-1
#   5. Grid search iper-parametri
#   6. Training BDT stage-1
#   7. Ricostruzione       data/selected/     -> results/reco/      (chi2 e BDT)
#   8. Plot                results/reco/      -> results/plots/    (Dalitz + masse)
#
# La ricostruzione e' in fondo perche' il run BDT ha bisogno del modello,
# che esiste solo dopo lo stage 6.
#
# --test-data ridirige su test_data/ sia i dati del rivelatore (raw,
# pre_analyzed, selected) sia i risultati (results/reco, results/plots). Il
# Monte Carlo e il modello restano quelli veri.
#
# I dati del rivelatore stanno sotto data/; i risultati sotto results/
# (results/reco per gli alberi ricostruiti, results/plots per le figure).
#
# --input-tree di default e' 'auto': la ricostruzione prende l'albero di
# preselezione che i file hanno davvero, h85 o il piu' vecchio h80 ereditato
# dalla pre-analisi. Passa un nome esplicito solo per forzarne uno.
#
# --signal-channel sceglie quale canale il BDT impara a riconoscere; gli altri
# otto diventano il suo fondo. Vale per gli stage 4-6 (feature, grid search,
# training). Lo stage 7 ricostruisce eta+pi0.
#
# --signal-prior e' la quota del peso di training che va al segnale (default
# 0.5, bilanciato). E' una SCELTA, non fisica: la sezione d'urto del segnale e'
# cio' che questa analisi misura, quindi non puo' essere anche un suo ingresso.
# I fondi fra loro sono invece pesati per sezione d'urto misurata.
#
# Lo stage 4 misura lo spettro del fascio da SELECTED_DIR e ci riponderа sopra
# il MC: i generatori estraggono un fascio piatto, GRAAL ha luce laser
# retrodiffusa Compton con un bordo.
#
# Esempio, per rifare solo la ricostruzione su una selected/ gia' pronta:
#   ./run_pipeline.sh --skip-preanalysis --skip-selection \
#                     --skip-mc --skip-features --skip-grid-search --skip-train
# ============================================================

set -euo pipefail

# ---- defaults ----
NEVENTS=1000000

# The tree the reconstruction reads out of selected/. "auto" takes whichever
# known preselection tree the files carry: the selection writes h85, an older
# selected/ still has the h80 it inherited from the pre-analysis. Name one
# explicitly to override the detection.
INPUT_TREE="auto"

# Which channel the stage-1 BDT is trained to pick out. Any of the nine in
# graal_common.channels can play signal; the rest become its background.
SIGNAL_CHANNEL="eta_pi0"

# Share of the training weight given to the signal class. A CHOICE, not physics:
# the signal cross-section is what this analysis measures, so it cannot also be
# an input to it. 0.5 = balanced against all backgrounds together.
SIGNAL_PRIOR="0.5"

MC_DIR="03_mc_simulation"
MC_DATA_DIR="${MC_DIR}/data"
BDT_DIR="04_bdt_training"
MODEL_DIR="${BDT_DIR}/model"
FEATURES_FILE="${BDT_DIR}/data/features_stage1.npz"
BEAM_SPECTRUM_FILE="${BDT_DIR}/data/beam_spectrum.npz"
CUTS_DIR="01_pre_analysis/cuts"
PREANALYSIS_MACRO="01_pre_analysis/PreAnalysis.C"

# Detector data in, results out. --test-data moves them all under test_data/.
#
# data/ is what the detector produced and the selection made of it: an input.
# results/ is what this analysis concluded: reco/ holds the reconstructed trees,
# plots/ the figures drawn from them. The two are separate because they age
# differently — data/ is given, results/ is rebuilt whenever the code changes.
#
# The reconstruction used to write into data/analyzed/, and the plots into
# 06_plots/plots/, next to the code that drew them. Results living inside a
# source folder is how they end up committed, and how a figure ends up
# disagreeing with the code beside it.
RAW_DIR="data/graal_data"
PRE_DIR="data/pre_analyzed"
SELECTED_DIR="data/selected"
RECO_DIR="results/reco"
PLOTS_DIR="results/plots"

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
SKIP_PLOTS=0
GRID_SEARCH_NITER=30

# ---- parse args ----
while [[ $# -gt 0 ]]; do
    case "$1" in
        --test-data)          TEST_DATA=1;            shift   ;;
        --nevents)            NEVENTS="$2";           shift 2 ;;
        --input-tree)         INPUT_TREE="$2";        shift 2 ;;
        --signal-channel)     SIGNAL_CHANNEL="$2";    shift 2 ;;
        --signal-prior)       SIGNAL_PRIOR="$2";      shift 2 ;;
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
        --skip-plots)         SKIP_PLOTS=1;           shift   ;;
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
    RECO_DIR="test_data/results/reco"
    PLOTS_DIR="test_data/results/plots"
fi

PYTHON="${PYTHON:-python}"
ROOT_EXEC="${ROOT_EXEC:-root}"

TOTAL_STAGES=8
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
if ! ${PYTHON} -c "import graal_common, event_selector, mc_simulation, bdt_training, reconstruction, plots" 2>/dev/null; then
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
                echo "       Creala e copiaci 1-2 run da /data/graal/graal_data/ (vedi wiki, Testing)"
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

# mc_status exits 0 when all nine channels are on disk, 1 when any is missing,
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

    # The channel list comes from the registry, so a channel added there cannot
    # be forgotten here and quietly never generated.
    read -r -a channels <<< "$(${PYTHON} -c \
        'from graal_common.channels import CHANNEL_NAMES; print(" ".join(CHANNEL_NAMES))')"

    # The macros write their .root file into the current directory, so run them
    # from the data dir and reach back up for the macro itself.
    pushd "${MC_DATA_DIR}" > /dev/null
    for channel in "${channels[@]}"; do
        echo "  -> ${channel} (N=${NEVENTS})"
        ${ROOT_EXEC} -l -b -q "../generate_${channel}_dataset.C(${NEVENTS})"
    done
    popd > /dev/null

    stage_done
fi

# ---- Stage 4: build features ----
if [[ $SKIP_FEATURES -eq 0 ]]; then
    stage 4 "Build features stage-1 (segnale: ${SIGNAL_CHANNEL})"

    mkdir -p "$(dirname "${FEATURES_FILE}")"

    # The beam the generators drew is flat; the beam GRAAL had is Compton
    # backscattered laser light with an edge. Measure the real one off the
    # selected data and reweight the MC onto it. Cheap next to the feature
    # build, so it is not cached: it is measured from whatever selected/ holds
    # now.
    #
    # Not optional, and it did not used to be a hard error. The channel weights
    # are cross-sections integrated over this flux — without it omega_pi0 and
    # etaprime, which open in the last few percent of the beam range, have no
    # defensible weight at all. Carrying on with a flat beam is how they came to
    # be overweighted in the first place.
    if [[ ! -d "${SELECTED_DIR}" ]]; then
        echo "ERRORE: ${SELECTED_DIR}/ non esiste."
        echo "        I pesi dei canali sono sezioni d'urto integrate sul flusso"
        echo "        del fascio misurato, e senza i dati selezionati non c'e'"
        echo "        flusso da misurare. Esegui prima lo stage di selezione."
        exit 1
    fi

    echo "  -> misuro lo spettro del fascio da ${SELECTED_DIR}/"
    ${PYTHON} -u -m bdt_training.beam_spectrum \
        --selected-dir "${SELECTED_DIR}" \
        --tree         "${INPUT_TREE}" \
        --output       "${BEAM_SPECTRUM_FILE}"

    # Which files are needed, and which channel is the background, are the
    # registry's business now: it resolves them from --signal-channel, and
    # stage 3 above has already checked all nine are on disk.
    ${PYTHON} -u -m bdt_training.build_background_features \
        --mc-dir         "$MC_DATA_DIR" \
        --signal-channel "$SIGNAL_CHANNEL" \
        --signal-prior   "$SIGNAL_PRIOR" \
        --beam-spectrum  "${BEAM_SPECTRUM_FILE}" \
        --output         "$FEATURES_FILE"

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

    ${PYTHON} -u -m bdt_training.grid_search_stage1 \
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

    ${PYTHON} -u -m bdt_training.train_bdt_stage1 \
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

    mkdir -p "${RECO_DIR}"

    echo "  -> analisi standard (chi2)"
    ${PYTHON} -u -m reconstruction.reconstruct_eta_pi0_chi2 \
        --input-dir   "${SELECTED_DIR}" \
        --input-tree  "${INPUT_TREE}" \
        --output-file "${RECO_DIR}/reco_eta_pi0_chi2.root"

    echo "  -> analisi con gate BDT stage-1"
    ${PYTHON} -u -m reconstruction.reconstruct_eta_pi0_bdt \
        --input-dir   "${SELECTED_DIR}" \
        --input-tree  "${INPUT_TREE}" \
        --output-file "${RECO_DIR}/reco_eta_pi0_bdt.root" \
        --model-dir   "${MODEL_DIR}"

    stage_done
else
    echo "[7/${TOTAL_STAGES}] Ricostruzione — saltata"
fi

# ---- Stage 8: plot (Dalitz + masse invarianti) ----
if [[ $SKIP_PLOTS -eq 0 ]]; then
    RECO_CHI2="${RECO_DIR}/reco_eta_pi0_chi2.root"
    RECO_BDT="${RECO_DIR}/reco_eta_pi0_bdt.root"

    if [[ ! -f "${RECO_CHI2}" || ! -f "${RECO_BDT}" ]]; then
        echo ""
        echo "[8/${TOTAL_STAGES}] Plot — saltato: manca almeno un file ricostruito in ${RECO_DIR}/"
        echo "    (i plot confrontano le due analisi: servono entrambi)"
    else
        stage 8 "Plot (Dalitz + masse invarianti)"

        ${PYTHON} -u -m plots.dalitz \
            --chi2    "${RECO_CHI2}" \
            --bdt     "${RECO_BDT}" \
            --out-dir "${PLOTS_DIR}"

        stage_done
    fi
else
    echo "[8/${TOTAL_STAGES}] Plot — saltato"
fi

echo ""
echo "=================================================="
echo "  Pipeline complete."
echo "=================================================="
