#!/usr/bin/env bash
# Compatibility entry point. The portable launcher rebuilds geometry by default.
set -euo pipefail
module_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if (( $# > 1 )); then
  printf 'Usage: %s [geometry.gdml]\n' "$0" >&2
  exit 1
fi
args=()
if (( $# == 1 )); then args+=(--gdml "$1"); fi
exec "${PYTHON:-python3}" -B "$module_dir/run.py" view "${args[@]}"
