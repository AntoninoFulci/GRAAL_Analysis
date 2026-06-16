# Photon-pairing BDT study

Trains an XGBoost BDT to assign the 4 photons of a gamma p -> p eta pi0 event
to the correct eta/pi0 pairing, and compares it to the chi2 baseline on MC.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r analysis/ml/requirements.txt
.venv/bin/python -m analysis.ml.build_features        # -> data/features.npz
.venv/bin/python -m analysis.ml.train_bdt             # -> model/bdt.json + plots
.venv/bin/python -m analysis.ml.evaluate_compare      # -> plots/metrics.txt + mass spectra
```

## Method

The 4 photons give 3 disjoint pairings. Per event the photons are shuffled
(no positional leakage), the 3 pairings are ordered by ascending chi2, and a
54-dim feature vector (3 blocks x 18 features: masses, mass distances, energy
asymmetry, opening angles, sorted energies, meson angle/pT/boost, chi2) is fed
to a multiclass `XGBClassifier`. The label is the chi2-ordered slot holding the
truth pairing; the chi2 baseline always picks slot 0. Headline metric: pairing
accuracy on a held-out test set, BDT vs chi2.

## Results (1M-event MC, 200k held-out test)

| Method | Pairing accuracy |
|--------|------------------|
| chi2 baseline | 0.9751 |
| XGBoost BDT   | 0.9808 |

The BDT improves pairing accuracy by +0.57 points absolute, recovering roughly
a quarter of the chi2 method's mis-pairings. The gain is modest because on this
**idealised MC (exactly 4 clean photons, no background, no splitoffs)** the
chi2 method is already near-optimal: the eta and pi0 masses are well separated
relative to the 10% photon energy smearing, so the correct pairing usually has
the smallest chi2. Reconstructed eta/pi0 peak widths are essentially unchanged
(the BDT fixes tail mis-pairings, not the core resolution). A larger ML gain
would be expected on more realistic data with variable photon multiplicity,
calorimeter splitoffs, and combinatorial background -- the natural next step.
