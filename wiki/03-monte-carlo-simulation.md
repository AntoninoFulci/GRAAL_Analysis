# Stage 03: simulation and geometry

[Generators](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/generators) and the [channel registry](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/00_common/physics/channels.py) define the signal and background channels, physical production thresholds, masses, branching fractions and detector-smearing assumptions. The workflow generates only channels kinematically open in the requested beam window. Seeds and thread assignment are explicit; a stage-label rename must not change them.

The ROOT event model uses simplified smearing and photon loss for BDT training. It does not establish full detector acceptance, trigger efficiency or background normalization. [Stage 04](04-bdt-training) folds the beam spectrum and channel weights into the training sample. This production interface is unchanged by the Geant4 diagnostic.

On 27 October the scientific owner defined the primary G4 role as efficiencies for cross-section estimates and residual backgrounds. The Fortran detector is confirmed as the basis, with liquid H/D and nominal 6/12 cm target options; preserve GENBOD weights and use measured production distributions or declared models. Required charged-particle benchmarks are central ΔE–E BGO and forward ΔE–TOF with pion/proton PID; γ/neutron discrimination is exploratory. See [requirements and validation](geant4-validation), the [original source map](legacy-fortran-map) and [production cross-section sources](geant4-cross-section-sources). These are requirements and source findings, not capabilities already implemented in the diagnostic replay.

## Running Geant4

From 9 November, batch transport records [raw detector steps and channel identities](geant4-hits), including zero-deposit crossings and aborted-event accounting. Existing BGO aggregates remain available in the same compressed `transport.root` as all detector tables and metadata (hit schema 2). ROOT ≥6.30 is now a native build dependency; no parallel CSV transport dump is written. Old GDML must be regenerated to add GEANT3 sensitivity metadata; archived source snapshots stay unchanged.

An offline [legacy09 BGO/barrel diagnostic digitizer](geant4-digitization) now consumes those ROOT hits without rerunning transport. Its C++ kernels reproduce the recovered MC arithmetic; its ROOT ledger preserves empty events and flags unsupported barrel overflow. This does not supply calibrated response, full trigger or reconstruction. `GRAAL_RESPONSE_ONLY=ON` builds `graal_digitize` with ROOT alone.

The [root README quick start](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/README.md#geant4-quick-start) gives dependencies and macOS/Spack, Linux and Windows commands. The portable [launcher](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/run.py) builds into a new diagnostic directory and runs `geometry`, `smoke`, `replay` or `view`. It regenerates GDML from the versioned snapshot instead of requiring a deleted historical output. `--gdml` reuses an explicitly selected file and skips conversion/overlap checks. `--macro` selects a transport macro in `smoke` mode. Run macros from the checkout root when they contain relative include paths; only the top-level macro is copied/hashed, so retain any included files separately.

The CMake project provides `graal_geometry`, `graal_gdml_check` with `BUILD_TESTING=ON`, and `graal_g4`. Batch builds require GDML; `-DGRAAL_WITH_QT=ON` adds interactive visualization. Installed Geant4 example sources are no longer needed. The GUI compatibility helper is `bash 03_mc_simulation/geant4/view_native.sh [geometry.gdml]`.

Spack environments and packages live outside the checkout. The portable recipe and native-macOS OpenGL override remain source files. The previous environment was copied to `~/.local/share/graal/spack-macos-qt`, verified file-by-file, then removed from the source directory. The [relocation manifest](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/reference/spack-relocation-20261026.json) preserves its hashes; installed packages were not rebuilt or removed.

## Monte Carlo per acquisition period

From 6 November, the launcher consumes the verified publication in `config/support/target_conditions_current/` through `--period PERIOD --seed SEED`. This derives a separate target geometry and samples a separate interaction-vertex distribution for each period. The [target database](target-vertex) supplies fitted active length and center z, material label from the run catalog, and the full equal-run mean XY map. Publication CSV/JSON and the original NPZ are checked against their published SHA-256 values before preparing inputs. Raw data, the NPZ and the frozen GEANT3 snapshot remain unchanged.

Prepare all available configurations, without building or starting transport:

```bash
python -B 03_mc_simulation/geant4/period_conditions.py \
  --output results_test/my-period-study/conditions --seed 20261106
```

The destination must be new. `--conditions DIRECTORY` selects another verified publication; repeated `--period PERIOD` selects a subset. `campaign.json` lists **20 available periods**, with distinct seeds in sorted period order, and explicitly records `2001_d` and `2005_d1` as unavailable. No fallback geometry is assigned to either. Each period has `period.json`, `geometry.g3` and `conditions.dat`. This preparation is not an MC production campaign.

Run one period through the existing launcher, after exporting independently generated truth for that period with `export_truth.py`:

```bash
python -B 03_mc_simulation/geant4/run.py replay \
  --period 1998_uv --seed 20261106 \
  --truth-dir results_test/my-period-study/truth-1998_uv \
  --work-dir results_test/my-period-study/mc-1998_uv
```

Geant4 discovery follows the existing prefix/Spack policy. `geometry` and `smoke` also accept `--period` and `--seed`; `view` and arbitrary `--gdml` do not. Repeating replay for each period produces independent output directories. Generate truth with separate generator seeds and retain source UUID/entry identity; reusing one truth sample across periods creates correlated origins, which must remain grouped in downstream training/validation splits. The launcher checks the truth energy window lies within the existing shared UV (1.10–1.50 GeV) or VIS (0.9313–1.10 GeV) analysis profile. A narrower window remains a subset, not full period coverage. No incident-energy spectrum, polarization, flux/exposure weighting or normalization is inferred from XY.

The exported `conditions.dat` is also accepted by native batch commands as a trailing `--conditions FILE`. Use the matching derived GDML; native transport verifies CIBM dimensions, material and nominal placement against the conditions. For many diagnostics, one build of `graal_geometry` and `graal_g4` can serve all prepared periods: convert each period's `geometry.g3` into a new GDML directory, then transport with that period's `conditions.dat`. Native ROOT replay checks scalar schemas, final-state ordering, kinematics and consumed-file identity; the Python launcher additionally binds the original generator, exact vectors and beam window. Historical HEPEvt input remains supported.

Declared approximations:

- **Cell diameter 50 mm and cell XY origin are historical assumptions**, not measured dimensions/alignment. The observed beam offset is never used as the transverse cell center. Native h70 coordinates are used as nominal detector coordinates; alignment remains unvalidated.
- **XY samples the full observed map**, selecting a weighted bin and a uniform point inside it. Points outside the nominal target radius are rejected explicitly; the `vertices` TTree in `events/transport.root` records each accepted coordinate and number of XY attempts. This is the observed interaction proxy conditioned on the cell radius, without acceptance/resolution unfolding. z is sampled independently and uniformly between the fitted target ends. The acceptance-shaped measured z histogram is not imposed on generated interactions.
- **Mechanical adaptation is diagnostic**: move both FEN3 windows to the fitted ends, preserve their thickness, keep the upstream ends and radial dimensions of ENVI/ENVM, and adjust their axial spans to meet the new cell. Other detector records stay exact. This avoids intersecting an extended liquid cell with the old internal feed tube; it is not a measurement of period-specific passive material.
- **P periods use explicit liquid H-1 at 0.0708 g/cm³**, a diagnostic density assumption; D retains pure D-2 at the frozen 0.162 g/cm³. Free-proton exclusive replay is supported for the 13 valid P periods. The seven valid D geometries support particle-gun diagnostics; exclusive replay is refused until an appropriate nuclear generator is supplied.

`run.json` embeds period provenance and artifact hashes. The `summary` object in `events/transport.root` records actual target, period, base seed and vertex policy. The effective seed is `base_seed + run_id`, applied at the start of each run so macro seed commands cannot silently override it; the embedded `random_state_run_N` object records the resulting engine state. Existing commands without `--period` preserve their frozen diagnostic behavior. Detector response, trigger, digitization and production acceptance remain open.

Verification on 6 November, macOS/Geant4 11.4.3: **50 focused Python/native tests passed**, including histogram validation, fixed-seed repeatability despite macro seed commands, cylindrical XY rejection, geometry mismatch rejection and the existing nine-channel truth bridge. All **20 derived geometries** reported zero sampled overlaps at 0.001 mm tolerance, 10,000 surface samples per placement. A separate **16-event pilot** covered short UV (full launcher), long UV, VIS and a D photon gun; zero aborts, vertices within the declared cell/profile and per-crystal sums consistent with BGO totals. Dated logs, input hashes, source snapshot and validation JSON remain in `results_test/geant4-periods-20261106/`; builds and disposable fixtures were removed. These checks establish the conditions-to-transport boundary, not physical acceptance or period-specific passive-material accuracy.

## Geometry and verification boundaries

The preserved GEANT3 profile is GRAAL_26, old cylinders, new planar chambers, Catania disks and a **6.12 cm deuterium target** at density 0.162 g/cm³. Its [geometry snapshot](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/reference/geometry.g3) and [historical manifest](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/reference/manifest.json) identify the original sources and libraries. Neither was rewritten for transport.

The dated 23 October audit reports 98,685 independent GEANT3/GEANT4 queries covering 858 occupied physical identities, no medium/path differences, no overlaps above 0.001 mm, and GDML reopening checks for 16 materials. The old output archive and GEANT3 answers are absent locally, as recorded in [input availability](data-and-artifacts#local-availability-after-cleanup). Those historical results are not claimed as a new run.

On 26 October 2026, a fresh macOS arm64 build with Geant4 11.4.3 regenerated geometry with 480 BGO crystals and zero sampled overlap reports (10,000 surface samples per placement, 0.001 mm tolerance). Recreated probes checked **98,685 current Geant4 navigation results before/after GDML reopening**, with zero differences; the snapshot inventory (858 physical instances) and 16 material density/A/Z/fraction definitions agreed. This is a round-trip check, not a repeated independent GEANT3 comparison or proof of continuous navigation everywhere. Local logs and `geometry-verification.json` are retained under `results_test/geant4-20261026/` as dated diagnostic evidence.

## Transport physics and material policy

[Transport](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/src/transport.cc) uses **FTFP_BERT_HP + G4EmStandardPhysics_option4**, conventionally `FTFP_BERT_HP_EMZ`. ROOT replay supports native event multithreading; execution policy is described below. It combines Bertini/FTFP hadronic transport, HP low-energy neutron interactions, decays and detailed electromagnetic transport suitable as a starting point for BGO photon calorimetry. It does not provide a validated polarized exclusive γp → pηπ⁰ generator. No physics list is demonstrably the most accurate for this detector without data comparisons. Compare alternative models and vary production cuts before selecting a production configuration.

Default γ/e⁻/e⁺ production range cuts are 0.1 mm; proton cut is zero. These control secondary production, not detector thresholds or maximum step length. Macros may override them; the ROOT `summary` object records final values. Optical scintillation/light collection is not modeled: energy deposition is not digitized BGO response. See the official [physics-list guide](https://geant4.web.cern.ch/documentation/pipelines/master/plg_html/PhysicsListGuide/physicslistguide.html) and [installation guide](https://geant4.web.cern.ch/documentation/pipelines/master/ig_html/InstallationGuide/installguide.html).

The geometry-equivalence snapshot intentionally retains effective legacy A/Z values. Using it directly with option4 failed in `G4PenelopeOscillatorManager::BuildOscillatorTable()` on fractional-Z air. [Runtime material policy](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/src/TransportMaterials.hh) `diagnostic_materials_v1` therefore creates separate material definitions without modifying solids, placements, densities or the source GDML:

| Material | Runtime interpretation | Scientific qualification |
| --- | --- | --- |
| Deuterium (1) | Explicit isotope Z=1, A=2, 100% abundance; preserved target density | Pure-isotope assumption; does not turn this into a hydrogen target |
| Air (7) | NIST air composition at legacy density | Explicit composition assumption |
| GASMAGIC (18) | Expand ETHANE (snapshot 15) into C/H, retain argon and outer mass fractions | Reconstructs the recorded nested mixture |
| STESA (22) | Expand EPOXIDE (20) and GLASS (21) into C/H/O/Si, retain outer mass fractions | Reconstructs the recorded nested mixture |
| Other elements/mixtures | Preserve Z and elemental mass fractions; use NIST natural isotopes/atomic masses | Replaces effective atomic masses, including anomalous legacy cobalt mass in PERMENDUR |

The original snapshot defines the nested-mixture fractions. Material interpretation still needs detector-owner review, composition/isotope confirmation and material-budget validation before production. Without period conditions, the runtime rejects a target inconsistent with frozen deuterium; period mode explicitly selects the H/D policy above. The ROOT `materials` object records actual runtime densities, elemental fractions and isotope abundances.

The supplied smoke macro transports ten 200 MeV photons from the target center toward BGO, with fixed seeds. `events` TTree records run/event IDs, total and BGO deposited energy in MeV, and step counts; it is **not** a GRAAL event tree or the 26-feature BDT contract. Embedded macro, per-run random-engine states and summary in `transport.root`, together with launcher hashes and logs, make this diagnostic reviewable. On 26 October this smoke completed with positive BGO deposits; it establishes runnable transport, not detector acceptance or meson-production accuracy.

## Exclusive truth replay

From 11 November 2026, the supported launcher defaults to **one ROOT replay job
with all available CPUs** (`--threads auto`). CPU affinity is respected where
available. `--threads N` selects native `G4MTRunManager`, including N=1 for MT
comparisons; `--threads serial` retains the historical sequential RNG stream.
GPS/smoke, visualization and legacy HEPEvt remain serial and reject explicit MT
counts. Native `graal_g4 --root-events ... --threads N` enables the same MT path;
omitting the native option preserves serial compatibility. An installation built
without Geant4 MT fails clearly on an MT request. Unset `G4FORCENUMBEROFTHREADS`:
the launcher rejects this competing override instead of reporting a false count.

Workers share geometry/physics and validated truth, but own actions, vertex
sampling state and event buffers. Scheduling assigns one event at a time. The
writer commits events in source order and adds global sensitive-step, callback
and passive-reset offsets, preserving cylinder state across the entire job.
Buffer memory scales with one event per worker, plus preloaded truth and ROOT
buffers; a slow early event can temporarily hold later workers. Output schemas,
compact/full storage, cuts and physics are unchanged. Summary and `run.json`
record mode/thread count; native summary also records RNG engine, event modulo
and `geant4_mt_per_event` seed policy. MT streams need not match historical serial
streams, and one large stream is not the old collection of independent batches.

The launcher holds `results_test/geant4-runtime/transport.lock` through build and
transport. A second launcher refuses admission. On POSIX, children inherit the
OS lock so killing the launcher cannot admit another job while its child survives.
The empty lock file is permanent coordination state; do not unlink it. Direct
native invocations bypass launcher admission and require external scheduling.
Windows normal locking is implemented; retaining exclusion after launcher death
is unsupported there. Native MT execution has only been verified on macOS. The launcher builds once for the submitted job;
digitization and later reconstruction are separate stages and are not made
multithreaded by this transport option.

With `--period`, omitting `--seed` now draws a nonzero 31-bit seed from OS entropy
and records it in `run.json` before invoking producers. The same value is bound
into period conditions/native provenance; ROOT replay excludes its generator seed
from the automatic transport draw. An explicit `--seed` remains the reproducible
override. Campaigns draw and freeze distinct seeds for all stochastic stages before
launch; restarting a declared campaign must reuse those values, never redraw them.
Distinct seeds alone do not establish statistical independence or replace grouping
by generator source and continuous cylinder stream.

The nine nominal ROOT generators retain the true beam, recoil proton and decay photons before smearing. Backgrounds use `beam_true`, `proton_true`, `g0_true`…`gN_true`; signal keeps its existing named photon branches. `truth_schema_version=1` identifies new output. Capturing truth consumes no random numbers. A 26 October comparison of ten events per channel at seed 71 found all pre-existing branch values exactly unchanged; this checks the sampled RNG/serialization boundary, not an exhaustive physics validation.

[export_truth.py](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/03_mc_simulation/geant4/export_truth.py) reads the generator ROOT without modifying it. Default output is `truth.root` schema 2: native `events` and `primaries` TTrees plus metadata. It validates original generator hash/UUID/schema/sampling, counts, beam window, exact unsmeared vectors, mass shells and four-momentum conservation. Event rows preserve source entry, incident energy and generation weight; primary rows contain the final-state proton followed by photons in GeV. Missing truth is an error; no smeared fallback exists. Default export is at most 10 events, configurable with `--max-events`. Current supported sampling is unit-unweighted accept/reject, without flux, cross sections, branching fractions or polarization factors. Source-generated and exported-prefix counts remain distinct.

`run.py replay --truth-dir <export> --period 1998_uv --seed <seed>` validates and copies the ROOT, transports exactly the exported count, and revalidates the original generator after transport before declaring completion. ROOT/PyROOT are required for export and full Python validation. Native equivalent: `graal_g4 geometry.gdml --root-events truth.root NEW_OUTPUT_DIR --conditions conditions.dat`. The native reader owns structure/kinematics/input-digest validation; original-source provenance belongs to the Python launcher and post-transport binder. Use the launcher for the supported source-bound workflow. ROOT replay requires hydrogen period conditions for free-proton truth; the target and sampled vertices are explicit in the transport summary. Original schema 1 HEPEvt/CSV exports remain readable, and `--format hepevt` explicitly requests the legacy export; that compatibility mode retains its historical behavior.

`events` TTree includes no-hit events. `bgo_hits` groups positive deposits by `(run,event,crystal)` with BGO copy IDs 1–480, MeV and earliest depositing pre-step time in ns. Sensitive steps, raw primaries and cylinder context remain in the same ROOT. The ROOT replay source uses `(run=0,event)` in source order. `beam_ledger.bind_beam_ledger` proves native input path/digest, raw primary identity/momenta and original generator provenance before writing `beam.root`; the tagger reads this incident energy and produces measured strip energy. The h70 bridge optionally consumes the exact same ledger and retains weights for every generated/transported event, including unavailable/rejected rows. No photon truth is substituted into the measured selection.

The 10 November fixed pilot generated 128 eta_pi0 events in UV 1.10–1.50 GeV (generator seed 20261110, transport seed 20261111), transported all 128 with zero aborts, and retained unit weights with sumw=sumw²=128. The measured chain produced 32 h70, 32 h80 and 0 h85. Both chi2 and BDT reconstruction ran to valid empty schema 2 outputs; the model loaded but no event was scored. All three four-photon h80 events lacked an identified proton; their charged candidates lie outside the unchanged proton PID polygons. These are diagnostic populations, not a physical efficiency estimate. Complete event accounting, tests and review are retained under `results_test/geant4-reaction-pilot-20261110/`; current details in [reconstruction](geant4-reconstruction).
The 26 October macOS check transported two actual generated events per channel through this bridge and a separate ten-event signal sample through the full launcher, checking event counts and BGO score sums. Those checks rejected malformed HEPEvt, missing truth, altered hashes/provenance and output overwrite attempts; the small dated replay checks agreed. The later Be8 repeatability discrepancy remains open as documented in [reconstruction](geant4-reconstruction). The historical evidence path was `results_test/geant4-truth-20261026/` (not currently verified as available); disposable builds and ROOT/test fixtures are removed after verification. These small tests establish the software path only.

## Replacing the ROOT Monte Carlo

The current ROOT samples remain the pipeline input. A production replacement needs all of these boundaries closed:

1. Declare geometry and target for each relevant data-taking period, especially hydrogen versus deuterium; validate material composition, isotopes and continuous transport/material budget.
2. Validate the implemented exclusive signal/background truth bridge with the correct beam window, vertex, polarization, cross-section weights and decay branching fractions. Detector smearing is already excluded from transport input.
3. Extend BGO deposition scores into calibrated response, clustering, timing, thresholds, inefficiencies, trigger and digitization; add required detector subsystems.
4. Export the existing event/truth/provenance contract and preserve feature order, selection cuts, normalization and flux/exposure policies.
5. Compare data/control channels and current MC; demonstrate efficiencies, resolutions, acceptance, cut/model convergence and an uncertainty budget before replacing training or acceptance samples.

ROOT can remain the generator/I/O/analysis layer while Geant4 replaces simplified detector transport. Switching file technology alone does not close these scientific requirements. Open work is tracked in [status](status).

The active 26 October proposal compares the fast response and Geant4 on common truth, with grouped event splits and independent detector/data controls. It keeps the current BDT as a reference until detector validation and observable-bias checks support a change. See the [design and decision criteria](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/plans/2026-10-26-geant4-bdt-design.md) and [execution plan](https://github.com/AntoninoFulci/GRAAL_Analysis/blob/main/docs/plans/2026-10-26-geant4-bdt-execution.md). Adoption for BDT training and adoption for acceptance estimates are separate gates; the plan does not certify either.
