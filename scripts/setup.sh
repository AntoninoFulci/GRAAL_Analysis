#!/usr/bin/env bash

set -euo pipefail

usage() {
    cat <<'EOF'
Usage:
  ./scripts/setup.sh --mode local [--python PATH] [--install venv|user]
  ./scripts/setup.sh --mode farm --raw-target DIR [--preanalysis-target DIR] [--python PATH] [--install venv|user]

Options:
  --mode local       Set up Python environment and local data directories.
  --mode farm        Link raw data; place h80 files in data/02_pre_analyzed/ manually.
  --raw-target DIR   Existing farm directory containing acquisition-period folders.
  --preanalysis-target DIR  Link an existing h80 input directory explicitly.
  --python PATH      Base Python interpreter (default: python3).
  --install venv     Install into repository .venv (default).
  --install user     Install into user site packages, outside any venv.
  --help             Show this help.
EOF
}

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
REPO_ROOT=$(cd "${SCRIPT_DIR}/.." && pwd -P)

MODE=""
PYTHON_BIN="python3"
RAW_TARGET=""
PREANALYSIS_TARGET=""
INSTALL_MODE="venv"

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
        --preanalysis-target)
            require_value "$1" "${2:-}"
            PREANALYSIS_TARGET=$2
            shift 2
            ;;
        --install)
            require_value "$1" "${2:-}"
            INSTALL_MODE=$2
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
if [[ ${INSTALL_MODE} != "venv" && ${INSTALL_MODE} != "user" ]]; then
    echo "ERROR: --install must be venv or user" >&2
    exit 2
fi

if [[ ${MODE} == "farm" ]]; then
    if [[ -z ${RAW_TARGET} ]]; then
        echo "ERROR: farm mode requires --raw-target" >&2
        exit 2
    fi
    if [[ ! -d ${RAW_TARGET} ]]; then
        echo "ERROR: raw target is not a directory: ${RAW_TARGET}" >&2
        exit 1
    fi
    RAW_TARGET=$(cd "${RAW_TARGET}" && pwd -P)
fi

if [[ -n ${PREANALYSIS_TARGET} ]]; then
    if [[ ${MODE} != "farm" || ! -d ${PREANALYSIS_TARGET} ]]; then
        echo "ERROR: --preanalysis-target requires farm mode and an existing directory" >&2
        exit 2
    fi
    PREANALYSIS_TARGET=$(cd "${PREANALYSIS_TARGET}" && pwd -P)
fi

if ! command -v "${PYTHON_BIN}" >/dev/null 2>&1; then
    echo "ERROR: Python interpreter not found: ${PYTHON_BIN}" >&2
    exit 1
fi

if ! "${PYTHON_BIN}" -c 'import sys; raise SystemExit(sys.version_info < (3, 10))'; then
    echo "ERROR: Python 3.10 or newer is required" >&2
    exit 1
fi
if [[ ${INSTALL_MODE} == "user" ]] && ! "${PYTHON_BIN}" -c \
    'import site, sys; raise SystemExit(not (sys.prefix == sys.base_prefix and site.ENABLE_USER_SITE))'; then
    echo "ERROR: --install user requires Python outside a virtual environment with user site packages enabled" >&2
    exit 1
fi
if ! "${PYTHON_BIN}" -c 'import ROOT'; then
    echo "ERROR: selected Python cannot import ROOT: ${PYTHON_BIN}" >&2
    exit 1
fi

INSTALL_PYTHON="${PYTHON_BIN}"
PIP_OPTIONS=()
if [[ ${INSTALL_MODE} == "venv" ]]; then
    VENV_DIR="${REPO_ROOT}/.venv"
    if [[ -e ${VENV_DIR} && ! -x ${VENV_DIR}/bin/python ]]; then
        echo "ERROR: existing .venv is incomplete: ${VENV_DIR}" >&2
        exit 1
    fi
    if [[ ! -e ${VENV_DIR} ]]; then
        "${PYTHON_BIN}" -m venv --system-site-packages "${VENV_DIR}"
    fi
    INSTALL_PYTHON="${VENV_DIR}/bin/python"
    if ! "${INSTALL_PYTHON}" -c 'import ROOT'; then
        echo "ERROR: .venv cannot import ROOT" >&2
        exit 1
    fi
    "${INSTALL_PYTHON}" -m pip install --upgrade pip
else
    PIP_OPTIONS=(--user)
fi

"${INSTALL_PYTHON}" -m pip install "${PIP_OPTIONS[@]}" -e "${REPO_ROOT}"

mkdir -p \
    "${REPO_ROOT}/data/00_external" \
    "${REPO_ROOT}/data/01_raw" \
    "${REPO_ROOT}/results/_cache/03_selected" \
    "${REPO_ROOT}/data_test" \
    "${REPO_ROOT}/results_test"

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

if [[ -n ${PREANALYSIS_TARGET} ]]; then
    ensure_directory_link "${REPO_ROOT}/data/02_pre_analyzed" "${PREANALYSIS_TARGET}"
else
    mkdir -p "${REPO_ROOT}/data/02_pre_analyzed"
fi

if [[ ${MODE} == "farm" ]]; then
    ensure_directory_link "${REPO_ROOT}/data/01_raw/graal_data" "${RAW_TARGET}"
fi

"${INSTALL_PYTHON}" -c \
    'import ROOT, numpy, uproot, awkward, xgboost, sklearn, matplotlib, tqdm, graal_common, event_selector, mc_simulation, bdt_training, reconstruction, calibration, observable_extraction, plots'

if [[ ! -f ${REPO_ROOT}/data/00_external/flux.root ]]; then
    echo "WARNING: data/00_external/flux.root is not present"
fi

echo "Setup complete (${MODE}, install=${INSTALL_MODE})."
if [[ ${INSTALL_MODE} == "venv" ]]; then
    echo "Activate environment: source ${VENV_DIR}/bin/activate"
else
    echo "No venv activation needed. Run with: ${INSTALL_PYTHON}"
fi
echo "Calibration help: ${INSTALL_PYTHON} ${REPO_ROOT}/06_calibration/build_strip_energy_flux.py --help"
