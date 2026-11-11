#!/usr/bin/env bash
# Run inside tmux. Tee keeps both the terminal and an external tail live.
set -Eeuo pipefail
if [[ $# -ne 4 ]]; then
    echo "Usage: $0 RAW_ROOT CATALOG CAMPAIGN_OUTPUT SUPPORT_OUTPUT" >&2
    exit 2
fi
raw_root=$1
catalog=$2
campaign=$3
support=$4
source_root=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
: "${GRAAL_PYTHON:=python3}"
: "${GRAAL_TARGET_WORKERS:=24}"
: "${GRAAL_RUNTIME_DIR:?Set absolute diagnostic runtime directory}"
mkdir -p "$campaign" "$GRAAL_RUNTIME_DIR"/{tmp,mpl,cache}
exec > >(tee -a "$campaign/campaign.log") 2>&1
trap 'status=$?; printf "%s\n" "$status" > "$campaign/exit_code"; printf "Campaign exit=%s at %s\n" "$status" "$(date -Is)"' EXIT
printf 'running\n' > "$campaign/exit_code"
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$GRAAL_RUNTIME_DIR/tmp" MPLCONFIGDIR="$GRAAL_RUNTIME_DIR/mpl" XDG_CACHE_HOME="$GRAAL_RUNTIME_DIR/cache"
export PYTHONPATH="$source_root${PYTHONPATH:+:$PYTHONPATH}"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
cd "$source_root"
printf 'Start %s host=%s workers=%s\n' "$(date -Is)" "$(hostname)" "$GRAAL_TARGET_WORKERS"
"$GRAAL_PYTHON" -B -u 06_calibration/target_batch.py --raw-root "$raw_root" --catalog "$catalog" \
    --output "$campaign" --workers "$GRAAL_TARGET_WORKERS" --bootstrap 32
"$GRAAL_PYTHON" -B -u 06_calibration/target_publish.py "$campaign/products" --output "$support"
printf 'Products: %s\nConditions: %s\n' "$campaign/products" "$support"
