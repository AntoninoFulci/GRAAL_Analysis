#!/usr/bin/env bash
# Open the certified GRAAL_26 GDML in the native Geant4 Qt viewer.
set -euo pipefail
module_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
repo_dir=$(cd -- "$module_dir/../.." && pwd)
spack_bin=${SPACK_BIN:-/Users/tonyf/Software/spack/bin/spack}
geant4_prefix=$("$spack_bin" -e "$module_dir/spack-macos-qt" location -i geant4)
build_dir="$repo_dir/build/graal-geant4-viewer"
gdml=${1:-"$repo_dir/results/geant4-migration-audit-20261023/conversion-spack-certified/geometry.gdml"}
if [[ ! -f "$gdml" ]]; then
  printf 'GDML non trovato: %s\n' "$gdml" >&2
  exit 1
fi
gdml=$(cd -- "$(dirname -- "$gdml")" && printf '%s/%s\n' "$PWD" "$(basename -- "$gdml")")
cmake -S "$module_dir/viewer" -B "$build_dir" \
  -DGeant4_DIR="$geant4_prefix/lib/cmake/Geant4" -DCMAKE_BUILD_TYPE=Release
cmake --build "$build_dir" --target load_gdml --parallel 4
# G01 initializes a physics list even when used only for visualization.
# Use its installed datasets and a single thread; no events are requested.
set +u
source "$geant4_prefix/bin/geant4.sh"
set -u
export G4FORCENUMBEROFTHREADS=1
export G4UI_USE_QT=1
cd -- "$build_dir"
exec "$build_dir/G01-build/load_gdml" "$gdml"
