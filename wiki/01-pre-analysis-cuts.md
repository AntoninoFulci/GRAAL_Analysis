# Detector cuts

`01_pre_analysis/CutManager.h` maps acquisition-period cut files to numeric
run IDs and exposes validated ROOT `TCutG` objects to pre-analysis.

## Cut families

Cut filenames follow:

```text
<Particle><Detector>Cut_<period>.cpp
```

Implemented families are central proton/pion, forward proton/pion, and forward
deuteron cuts. Period suffix matches raw-data folder such as `1999_uv` or
`2002_d1`.

## Map construction

`BuildCutMap(dataPath, cutPath)`:

1. scans raw data folders for `run<number>.root`;
2. records run-to-folder mapping;
3. loads matching cut macro;
4. maps loaded cut to every run in corresponding folder.

Map is built once before batch analysis. `ValidateRunCuts` checks each run on
its first event.

## Required versus absent cuts

`RequireCut` exits when needed cut is missing. Continuing would silently
reclassify every affected candidate.

Two absences are intentional:

- hydrogen runs do not require deuteron cuts;
- runs 4578–4605 (`2005_d1`) skip forward detector block because detector was
  unusable.

`HasCut`, `IsDeuteriumRun`, and `IsForwardExcluded` encode these policies.

## Adding cuts

Add correctly named ROOT macro under `01_pre_analysis/cuts/`. Ensure its
`TCutG` name matches loader convention and acquisition period exists in raw
folder map. Run representative pre-analysis and cut-validation tests before
production.
