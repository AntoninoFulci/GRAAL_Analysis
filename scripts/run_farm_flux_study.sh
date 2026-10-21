#!/usr/bin/env bash
# Run one stage in a separately provisioned farm source snapshot/environment.
set -euo pipefail
if [[ $# -ne 4 ]]; then
    echo "Usage: $0 prepare|realistic|block3 STUDY_DIR CAMPAIGN_DIR H80_DIR" >&2
    exit 2
fi
stage=$1
study_dir=$2
campaign_dir=$3
h80_dir=$4
source_dir=$(cd "$(dirname "$0")/.." && pwd)
python_bin=${GRAAL_PYTHON:?Set GRAAL_PYTHON to the isolated ROOT-compatible interpreter}
cd "$source_dir"
export MPLBACKEND=Agg
export MPLCONFIGDIR="$study_dir/cache/matplotlib-$stage"
export XDG_CACHE_HOME="$study_dir/cache/$stage"
export OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 MKL_NUM_THREADS=1
mkdir -p "$MPLCONFIGDIR" "$XDG_CACHE_HOME"
trap 'rc=$?; printf "%s\n" "$rc" > "$study_dir/$stage.exit_code"' EXIT
printf 'Stage %s started at %s\n' "$stage" "$(date -u +%FT%TZ)"
case "$stage" in
    prepare)
        "$python_bin" -u -m flux_studies.prepare_native_recovery \
            --manifest "$source_dir/config/run_manifest.csv" \
            --raw-flux "$study_dir/flux.root" \
            --calibrated-flux "$campaign_dir/common/flux_calibrated.root" \
            --h80-dir "$h80_dir" --output-dir "$study_dir/prepared" --seed 142
        ;;
    realistic)
        "$python_bin" -u -m flux_studies.study_native_recovery \
            --manifest "$source_dir/config/run_manifest.csv" \
            --raw-flux "$study_dir/flux.root" \
            --calibrated-flux "$campaign_dir/common/flux_calibrated.root" \
            --counts-cache "$study_dir/prepared/h80_counts.json" \
            --reference-study "$study_dir/prepared" \
            --run-quality "$study_dir/prepared/run_quality_exclusions.json" \
            --reco-uv "$campaign_dir/uv/reco/reco_eta_pi0_bdt.root" \
            --reco-vis "$campaign_dir/vis/reco/reco_eta_pi0_bdt.root" \
            --output-dir "$study_dir/realistic" --replicas 64 --seed 142
        "$python_bin" -u -m flux_studies.native_diagnostics "$study_dir/realistic"
        ;;
    block3)
        "$python_bin" -u -m flux_studies.study_calibrated_neighbors \
            --manifest "$source_dir/config/run_manifest.csv" \
            --raw-flux "$study_dir/flux.root" \
            --calibrated-flux "$campaign_dir/common/flux_calibrated.root" \
            --counts-cache "$study_dir/prepared/h80_counts.json" \
            --run-quality "$study_dir/prepared/run_quality_exclusions.json" \
            --representation native_strip --models extra_trees kernel_ridge \
            --block-size 3 --seed 42 --output-dir "$study_dir/block3"
        "$python_bin" -u -m flux_studies.native_diagnostics "$study_dir/block3"
        ;;
    *) echo "Unknown stage: $stage" >&2; exit 2 ;;
esac
printf 'Stage %s completed at %s\n' "$stage" "$(date -u +%FT%TZ)"
