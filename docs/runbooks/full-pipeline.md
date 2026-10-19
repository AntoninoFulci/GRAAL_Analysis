# Full UV/VIS pipeline

For h70 conversion, parallel execution and server acceptance tests, see
[server parallel validation](server-parallel-validation.md). The launcher accepts
`--cpus N`, `--extraction-workers N` (default 1), `--seed S`, `--preanalysis-dir DIR` and
`--require-current-preanalysis`; standalone h70 conversion uses
`python -m scripts.run_preanalysis`.

## Inputs and setup

Place production `pre_analisi_*.root` files with usable `h80` trees directly in
`data/02_pre_analyzed/`. Place disposable subset files in
`test_data/02_pre_analyzed/`. The launcher does not create `h80` from raw `h70`.
Farm setup links only raw detector data:

```bash
./scripts/setup.sh --mode farm \
  --python /path/to/pyroot-compatible-python \
  --raw-target /path/to/graal_data
source .venv/bin/activate
```

To install outside a venv, add `--install user` and use the selected base
Python directly, without activating `.venv`. Dependencies persist in the user
site for that Python major/minor version. Load the same ROOT environment in
each new session. Reinstall once if the Python major/minor version changes.
User installs share packages with other projects; the farm Python must allow
`pip install --user` and have user site packages enabled.

Setup creates `data/02_pre_analyzed/` without moving, replacing, or linking its
contents. `data/00_external/flux.root`, `config/run_manifest.csv`, and checked-in
Stage-1 hyperparameters remain required.

## Baseline without kinematic fit (13 October 2026)

The launcher and direct reconstruction CLIs default to **no 6C fit**. Both
pairing and BDT+pairing use the same profile energy range, first four photons
of events with at least four photons, and exactly one measured proton.
Approved selections: pairing chi2 < 10, relative mass resolution 0.08,
missing mass within 0.06 GeV of the proton mass. The missing-mass cut is active
without 6C; no confidence-level selection is applied. Azimuthal ratio and
likelihood fits that extract Sigma remain active.

Start a fresh campaign from selected `h85` (or selected legacy `h80`) inputs.
Raw branches from an old fit-selected ROOT file are **not** a no-fit baseline.
New reconstruction ROOT files contain `reconstruction_provenance`: `do_fit`,
input SHA-256 hashes, source revision and hashes, effective cuts, model inputs,
and input/accepted/rejected counts per run and polarization. No-fit extraction
and campaign plotting reject missing provenance or historical fitted branches.
The raw/6C systematic is absent, with `raw_vs_kinematic_fit=disabled` recorded
in extraction provenance; absence is not a measured zero uncertainty.

For existing selected files in a different local layout, pass paths explicitly:

```bash
python -m reconstruction.reconstruct_eta_pi0_chi2 --no-fit --profile uv \
  --input-dir /path/to/selected/uv \
  --output-file results/new-no-fit/uv/reco/reco_eta_pi0_chi2.root
python -m reconstruction.reconstruct_eta_pi0_bdt --no-fit --profile uv \
  --input-dir /path/to/selected/uv --model-dir /path/to/uv/artifacts/stage1 \
  --output-file results/new-no-fit/uv/reco/reco_eta_pi0_bdt.root
```

Repeat for VIS with its own model and `--profile vis`. Existing valid selected,
MC, and BDT caches keep their contracts: disabling 6C only changes downstream
reconstruction, extraction and plotting. Reconstruction is always rerun by the
launcher. Baseline plots use raw vectors with no 6C overlays, mass comparisons,
or `comparison_raw_fit_*` products.

Historical analysis stays available only by explicit opt-in:
`--with-kinematic-fit` on reconstruction, Dalitz and campaign plotting, and
an explicit `--raw-bdt-fit FILE` on extraction. These switches describe an
archival workflow, not the baseline. Preserve old ROOT/PDF products separately.

## Production campaign

```bash
python scripts/run_pipeline.py --mode production \
  --output-dir results/october-uv-vis --phi-bins 12
```

`--phi-bins` accepts `8`, `12`, or `16` and defaults to `12`. Each launch
produces one azimuth binning, shared by UV and VIS, with the same output
layout. The choice controls the ratio fits and their azimuthal controls;
the conditional likelihood remains unbinned. Stage-08 ROOT files store
`binning/phi_edges` and `phi_bins` in provenance. Combined plots require
matching UV/VIS phi edges. Legacy ROOT files without phi metadata are read
as the previously enforced 12-bin case. For comparisons, use separate output
directories, for example `results/phi8` and `results/phi16`. To reuse completed
reconstructions, use the extraction-only commands below; the full launcher
always reruns calibration and reconstruction, even when its upstream caches
are valid.

Ratio Sigma and its statistical error are automatically divided by the fixed
approved values `0.9003`, `0.9549`, or `0.9745` for 8, 12, or 16 bins,
respectively, including the default 12-bin case. Azimuthal curves keep the
raw fit amplitude; likelihood remains unscaled. ROOT provenance records
`phi_bin_correction=ratio_only_rounded` and `phi_bin_divisor`. Composition
also requires matching correction conventions: rerun extraction before
combining a newly corrected profile with an old uncorrected one. Reading or
replotting older campaigns does not apply a new correction. See the
[scientific verification and acceptance assumptions](../research/2026-10-09-finite-phi-bin-correction.md).

### Adaptive phi binning (temporary opt-in)

Add `--best-binning` to Stage 08 or the full launcher to fit **8, 12 and 16**
phi bins in one extraction. It overrides `--phi-bins`. Inputs are read and
selected once per sample/period, and the three fits reuse the same pair
projections. The unbinned likelihood is evaluated once, without a finite-bin
correction; `--estimator likelihood --best-binning` is rejected.

Each ratio point (sample, pair, energy bin, mass bin) selects its own binning
before background corrections, covariance construction and final plots:

1. Exclude unavailable/nonconverged fits and fits with nonpositive ndf.
2. Prefer acceptable fits (`p >= 0.01`), then nominal fits over diagnostic
   fallbacks within each quality class.
3. Minimize `abs(chi2/ndf - 1)`. Exact ties prefer 12, then 8, then 16 bins.

No ranking uses Sigma or its error. If only poor fits remain, retain the best
available one with its poor-fit diagnostics; if none remain, omit the point.
The existing correction divides Sigma **and its errors** by 0.9003, 0.9549 or
0.9745 exactly once. Sidebands and photon-multiplicity controls use the chosen
nominal binning; bootstrap replicas repeat selection. Conditional fit errors
alone do not include adaptive-selection uncertainty; the existing suspension
of final inference remains in effect.

`sigma_points` stores `phi_bins` and `phi_bin_divisor` per point (0 and 1 for
unbinned likelihood). `binning_candidates/{8,12,16}/sigma_points` preserves
all estimable candidate ratio points before background correction; nominal
sample ratio graphs, fitted curves and overlays are stored alongside them.
Missing candidates are not estimable. `ratio_objects` and `ratio_overlays`
contain the chosen nominal fits, including fallback constant/sine terms.
Provenance records `phi_bins=best-binning` and `phi_bin_divisor=per_point`.
The top-level `binning/phi_edges` is the fixed 12-bin grid for BREM control
plots only. Both UV and VIS must use best-binning when composing these outputs;
their per-point choices may differ.

Figure-4 plots encode the stored phi binning with circles (8), squares (12)
and triangles (16). Hollow markers identify diagnostic fallback fits without
changing the binning shape. The shared legend sits below the panels; matching
Ajaka reference points use red hollow diamonds in that same legend. Legacy
points without phi-bin metadata retain a generic circle and analysis label.

To reuse existing reconstruction ROOT files, run only Stage 08, for example:

```bash
python -m observable_extraction.beam_asymmetry \
  --profile uv --best-binning --by-period \
  --raw results/production/uv/reco/reco_eta_pi0_chi2.root \
  --raw-bdt results/production/uv/reco/reco_eta_pi0_bdt.root \
  --flux-file results/production/common/flux_calibrated.root \
  --run-manifest config/run_manifest.csv \
  --output-dir results/best-binning/uv/beam_asymmetry
```

Repeat with `--profile vis` and VIS input/output paths. Use the source
campaign's energy configuration if nondefault. Then combine with:

```bash
python -m observable_extraction.combine_profiles \
  --uv-root results/best-binning/uv/beam_asymmetry/beam_asymmetry.root \
  --vis-root results/best-binning/vis/beam_asymmetry/beam_asymmetry.root \
  --output-dir results/best-binning/common/plots
```

These commands do not rerun selection, training, calibration or reconstruction.
The full launcher still has its usual upstream behavior.

Production requires a new empty campaign directory. No timestamp is added to
its name. Omit `--output-dir` to use `results/production/`, also only if empty.
After preflight, the launcher prints a table with inputs, paths, MC settings,
cache policy, force flags, and the ordered stages. A separate warning table
lists production `h80` files older than ten days. Tables wrap within the
terminal width; colors appear on compatible terminals unless `NO_COLOR` is set.
The same color policy applies to stage headers, cache decisions and streamed
Python/ROOT output: cyan for information, green for completion, yellow for
warnings, red for errors, and dim text for commands and cache skips. Unlabelled
stage output remains plain; words such as "error" inside metrics do not mark a
line as an error. Stdout and stderr stay separate, and Python stages flush their
output immediately. Native stages retain their own flushing behavior.

`--color auto` (the default) enables colors separately on each compatible
terminal stream, including an interactive SSH terminal. Redirected streams stay
plain. Use `--color always` to keep colors through `tee`, or `--color never` to
disable them. Presence of `NO_COLOR`, even empty, disables colors in every mode.
The saved `pipeline_commands.log` always stays plain; a `tee` capture with
`--color always` contains ANSI color codes.

```bash
# Color on the terminal; plain captured output with the default auto policy.
python scripts/run_pipeline.py --mode test_data --color auto

# Keep colors through tee; view the captured ANSI colors with less -R.
python scripts/run_pipeline.py --mode test_data --color always 2>&1 | tee pipeline.log
less -R pipeline.log

# Disable colors for the entire launch.
NO_COLOR=1 python scripts/run_pipeline.py --mode test_data
```

Answer `s` (or `si`, `sì`, `y`, `yes`) to start. Enter, any other answer,
or EOF cancels before output creation or replacement. Batch launchers must
provide an explicit answer.
Use `--force-selected`, `--force-mc`, or `--force-bdt` to rebuild that artifact
class. Otherwise a complete manifest and validated output can be reused for
up to ten 24-hour days after recorded completion. Changes to input identity,
options, relevant source, or output force a rebuild. Old `h80` inputs warn but
remain usable when valid. Missing or invalid inputs stop the run. A launcher
lock prevents concurrent campaigns from replacing shared artifacts.

Production intermediates live at stable paths:

```text
data/02_pre_analyzed/pre_analisi_*.root
data/03_selected/{uv,vis}/
data/04_mc/{uv,vis}/<channel>_mc.root
data/05_bdt/{uv,vis}/beam_spectrum.npz
data/05_bdt/{uv,vis}/features_stage1.npz
data/05_bdt/{uv,vis}/artifacts/stage1/
```

Adjacent `*.manifest.json` files record cache signatures, completion time, and
output identity. Selected, MC, and BDT output is validated in staging before
publication. A failed stage leaves its previous artifact in place.

## Change phi binning without rerunning earlier stages

Run from the repository root after loading ROOT. Set `GRAAL_PYTHON` to the
same interpreter used during setup, and replace `results/production` with
the completed **no-fit** source campaign. Keep its original run manifest available at
`config/run_manifest.csv`.

These commands run Stage 08 for UV and VIS with 8 and 16 bins, then regenerate
campaign plots. Selection, MC, BDT training, flux calibration, and
reconstruction are reused. Likelihood is recalculated together with ratio,
but remains unbinned. Outputs follow the standard campaign layout; references
to source ROOT files use symlinks, so retain the source campaign. Existing
`results/phi8` or `results/phi16` directories are refused by `mkdir`.

```bash
GRAAL_PYTHON=/path/to/pyroot-compatible-python
(
  set -e
  SOURCE_CAMPAIGN=$(cd results/production && pwd -P)
  for input in common/flux_calibrated.root \
      uv/reco/reco_eta_pi0_chi2.root uv/reco/reco_eta_pi0_bdt.root \
      vis/reco/reco_eta_pi0_chi2.root vis/reco/reco_eta_pi0_bdt.root; do
    test -r "$SOURCE_CAMPAIGN/$input" || { echo "Missing input: $input" >&2; exit 1; }
  done
  for bins in 8 16; do
    OUT="$PWD/results/phi$bins"
    mkdir "$OUT"
    mkdir "$OUT/common"
    ln -s "$SOURCE_CAMPAIGN/common/flux_calibrated.root" "$OUT/common/flux_calibrated.root"
    for profile in uv vis; do
      mkdir "$OUT/$profile"
      ln -s "$SOURCE_CAMPAIGN/$profile/reco" "$OUT/$profile/reco"
      "$GRAAL_PYTHON" 08_observable_extraction/beam_asymmetry.py \
        --profile "$profile" --phi-bins "$bins" \
        --raw "$OUT/$profile/reco/reco_eta_pi0_chi2.root" \
        --raw-bdt "$OUT/$profile/reco/reco_eta_pi0_bdt.root" \
        --flux-file "$OUT/common/flux_calibrated.root" \
        --run-manifest config/run_manifest.csv \
        --output-dir "$OUT/$profile/beam_asymmetry" \
        --plots-dir "$OUT/$profile/plots" \
        --estimator both --bootstrap-replicas 0
    done
    "$GRAAL_PYTHON" -m scripts.plot_campaign --campaign "$OUT"
  done
)
```

These derived campaigns have Stage-08 binning provenance but no full-launcher
`pipeline_artifacts.json` or `pipeline_commands.log`, since earlier stages
were not run. If extraction fails, partial new outputs remain for inspection;
choose fresh destination names before repeating.

## Disposable test campaign

```bash
python scripts/run_pipeline.py --mode test_data
python scripts/run_pipeline.py --mode test_data --output-dir results/test_subset
```

Test runs always rebuild selected data, every MC channel, beam spectrum,
features, and BDT in the parallel `test_data/{03_selected,04_mc,05_bdt}/`
layout. They overwrite the previous test artifacts and the named
`results/test_<campaign>/` directory. Output outside that namespace is refused.
Test files have no production cache eligibility or age warning. No automatic
timestamp enters a file or campaign name. The default is `results/test_data/`.

## Campaign output and plots

```text
results/<campaign>/
|-- common/flux_calibrated.root
|-- common/plots/                   UV/VIS and five-row comparisons
|-- uv/reco/                        chi2 and BDT ROOT files
|-- uv/beam_asymmetry/beam_asymmetry.root
|-- uv/plots/                       Dalitz, mass, asymmetry, diagnostics
|-- vis/reco/
|-- vis/beam_asymmetry/beam_asymmetry.root
|-- vis/plots/
|-- pipeline_artifacts.json         production cache outcomes and input identities
`-- pipeline_commands.log          RUN/SKIP reasons and commands
```

Profile and common plots include raw/6C-fit mass distributions for `M(p eta)`,
`M(p pi0)`, and `M(eta pi0)`, constrained eta/pi0 mass distributions, and
raw/fit asymmetry comparisons for ratio and likelihood estimators. Common
asymmetry figures use the five-row UV/VIS energy grid; mass figures use
separate UV/VIS panels with matching axes and per-profile normalization.

To regenerate plots from a completed campaign without rerunning selection,
MC, BDT, calibration, reconstruction, or extraction:

```bash
python -m scripts.plot_campaign --campaign results/october-uv-vis
```

This validates reconstructed and Stage-08 ROOT inputs before replacing
canonical plot directories. Legacy `combined/` and `beam_asymmetry/*.pdf`
files in older campaigns remain intact. Existing campaign ROOT results are
never modified by postprocessing.

## Asymmetries by source period

Pipeline Stage 08 enables `--by-period`. The standalone extractor accepts the
same flag; omitting it retains the historical pooled-only interface.
The inclusive run universe comes from reconstruction `counts_by_run_state`,
including runs with zero reconstructed yield. For inputs without this cutflow,
supply `--run-universe-manifest FILE` with the standard manifest schema.
Run identities and period labels must agree with `--run-manifest`; UV/VIS and
P/D are never pooled implicitly. All comparison samples must share this universe.

Outputs in each profile's `beam_asymmetry/` directory:

- `beam_asymmetry.root`: fit on the pooled union of events and exposures.
- `periods/<source_period>/beam_asymmetry.root`: same estimator and binning.
- `periods/index.json`: availability, run lists, cutflow, flux exclusions,
  exposure strata, bin status, input/source hashes, closure and signed nuisance responses.
- `period_stability.pdf`: disjoint-period estimates at identical bins.

A period with inputs but no estimable bins has an empty `sigma_points` tree,
`extraction_metadata.status=not_estimable`, and no dummy covariance or Sigma=0.
Manifest periods outside the input universe are listed as `not_available`.
Output directories publish atomically after extraction and closure succeed.

Closure re-extracts the disjoint union and checks identical bins, event counts,
exposure strata and uncorrected Sigma within 1e-8. It does not average period
Sigmas. Signed polarization-scale responses retain the shared global nuisance;
other cross-period correlations remain unclassified. Stability plots and stored
differences are diagnostics, without pulls against an overlapping pooled sample.
Final uncertainty inference remains suspended under plan 01.

## Failure checks

Launcher stops on first failed stage. Inspect `pipeline_commands.log` and
`pipeline_artifacts.json` for production cache decisions. Verify both profile
ROOT metadata and energy edges, then inspect PDFs under each `plots/` directory.
Run `python -m pytest -q` for repository checks.

## Optional missing-flux study

Use `--flux-study audit` or `--flux-study study` to run stage 07 after common calibration. Default: `off`. Acquisition metadata use `--flux-study-metadata conditions.json`. Outputs stay in `<campaign>/missing_flux/`; stage 08 extraction continues using measured calibrated flux. See [standalone commands, prerequisites and artifacts](missing-flux.md).
