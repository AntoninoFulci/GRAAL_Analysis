# Dedicated eta pi0 signal detector chain — 21 October 2026

## Current result: native execution resolves the missing photon showers

The stop state recorded below is historical. The same proton21 executables,
image digest, card and seeds were run on native x86_64 `trima` after explicit
user authorization. They yield **1000 generated → 999 digitized/PREAN → 727 h85
→ 11 final reconstructed candidates**. OrbStack gave 117 PREAN and zero final
candidates. Binary hashes are recorded in both runs; no GTGAMA replacement was
used on the native run. Artifacts:
`results/cross-section-signal-acceptance-20261021/native-original-1000/`.
`validation.json` records complete identities and prompt-decay invariants.
The pilot efficiency is 0.011 ± 0.00330 (binomial statistical only), at fixed
1.2 GeV and provisional period21 geometry. One of eight true-phi cells has no
selected events; the response guard correctly refuses publication. This is
not yet the cross-section calibration.

The investigation traced primary photons through `GUSKIP` (correct zero skip)
and `GUTRAK`. Photons enter with correct nonzero energy but terminate after
one step, zero path, with `ISTOP=2` on OrbStack. A minimal GTGAMA program,
without generator or detector geometry, reproduces incorrect absorption of
a 100 MeV photon with a 0.01 MeV cutoff using the historical CERN object.
The same source recompiled locally passes this probe. A diagnostic-only
four-byte substitution of the x87 control-word conversion instruction
(`OR AX,0x0c00` → `MOV AH,0x0c` + two NOPs) also makes it pass while preserving
object layout. This isolates an emulated execution sensitivity; it does not
prove an instruction-level emulator root cause or justify binary patching
other routines. Full-chain native execution provides the independent check.
The separately linked minimal probe has not been run on trima: transfer of
those additional binaries was rejected by automatic approval review pending
broader authorization. No such transfer occurred.

Production retains the historical GEANT library. `transport_probe.F` now
checks both above-cut preservation and below-cut absorption before every new
chain run. It uses `CALL EXIT` and the shell requires a PASS marker: historical
g77 `STOP 1` was experimentally observed to return process status zero.
End-to-end OrbStack test `runtime-guard-rejection` stops before event generation
and records failure. This prevents silently using that environment for an
acceptance measurement. Rebuilding GTGAMA alone is deliberately not adopted.

`energy_window.patch` adds an optional uniform energy interval for channel38;
fixed-energy cards remain supported. The prepared native campaign covers
0.95–1.4875 GeV, with 0.95–1.1 retained as truth guard region for migration
into the 1.1–1.5 analysis window. A domain is not declared closed merely by
throwing away those generated events. Production and guard audit remain
pending extended remote authorization at this report update.


**Current outcome: implementation and full-chain plumbing exist, but no physical
acceptance is certified.** The dedicated source compiles reproducibly from the
pinned image and an instrumented1000-event run reaches the unchanged data
reconstruction/BDT with46 selected events. Clean transport loses photon showers
and can stall; the apparent GSKING-only fix was disproved by clean replay.
The current implementation now uses provisional proton period21/old cylinders
and explicit prompt photon primaries; its clean1000-event test still retains
only117 after the BGO trigger. Period26 diagnostics remain separate.
The launcher labels normally terminated runs as unvalidated detector-chain
results and explicitly sets `transport_validated=false`.

A dedicated channel **38: gamma p -> eta pi0 p** is implemented as a reproducible
source patch of the digest-pinned historical LAGGEN. Existing reactions retain
their definitions. The new channel is pure three-body Lorentz-invariant phase
space; it does not use Ajaka cross sections or fit the measured data.

The patch uses existing GENBOD with `KGENEV=1`, whose source still returns an
event weight `WT`. Channel38 explicitly rejects proposals with a uniform draw
above `WT`; accepted events carry `WT=1`. A bound check aborts if weight escapes
[0,1]. The arbitrary unit channel strength is used only to register the channel;
fixed-energy single-channel generation does not use it as normalization.

Both eta and pi0 decay to two photons with forced branching fraction100%.
Physical branching fractions are excluded from detector efficiency and must be
applied once by the cross-section normalization. Historical generator masses
are eta0.54745, pi0 0.13496, proton0.93821GeV; this pilot retains them explicitly.

`TARG 1 4` is a new explicit12cm hydrogen target option. It changes the volume and
vertex length used by GEANT3, and the isolated digitization/reconstruction base
is patched to12cm too. It represents the user's provisional all-period target
assumption; it is not proof of the true run geometry.

The complete generated denominator is written after `VERTEX` and before
transport: `generated_signal.dat`, 20 whitespace-separated columns:

```
IDRUN IDEVT channel npart Egamma vx vy vz
eta_px eta_py eta_pz eta_E pi0_px pi0_py pi0_pz pi0_E
p_px p_py p_pz p_E
```

Units are GeV and cm. A final `-1` certifies generator completion. IDs are
complete and sequential even if later stages reject an event. No legacy
`outev.dat` vertex is used for acceptance. LAGDIG output fields are widened to
IDRUN16/IDEVT24bits and its historical OFFSET macro is disabled. IDs remain
local to a campaign; campaign identity is also needed when combining samples.

Separate RNG seeds are recorded: GEANT GRNDM has its two steering seeds;
GENBOD uses CERN RNDM and is explicitly initialized with RDMIN; LAGDIG initializes
both RDMIN and g77 SRAND from a required environment seed. This fixes two
otherwise hidden reproducibility problems (GENBOD default seed and wall-clock
digitizer seed).

The isolated fresh build includes all three executables. It removes archived
object files, uses the actual legacy source compiler flags and installed
32bit startup objects, records logs and binary hashes, and avoids Condor/qsub.
GRAAL_BIN is disabled because its unused historical binary writer does not
compile; GRAAL_NTUP writes the required HBOOK hit ntuple. No container image or
original source is changed.

Two more historical hazards were corrected in the dedicated build:

- The digitizer computes trigger bits but accepts everything unless trigger
  macros are enabled. This build enables `GRAAL_T_BGO` explicitly. The period26
  base has a90MeV BGO total-energy threshold.
- PREAN data-specific barrel wiring corrections and run<=666 trigger override
  now require LDATA, preserving correctly wired simulated channels in LSIMUL.

The first100-event test (`smoke2`) completed LAGGEN -> LAGDIG -> PREAN, but used an
archived PREAN binary whose log revealed OLD_CYL despite its unsuffixed name.
Its digitizer also still had the disabled-trigger default. It is retained only
as an end-to-end schema test, never as a valid acceptance sample. The current
fresh PREAN build has NEW_CYL and matching period26 macros.

**Period26/run4300 belongs to deuterium2002_d3 in the analysis run manifest.**
The signal pilot uses a hydrogen target and period26 detector conditions as a
technical test, not an acceptance assigned to the proton periods. Physical
production requires the appropriate proton run, period calibration and chamber
epoch. This limitation cannot be cured by renaming a converted file.

The reusable `mc_simulation.geant3_signal` launcher pins the container image,
uses read-only inputs and narrowly scoped output mounts without network,
requires fresh output, validates truth identities/masses/four-momentum/vertices,
and verifies digitizer loss accounting and PREAN completion/geometry.
It produces `.pol` only. Acceptance requires conversion and the current data
selection/pairing/BDT afterward. Its eight unit tests passed; full detector-pilot
results and downstream selection are recorded below as they complete.

## Secondary transport defect identified and isolated

The first matched100-event pilot completed but had100 generated ->10 triggered,
all with a single BGO cluster. Independent HBOOK→ROOT inspection by the parent
analysis found only17/100 nonzero BGO-hit records, total energy at most253MeV.
Therefore the problem preceded digitization. Decay instrumentation verified
both mesons produced exactly2 photons. At event653 the1000-event reproduction
then repeated pi0 decay indefinitely; no incomplete sample enters a denominator.

A controlled rebuild of the **unchanged CERN GSKING source** restored secondary
transport and completed1000 events (same steering, geometry and initial seeds):
1000 generated,0 tagging rejects,4 BGO-trigger rejects,996 digitized, PREAN
normal termination. PREAN reported991/996 BGO-OK events. This is a detector-stage
technical count, not a selected-signal efficiency. The source override is now
part of `build_signal.sh`; no transport cuts or event-skipping workaround were
introduced. Exact reason for the archived object's different behavior remains
unresolved. The archived GSKING object SHA256 is
`7895f9e858a29ac3c5f56aebd753488bc910073f8f7b631d236b9a3d80e8195d`.

The instrumented successful sample is `debug-restack-1000`; the clean10000-event
sample is `pilot-restack-10000`. `pilot-10000` and `debug-1000` are deliberately
failed/incomplete transport diagnostics, and `pilot-100` has the defective
transport. They must not be used for cross-section efficiency. The clean sample
and a pristine complete rebuild are being validated separately.

**Correction after clean replay:** GSKING source recompilation alone does not
fix the failure. Both clean production and pristine rebuild still stall near
event653 and show missing showers. Only the instrumented build has succeeded;
its successful downstream46/1000 selections certify chain/identity plumbing,
not physical efficiency. Instrumentation is being bisected to identify the
undefined-state or compiler sensitivity before a valid acceptance is claimed.

## Final bounded diagnostics and verification

A complete fresh build (`rebuild-proof/build.log`) succeeds from the pinned
image with the committed recipes. Its clean1000-event run reproduces the stall;
this establishes build reproducibility, not correct detector transport.
Neither isolated stepping instrumentation nor isolated event-boundary
instrumentation reproduces the successful full instrumented build: both100-event
variants retain only10 events after the BGO trigger. GSKING alone is not causal
proof and no claim of its being the fix remains valid.

A full user-source `-fbounds-check -g` build first stops at `lagmat.F:82`, because
ZEBRA intentionally indexes its one-element declaration `LQ` into the larger
allocated bank (`LQ(2999902)`). Excluding **only LAGMAT** from bounds checking,
1000 events complete without another bounds error:1000 hit entries,0 tagging
rejects,893 BGO-trigger rejects,107 digitized/PREAN input. It still shows the
missing-shower behavior. This experiment did not identify a genuine
out-of-bounds location; libraries remain uninstrumented. Files are preserved in
`bounds-1000`, `bounds-zebra-1000`, and their build logs. All task-owned simulation
containers were stopped or finished; no background simulation remains.

Generator-only validation on the instrumented1000-event truth gives maximum
four-momentum residual2.92e-7GeV, z from−5.978 to5.997cm, mean eta-CM cosine
−0.0125±0.0180, and eta-pi0 invariant-mass KS p=0.934 against analytic three-body
phase space. These tests validate generated kinematics; they cannot validate
secondary transport.

Python validation:14 focused tests pass; Ruff check/format clean. Two additional
regressions were observed failing before the guards were added, then passing:
requested beam energy must match truth (absolute tolerance2e-7GeV), and PREAN
input count must exactly match digitizer output. Hit losses are separately
accounted against the complete generated denominator. The parent analysis has
independently verified the unchanged data-selection signature and complete
identity join for the diagnostic46/1000 selected sample; its response is
technical evidence only.

Remaining physical blockers are (1) clean, instrumentation-independent photon
transport; (2) implementation and validation of the provisional proton profiles
below; (3) energy/angle coverage and sufficient independent MC after those are
resolved. No failed,
partial, or instrumentation-dependent sample should be normalized into a
physical cross section.


## Proton-period mapping inferred from historical sources

The user has no logbook and authorized a provisional choice. The concrete,
machine-readable result is
[`proton_periods_provisional.json`](../../resources/geant3/proton_periods_provisional.json).
It selects **2002_uv1, run3629, GRAAL_21/data21.base** as the initial proton
profile. It does not relabel or reuse diagnostic period26 as proton acceptance.

Every canonical P/UV run in each row falls in exactly one explicit PREAN
`constan.F` interval. Historical `prean_run_<period>` wrappers independently
assign **all 1289 runs** in the seven rows to the same period number. The
wall calibration comes from `wall_choose_file.F`; planar geometry and CTD
come from `GRAAL_period.h`. SHA256 identities for the manifest, yield-domain
index, source files, wrappers and each base are retained in the JSON.

| Proton period | Manifest runs | Current exposure runs | Base/macro | Planar chambers | Wall calibration |
|---|---:|---:|---|---|---|
| 1998_uv | 179 | 166 | 09 | old | calib_1400.cal |
| 1999_uv | 339 | 282 | 10 | old | calib_1700.cal |
| 2000_uv1 | 204 | 202 | 14 | new | calib_2500.cal |
| 2000_fuv | 147 | 91 | 15 | new | calib_2700.cal |
| 2000_uv2 | 102 | 53 | 17 | new | calib_3100.cal |
| 2002_uv1 | 128 | 105 | 21 | new | calib_3700.cal |
| 2002_uv2 | 190 | 115 | 22 | new | calib_3800.cal |

`2001_uv` maps to base18 (137 manifest runs) but has no complete calibrated
exposures in the current yield domain, so it is explicitly unavailable.
Manifest counts include runs excluded by analysis quality/flux rules; they are
configuration-coverage counts, not selected data exposures.

For cylindrical chambers the explicit provisional choice is **GRAAL_OLD_CYL**
for all seven profiles. `comp_prean` creates unsuffixed `prean_<period>` aliases
for old-cylinder builds, and data wrappers request those unsuffixed executables.
That is useful evidence for the choice, but cannot establish which historical
binary was used for the existing data. Image pilots themselves are inconsistent
(LAGGEN/LAGDIG old, PREAN new), so chamber validation remains necessary.

All seven bases contain a **90 MeV BGO total-energy threshold** and **2.2 MeV
crystal threshold**. The JSON chooses BGO-only trigger provisionally and also
preserves period-specific barrel thresholds. The base threshold is evidenced;
actual historical trigger enablement is not established by the available
logbook-free evidence. The common 12 cm LH2 target at0.071 g/cm³ is the user's
provisional assumption; the historical default11.1 cm is recorded separately.

The initial2002_uv1 profile is now implemented together in the build scripts,
Stage03 launcher, private period headers and runtime base/calibration checks;
the remaining six profiles are declarative. No transport run was made for
the mapping itself; the subsequent initial-profile validation is below.
Static verification passed: all seven available profiles, all1289 canonical
runs, independent wrapper assignments, source/base hashes, representative-run
availability and explicit run4300 deuterium exclusion.

## Final optimization diagnostic

The parent compared clean and successful instrumented objects: only
GUKINE/GUSTEP/GUOUT instrumentation changes and a temporary CPP filename in
GSKING differ. The actual GSKING machine code is unchanged, ruling out the
claimed GSKING recompilation fix. A clean isolated all-LAGGEN **-O0** build
completed1000 events but still rejected883 at the BGO trigger, leaving117
LAGDIG/PREAN events. Evidence: `noopt-build/rebuild.sh` and `noopt-1000` under
the signal-acceptance result directory. Optimization changes affect the stall,
but do not restore photon showers. No validated physical acceptance follows
from this test, and no further random transport variants were started.


## Explicit prompt photons and initial proton build

The parent tested a clean period26 alternative that decays the two generated
pseudoscalars isotropically into photon pairs before GEANT, inserting four
photons plus the proton as primary tracks. It completed1000 events with996
BGO-trigger survivors. Prompt two-photon decay is physically appropriate at
detector scales; physical branching fractions remain outside efficiency.
The historical GEANT meson-decay mechanism is bypassed only for channel38.

This implementation is now in `signal.patch`. `generated_signal.dat` retains
all mother truth. New `generated_decays.dat` stores two rows per event:
`IDRUN IDEVT mother_index` followed by the two daughter four-vectors. Both
files require normal terminators. Python validates every daughter identity,
positive photon energy, masslessness and four-momentum sum, then reports
inverse-boost rest-frame angular moments. Source checks also reject
four-momentum violation above1e-5GeV.

Fresh `proton21-build/build` uses run3629, `GRAAL_21`, `GRAAL_OLD_CYL`,
`data21.base`, `calib_3700.cal`, CTD and new planar chambers consistently.
The 12cm target change applies to the private base. All three compilation
units have private period headers, avoiding modification of the image.
Runtime logs independently confirm the compiled profile and calibration.

**The proton-profile test is not a validated acceptance:** `proton21-1000`
completed1000 generated/hit events, zero tagging losses,883 BGO-trigger losses,
and117 digitized/PREAN events. It differs from the parent's period26 test in
period/chambers/base and in daughter-truth recording; those changes have not
been isolated. The117 surviving events therefore do not establish restored
photon showers. All2000 decays pass physical checks: maximum four-momentum
residual7.5e-8GeV, maximum photon mass squared9.17e-8GeV²,
rest-frame mean cosine0.02495, mean squared cosine0.33181, mean sin(phi)0.01240,
and mean cos(phi)−6.77e-6. The direction moments are consistent with isotropy
at this sample size but do not validate detector transport.

Runtime resources are frozen into each output's `resource_snapshot`, hashed,
and bound read-only. This prevents concurrent source editing from changing
an executing shell script. The parent found exactly such a race in its older
period26 replay; that replay remains failed despite physically matching truth.
Focused tests:11 passed after the prompt-decay/proton-profile updates;
Ruff check and formatting passed. The launcher still explicitly records
`transport_validated=false`.


Final stop state: the successful period26 prompt-photon transport result did
**not transfer** to the implemented proton21 configuration. The current
blocker is unresolved detector transport, not a missing user decision about
provisional geometry. No more variants were run. Docker inventory confirms
no signal/build containers remain; unrelated application containers were
untouched. Parent verification reports92 Stage03 tests and310 Stage08 tests
passing. These software checks do not certify the missing physical acceptance.

## Downstream inspection of the final proton pilot

Parent converted proton21-1000 PREAN using the existing remote h2root, then
ran unchanged current preanalysis, event selection and UV BDT reconstruction.
Polarization was explicitly mapped before preanalysis. h70 contains117 events:
114 have one BGO cluster,3 have two. Final reconstruction has **zero events**.
`response_probabilities` rejected publication with its zero-acceptance guard;
no efficiency floor or extrapolation was inserted. Accounting and logs are in
`results/cross-section-signal-acceptance-20261021/proton21-1000/evaluation/`,
including `validation.json`. This confirms that the completed technical chain
still cannot supply the signal acceptance needed for a physical cross section.

Verification after the runtime-guard changes: Stage03 suite **94 passed**;
focused signal tests **13 passed**; Ruff clean. Direct comparison of the
recorded `binary-sha256.txt` files confirms identical LAGGEN/LAGDIG/PREAN
executables for the failing OrbStack and successful native pilot.
`runtime-guard-rejection/run.json` records `failed`, exit1, and no generated
truth file. These checks validate the guard and provenance, not a production
response or cross section.
