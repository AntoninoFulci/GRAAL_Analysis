# GRAAL Analysis

Analysis code for the GRAAL experiment: event processing, particle identification, and 4-vector reconstruction using the ROOT framework.

## Repository Structure

```
GRAAL_Analysis/
├── pre_analysis/
│   ├── PreAnalysis.h      # ROOT-generated TTree class (detector variables)
│   ├── PreAnalysis.C      # Analysis logic: Loop(), AnalyzeAll()
│   ├── CutManager.h       # Dynamic cut loading and lookup
│   └── cuts/              # TCutG definitions per particle/period/dataset
├── analysis/
│   ├── reconstruct_2pi0.py     # gamma p -> p pi0 pi0 reconstruction
│   └── reconstruct_eta_pi0.py  # gamma p -> p eta pi0 reconstruction
└── simulation/
    └── generate_eta_pi0_dataset.C  # MC generator (ML training dataset)
```

## Pipeline

1. **Pre-analysis** (`pre_analysis/`) — turns raw detector trees (`h70`) into
   per-event 4-vector trees (`h80`).
2. **Reconstruction** (`analysis/`) — pairs the photons of the `h80` tree into
   the meson candidates of a given channel. Run `reconstruct_2pi0.py` **before**
   `reconstruct_eta_pi0.py`.
3. **Simulation** (`simulation/`) — standalone Monte Carlo generator used to
   build a labelled dataset for a future ML model.

## Components

### PreAnalysis.h

ROOT-generated class providing structured access to all detector variables. Key variable groups:

| Group | Variables |
|-------|-----------|
| Event metadata | `Idrun`, `Idevt`, `Itrig`, `Ipol` |
| Tagging system | `Mplastic`, `Iplastic`, `Eg_tag_pm`, `Ncstrip`, `Eg_tag_strip` |
| Calorimeter (BGO) | `Nbclus`, `Eclus`, `Tetclus`, `Phiclus`, `Eclusc` |
| Central tracks | `Nass_3`, `Itipo_track`, `Dedx_track`, `Eclusc_track`, `Thet_centr_track` |
| Forward tracks | `Nparf`, `Theta_trf`, `Phi_trf`, `Tof_trf`, `De_trf` |
| Barrel / wall | `Nbar`, `Ebar`, `M_wal`, `Wal_par` |

### PreAnalysis.C

Implements `Loop()`, which produces an output TTree (`h80`) per run folder. The pipeline per event:

1. **Beam reconstruction** — 4-vector from first tagging strip energy `Eg_tag_strip[0]`
2. **Central detector** (`Nass_3` loop, `Itipo_track`):
   - `== 11` → photon candidate (neutral, BGO cluster energy)
   - `== 13/14` → charged: proton or pion via graphical cuts on `Eclusc_track` vs `Dedx_track`
3. **Forward detector** (`Nparf` loop, `Iass_trf`):
   - Neutral (`index == 1`): neutron (TOF ≥ 12 ns) or photon (7.5–12.5 ns)
   - Charged: proton / pion / deuteron via graphical cuts on `Tof_trf` vs `De_trf`
4. **4-vector reconstruction** — relativistic kinematics from β, detector angles
5. **Output** — fills `beam`, `gammas`, `neutrons`, `protons`, `deuterons` 4-vector branches plus lightweight angle branches (`gamma_theta/phi`, `pions_theta/phi`, `deuterons_theta/phi`, `fcharged_*`)

The wrapper `AnalyzeAll(base_in, base_out)` iterates all run subfolders and calls `PreAnalysis()` once per folder.

### CutManager.h

Loads and organizes `TCutG` particle ID cuts at startup. Cuts are keyed by `Particle → Detector → RunID`.

**Key functions:**

| Function | Description |
|----------|-------------|
| `BuildCutMap(dataPath, cutPath)` | Scans data folders for run IDs, loads all `.cpp` cut files |
| `GetCut(particle, detector, runID)` | Returns the `TCutG*` for a given particle/detector/run |
| `PrintCutMap()` | Prints a summary of loaded cuts for debugging |

Cut files follow the naming convention `{Particle}{Detector}Cut_{Year}_{Dataset}.cpp` (e.g. `ProtonFwdCut_2002_uv1.cpp`). `BuildCutMap` parses the filename to extract particle, detector region, and run period, then maps the cut to all run IDs belonging to that period's data folder.

### cuts/

Each file defines one `TCutG` polygon. Two parameter spaces are used:

| Detector region | X-axis | Y-axis |
|----------------|--------|--------|
| Central (Cnt) | `Eclusc_track` (corrected BGO energy) | `Dedx_track` (dE/dx) |
| Forward (Fwd) | `Tof_trf` (time of flight) | `De_trf` (energy loss) |

Cuts cover particles **Proton**, **Pion**, **Deuteron** across experimental periods 1998–2006 and datasets (`d1`, `d2`, `d3`, `uv`, `vis`, `fuv`, ...). Each cut is empirically determined from calibration data.

### analysis/

Channel reconstruction scripts that run on the pre-analysis `h80` trees. Both
chain all `subsample/analisi_*.root` files, loop over events, and for each event
pick the photon pairing that minimises a chi2 against the expected meson masses
(8% resolution, `chi2 < 10` cut), then write the reconstructed 4-vectors.

| Script | Channel | Output file | Output tree | Combination table |
|--------|---------|-------------|-------------|-------------------|
| `reconstruct_2pi0.py` | gamma p -> p pi0 pi0 | `reco_2pi0.root` | `reco_2pi0` | `combinations_2pi0.txt` |
| `reconstruct_eta_pi0.py` | gamma p -> p eta pi0 | `reco_eta_pi0.root` | `reco_eta_pi0` | `combinations_eta_pi0.txt` |

The combination table has one row per allowed pairing: four gamma indices plus
the two target masses, `i1 i2 i3 i4 m12 m34`. In the eta-pi0 case the pair with
target mass `> 0.4` GeV is assigned to the eta.

Run order: `reconstruct_2pi0.py` first, then `reconstruct_eta_pi0.py`.

```bash
python analysis/reconstruct_2pi0.py
python analysis/reconstruct_eta_pi0.py
```

### simulation/

`generate_eta_pi0_dataset.C` is a standalone ROOT macro generating
`gamma p -> p eta pi0` events with `TGenPhaseSpace` (eta and pi0 decaying to two
photons each) and applying Gaussian detector smearing. It stores both truth and
smeared 4-vectors, producing a labelled dataset (`eta_pi0_mc.root`, tree `mc`)
for training a future ML model.

```bash
root -l 'simulation/generate_eta_pi0_dataset.C(1000000)'
```

### analysis/ml/

XGBoost BDT study for photon pairing (gamma p -> p eta pi0): trains on the
labelled MC and compares pairing accuracy and reconstructed mass resolution
against the chi2 baseline. On idealised 4-photon MC the BDT reaches 98.1%
pairing accuracy vs 97.5% for chi2 (chi2 is already near-optimal here). See
`analysis/ml/README.md`. Design and plan in `docs/superpowers/`.

## Prerequisites

- ROOT 6.x
- C++17-compatible compiler
- GRAAL data files (ROOT TTrees with tree name `h70`)

## Usage

### Process all run folders

```bash
root -l pre_analysis/PreAnalysis.C
```
```cpp
AnalyzeAll("/path/to/graal_data", "/path/to/output")
```

`AnalyzeAll` calls `BuildCutMap` once, then runs `PreAnalysis` for each subfolder, writing one output file per period: `pre_analisi_<folder_name>.root`.

### Process a single glob pattern

```cpp
PreAnalysis("/path/to/graal_data/1999_uv/*.root", "out.root")
```

## Output Format

Output trees (`h80`) contain per-event branches:

| Branch | Type | Content |
|--------|------|---------|
| `beam` | `PxPyPzEVector` | Beam photon 4-vector |
| `gammas` | `vector<PxPyPzEVector>` | Photon candidates |
| `protons` | `vector<PxPyPzEVector>` | Proton candidates |
| `neutrons` | `vector<PxPyPzEVector>` | Neutron candidates |
| `deuterons` | `vector<PxPyPzEVector>` | Deuteron candidates |
| `gamma_theta/phi` | `vector<double>` | Photon angles (deg) |
| `pions_theta/phi` | `vector<double>` | Pion angles (deg) |
| `deuterons_theta/phi` | `vector<double>` | Deuteron angles (deg) |
| `fcharged_theta/phi/beta/tof` | `vector<double>` | Forward charged particle kinematics |
| `fcharded_de` | `vector<double>` | Forward charged dE |
| `Polarization` | `Int_t` | Beam polarization state |
| `RunNumber` | `Int_t` | Run ID |
