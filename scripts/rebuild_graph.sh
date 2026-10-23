#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
GRAPH_PYTHON=${GRAPHIFY_PYTHON:-}
if [[ -z "$GRAPH_PYTHON" ]]; then
  GRAPH_BIN=$(command -v graphify || true)
  if [[ -n "$GRAPH_BIN" ]]; then
    IFS= read -r GRAPH_SHEBANG < "$GRAPH_BIN"
    GRAPH_PYTHON=${GRAPH_SHEBANG#\#!}
  else
    GRAPH_PYTHON=python3
  fi
fi
export PYTHONDONTWRITEBYTECODE=1
exec "$GRAPH_PYTHON" -B "$ROOT/scripts/rebuild_graph.py" "$@"
