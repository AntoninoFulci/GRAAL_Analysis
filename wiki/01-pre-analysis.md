# 01 — Pre-analysis

Pre-analysis converts raw GRAAL detector trees into one compact ROOT file per
run. ROOT entry point is `AnalyzeAll` in `01_pre_analysis/PreAnalysis.C`.

## Responsibilities

- scan raw run directories and build run-to-acquisition-period mapping;
- load and validate graphical detector cuts;
- read raw detector branches through generated `PreAnalysis` bindings;
- construct beam and particle four-vectors;
- preserve detector observables and run metadata needed downstream;
- write tree `h80`.

`PreAnalysis::Loop` classifies central and forward candidates into photons,
protons, neutrons, pions, and deuterons. Every input entry is written after
candidate reconstruction; tighter event topology selection belongs to stage 2.

## Output

Primary h80 branches:

- `beam`;
- vectors `gammas`, `protons`, `neutrons`, `deuterons`;
- angular and detector-response vectors;
- `Polarization`, `RunNumber`, and `Xstrip`.

`AnalyzeAll(base_in, base_out, cuts_dir)` writes
`pre_analisi_<run>.root` under output directory. Pipeline detects reusable
outputs using broader `pre_*.root` pattern.

## Pipeline invocation

```bash
root -l -b -q -e \
  'gROOT->ProcessLine(".L 01_pre_analysis/PreAnalysis.C"); AnalyzeAll("data/graal_data", "data/pre_analyzed", "01_pre_analysis/cuts");'
```

Pipeline skips stage when pre-analysis files already exist unless
`--force-preanalysis` is set.

See [Detector cuts](01-pre-analysis-cuts) and
[Data and storage](data-and-storage).
