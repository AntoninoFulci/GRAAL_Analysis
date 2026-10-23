#!/usr/bin/env bash
# Isolated single-bin job. Each task owns its checkpoint directory.
set -euo pipefail
if [[ $# -ne 2 ]]; then
    echo "Usage: $0 CAMPAIGN_DIR PAIR:ENERGY_BIN:MASS_BIN" >&2
    exit 2
fi
campaign=$1
bin_key=$2
source_dir=$(cd "$(dirname "$0")/../.." && pwd)
python_bin=${GRAAL_PYTHON:?Set the farm scientific Python interpreter}
cd "$source_dir"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1 NUMEXPR_NUM_THREADS=1
export PYTHONPATH="$source_dir/09_theory/src"
sha256sum --status -c SNAPSHOT.sha256
mkdir -p "$campaign/exits"
exit_record="$campaign/exits/${bin_key//:/_}.${SLURM_JOB_ID:-local}.exit"
trap 'status=$?; printf "%s\n" "$status" > "$exit_record.tmp"; mv "$exit_record.tmp" "$exit_record"' EXIT
"$python_bin" -u 09_theory/scripts/figure4_angular_fit.py compute --campaign "$campaign" --key "$bin_key"
