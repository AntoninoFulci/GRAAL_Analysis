# Stage 03: simulation and geometry

[Generators](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/generators) and the [channel registry](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/00_common/physics/channels.py) define the signal and background channels, physical production thresholds, masses, branching fractions and detector-smearing assumptions. The workflow generates only channels kinematically open in the requested beam window. Seeds and thread assignment are explicit; a stage-label rename must not change them.

The ROOT event model uses simplified smearing and photon loss for BDT training. It does not establish full detector acceptance, trigger efficiency or background normalization. [Stage 04](04-bdt-training) folds the beam spectrum and channel weights into the training sample. This production interface is unchanged by the Geant4 diagnostic.

## Running Geant4

The [root README quick start](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/README.md#geant4-quick-start) gives dependencies and macOS/Spack, Linux and Windows commands. The portable [launcher](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/run.py) builds into a new diagnostic directory and runs `geometry`, `smoke`, `replay` or `view`. It regenerates GDML from the versioned snapshot instead of requiring a deleted historical output. `--gdml` reuses an explicitly selected file and skips conversion/overlap checks. `--macro` selects a transport macro in `smoke` mode. Run macros from the checkout root when they contain relative include paths; only the top-level macro is copied/hashed, so retain any included files separately.

The CMake project provides `graal_geometry`, `graal_gdml_check` with `BUILD_TESTING=ON`, and `graal_g4`. Batch builds require GDML; `-DGRAAL_WITH_QT=ON` adds interactive visualization. Installed Geant4 example sources are no longer needed. The GUI compatibility helper is `bash 03_mc_simulation/geant4/view_native.sh [geometry.gdml]`.

Spack environments and packages live outside the checkout. The portable recipe and native-macOS OpenGL override remain source files. The previous environment was copied to `~/.local/share/graal/spack-macos-qt`, verified file-by-file, then removed from the source directory. The [relocation manifest](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/reference/spack-relocation-20261026.json) preserves its hashes; installed packages were not rebuilt or removed.

## Geometry and verification boundaries

The preserved GEANT3 profile is GRAAL_26, old cylinders, new planar chambers, Catania disks and a **6.12 cm deuterium target** at density 0.162 g/cm³. Its [geometry snapshot](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/reference/geometry.g3) and [historical manifest](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/reference/manifest.json) identify the original sources and libraries. Neither was rewritten for transport.

The dated 23 October audit reports 98,685 independent GEANT3/GEANT4 queries covering 858 occupied physical identities, no medium/path differences, no overlaps above 0.001 mm, and GDML reopening checks for 16 materials. The old output archive and GEANT3 answers are absent locally, as recorded in [input availability](data-and-artifacts#local-availability-after-cleanup). Those historical results are not claimed as a new run.

On 26 October 2026, a fresh macOS arm64 build with Geant4 11.4.3 regenerated geometry with 480 BGO crystals and zero sampled overlap reports (10,000 surface samples per placement, 0.001 mm tolerance). Recreated probes checked **98,685 current Geant4 navigation results before/after GDML reopening**, with zero differences; the snapshot inventory (858 physical instances) and 16 material density/A/Z/fraction definitions agreed. This is a round-trip check, not a repeated independent GEANT3 comparison or proof of continuous navigation everywhere. Local logs and `geometry-verification.json` are retained under `results_test/geant4-20261026/` as dated diagnostic evidence.

## Transport physics and material policy

[Transport](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/src/transport.cc) runs serially with **FTFP_BERT_HP + G4EmStandardPhysics_option4**, conventionally `FTFP_BERT_HP_EMZ`. It combines Bertini/FTFP hadronic transport, HP low-energy neutron interactions, decays and detailed electromagnetic transport suitable as a starting point for BGO photon calorimetry. It does not provide a validated polarized exclusive γp → pηπ⁰ generator. No physics list is demonstrably the most accurate for this detector without data comparisons. Compare alternative models and vary production cuts before selecting a production configuration.

Default γ/e⁻/e⁺ production range cuts are 0.1 mm; proton cut is zero. These control secondary production, not detector thresholds or maximum step length. Macros may override them; `summary.json` records final values. Optical scintillation/light collection is not modeled: energy deposition is not digitized BGO response. See the official [physics-list guide](https://geant4.web.cern.ch/documentation/pipelines/master/plg_html/PhysicsListGuide/physicslistguide.html) and [installation guide](https://geant4.web.cern.ch/documentation/pipelines/master/ig_html/InstallationGuide/installguide.html).

The geometry-equivalence snapshot intentionally retains effective legacy A/Z values. Using it directly with option4 failed in `G4PenelopeOscillatorManager::BuildOscillatorTable()` on fractional-Z air. [Runtime material policy](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/src/TransportMaterials.hh) `diagnostic_materials_v1` therefore creates separate material definitions without modifying solids, placements, densities or the source GDML:

| Material | Runtime interpretation | Scientific qualification |
| --- | --- | --- |
| Deuterium (1) | Explicit isotope Z=1, A=2, 100% abundance; preserved target density | Pure-isotope assumption; does not turn this into a hydrogen target |
| Air (7) | NIST air composition at legacy density | Explicit composition assumption |
| GASMAGIC (18) | Expand ETHANE (snapshot 15) into C/H, retain argon and outer mass fractions | Reconstructs the recorded nested mixture |
| STESA (22) | Expand EPOXIDE (20) and GLASS (21) into C/H/O/Si, retain outer mass fractions | Reconstructs the recorded nested mixture |
| Other elements/mixtures | Preserve Z and elemental mass fractions; use NIST natural isotopes/atomic masses | Replaces effective atomic masses, including anomalous legacy cobalt mass in PERMENDUR |

The original snapshot defines the nested-mixture fractions. Material interpretation still needs detector-owner review, composition/isotope confirmation and material-budget validation before production. A different target requires an explicitly declared policy; the runtime rejects a target inconsistent with the frozen deuterium definition. `events/materials.json` records the actual runtime densities, elemental fractions and isotope abundances.

The supplied smoke macro transports ten 200 MeV photons from the target center toward BGO, with fixed seeds. `events.csv` records run/event IDs, total and BGO deposited energy in MeV, and step counts; it is **not** a GRAAL event tree or the 26-feature BDT contract. `input.mac`, per-run random-engine states, `summary.json`, launcher hashes and logs make this diagnostic reviewable. On 26 October this smoke completed with positive BGO deposits; it establishes runnable transport, not detector acceptance or meson-production accuracy.

## Exclusive truth replay

The nine nominal ROOT generators retain the true beam, recoil proton and decay photons before smearing. Backgrounds use `beam_true`, `proton_true`, `g0_true`…`gN_true`; signal keeps its existing named photon branches. `truth_schema_version=1` identifies new output. Capturing truth consumes no random numbers. A 26 October comparison of ten events per channel at seed 71 found all pre-existing branch values exactly unchanged; this checks the sampled RNG/serialization boundary, not an exhaustive physics validation.

[export_truth.py](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/export_truth.py) reads ROOT without modifying it. It validates generator/schema/sampling metadata, counts, beam window, on-shell particles and four-momentum conservation, then writes flat HEPEvt final states (proton plus photons, momenta/masses in GeV). Missing truth is an error; no smeared fallback exists. Default export is ten events, configurable with `--max-events`. File SHA-256, ROOT UUID, channel, seed, counts and entry mapping establish provenance. Unit generation weight is not a physical yield; flux, cross sections, decay branching fractions and polarization are not applied here.

`run.py replay --truth-dir <export>` verifies the export hashes, copies provenance into its new run directory and transports exactly the exported count using `G4HEPEvtInterface`. It needs no ROOT installation. Native equivalent: `graal_g4 geometry.gdml --hepevt primaries.dat NEW_OUTPUT_DIR`; the native interface validates the supported flat HEPEvt subset, while the launcher additionally enforces the export manifest. Replay uses seed 20261026, origin vertex and time zero. It intentionally transports **free-proton reaction truth through the frozen deuterium geometry** as a software diagnostic, not as a consistent production model.

`events.csv` includes zero-deposit events. `bgo_hits.csv` groups positive energy deposits by `(run,event,crystal)` with preserved BGO copy IDs 1–480, energy in MeV and earliest depositing pre-step time in ns. The sum per event agrees with BGO energy in `events.csv`. No light transport, electronics, clustering, trigger or detected-photon definition is inferred from these deposits. For replay, `(run=0,event)` joins `truth/truth.csv`; source entry and manifest identify the ROOT event. This bridge does not feed the existing analysis/BDT pipeline automatically.

The 26 October macOS check transported two actual generated events per channel through this bridge and a separate ten-event signal sample through the full launcher, checking event counts and BGO score sums. Malformed HEPEvt, missing truth, altered hashes/provenance and output overwrite attempts are rejected; fixed-seed replay is repeatable. Dated evidence is retained under `results_test/geant4-truth-20261026/`; disposable builds and ROOT/test fixtures are removed after verification. These small tests establish the software path only.

## Replacing the ROOT Monte Carlo

The current ROOT samples remain the pipeline input. A production replacement needs all of these boundaries closed:

1. Declare geometry and target for each relevant data-taking period, especially hydrogen versus deuterium; validate material composition, isotopes and continuous transport/material budget.
2. Validate the implemented exclusive signal/background truth bridge with the correct beam window, vertex, polarization, cross-section weights and decay branching fractions. Detector smearing is already excluded from transport input.
3. Extend BGO deposition scores into calibrated response, clustering, timing, thresholds, inefficiencies, trigger and digitization; add required detector subsystems.
4. Export the existing event/truth/provenance contract and preserve feature order, selection cuts, normalization and flux/exposure policies.
5. Compare data/control channels and current MC; demonstrate efficiencies, resolutions, acceptance, cut/model convergence and an uncertainty budget before replacing training or acceptance samples.

ROOT can remain the generator/I/O/analysis layer while Geant4 replaces simplified detector transport. Switching file technology alone does not close these scientific requirements. Open work is tracked in [status](status).

The active 26 October proposal compares the fast response and Geant4 on common truth, with grouped event splits and independent detector/data controls. It keeps the current BDT as a reference until detector validation and observable-bias checks support a change. See the [design and decision criteria](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/plans/2026-10-26-geant4-bdt-design.md) and [execution plan](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/plans/2026-10-26-geant4-bdt-execution.md). Adoption for BDT training and adoption for acceptance estimates are separate gates; the plan does not certify either.
