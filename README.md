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

These commands run scientific campaigns after preflight and confirmation. Restore missing local inputs first; see [availability after cleanup](wiki/data-and-artifacts.md#local-availability-after-cleanup). Their UV and VIS extractions include the reproducible [core-versus-tail candle test](wiki/core-tail-candle-test.md) with a `±0.05 GeV` raw-mass window. `--phi-bins 8|12|16` defaults to 12; `--best-binning` chooses per point. [Finite-bin correction](wiki/finite-bin-correction.md) applies only to the ratio estimator. The reduced UV+VIS input is diagnostic, not a normalized production dataset. Optional flux recovery remains experimental.

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

## Geant4 quick start

`03_mc_simulation/geant4` builds the preserved GRAAL geometry, runs diagnostic transport of particles or exported generator truth, and opens a Qt viewer. It needs **Python ≥3.10, CMake ≥3.16, a C++17 compiler, Geant4 ≥11.4 with GDML/Xerces-C and its physics datasets**. Qt 6/OpenGL are needed only for the viewer. ROOT/PyROOT is needed only to generate/export ROOT truth; geometry, smoke, replay and viewer need no ROOT or installed Geant4 examples. Tested locally with Geant4 11.4.3 on macOS arm64; Linux and Windows commands below have not been executed here.

From the repository root, after selecting an installation as described below:

```bash
python3 -B 03_mc_simulation/geant4/run.py geometry
python3 -B 03_mc_simulation/geant4/run.py smoke
python3 -B 03_mc_simulation/geant4/run.py view
```

Each command creates a new `results_test/geant4-<mode>-<timestamp>/` directory, builds there, and regenerates GDML from the frozen snapshot. `geometry` checks sampled overlaps; `smoke` transports ten 200 MeV photons toward the BGO and writes `events/events.csv`, material composition, random-engine state and a diagnostic summary. `view` opens the interactive detector. Logs and SHA-256 provenance are in the run directory. Existing output directories are refused; select a new one with `--work-dir results_test/my-new-check`. Once reviewed, remove disposable build/test directories; retain only needed diagnostic evidence.

Use `--geant4-prefix /path/to/install` to select Geant4 explicitly, `--gdml /path/to/geometry.gdml` to reuse a geometry, or `smoke --macro /path/to/run.mac` for another diagnostic. An explicit GDML bypasses conversion/overlap checking. `bash 03_mc_simulation/geant4/view_native.sh [geometry.gdml]` remains available on Unix. Paths with spaces are supported. Batch execution needs no display.

### macOS — external Spack

Install Xcode command-line tools (`xcode-select --install`), CMake, Python and [Spack](https://spack.readthedocs.io/en/latest/getting_started.html). Keep Spack itself and its environments outside the checkout. On this workstation the existing environment was moved, with file hashes verified, to `~/.local/share/graal/spack-macos-qt`; installed packages were preserved:

```bash
export SPACK_BIN="$HOME/Software/spack/bin/spack"  # adjust to your installation
export SPACK_ENV="$HOME/.local/share/graal/spack-macos-qt"
python3 -B 03_mc_simulation/geant4/run.py smoke
python3 -B 03_mc_simulation/geant4/run.py view
```

For a **new** installation, load Spack's shell setup and create an external environment from the portable recipe:

```bash
source /path/to/spack/share/spack/setup-env.sh
spack repo add "$PWD/03_mc_simulation/geant4/spack-repo/spack_repo/graal"
spack env create -d "$HOME/.local/share/graal/spack-macos-qt" 03_mc_simulation/geant4/spack.yaml
spack -e "$HOME/.local/share/graal/spack-macos-qt" install
export SPACK_ENV="$HOME/.local/share/graal/spack-macos-qt"
```

The recipe includes Qt and datasets. Its small package override selects Apple's native OpenGL framework rather than XQuartz, avoiding incompatible Cocoa contexts. The checkout contains only this recipe/package source, not a concretized environment or lockfile. If multiple installations match, set `SPACK_SPEC=/your-installation-hash`, or use `--geant4-prefix`. `Geant4_DIR` and `GEANT4_PREFIX` are also accepted.

### Linux

Use an existing Geant4 11.4 installation with GDML and datasets, or build the [official Geant4 source](https://geant4.web.cern.ch/download/) outside this repository. On Debian/Ubuntu, base build dependencies are `build-essential cmake python3 libxerces-c-dev`; add `qt6-base-dev libgl1-mesa-dev libxmu-dev libxi-dev` for the viewer. For example, after extracting the source into `$HOME/src/geant4-v11.4.3`:

```bash
cmake -S "$HOME/src/geant4-v11.4.3" -B "$HOME/build/geant4" \
  -DCMAKE_INSTALL_PREFIX="$HOME/.local/geant4-11.4.3" \
  -DCMAKE_BUILD_TYPE=Release -DGEANT4_USE_GDML=ON \
  -DGEANT4_INSTALL_DATA=ON -DGEANT4_USE_QT=ON
cmake --build "$HOME/build/geant4" --parallel 4
cmake --install "$HOME/build/geant4"
source "$HOME/.local/geant4-11.4.3/bin/geant4.sh"
export GEANT4_PREFIX="$HOME/.local/geant4-11.4.3"
python3 -B 03_mc_simulation/geant4/run.py smoke
```

For servers, omit Qt packages and set `-DGEANT4_USE_QT=OFF`; `geometry` and `smoke` still work. For `view`, use a graphical session with functioning Qt/OpenGL. `Geant4_DIR` supports installations with a nonstandard CMake package directory, including `lib64`.

### Windows — native PowerShell

Install Python ≥3.10, CMake, Visual Studio 2022 with **Desktop development with C++**, and an x64 Xerces-C build. Use Geant4 11.4.x and dependencies built for the same MSVC architecture/runtime; Qt 6 MSVC is optional. In Developer PowerShell, build the [official source](https://geant4.web.cern.ch/documentation/pipelines/master/ig_html/InstallationGuide/installguide.html), adjusting these paths:

```powershell
cmake -S C:/src/geant4-v11.4.3 -B C:/build/geant4 -A x64 `
  -DCMAKE_INSTALL_PREFIX=C:/Geant4/11.4.3 -DGEANT4_USE_GDML=ON `
  -DGEANT4_INSTALL_DATA=ON -DGEANT4_USE_QT=OFF `
  -DCMAKE_PREFIX_PATH=C:/deps/xerces
cmake --build C:/build/geant4 --config Release --parallel 4
cmake --install C:/build/geant4 --config Release
$env:GEANT4_PREFIX = 'C:/Geant4/11.4.3'
$env:PATH = "C:/Geant4/11.4.3/bin;C:/deps/xerces/bin;$env:PATH"
py -3 -B 03_mc_simulation/geant4/run.py smoke
```

For the viewer, rebuild Geant4 with `-DGEANT4_USE_QT=ON` and `'-DCMAKE_PREFIX_PATH=C:/deps/xerces;C:/Qt/6.x/msvc2022_64'`; add Qt's `bin` to `PATH`, then run `py -3 -B 03_mc_simulation/geant4/run.py view`. The launcher handles `.exe` and `Release/` output directories. Bash/Spack are not required. WSL follows the Linux instructions.

All platforms need datasets from the **same Geant4 release**. Missing-data errors require fixing the installation, not disabling processes: source `geant4.sh` on Unix, or set `GEANT4_DATA_DIR` to the directory containing the installed `G4NDL*`, `G4EMLOW*`, etc. Existing per-dataset `G4…DATA` variables take precedence and must not point to another release. Qt/DLL errors require matching dependency paths; `Geant4_DIR` must contain `Geant4Config.cmake`.

### ROOT truth → Geant4

All nine nominal generators now retain unsmeared beam, proton and photon four-vectors. Existing smeared branches and seeded random streams are preserved. Old background files without truth must be regenerated into a **new diagnostic directory**; the exporter refuses smeared-only input. Existing signal truth is accepted when its generator metadata is valid.

With ROOT/PyROOT loaded and this checkout installed (`python3 -m pip install -e . --no-deps` after the normal setup), generate ten signal events and export them on macOS/Linux:

```bash
mkdir -p results_test/g4-example
root -l -b -q '03_mc_simulation/generators/generate_eta_pi0_dataset.C(10,1.5,1.6,"results_test/g4-example/eta_pi0_mc.root",71)'
python3 -B 03_mc_simulation/geant4/export_truth.py results_test/g4-example/eta_pi0_mc.root results_test/g4-example/truth --max-events 10
python3 -B 03_mc_simulation/geant4/run.py replay --truth-dir results_test/g4-example/truth --work-dir results_test/g4-example/transport
```

Choose a fresh example directory on reruns: export/transport refuse existing output directories, while the ROOT generator itself can overwrite its output file. Substitute another `generate_<channel>_dataset.C` and `<channel>_mc.root` for backgrounds. `--channel` allows a nonstandard ROOT filename. Export defaults to at most ten events, checks generator metadata, on-shell four-vectors and four-momentum conservation, and never applies detector smearing.

Windows can replay the same exported `truth/` directory without ROOT:

```powershell
py -3 -B 03_mc_simulation/geant4/run.py replay --truth-dir C:/inputs/truth --work-dir results_test/g4-replay-windows
```

Native Windows export additionally needs compatible CERN ROOT/PyROOT and the installed Python project; use the same `export_truth.py` arguments with `py -3`. WSL follows the Linux example. Transport uses Geant4's HEPEvt reader, fixed seed 20261026 and origin/time-zero vertices. `truth/manifest.json` records source SHA-256/UUID and generator metadata; `truth.csv` maps Geant4 event IDs to ROOT entries. `events/events.csv` contains all completed events, including zero BGO deposits; `events/bgo_hits.csv` contains positive deposits per crystal (IDs 1–480), with earliest depositing pre-step time in ns. These are energy deposits, not calibrated signals or reconstructed photons. Exported events have unit generation weights, without flux, cross-section or branching-ratio normalization; polarization is not modeled.

### Physics and the ROOT replacement boundary

The diagnostic uses **FTFP_BERT_HP + electromagnetic option4 (`FTFP_BERT_HP_EMZ`)**, with 0.1 mm γ/e⁻/e⁺ production range cuts and zero proton range cut. This is an accuracy-oriented starting point for photon calorimetry and secondary neutron transport, not a demonstrated universally “most accurate” choice. Range cuts are secondary-production thresholds, not track-length or detector thresholds. Cut convergence and physics-model comparisons remain required.

**Do not replace the current ROOT-generated analysis samples yet.** The ROOT → Geant4 diagnostic bridge works for signal and backgrounds; production still needs period-specific geometry/material validation, beam/vertex/polarization and normalization, calibrated response, trigger, digitization and analysis event format. The frozen geometry has a **deuterium** target, while the generators describe a free proton. Runtime material interpretation is explicit and diagnostic; the original snapshot remains unchanged. ROOT remains useful for generation and I/O, with Geant4 supplying transport. See [material policy, verification and migration requirements](wiki/03-monte-carlo-simulation.md).
