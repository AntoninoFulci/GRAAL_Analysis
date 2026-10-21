#!/usr/bin/env bash
# Submit only after snapshot verification and a successful isolated smoke trial.
set -euo pipefail
if [[ $# -ne 1 ]]; then
    echo "Usage: $0 STUDY_DIR" >&2
    exit 2
fi
study_dir=$(cd "$1" && pwd)
test -f "$study_dir/prepared/protocol.json"
test -f "$study_dir/smoke/trial/trial.json"
test ! -e "$study_dir/jobs.json"
export GRAAL_ACCEPTANCE_STUDY="$study_dir"
array_id=$(sbatch --parsable --partition=LocalQ --nodes=1 --ntasks=1 \
    --cpus-per-task=4 --mem=10G --time=2-00:00:00 --array=0-9%10 \
    --job-name=flux-accept-dev --output="$study_dir/logs/development-%A_%a.log" \
    "$study_dir/job.sh" development)
printf '%s\n' "$array_id" > "$study_dir/development.job_id"
collect_id=$(sbatch --parsable --partition=LocalQ --nodes=1 --ntasks=1 \
    --cpus-per-task=1 --mem=4G --time=04:00:00 \
    --dependency="afterok:$array_id" --kill-on-invalid-dep=yes \
    --job-name=flux-accept-select --output="$study_dir/logs/selection-%j.log" \
    "$study_dir/job.sh" collect)
printf '%s\n' "$collect_id" > "$study_dir/selection.job_id"
confirmation_id=$(sbatch --parsable --partition=LocalQ --nodes=1 --ntasks=1 \
    --cpus-per-task=4 --mem=10G --time=2-00:00:00 \
    --dependency="afterok:$collect_id" --kill-on-invalid-dep=yes \
    --job-name=flux-accept-confirm --output="$study_dir/logs/confirmation-%j.log" \
    "$study_dir/job.sh" confirmation)
printf '%s\n' "$confirmation_id" > "$study_dir/confirmation.job_id"
"$study_dir/venv/bin/python" - "$study_dir" "$array_id" "$collect_id" "$confirmation_id" <<'PY'
from datetime import datetime, timezone
import hashlib, json, sys
from pathlib import Path
root = Path(sys.argv[1])
record = dict(submitted_utc=datetime.now(timezone.utc).isoformat(), status='submitted_not_completed',
              jobs=dict(zip(('development_array', 'selection', 'confirmation'), sys.argv[2:])),
              maximum_concurrent_cores=40, development_tasks=10, cores_per_development_task=4,
              memory_gib_per_development_task=10, protocol_sha256=hashlib.sha256(
                  (root / 'prepared/protocol.json').read_bytes()).hexdigest(),
              source_manifest_sha256=hashlib.sha256((root / 'source_manifest.json').read_bytes()).hexdigest())
(root / 'jobs.json').write_text(json.dumps(record, indent=2) + '\n')
print(json.dumps(record, indent=2))
PY
squeue -j "$array_id,$collect_id,$confirmation_id" -o '%.18i %.22j %.10T %.10M %.6C %R'
