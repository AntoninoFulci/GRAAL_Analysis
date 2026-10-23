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

The analysis test paths are declared in [pyproject.toml](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/pyproject.toml). Theory has a separate suite under `09_theory/tests`; its numerical and physics acceptance gates remain distinct. Use focused tests for the changed boundary, then required integration checks. Do not launch long scientific jobs or modify farm campaigns for routine maintenance. Explicit build directories belong under `results_test/`.

[Wiki tests](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/tests/test_wiki.py) validate links, unique navigation, supported command contracts and retired interfaces, without a fixed page count. [Sync tests](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/tests/test_wiki_sync.py) publish only to temporary local Git remotes and verify deletion/idempotence. `scripts/sync-wiki.sh` publishes the current page set to GitHub Wiki, pruning obsolete pages. Set `WIKI_REMOTE` to a local fixture remote when testing; actual external publication is an explicit integration action.

Graphify output is generated evidence. Rebuild it after source/document changes before treating it as current architecture; the pre-refactor graph is stale. Do not ingest archived plans, generated reports or the graph itself as current source. The active refactor [specification](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/plans/2026-10-23-repository-refactor-spec.md) and [plan](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/plans/2026-10-23-repository-refactor-plan.md) remain while this work is in progress.

If a command fails, check the selected PyROOT-compatible interpreter, declared checkout root, input digests/cohort, BDT coverage and ROOT provenance before recomputation. Retain the failing log and existing valid artifacts. Missing calibration/flux coverage is a scientific input issue, not a reason to substitute synthetic flux.
