# Data and artifact contracts

| Location | Ownership |
| --- | --- |
| `data/` | Production inputs and server/farm links; never generated intermediates |
| `data_test/sample/` | One fixed UV+VIS diagnostic cohort, with source/exposure manifest |
| `results/_cache/` | Validated reusable production intermediates |
| `results/<campaign>/` | Production reconstruction, extraction and figures |
| `results_test/<campaign>/` | Diagnostics, test intermediates, reports, logs, temporary/build output |
| `config/` | Curated catalog, frozen exclusions, common input manifest and explicit configurations |
| `docs/papers/` | Original scientific PDFs |
| `docs/reference/` | Historical scientific sources, Fortran and dated research evidence |
| `docs/plans/` | Active plans only |

Raw detector data uses `h70`, pre-analysis `h80`, selection `h85`. Momentum four-vectors use `[px, py, pz, E]` in GeV; angles use radians. The [shared contract code](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/00_common) owns feature order, metadata and physics constants.

New reconstructed ROOT provenance requires `schema=2` and `selection_algorithm="pairing_missing_mass"`. Samples are `raw` and `raw_bdt`. Certified consumers reject older provenance: raw vector branches alone do not establish compatible event selection. Historical outputs retain their original bytes and are not upgraded by editing metadata.

[Stage 04](04-bdt-training) validates the ordered 26-feature schema, hypothesis, beam coverage, threshold and model provenance. [Stage 06](06-calibration) binds calibrated ROOT and QA to the actual inclusive input cohort. Run/state cutflow establishes exposure accounting, including zero selected yield; event survival cannot be used to infer exposure.

The diagnostic UV+VIS sample retains identified source exposures, not exposures multiplied by the retained event fraction. Its calibration support includes the required strips and at least five distinct strips per retained group, including 1 and 128. It is a regression cohort, not a normalized measurement.

`config/common_inputs.json` uses schema 1, explicit `checkout`/`cache` roots and SHA256 values. The optional `local_1998uv_1999vis` inclusive-count bundle is diagnostic only: 864 rows and 184681346 input events from the two original full h80s. It is not the reduced sample, a good-run list, or a production eligibility rule. Explicit consumers validate exact cohort, source SHA/UUID/entry count and audit provenance; normal common-input resolution does not require the bundle.

[Historical reference evidence](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/reference/index.md) retains dated audits without making their old commands current. Machine-readable references remain in their owning packages. The experimental Ajaka CSV is canonical at [08_observable_extraction/references/ajaka2008_figure4_digitized.csv](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/08_observable_extraction/references/ajaka2008_figure4_digitized.csv). Stage 09's separately digitized theory strokes are a different scientific object, not a duplicate experimental dataset.
