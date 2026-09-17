#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  ./scripts/setup.sh --mode local [--python PATH]
  ./scripts/setup.sh --mode farm --raw-target DIR --pre-target DIR [--python PATH]

Options:
  --mode local       Set up Python environment and local data directories.
  --mode farm        Also link raw and pre-analysis directories from farm storage.
  --raw-target DIR   Existing farm directory containing acquisition-period folders.
  --pre-target DIR   Existing farm directory containing pre_analisi_*.root files.
  --python PATH      Base Python interpreter (default: python3).
  --help             Show this help.
EOF
}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd -P)

MODE=""
PYTHON_BIN="python3"
RAW_TARGET=""
PRE_TARGET=""

require_value() {
    local option=$1 value=${2:-}
    if [[ -z ${value} ]]; then
        echo "ERROR: ${option} requires a value" >&2
        exit 2
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --mode)
            require_value "$1" "${2:-}"
            MODE=$2
            shift 2
            ;;
        --python)
            require_value "$1" "${2:-}"
            PYTHON_BIN=$2
            shift 2
            ;;
        --raw-target)
            require_value "$1" "${2:-}"
            RAW_TARGET=$2
            shift 2
            ;;
        --pre-target)
            require_value "$1" "${2:-}"
            PRE_TARGET=$2
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown option: $1" >&2
            exit 2
            ;;
    esac
done

if [[ ${MODE} != "local" && ${MODE} != "farm" ]]; then
    echo "ERROR: --mode must be local or farm" >&2
    exit 2
fi

if [[ ${MODE} == "farm" ]]; then
    if [[ -z ${RAW_TARGET} || -z ${PRE_TARGET} ]]; then
        echo "ERROR: farm mode requires --raw-target and --pre-target" >&2
        exit 2
    fi
    if [[ ! -d ${RAW_TARGET} ]]; then
        echo "ERROR: raw target is not a directory: ${RAW_TARGET}" >&2
        exit 1
    fi
    if [[ ! -d ${PRE_TARGET} ]]; then
        echo "ERROR: pre-analysis target is not a directory: ${PRE_TARGET}" >&2
        exit 1
    fi
    RAW_TARGET=$(cd "${RAW_TARGET}" && pwd -P)
    PRE_TARGET=$(cd "${PRE_TARGET}" && pwd -P)
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "ERROR: Python interpreter not found: ${PYTHON_BIN}" >&2
    exit 1
fi

if ! "${PYTHON_BIN}" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "ERROR: Python 3.10 or newer is required" >&2
    exit 1
fi
if ! "${PYTHON_BIN}" -c 'import ROOT'; then
    echo "ERROR: selected Python cannot import ROOT: ${PYTHON_BIN}" >&2
    exit 1
fi

VENV_DIR="${REPO_ROOT}/.venv"
if [[ -e ${VENV_DIR} && ! -x ${VENV_DIR}/bin/python ]]; then
    echo "ERROR: existing .venv is incomplete: ${VENV_DIR}" >&2
    exit 1
fi
if [[ ! -e ${VENV_DIR} ]]; then
    "${PYTHON_BIN}" -m venv --system-site-packages "${VENV_DIR}"
fi

VENV_PYTHON="${VENV_DIR}/bin/python"
if ! "${VENV_PYTHON}" -c 'import ROOT'; then
    echo "ERROR: .venv cannot import ROOT" >&2
    exit 1
fi

"${VENV_PYTHON}" -m pip install --upgrade pip
"${VENV_PYTHON}" -m pip install -r "${REPO_ROOT}/04_bdt_training/requirements.txt"
"${VENV_PYTHON}" -m pip install -e "${REPO_ROOT}"

mkdir -p \
    "${REPO_ROOT}/data/00_external" \
    "${REPO_ROOT}/data/01_raw" \
    "${REPO_ROOT}/data/02_pre_analyzed" \
    "${REPO_ROOT}/data/03_selected"

resolve_link_target() {
    local link=$1 target
    target=$(readlink "${link}")
    if [[ ${target} != /* ]]; then
        target="$(dirname "${link}")/${target}"
    fi
    if [[ ! -d ${target} ]]; then
        return 1
    fi
    (cd "${target}" && pwd -P)
}

ensure_directory_link() {
    local link=$1 target=$2 current
    if [[ -L ${link} ]]; then
        current=$(resolve_link_target "${link}") || {
            echo "ERROR: existing symlink is broken: ${link}" >&2
            exit 1
        }
        if [[ ${current} != "${target}" ]]; then
            echo "ERROR: existing symlink has different target: ${link} -> ${current}" >&2
            exit 1
        fi
        return
    fi
    if [[ -e ${link} ]]; then
        echo "ERROR: path exists and is not expected symlink: ${link}" >&2
        exit 1
    fi
    ln -s "${target}" "${link}"
}

if [[ ${MODE} == "farm" ]]; then
    ensure_directory_link "${REPO_ROOT}/data/01_raw/graal_data" "${RAW_TARGET}"
    ensure_directory_link "${REPO_ROOT}/data/02_pre_analyzed/pre_analisi" "${PRE_TARGET}"
fi

"${VENV_PYTHON}" -c \
    'import ROOT, graal_common, event_selector, mc_simulation, bdt_training, reconstruction, plots'

if [[ ! -f ${REPO_ROOT}/data/00_external/flux.root ]]; then
    echo "WARNING: data/00_external/flux.root is not present"
fi

echo "Setup complete (${MODE}). Activate with: source ${VENV_DIR}/bin/activate"
