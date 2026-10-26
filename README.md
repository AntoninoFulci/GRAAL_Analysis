# GRAAL Analysis

Analysis of γp → pηπ⁰ with η, π⁰ → γγ. The pipeline compares χ² photon pairing with a Stage-1 BDT gate followed by the same pairing and missing-mass selection, then extracts beam asymmetry from measured calibrated flux. Stage 09 theory was retired on 26 October 2026; see the [restart boundary](wiki/09-theory.md).

The [GitHub Wiki](https://github.com/AntoninoFulci/GRAAL_Analysis/wiki) is the current technical guide; its [source index](wiki/Home.md) is versioned here. Start with [setup](wiki/getting-started.md), [workflow](wiki/workflow.md), [commands](wiki/commands-and-configuration.md), and [scientific status](wiki/status.md).

Use Python ≥3.10 compatible with CERN ROOT/PyROOT. Load ROOT, then:

```bash
./scripts/setup.sh --mode local
source .venv/bin/activate
python scripts/run_pipeline.py --help
```

For a farm use `--mode farm --python /path/to/pyroot-compatible-python --raw-target /farm/path/graal_data`. Setup validates imports and input links. See the wiki for user-site installation and wheel checkout requirements.

```bash
python scripts/run_pipeline.py --mode test_data
python scripts/run_pipeline.py --mode production --output-dir results/my-campaign
```

These commands run scientific campaigns after preflight and confirmation. Restore missing local inputs first; see [availability after cleanup](wiki/data-and-artifacts.md#local-availability-after-cleanup). `--phi-bins 8|12|16` defaults to 12; `--best-binning` chooses per point. [Finite-bin correction](wiki/finite-bin-correction.md) applies only to the ratio estimator. The reduced UV+VIS input is diagnostic, not a normalized production dataset. Optional flux recovery remains experimental.

| Path | Contents |
| --- | --- |
| `00_common/`–`08_observable_extraction/` | Shared contracts and numbered analysis components |
| `graal_workflow/`, `scripts/`, `plots/` | Orchestration, entry points and output rendering |
| `config/` | Curated manifests, policy and authenticated common inputs |
| `data/`, `data_test/` | Production inputs, local raw/h80 test sources and reserved reduced-cohort path |
| `results/`, `results/_cache/` | Production campaigns and validated reusable products |
| `results_test/` | Tests, diagnostics, reports and explicit temporary/build roots |
| `wiki/` | Current technical documentation |
| `docs/papers/`, `docs/plans/`, `docs/reference/` | Original papers, active plans and scientific evidence |

See [maintenance and tests](wiki/maintenance.md) for isolated verification commands and wiki synchronization. Scientific sources and historical results retain their provenance; software tests do not establish detector acceptance, theory convergence or a complete uncertainty budget.
