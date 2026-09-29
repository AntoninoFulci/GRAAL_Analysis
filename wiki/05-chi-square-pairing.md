# 05 — Chi-Square Pairing

The standard eta-pi0 reconstruction uses no trained model. It provides the
reference sample against which the Stage-1-gated path is compared while still
sharing topology guards, pairing, post-pairing cuts, and optional 6C fitting.

## Standard Path

Run:

```bash
python -m reconstruction.reconstruct_eta_pi0_chi2 \
  --input-dir data/03_selected \
  --output-file results/reco/reco_eta_pi0_chi2.root
```

Defaults are tree auto-detection, `chi2_cut=10`, proton partner,
`missing_mass_window=0.06 GeV`, enabled 6C fit, and `fit_cl=0.01`. With the fit
enabled, the confidence-level decision replaces the missing-mass window. Use
`--no-fit` to select with raw missing mass instead.

“Chi-square path” means no BDT dependency; it does not mean the pairing score
is the only selection or that the kinematic fit is disabled.

## Pairing Selection

For four photons there are three disjoint partitions:

```text
(01)(23), (02)(13), (03)(12)
```

When heavy and light mesons differ, both assignments of each partition are
evaluated, giving six `Pairing` objects. A degenerate hypothesis such as
two-pi0 evaluates three because swapping identical mesons is not a new case.

For a pairing with measured masses `m_H` and `m_L`:

```math
\chi^2=\left(\frac{m_H-M_H}{rM_H}\right)^2+
       \left(\frac{m_L-M_L}{rM_L}\right)^2,
```

where `M_H`, `M_L`, and fixed fractional resolution `r` come from the shared
hypothesis registry. `best_pairing` selects NumPy's first minimum and returns
its indices and score. An event passes only when `chi2 < chi2_cut`; equality is
rejected.

After selection, photons are reordered as heavy pair first, then light pair.
This canonical order is passed to the fit as `(0,1)` heavy and `(2,3)` light
and is also the order written to the daughter branches.

## Event Guards

Guards execute in this order:

1. require at least four reconstructed photons;
2. require exactly one reconstructed proton;
3. if configured, apply the Stage-1 gate—absent on this standard path;
4. select the minimum-chi-square pairing and require it below the ceiling;
5. reject if either reconstructed meson energy exceeds tagged beam energy;
6. with fit enabled, require convergence and `CL >= fit_cl`;
7. without fit, require `abs(m_missing - m_partner) < window` when enabled.

The missing mass is built from `beam + stationary partner - heavy - light`.
The window is centered on the nominal configured partner mass, not on an
observed data peak. Non-positive or null window disables that guard.

The `--partner` choice controls the raw missing-mass target and output `target`
vector. It does not change the default fit's proton-target/proton-recoil
reaction model; that is the separate `RecoConfig.fit_reaction` boundary.

## Output Contract

Default output is `results/reco/reco_eta_pi0_chi2.root`, tree
`reco_eta_pi0_chi2`. It has no `bdt_score` branch. Raw branches include:

```text
chi2, eta_mass, pi0_mass
RunNumber, Polarization, Xstrip, n_photons_input
beam, target, proton, neutron, missing
eta, eta_gamma1, eta_gamma2
pi0, pi0_gamma1, pi0_gamma2
```

With the default fit it also contains fitted eta/pi0 daughters and composites,
`proton_fit`, `fit_chi2`, `fit_ndf`, and `fit_converged`. Stored events always
have a converged fit passing the configured confidence level, so
`fit_converged` is 1 for persisted fitted rows.

The ROOT output file is replaced directly. An interrupted run can therefore
leave a partial file and must be rerun. Summary counters distinguish topology,
impossible-energy, missing-mass, and fit rejections; chi-square rejection is
not separately printed.

Tests in `05_reconstruction/tests/test_event_logic.py`, `test_reco_core.py`,
and `test_cli_contracts.py` pin order, strict inequalities, output schema, and
the equivalence of an accept-all gate to this ungated path.

Related pages: [photon pairing](photon-pairing),
[reconstruction](05-reconstruction), and [kinematic fit](05-kinematic-fit).
