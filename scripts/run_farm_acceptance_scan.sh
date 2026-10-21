#!/usr/bin/env bash
# One stage of an isolated, frozen acceptance scan. Submission owns concurrency.
set -euo pipefail
if [[ $# -ne 2 ]]; then
    echo "Usage: $0 development|collect|confirmation STUDY_DIR" >&2
    exit 2
fi
stage=$1
study_dir=$2
source_dir=$(cd "$(dirname "$0")/.." && pwd)
cd "$source_dir"
python_bin=${GRAAL_PYTHON:?Use the isolated scan environment}
export MPLBACKEND=Agg OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
export NUMEXPR_NUM_THREADS=1
export MPLCONFIGDIR="$study_dir/cache/mpl-${SLURM_JOB_ID:-local}"
export XDG_CACHE_HOME="$study_dir/cache/xdg-${SLURM_JOB_ID:-local}"
mkdir -p "$MPLCONFIGDIR" "$XDG_CACHE_HOME"
protocol="$study_dir/prepared/protocol.json"
"$python_bin" - "$source_dir" "$study_dir/source_manifest.json" <<'PY'
import hashlib, json, sys
from pathlib import Path
root, manifest = map(Path, sys.argv[1:])
for name, digest in json.loads(manifest.read_text())['files'].items():
    if hashlib.sha256((root / name).read_bytes()).hexdigest() != digest:
        raise RuntimeError(f'source snapshot changed: {name}')
print('Source snapshot verified', flush=True)
PY
case "$stage" in
    development)
        index=${SLURM_ARRAY_TASK_ID:?Array index required}
        workers=${SLURM_CPUS_PER_TASK:-4}
        [[ "$workers" -ge 1 && "$workers" -le 4 ]] || exit 2
        "$python_bin" -u -m flux_studies.acceptance_experiment trial \
            --protocol "$protocol" --trial-index "$index" --workers "$workers" \
            --output-dir "$study_dir/development/trial_$index"
        ;;
    collect)
        "$python_bin" -u -m flux_studies.acceptance_report \
            --trials "$study_dir"/development/trial_{0..9} \
            --protocol "$protocol" --output-dir "$study_dir/selection"
        ;;
    confirmation)
        "$python_bin" -u - "$study_dir" <<'PY'
import json, os, sys
from pathlib import Path
from calibration.calibration_qa import sha256_file
from flux_studies.acceptance_experiment import run_trial
from flux_studies.acceptance_report import confirm_scan
from flux_studies.reporting import publish_output, write_json
root = Path(sys.argv[1])
selection = root / 'selection/summary.json'
protocol = root / 'prepared/protocol.json'
chosen = json.loads(selection.read_text())
if chosen['status'] != 'complete':
    raise RuntimeError('development scan incomplete; no confirmation allowed')
if chosen['selected_policy'] is None:
    with publish_output(root / 'confirmation_decision', [selection, protocol]) as output:
        write_json(output / 'summary.json', dict(status='not_run_no_feasible_policy',
            selected_policy=None, production_adopted=False, selection_sha256=sha256_file(selection),
            protocol_sha256=sha256_file(protocol)))
    print('No feasible development policy; confirmation not run.', flush=True)
else:
    run_trial(protocol, root / 'confirmation', phase='confirmation', selection_path=selection,
              workers=min(4, int(os.environ.get('SLURM_CPUS_PER_TASK', '4'))))
    result = confirm_scan(root / 'confirmation', selection, protocol_path=protocol)
    with publish_output(root / 'confirmation_decision', [protocol, selection, *result['input_files']]) as output:
        write_json(output / 'summary.json', result)
    print(json.dumps({k: result[k] for k in ('status', 'selected_policy', 'diagnostic_passed')}), flush=True)
PY
        ;;
    *) echo "Unknown stage: $stage" >&2; exit 2 ;;
esac
