# 06 — Plotting

Plotting compares standard χ² and BDT-gated ηπ⁰ reconstruction and studies
kinematic-fit resolution.

## Structure

- `core/kinematics.py`: ROOT-free invariant masses and Dalitz limits;
- `core/reconstruction_data.py`: ROOT tree validation and array collection;
- `dalitz.py`: comparison histograms and ROOT/PDF output;
- `kinfit_resolution.py`: uproot/matplotlib fit-resolution study;
- `fig7_compton_polarization.py`: Compton polarization reference artifact.

## Main comparison

```bash
python -m plots.dalitz \
  --chi2 results/reco/reco_eta_pi0_chi2.root \
  --bdt results/reco/reco_eta_pi0_bdt.root \
  --out-dir results/plots
```

Both files are required and empty trees fail explicitly. Output includes
measured- and implied-proton Dalitz plots, χ²-versus-BDT comparison, η and π⁰
mass distributions, raw-before-fit comparisons, mass correlation, and
`istogrammi.root` for restyling without rereading event trees.

Dalitz boundary violations are counted rather than cut. Current reconstruction
should already remove mesons carrying more energy than beam; plot warns when
older trees still contain them.

## Fit-resolution study

```bash
python -m plots.kinfit_resolution \
  --signal 03_mc_simulation/data/eta_pi0_mc.root \
  --bdt results/reco/reco_eta_pi0_bdt.root \
  --out-dir results/plots
```

Signal truth provides raw/fitted residuals for M(ηp) and M(π⁰p). Reconstructed
data provides raw/fitted spectra when BDT file exists. Missing signal MC is
fatal for residual study; missing BDT data skips only data figures.

## Compton polarization

`python -m plots.fig7_compton_polarization` writes default PDF and ROOT
objects under `06_plots/artifacts/` using versioned GRAAL electron energy,
laser wavelengths, and tagging threshold.
