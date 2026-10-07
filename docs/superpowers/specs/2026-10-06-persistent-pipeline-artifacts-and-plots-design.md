# Persistent pipeline artifacts and campaign plots

Date: 2026-10-06
Revised: 2026-10-07
Status: design approved in conversation; written specification pending review

## Goal

Run new production UV/VIS campaigns without repeating valid event selection,
Monte Carlo generation, or Stage-1 BDT training. Keep production reusable
inputs and intermediate artifacts under stable paths in `data/`. Keep each
campaign's reconstruction, asymmetry results, and plots together under its
`results/<campaign>/` root. Intensive `test_data` runs use parallel paths in
`test_data/` and replace their own intermediate artifacts and results on each
run.
Produce invariant-mass and raw-versus-kinematic-fit asymmetry comparisons for
both profiles, plus combined UV/VIS views. Add the missing plots to the full
pipeline and support plotting an already completed campaign without rerunning
expensive stages.

## Ownership and paths

The production input directory is `data/02_pre_analyzed/` itself. It contains
`pre_analisi_*.root` files directly. The operator copies existing farm files
there manually. Farm setup stops accepting `--pre-target` and stops creating
`data/02_pre_analyzed/pre_analisi` as a symlink. It creates the parent directory
but does not copy, move, delete, or replace pre-analysis data. The standalone
event selector and production launcher defaults use the new directory. The
existing raw-data setup path is independent of this h80-starting launcher.

Production reusable outputs use stable paths and filenames:

```text
data/
|-- 02_pre_analyzed/pre_analisi_*.root
|-- 03_selected/{uv,vis}/<selected ROOT files>
|-- 04_mc/{uv,vis}/<channel>_mc.root
`-- 05_bdt/{uv,vis}/
    |-- beam_spectrum.npz
    |-- features_stage1.npz
    `-- artifacts/stage1/{model,threshold,provenance,metrics,plots}
```

Intensive `test_data` runs use the same visible layout under their own root:

```text
test_data/
|-- 02_pre_analyzed/pre_analisi_*.root
|-- 03_selected/{uv,vis}/<selected ROOT files>
|-- 04_mc/{uv,vis}/<channel>_mc.root
`-- 05_bdt/{uv,vis}/
    |-- beam_spectrum.npz
    |-- features_stage1.npz
    `-- artifacts/stage1/{model,threshold,provenance,metrics,plots}
```

The operator places the test subset's h80 files directly in
`test_data/02_pre_analyzed/`; the old `test_data/pre_analyzed/` path is no
longer read. The operator may replace this test input subset. Every
`test_data` run regenerates selected data, MC, beam spectrum, features, and
BDT, overwriting the previous files at the same test paths. Test artifacts
have no cache manifest, ten-day reuse check, or force-flag decision. These
overwrites never touch production `data/`. No artifact filename or directory
gets an automatic timestamp. Production cache completion time lives only in
metadata. The operator chooses each campaign name; the launcher does not add
a timestamp to it.

Production campaigns write:

```text
results/<campaign>/
|-- common/
|   |-- flux_calibrated.root
|   `-- plots/                 UV/VIS comparisons and combined figures
|-- uv/
|   |-- reco/
|   |-- beam_asymmetry/beam_asymmetry.root
|   `-- plots/                 UV mass, Dalitz, asymmetry, diagnostics
|-- vis/
|   |-- reco/
|   |-- beam_asymmetry/beam_asymmetry.root
|   `-- plots/                 VIS mass, Dalitz, asymmetry, diagnostics
|-- pipeline_artifacts.json
`-- pipeline_commands.log
```

Intensive test campaigns use the same result layout at
`results/test_<campaign>/` (default `results/test_data/`). Every test run
overwrites its previous result directory. The launcher refuses a test output
path outside the dedicated `test_` namespace, so test replacement cannot
erase production results. Test runs need no production cache manifest in their
result directory.

Existing per-profile Stage-07 PDFs go to the profile `plots/` directory while
its ROOT result stays under `beam_asymmetry/`. The four figures currently
written to `combined/` go to `common/plots/` for new campaigns. Training plots
stay beside the cached model because they describe that model rather than a
campaign's physics result.

## Cache decision

For production, use the existing stage entry points and one small
launcher-owned cache check.
Every cache item has a sidecar manifest at a stable path. The manifest records
its input inventory/fingerprint, relevant options, source fingerprint,
completion time, and output identity. Source fingerprints cover the stage's
implementation and shared physics code it imports; a change invalidates that
item. File inventories use canonical path, size, and nanosecond modification
time; required ROOT trees and branches are validated separately. Small config
and numerical input files are content-hashed. A manifest is valid only when
all recorded inputs match, all required outputs exist and pass their format
checks, and completion age is at most ten 24-hour days. Missing or malformed
manifests never authorize reuse. Expiration is measured from recorded
completion, not from a timestamp in a filename or a touched output file.

The production launcher logs `RUN` or `SKIP` for every candidate cache item,
including reason. It never interprets a status-tool internal error as a
missing item. `--force-selected`, `--force-mc`, and `--force-bdt` override
production reuse for their respective stages. Forcing or rebuilding an
upstream item invalidates dependent items through its changed output identity.
Test runs execute all stages and overwrite only test paths.

### Pre-analysis input

Production pre-analysis remains externally produced. Preflight requires UV
and VIS `pre_analisi_*.root` files containing usable `h80` trees and required
selection branches. It records their inventory for downstream validation.
Files older than ten days produce an explicit warning and remain usable if
otherwise valid. Missing or invalid files stop the pipeline. A legacy nested
`pre_analisi` symlink is not followed as the production input; preflight
reports the expected flat path. The launcher does not generate h80 from raw
h70.
Test pre-analysis is read from `test_data/02_pre_analyzed/` and validated for
the same h80 contract. Its age does not gate or warn on disposable test runs.

### Selected data

Selection is cached separately for UV and VIS. Its signature includes the
matching pre-analysis inventory, selection pattern and parameters, and
selector/shared-code fingerprint. A valid complete `h85` set younger than ten
days skips selection. A change in the source file set, source identity, code,
or selection options rebuilds only the affected profile. The existing atomic
directory publisher stages the new set and replaces the old one after every
output file passes validation.

### Monte Carlo

MC decisions are per profile and channel. A channel signature includes channel
identity, generator and included physics code, attempted event count, and beam
energy window. The ROOT file must have a readable, nonempty `mc` tree and
required channel branches. A valid channel younger than ten days is reused;
missing, expired, or incompatible channels regenerate individually. Generation
targets a temporary sibling file. The launcher validates it before replacing
the stable filename and sidecar. The existing `mc_status` can still report the
set, but its presence-only exit code is insufficient for cache eligibility.

### Stage-1 BDT

The BDT cache is profile-specific and contains beam spectrum, feature NPZ,
model, threshold, provenance, metrics, and training plots. Its signature
includes selected-data identity, all required MC item identities, beam
spectrum/feature-building options, hyperparameter file contents, training
options, and relevant source fingerprints. The loader validates the NPZ schema
and complete model bundle, including profile and energy range. If the bundle
is valid and younger than ten days, beam-spectrum construction, feature
construction, and training all skip. Otherwise they run into a staged
directory and publish together after validation. UV and VIS never share a
model.

## Execution and failure behavior

Production runs continue to require a new empty `results/<campaign>/`
directory. They read selected data, MC, and BDT from `data/` and write
calibration, reconstruction, extraction, and plots under that campaign root.
The launcher records cache paths and fingerprints, source revision,
pre-analysis inventory, and run/skip outcomes in `pipeline_artifacts.json`
and the command log. It stops on the first failed stage. Cache checks and
writes run under a single launcher lock so two full campaigns cannot replace
stable shared paths while another consumes them. Direct standalone stage calls
remain the operator's responsibility.

Test runs read h80 inputs from `test_data/02_pre_analyzed/`, rebuild
intermediates under `test_data/`, and replace `results/test_<campaign>/`.
The dedicated test output prefix is checked before any replacement. They do
not inspect, age-check, or modify production cache. The same launcher lock
prevents concurrent test runs from writing the fixed test paths. The command
log records every test stage as executed.

No stage replaces a valid cached artifact with a partial one. New output is
validated before publication; a failure leaves the prior cache usable if it
still meets its own manifest. If a process stops between publication of an
output and its sidecar, the next run detects the mismatch and rebuilds it.
Stable cache paths can later hold newer artifacts; old campaign result ROOT
files remain intact, but previous cache contents are not archived. Their
fingerprints remain in the campaign manifest.

An explicit postprocessing command accepts an existing campaign root, reads
its reconstructed and Stage-07 ROOT files, and writes canonical plots without
running preflight for MC, selected data, BDT, calibration, reconstruction, or
extraction. It validates required trees, fit branches, profile metadata, and
energy edges before replacing the relevant plot set. This path backfills the
already completed production campaign. It leaves legacy `combined/` and
`beam_asymmetry/*.pdf` files in older campaigns intact; new canonical plots
are under `common/plots/` and profile `plots/`. Old campaign MC and BDT files
do not gain cache eligibility automatically: they have no source fingerprints
or cache manifests. The first new campaign populates `data/` once; later
campaigns reuse it while valid.

## Plot content and scientific interpretation

For each profile, the plot stage runs the existing Dalitz/mass plotting flow
and adds one-dimensional raw/fit distributions for `M(p eta)`, `M(p pi0)`, and
`M(eta pi0)`. Both distributions come from the same BDT-gated events passing
the fit selection. Raw masses use raw eta, pi0, and proton vectors; fitted
masses use fitted eta, pi0, and proton vectors. The plotting adapter must not
combine fitted mesons with the raw proton. Eta and pi0 meson-mass plots are
included and labelled as constrained by the 6C fit; their fitted narrowness
is not presented as a measured resolution gain. Dalitz plots retain the
existing measured-proton versus missing-vector distinction.

Each profile also gets raw/fit beam-asymmetry comparisons in its own energy
bins, with statistical uncertainties and pair labels. The raw and fit sample
points already extracted from the same BDT ROOT tree are used; no separate
`--no-fit` reconstruction is run. Ratio and likelihood estimators are shown
separately. The common plot uses the existing five-row UV/VIS energy grid and
overlays raw and fit in each row. Common mass figures use matching mass axes,
show UV and VIS in separately labelled panels because their beam energies do
not overlap, and normalize event counts within each profile for shape
comparison. Existing combined Figure 4, Ajaka comparison, estimator
comparison, and fit diagnostics share `common/plots/`.

Requested plot inputs are required: a missing fit branch or absent sample is
an error, never a silently omitted comparison. Plot sets are staged and
published together so a failed later figure does not masquerade as a complete
campaign plot set.

## Verification and acceptance

- Unit tests cover exact reuse, ten-day boundary, changed input inventory,
  source/config changes, profile separation, per-channel MC regeneration,
  force flags, and warning-only pre-analysis age.
- Failure tests cover malformed ROOT/NPZ/model artifacts, interrupted cache
  publication, status-tool errors, competing launcher locks, and preservation
  of the last valid cache on stage failure.
- Plot tests use small reconstructed ROOT fixtures and Stage-07 point fixtures
  to verify same-event raw/fit pairing, fitted-proton use, energy-bin grouping,
  output paths, and missing-fit errors.
- Two `test_data` pipeline runs against the same test paths verify complete
  replacement and the `results/test_<campaign>/` layout without touching
  production paths. Production cache fixtures verify skip decisions, force
  flags, and expiry. Postprocessing a completed campaign creates all
  requested PDFs without changing its reconstruction or asymmetry ROOT files.
- Runbook and wiki describe manual placement of production h80 files, new
  cache paths, the parallel disposable `test_data/` layout, no-timestamp
  filenames, production cache validity and expiry, force flags, both result
  namespaces, and the postprocessing command.
