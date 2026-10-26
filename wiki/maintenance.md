# Maintenance and tests

The root README introduces the project; this wiki owns current technical guidance. Keep only active plans under `docs/plans/`, original papers under `docs/papers/`, and persistent scientific reference material under `docs/reference/`. Keep machine-readable runtime/provenance references in their owning packages. Preserve source data, period cuts, BDT bundles/provenance, bibliography, Fortran and geometry snapshots. Never edit a historical ROOT result to satisfy a new contract.

Run tests in a named diagnostic campaign with absolute temporary/cache roots. From the checkout root:

```bash
TASK_ROOT="$PWD/results_test/manual-verification"
mkdir -p "$TASK_ROOT/tmp" "$TASK_ROOT/mpl"
export PYTHONDONTWRITEBYTECODE=1
export TMPDIR="$TASK_ROOT/tmp"
export MPLCONFIGDIR="$TASK_ROOT/mpl"
python -B -m pytest -q tests/test_wiki.py tests/test_wiki_sync.py tests/test_run_pipeline.py --basetemp="$TASK_ROOT/pytest-tmp" -o cache_dir="$TASK_ROOT/pytest-cache"
```

The analysis test paths are declared in [pyproject.toml](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/pyproject.toml). The retired theory suite is archived with its sources and is not part of current verification; [restart requirements](09-theory) apply to future work. Use focused tests for the changed boundary, then required integration checks. Do not launch long scientific jobs or modify farm campaigns for routine maintenance. Explicit build directories belong under `results_test/`.

[Wiki tests](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/tests/test_wiki.py) validate links, unique navigation, supported command contracts and retired interfaces, without a fixed page count. [Sync tests](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/tests/test_wiki_sync.py) publish only to temporary local Git remotes and verify deletion/idempotence. `scripts/sync-wiki.sh` publishes the current page set to GitHub Wiki, pruning obsolete pages. Set `WIKI_REMOTE` to a local fixture remote when testing; actual external publication is an explicit integration action.

Graphify output is generated evidence. Rebuild it after source/document changes before treating it as current architecture. Do not ingest archived plans, generated reports or the graph itself as current source. The completed refactor [specification](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/fd00a45b01b13c690afa1645687e73a18eb873e3/docs/plans/2026-10-23-repository-refactor-spec.md) and [plan](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/fd00a45b01b13c690afa1645687e73a18eb873e3/docs/plans/2026-10-23-repository-refactor-plan.md) are historical Git records, retired from the checkout on 24 October 2026. Open scientific work remains in [status](status). An empty `docs/plans/` is retained for future active plans.

The [Graphify corpus policy](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/reference/graph-corpus.json) explicitly selects current code, tests, configuration, wiki and scientific text references. A fresh build uses the installed Graphify interpreter (override with `GRAPHIFY_PYTHON`) and a new diagnostic directory:

```bash
GRAPH_RUN="$PWD/results_test/manual-graph-rebuild"
bash scripts/rebuild_graph.sh prepare --run-dir "$GRAPH_RUN"
# Inspect detection.json and every detection shard before extraction.
bash scripts/rebuild_graph.sh ast --run-dir "$GRAPH_RUN"
# Run each prompts/chunk-NN.txt with the host agent, writing its exact JSON output.
# All chunks are disjoint, freshly read and bound to corpus/spec hashes.
bash scripts/rebuild_graph.sh build --run-dir "$GRAPH_RUN"
bash scripts/rebuild_graph.sh verify --run-dir "$GRAPH_RUN"
bash scripts/rebuild_graph.sh publish --run-dir "$GRAPH_RUN"
```

Host semantic extraction is a required manual agent step; the shell command cannot invoke the conversation model. It must follow the installed Graphify extraction specification. Missing chunks, missing document coverage or source changes stop the build. Start a new run after source changes. AST caches are fresh for each extraction invocation, and cross-stage resolution uses only that invocation's corpus. Review `health.txt`, `community-summary.json`, candidate coverage and source-cited queries before publishing. HTML above 5,000 nodes uses an aggregated community view. Publication verifies and archives every previous active output by SHA-256; generated graph output remains reproducible evidence, not normative documentation. Host token counters are explicitly unknown when the orchestrator does not expose usage.

If a command fails, check the selected PyROOT-compatible interpreter, declared checkout root, input digests/cohort, BDT coverage and ROOT provenance before recomputation. Retain the failing log and existing valid artifacts. Missing calibration/flux coverage is a scientific input issue, not a reason to substitute synthetic flux.
