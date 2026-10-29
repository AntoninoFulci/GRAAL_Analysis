# Stage 06: measured calibration

[run_manifest.py](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/06_calibration/run_manifest.py) validates the curated run catalog. `build_run_manifest.py --validate config/support/run_manifest.csv` checks it. Scanning inputs may create a new candidate catalog, but cannot infer all manual classifications and refuses to overwrite an existing catalog.

The [common input loader](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/06_calibration/common_inputs.py) validates `config/support/common_inputs.json`, the manual catalog, frozen quality policy and raw flux identities. The native producer calibrates strip-to-energy on inclusive h80, joins measured run/state flux and writes a calibrated ROOT/QA pair. Numerical calibration, native production, inspection and QA have separate public owners under [06_calibration](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/06_calibration).

`build_strip_energy_flux.py --help` documents the producer interface. The workflow owns explicit input/output paths; do not use a selected-event cohort as a substitute for inclusive calibration. Energy-axis interpolation/extrapolation within a calibration is distinct from inventing a missing flux histogram.

The content-bound cache is `results/_cache/06_calibration/<key>` in production. Its key includes recursive input content/cohort, catalog, raw flux, numerical options/binnings, threads, schema and the installed source/driver identities actually executed. There is no calibration TTL. Thread count remains in the key because scheduling can affect sample claims and floating-point merges. A quality policy not read by the producer is not falsely added to its key.

A per-key lock and atomic directory publication protect ROOT, QA and manifest together. Tampering or changing source/input during production/copy invalidates publication. The campaign receives a coherent pair and `calibration_reuse.json` recording key, reuse, source and effective paths; original QA is not rewritten after relocation. Cache hits still read bytes for integrity, while avoiding event scanning/fitting.

Diagnostic runs use a distinct scope and campaign-local cache under `results_test/`. The common optional inclusive-count bundle is documented in [data contracts](data-and-artifacts); it cannot change production run policy. [Stage 07](07-flux-studies) handles exploratory recovery separately.

The `flux_build` coordinator names three local QA calculations: unmapped strips, raw flux excluded by binning, and manifest/state calibration coverage. These helpers preserve diagnostic ordering and accumulation order. Native scans, calibration fits, input-identity checks, atomic publication and cache certification remain in their existing owners and execution order.
