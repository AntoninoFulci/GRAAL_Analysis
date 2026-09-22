# 06 — Beam-asymmetry extraction

This standalone stage extracts beam asymmetry `Sigma` for
`gamma p -> p eta pi0`. Nominal result uses raw four-vectors after BDT gate.
Stage remains outside `run_pipeline.sh` until farm dry-run validation; existing
`06_plots` remains available during comparison period.

## Physics convention and binning

- `POL1` and event `Polarization == 1`: vertical;
- `POL2` and event `Polarization == 2`: horizontal;
- `BREM` and event `Polarization == 0`: independent unpolarized control;
- no BREM subtraction;
- no ROOT flux-bin-error contribution to `Sigma`;
- proton target, UV Compton transfer, `1.10 <= E_gamma <= 1.50 GeV`;
- four 100 MeV photon-energy bins, ten invariant-mass bins per pair, twelve
  azimuth bins;
- columns: `p pi0`, `p eta`, `eta pi0`;
- azimuth comes from pair momentum around beam axis. Longitudinal boosts do not
  alter it.

Ratio estimator fits normalized vertical/horizontal yield ratio to
`Sigma cos(2 phi)`. Nominal fit with p-value below 0.01 switches visibly to
diagnostic `c0 + Sigma cos(2 phi) + s2 sin(2 phi)` fit. Conditional-likelihood
estimator retains run/strip exposure, asymmetric polarization transfer, 68%
profile interval, physical `[-1,1]` bound, and unbounded positivity diagnostic.

## Farm reconstruction

Paths below are configuration examples. Large ROOT inputs live under `data/`
on farm and need not exist on workstation.

```bash
python -m reconstruction.reconstruct_eta_pi0_chi2 \
  --input-dir data/03_selected \
  --no-fit \
  --output-file results/reco/reco_eta_pi0_chi2_raw.root

python -m reconstruction.reconstruct_eta_pi0_bdt \
  --input-dir data/03_selected \
  --no-fit \
  --output-file results/reco/reco_eta_pi0_bdt_raw.root

python -m reconstruction.reconstruct_eta_pi0_bdt \
  --input-dir data/03_selected \
  --output-file results/reco/reco_eta_pi0_bdt_fit.root

python -m reconstruction.reconstruct_eta_pi0_bdt_sideband \
  --input-dir data/03_selected \
  --output-file results/reco/reco_eta_pi0_bdt_sideband.root
```

Run broad sideband reconstruction over signal MC too; output must contain tree
`reco_eta_pi0_bdt_sideband`:

```bash
python -m reconstruction.reconstruct_eta_pi0_bdt_sideband \
  --input-dir data/signal_mc_selected \
  --output-file results/reco/reco_eta_pi0_signal_mc.root
```

All streams retain run, strip, polarization, raw masses/vectors, input-photon
multiplicity, and BDT score when gated. Current first-four-photon association
remains unchanged.

## Flux calibration

```bash
python scripts/build_strip_energy_flux.py \
  --preanalysis-dir data/02_pre_analyzed/pre_analisi \
  --manifest config/run_manifest.csv \
  --flux data/00_external/flux.root \
  --output-dir results/strip_energy_flux
```

Extraction consumes schema-v2 `flux_by_run_strip.csv`. POL1/POL2/BREM contents
are final independent exposures. Extra complete flux runs warn and are ignored;
missing selected run/strip joins fail.

## Extraction

First raw+BDT replica, without background inputs:

```bash
python -m observable_extraction.beam_asymmetry \
  --raw-bdt results/reco/reco_eta_pi0_bdt_raw.root \
  --calibration-dir results/strip_energy_flux \
  --output-dir results/beam_asymmetry
```

Full available comparison and sideband correction:

```bash
python -m observable_extraction.beam_asymmetry \
  --raw results/reco/reco_eta_pi0_chi2_raw.root \
  --raw-bdt results/reco/reco_eta_pi0_bdt_raw.root \
  --raw-bdt-fit results/reco/reco_eta_pi0_bdt_fit.root \
  --sideband results/reco/reco_eta_pi0_bdt_sideband.root \
  --signal-mc results/reco/reco_eta_pi0_signal_mc.root \
  --calibration-dir results/strip_energy_flux \
  --output-dir results/beam_asymmetry \
  --estimator both \
  --bootstrap-replicas 500 \
  --bootstrap-seed 1208
```

`--sideband` and `--signal-mc` must appear together. Hard sideband requires at
least two of eta mass, pi0 mass, and proton missing mass at 2–4 signal-window
half-widths, with none outside four. Signal-MC leakage into hard sideband above
5% is fatal. Per-energy-bin 3D template fit estimates broad mixture; fitted
factorized sideband marginals interpolate background into signal cube.
Background `Sigma` uses same estimator as observed `Sigma`, followed by
mixture inversion and uncertainty propagation. Both corrected and uncorrected
values remain in ROOT.

## Systematics and diagnostics

Implemented covariance components are 3% fully correlated polarization scale,
ratio-versus-likelihood envelope, raw-versus-kinematic-fit envelope when both
samples exist, background correction, diagnostic sine leakage, and
inclusive-versus-exactly-four photon selection. Run bootstrap preserves whole
run blocks and run/strip exposure multiplicity. Flux histogram bin errors never
enter covariance.

BREM azimuth distributions are control-only. Best-quartet comparison is marked
unresolved; no output claims it exists. BDT-threshold, flux-balance,
sideband-definition, alternate mass/phi binning, randomized-label,
same-orientation, and run-period variations remain farm validation gates before
publication use.

## Products

Public output contains ROOT and PDF only:

- `beam_asymmetry.root` with points, exact bin edges, counts, fluxes,
  polarizations, fit status, ratio objects, diagnostic graphs, and statistical,
  bootstrap, systematic, total covariance/correlation matrices;
- `figure4_experimental.pdf`, raw+BDT and statistical bars, no theory overlay;
- reconstruction and estimator comparisons;
- fit, background, BREM-control, photon-multiplicity, and systematic PDFs.

Original theory model is intentionally absent until separate audit of original
equations, parameters, and references succeeds.

## Overnight runner

Full workflow from flux calibration through corrected extraction can run
unattended:

```bash
nohup bash scripts/run_beam_asymmetry_overnight.sh \
  > results/beam_asymmetry_overnight.out 2>&1 &
```

Runner continues after failed commands, writes one timestamped log per step,
skips only downstream steps whose newly produced inputs are unavailable, and
prints final `OK`, `FAILED`, or `SKIPPED` summary. Final exit code is non-zero
when any command fails. Calibration failure does not stop reconstruction, but
both extraction steps are skipped to prevent reuse of stale calibration.

Farm paths can be overridden without editing script:

```bash
SIGNAL_MC_SELECTED_DIR=/farm/path/signal_mc_selected \
PREANALYSIS_DIR=/farm/path/pre_analisi \
FLUX_FILE=/farm/path/flux.root \
PYTHON_BIN=/farm/path/venv/bin/python \
FLUX_PROGRESS_EVERY_EVENTS=100000 \
BOOTSTRAP_REPLICAS=500 \
nohup bash scripts/run_beam_asymmetry_overnight.sh \
  > results/beam_asymmetry_overnight.out 2>&1 &
```
