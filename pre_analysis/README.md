## Structure

### pre_analysis/

This folder contains the core pre-analysis code for processing GRAAL experiment data. The analysis pipeline consists of three main components that work together to identify and reconstruct particles from raw detector data.

#### PreAnalysis.h/C: Event Processing and Particle Reconstruction

**PreAnalysis.h** is a ROOT-generated class (automatically created from TTree data) that provides structured access to all detector variables in the GRAAL experiment. The class encapsulates over 100 variables covering:

- **Event Metadata**: Run ID (`Idrun`), event ID (`Idevt`), trigger information (`Itrig`), polarization (`Ipol`)
- **Tagging System**: Plastic scintillators (`Mplastic`, `Iplastic`, `Eg_tag_pm`), tagging strips (`Ncstrip`, `Mstrip`, `Xstrip`, `Eg_tag_strip`)
- **Calorimeter Data**: BGO clusters (`Nbclus`, `Mclus`, `Eclus`, `Tetclus`, `Phiclus`, `Eclusc`)
- **Track Reconstruction**: Central tracks (`Nass_3`, `Itipo_track`, `Dedx_track`, `Eclusc_track`, angles), forward tracks (`Nparf`, `Theta_trf`, `Phi_trf`, `Tof_trf`, `De_trf`)
- **Detector Components**: Barrel (`Nbar`, `Ibar`, `Ebar`), wall detectors (`M_wal`, `Wal_par`), cylindrical traces (`Nb_traces_cyl`)

**PreAnalysis.C** implements the main analysis logic in the `Loop()` method, which:

1. **Initializes Output**: Creates ROOT file with TTree containing reconstructed particles as 4-vectors (`ROOT::Math::PxPyPzEVector`) and angles
2. **Processes Each Event**: Loops through all events in the input TChain
3. **Particle Identification**:
   - **Photons**: Identified by track type (`Itipo_track == 11`) in central detector or TOF window (7.5-12.5 ns) in forward
   - **Protons**: Use graphical cuts on energy deposition vs. dE/dx (central) or TOF vs. dE/dx (forward)
   - **Pions**: Identified via cuts in parameter space, storing angles for further analysis
   - **Neutrons**: TOF > 12 ns in forward detector
   - **Deuterons**: Graphical cuts in forward detector TOF vs. energy space
4. **4-Vector Reconstruction**: Calculates momentum components using relativistic kinematics and detector angles
5. **Output Storage**: Fills TTree with identified particles and their properties

The analysis distinguishes between central (high-angle) and forward (low-angle) detector regions, applying different identification strategies for each.

#### CutManager.h: Dynamic Cut Management System

This header file implements a sophisticated cut management system that dynamically loads and organizes particle identification cuts based on experimental conditions:

**Core Functionality**:
- **Automatic Mapping**: Scans data directories to build run ID → folder mappings
- **Cut Loading**: Parses cut filenames to extract particle type, detector region, and run period
- **Hierarchical Storage**: Organizes cuts in nested maps: `Particle → Detector → RunID → TCutG*`
- **Error Handling**: Provides detailed diagnostics when cuts are missing or invalid

**Key Functions**:
- `BuildCutMap()`: Main function that scans directories and loads all cut files
- `GetCut(particle, detector, runID)`: Retrieves appropriate cut for specific conditions
- `PrintCutMap()`: Debugging utility to visualize loaded cuts

**File Naming Convention**: Cuts follow pattern `{Particle}{Detector}Cut_{Year}_{Dataset}.cpp` (e.g., `PionFwdCut_1999_d1.cpp`)

#### cuts/: Particle Identification Cut Definitions

This subdirectory contains individual C++ files, each defining a single `TCutG` (graphical cut) object. Each cut is a closed polygon in 2D parameter space used for particle separation.

**Example: PionCntCut_1998_uv.cpp**
```cpp
TCutG* PionCntCut_1998_uv() {
    TCutG *cutg = new TCutG("PionCntCut_1998_uv", 19);
    cutg->SetVarX("Eclusc_track");  // X-axis: Corrected cluster energy
    cutg->SetVarY("Dedx_track");    // Y-axis: Energy loss (dE/dx)
    // 19 points defining the pion acceptance region
    cutg->SetPoint(0, 0.0536919, 2.58681);
    // ... additional points ...
    return cutg;
}
```

**Cut Types by Detector Region**:
- **Central (Cnt)**: Cuts in `Eclusc_track` vs `Dedx_track` space for charged particle separation
- **Forward (Fwd)**: Cuts in `Tof_trf` vs `De_trf` space for TOF-based identification

**Particle Types**: Pions, protons, deuterons across multiple experimental periods (1998-2006) and datasets (d1, d2, uv, vis, etc.)

The cuts are empirically determined from calibration data and define the regions where each particle type produces distinct detector signatures.

## Usage

1. Ensure ROOT is properly installed and configured.

2. Compile the analysis code:
   ```bash
   root
    .L PreAnalysis.C
    AnalyzeAll()
   ```

4. The analysis will process input data files and produce output ROOT files with filtered and analyzed events.

## Data Format

Input data should be in ROOT TTree format with the structure defined in PreAnalysis.h. The tree is expected to contain event-by-event information from the GRAAL detectors.