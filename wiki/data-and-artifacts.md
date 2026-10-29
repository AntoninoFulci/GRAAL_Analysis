# Data and artifact contracts

| Location | Ownership |
| --- | --- |
| `data/` | Production inputs and server/farm links; never generated intermediates |
| `data_test/raw_data/`, `data_test/pre_analyzed/` | Local raw test run and full legacy UV+VIS h80 inputs |
| `data_test/sample/` | Reserved path for the fixed reduced UV+VIS cohort; currently absent |
| `results/_cache/` | Validated reusable production intermediates |
| `results/<campaign>/` | Production reconstruction, extraction and figures |
| `results_test/<campaign>/` | Diagnostics, test intermediates, reports, logs, temporary/build output |
| `config/` | YAML launch configurations, including inline energy grids |
| `config/support/` | Curated catalog, frozen exclusions and authenticated common input references |
| `data_test/reference/` | Small versioned diagnostic count reference; not production input |
| `docs/papers/` | Original scientific PDFs |
| `docs/reference/` | Original Fortran, graph corpus policy and historical evidence index |
| `docs/plans/` | Active plans only |

Raw detector data uses `h70`, pre-analysis `h80`, selection `h85`. Momentum four-vectors use `[px, py, pz, E]` in GeV; angles use radians. The [shared contract code](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/00_common) owns feature order, metadata and physics constants.

New reconstructed ROOT provenance requires `schema=2` and `selection_algorithm="pairing_missing_mass"`. Samples are `raw` and `raw_bdt`. Certified consumers reject older provenance: raw vector branches alone do not establish compatible event selection. Historical outputs retain their original bytes and are not upgraded by editing metadata.

[Stage 04](04-bdt-training) validates the ordered 26-feature schema, hypothesis, beam coverage, threshold and model provenance. [Stage 06](06-calibration) binds calibrated ROOT and QA to the actual inclusive input cohort. Run/state cutflow establishes exposure accounting, including zero selected yield; event survival cannot be used to infer exposure.

The diagnostic UV+VIS sample retains identified source exposures, not exposures multiplied by the retained event fraction. Its calibration support includes the required strips and at least five distinct strips per retained group, including 1 and 128. It is a regression cohort, not a normalized measurement.

`config/support/common_inputs.json` uses schema 1, explicit `checkout`/`cache` roots and SHA256 values. The optional `local_1998uv_1999vis` inclusive-count bundle is diagnostic only: 864 rows and 184681346 input events from the two original full h80s. It is not the reduced sample, a good-run list, or a production eligibility rule. Explicit consumers validate exact cohort, source SHA/UUID/entry count and count totals; the bundle records dated audit provenance; normal common-input resolution does not require the bundle.

[Historical reference index](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/reference/index.md) locates dated audits in Git history without making their old commands current. Active references remain in their owning packages; retired theory evidence is preserved in [docs/reference/theory](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/reference/theory/index.md). The experimental Ajaka CSV is canonical at [08_observable_extraction/references/ajaka2008_figure4_digitized.csv](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/08_observable_extraction/references/ajaka2008_figure4_digitized.csv). Stage 09's separately digitized theory strokes are a different scientific object, not a duplicate experimental dataset.

## Local availability after cleanup

On 24 October 2026, `data_test/sample/`, `results/_cache/`, local virtual environments and the previous `results_test/` archives were absent. Production input directories `data/01_raw/` and `data/02_pre_analyzed/` were empty. The two full h80 files now live under `data_test/pre_analyzed/`; their SHA256, ROOT UUID and entry counts match the registered inclusive-count cohort (90,279,078 UV and 94,402,268 VIS entries). Its portable source paths and enclosing common-input digest were updated without changing counts, source identities or historical audit evidence. The raw test run is `data_test/raw_data/1998_uv/run1321.root`; external flux files remain under `data/00_external/`. Relocation evidence is recorded in local `results_test/cleanup-20261024/input-relocation.json`. The old scalar-audit files named in the count bundle were deleted; content/header validation does not recreate that audit.

The owner confirmed the missing reduced cohort and old archives were deleted, with no relocated copy. `test_data` therefore remains unavailable until a separately requested cohort rebuild creates and validates a new frozen sample and manifest. The retained full h80 files must not silently replace the reduced cohort. `scripts/prepare_test_sample.py` accepts explicit `--uv` and `--vis` source paths for that future operation. Reconnect production inputs before production preflight. Caches can be rebuilt by an explicitly requested campaign; historical validation logs cannot be reconstructed from a passing software test. Local availability does not describe farm storage or queue state.

## Configuration layout migration, 29 October 2026

The launch YAML files remain in `config/`. Active defaults, scripts, examples and tests now read the support files from `config/support/`. The optional diagnostic count bundle moved to `data_test/reference/` and remains versioned. No data event, run classification, exclusion or historical evidence record was changed.

| Previous path | Current path | SHA256 before | SHA256 after |
| --- | --- | --- | --- |
| `config/common_inputs.json` | `config/support/common_inputs.json` | `f493d5179b4447ff1eff693c2cea67d529a74bc49db84809596909c3f8480588` | `b8abd680ae19ec191138f450be16c1936d45a768cd07cf05e19897615c369ebe` |
| `config/run_manifest.csv` | `config/support/run_manifest.csv` | `64a2096602e0db2a7de2b5a2c4b64c94df3e2719c3f8510b69b44018033d3160` | `64a2096602e0db2a7de2b5a2c4b64c94df3e2719c3f8510b69b44018033d3160` |
| `config/run_quality_exclusions.json` | `config/support/run_quality_exclusions.json` | `52533f31d2ef0fb946ff60947712e516ecc94b8a98091a2ac51bcfbcf61ccc35` | `52533f31d2ef0fb946ff60947712e516ecc94b8a98091a2ac51bcfbcf61ccc35` |
| `config/inclusive_counts_local_1998uv_1999vis.json` | `data_test/reference/inclusive_counts_local_1998uv_1999vis.json` | `4e2f4032289038bf30f59ef1f109a4807d13929d3659dfb7b8ebf3183b875470` | `4e2f4032289038bf30f59ef1f109a4807d13929d3659dfb7b8ebf3183b875470` |

Only `common_inputs.json` changed content: its reference paths now point to the relocated files; the referenced SHA256 digests are unchanged. Historical paths inside the frozen quality policy and count provenance remain untouched because they identify dated evidence, not active file lookups.

The three files formerly under `config/energy/` were redundant launch presets. Their exact nominal, split and low-UV grids are preserved as active values or commented examples in `config/pipeline.yaml`; user-provided JSON energy files remain supported through `--energy-config`. The low-UV example starts at 0.9313 GeV; the separately requested trima campaign starts at 0.930 GeV.
