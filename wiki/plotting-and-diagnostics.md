# Plotting and Diagnostics

Plotting is an unnumbered consumer of validated stage artifacts. It does not
reconstruct events, retrain the BDT, or calibrate flux. Entry points cover
campaign postprocessing, reconstruction comparisons, Compton-polarization
reproduction, and kinematic-fit resolution. Shared numerical kinematics live in `plots/core/kinematics.py`;
ROOT access for reconstructed trees lives in
`plots/core/reconstruction_data.py`.

## Plot Entry Points

| Entry point | Inputs | Backend | Purpose |
|---|---|---|---|
| `scripts.plot_campaign` | completed UV/VIS campaign ROOT files | PyROOT, matplotlib | regenerate canonical profile and common plots |
| `plots.dalitz` | chi-square and BDT reconstruction ROOT files | PyROOT | Dalitz, meson-mass, raw/fit, and reconstruction-path comparisons |
| `plots/fig7_compton_polarization.py` | shared Compton constants only | PyROOT | reproduce UV/VIS polarization-transfer curves and persist ROOT objects |
| `plots.kinfit_resolution` | signal-MC ROOT plus optional fitted BDT data ROOT | uproot, NumPy, matplotlib | compare raw and fitted recoil-mass resolution against MC truth |

### Dalitz and mass plots

```bash
python -m plots.dalitz \
  --chi2 results/reco/reco_eta_pi0_chi2.root \
  --bdt results/reco/reco_eta_pi0_bdt.root \
  --out-dir results/plots
```

The files must contain `reco_eta_pi0_chi2` and `reco_eta_pi0_bdt`
respectively. If `fit_chi2` exists, the adapter uses `eta_fit`, `pi0_fit`, and `proton_fit`
for the displayed meson masses and Dalitz axes while retaining raw masses for
dashed before/after overlays. Without fit branches it consistently falls back
to raw vectors.

Two proton constructions are intentionally shown:

- `misurato` uses measured `proton` for raw data and `proton_fit` with fitted
  mesons; the recoil track contributes independent information;
- `implicito` uses `missing`. Because `eta + missing = beam + target - pi0`,
  this is a missing-mass construction, clean by algebra but not independent
  information.

### Compton Figure 7

```bash
python plots/fig7_compton_polarization.py
```

The script evaluates the shared analytic Compton functions for the 514 nm
green and 351 nm UV laser lines, marks each Compton edge and the 550 MeV
tagging threshold, and prints edge energy and endpoint polarization. There are
no CLI options; callers that need custom output paths may import `draw_fig7`.

### Kinematic-fit resolution

```bash
python -m plots.kinfit_resolution \
  --signal 03_mc_simulation/data/eta_pi0_mc.root \
  --bdt results/reco/reco_eta_pi0_bdt.root \
  --out-dir results/plots \
  --n 20000
```

The signal file must contain tree `mc`, smeared and `*_true` four-vectors for
the eta daughters, pi0 daughters, proton, and beam. The script reruns the same
6C `fit_event` used by reconstruction on up to `--n` signal events. The BDT
data file is optional; when absent, data comparison figures are skipped with a
message. When present it must include raw and fitted eta, pi0, and proton
vectors.

## Reconstruction Data Adapter

`open_tree(path, tree_name)` refuses a missing file, zombie ROOT file, missing
tree, or empty tree and reports available keys for a tree mismatch. `collect`
makes one pass and returns detached `ReconstructionArrays`:

| Field | Meaning |
|---|---|
| `mep_meas`, `mpp_meas` | `M(eta p)` and `M(pi0 p)` using measured proton |
| `mep_miss`, `mpp_miss` | same pairs using missing four-vector |
| `eta_mass`, `pi0_mass` | fitted masses when fit branches exist, otherwise raw |
| `eta_mass_raw`, `pi0_mass_raw` | always the stored pre-fit masses |
| `over_limit` | event exceeds the kinematic Dalitz limit; counted, not cut |
| `eta_over_beam` | impossible raw eta-energy diagnostic for stale trees |
| `has_fit` | whether the tree carries the fit branch family |

Four-vectors are normalized to NumPy `[px, py, pz, E]`. Plot definitions use
the same masses and invariant-mass helpers as reconstruction rather than
maintaining plot-local physics constants.

## Outputs

All defaults write below ignored `results/plots/`.

| Producer | Outputs |
|---|---|
| Dalitz | individual `dalitz_*.pdf`, `masse_2d_*.pdf`, comparison PDFs, `massa_eta*.pdf`, `massa_pi0*.pdf`, and `istogrammi.root` |
| Compton Figure 7 | `fig7_compton_polarization.pdf` and `fig7_compton_polarization.root` |
| fit resolution | `risoluzione_eta_p.pdf`, `risoluzione_pi0_p.pdf`, `massa_eta_p_mc.pdf`, `massa_pi0_p_mc.pdf`, plus optional data `massa_eta_p.pdf` and `massa_pi0_p.pdf` |

`istogrammi.root` stores every filled Dalitz and mass histogram so style can be
changed without rereading event trees. The Figure 7 ROOT file stores the two
polarization graphs, edge lines, tagging-threshold line, and canvas.
Matplotlib runs with the non-interactive `Agg` backend.

## Interpretation Boundaries

- Dalitz points above the calculated kinematic limit are reported as a
  resolution diagnostic, not automatically removed by plotting.
- The implicit-proton Dalitz view is not an independent measurement because
  of its four-vector identity.
- A fitted eta or pi0 mass is fixed by the 6C meson-mass constraints; its
  apparent narrowness is not a resolution measurement. Recoil observables
  `M(eta p)` and `M(pi0 p)` carry the meaningful propagated improvement.
- `core_sigma` measures standard deviation only in the central residual window
  `(-0.3, 0.3)` GeV. It describes the core and intentionally excludes tails.
- Non-converged MC fits remain in raw distributions but are absent from fitted
  distributions.
- Figure 7 is an analytic beam/polarization reproduction, not a fit to detector
  data.
- The campaign postprocessor stages profile and common plot directories before
  publishing. Run `python -m scripts.plot_campaign --campaign results/NAME` to
  regenerate plots from existing reconstruction and Stage-07 ROOT files.
- Campaign plots include paired raw/6C-fit mass shapes for `M(p eta)`,
  `M(p pi0)`, and `M(eta pi0)`, constrained eta/pi0 masses, and separate ratio
  and likelihood asymmetry comparisons. Common plots show UV/VIS in the
  five-row energy grid and separate normalized mass panels.

Tests are in `plots/tests/`: pure kinematics, ROOT adapter behavior, Dalitz
construction, Compton ROOT objects, and fit-resolution pairing/order checks.
