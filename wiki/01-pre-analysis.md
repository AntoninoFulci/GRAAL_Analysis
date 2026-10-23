# Stage 01: pre-analysis

[PreAnalysis.C](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/01_pre_analysis/PreAnalysis.C), [CutManager.h](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/01_pre_analysis/CutManager.h), and [period cuts](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/01_pre_analysis/cuts) convert raw `h70` detector records to `h80`. [RawTrackContract.h](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/01_pre_analysis/RawTrackContract.h) retains raw identities for later track diagnostics. The historical classification Fortran is preserved in [docs/reference/fortran](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/reference/fortran).

`scripts/run_preanalysis.py` runs isolated ROOT processes, applies the actual period-dependent cuts, validates accounting, and merges staged products. Events without tagger information are discarded with recorded counts. The contract checks input = written + discarded per run/state. Source identities and conversion provenance distinguish fresh h80 files from legacy fixtures.

```bash
python scripts/run_preanalysis.py --help
```

The complete analysis launcher consumes h80 and does not perform stage 01 implicitly. Use `--require-current-preanalysis` on the launcher when fresh raw-track identity/tagger-discard provenance is required. Preserve the detector cuts and original h70 files. Zero reconstructed charge in a period with an excluded detector does not prove physical absence; see [status](status).
