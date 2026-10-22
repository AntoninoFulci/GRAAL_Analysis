# Provisional data signal yields — 21 October 2026

The extraction uses measured UV events and estimates/subtracts their smooth
mass continuum. These are **provisional model-conditional signal yields**:
the nominal model converges with an identifiable, interior optimum, but its
mass-distribution goodness of fit fails. They are not validated purity estimates
or cross sections. Complete systematic uncertainties remain deferred.

## Inputs and selection

The source is `results/uv/reco/reco_eta_pi0_bdt.root`, with checked no-fit
provenance, the original BDT gate, measured four-vectors, pairing chi2 < 10,
and the original missing-proton-mass window ±0.06 GeV. No Sigma correction
is used. The selected run/strip/polarization universe follows
`prepare_analysis(..., observations_only=True)`: canonical manifest,
complete calibrated flux triplets, valid polarization domain, and polarization
states 1 and 2. Inputs and exact observation signatures are stored in outputs.

Seven UV periods have usable exposures: 1998_uv, 1999_uv, 2000_fuv, 2000_uv1,
2000_uv2, 2002_uv1, 2002_uv2. Period 2001_uv has no complete calibrated
exposures in the requested domain and is recorded as unavailable.

## Estimator and covariance

In each 50-MeV photon-energy interval, a 20×20 histogram of
`x=(M_gg(eta)-M_eta)/(0.08 M_eta)` and
`y=(M_gg(pi0)-M_pi0)/(0.08 M_pi0)` is fit by binned maximum likelihood.
The nominal components are a correlated skew-normal double peak and a smooth
exponential continuum in both coordinates. Both components are integrated
inside the **actual selected disk** x²+y²<10 using Gauss-Legendre quadrature;
they are not untruncated Gaussian fits to already selected events.

Signal weights are derived from the two normalized mass templates. Their
integral is one for the signal template and zero for the background template.
Summing these signed weights gives yields separately for every period,
polarization, azimuth and invariant-mass bin. No equal signal fraction across
these cells is imposed. This does require each component's mass-shape model
to be applicable across those kinematic cells within an energy slice.

Covariance differentiates the fitted weights **and the same Poisson counts
used to fit them**. Thus it includes their correlation and the correlation
between periods sharing a mass fit. It is stored exactly as
`diag(diagonal) + factors @ kernel @ factors.T` in compressed NPZ files;
the kernel alone need not be positive semidefinite, whereas the complete
influence covariance is. Per-period marginal matrices are also supplied.
Independent energy fits are combined without introducing cross-energy terms.
Empty cells have zero observed-information variance; no unit variance or
invented background is inserted.

Each energy fit also has 24 refitted Poisson bootstrap trials, with convergence
and boundary failures explicitly counted. These are a diagnostic, not the
primary covariance estimate; discarding boundary trials can bias their reported
standard deviation. The finite bootstrap sample is not used as a large,
rank-deficient covariance matrix.

An extended model adds one-real-meson peak backgrounds. Its yield difference,
convergence and boundary status are saved as diagnostics. This variation is
not a complete model uncertainty and is not added to the quoted statistical
error. The earlier symmetric-Gaussian and flat-annulus candidates were rejected:
the former fits the mass distributions poorly, while the latter would subtract
signal leakage and assumes a flat annulus inconsistent with the data.

## Grids and artifacts

The extraction is runnable with:

```bash
.venv-flux/bin/python -m observable_extraction.signal_yields \
  --output-dir results/cross-section-net-yields-20261021/extracted \
  --bootstrap-replicas 24
```

Total yields use energy edges 1.10,1.15,…,1.50 GeV and eight azimuthal bins.
Each period has 128 rows, ordered polarization, energy, azimuth; the joint
sample has 896 rows.

Differential yields use local energy windows [1.10,1.15], [1.15,1.25],
[1.25,1.35], [1.35,1.45], [1.45,1.50] GeV. These are analysis-defined windows,
not claimed Ajaka bin edges; the first and last centers are 1.125 and 1.475 GeV.
There are eight 50-MeV mass bins for each pair: p_pi0 1.05–1.45 GeV,
p_eta 1.45–1.85 GeV, eta_pi0 0.65–1.05 GeV. Each period has 640 rows,
ordered polarization, energy, invariant mass, azimuth; joint dimension 4480.
Some cells are outside kinematic support and have no events. A downstream
Gaussian extraction must select supported cells or merge bins; this release
does not provide artificial positive variance in empty cells.

Every observable directory contains an observations config compatible with
Stage-08 checks, a dense marginal yield/covariance JSON per period, the joint
factorized covariance manifest and NPZ, and an aggregated summary. The root
contains fit diagnostics, input identities, excluded-period audit, and a
multi-page PDF showing fitted projections, 2D residuals, and yields.

## Limitations and VIS diagnostic

Statistical uncertainties condition on the adopted mass model. Nominal
mass-fit goodness of fit is rejected in the UV slices: a converged numerical
fit is not evidence that background separation is accurate. One-real-meson
backgrounds, doubly peaking physics backgrounds, kinematic dependence of mass
shapes, and data-driven BDT/pairing sculpting need further controls before a
final result. Background estimates can shift by more than statistical errors
under model changes. Cross-observable covariance is not supplied; the three
pair projections and total share the same events and must not be treated as
independent measurements.

A separate flux-matched VIS study uses 1,638 events in .9313–1.0 GeV and
10,250 in 1.0–1.1 GeV. Both fits hit continuum-shape boundaries, so regular
unconstrained statistical yield contracts are not published for VIS.
`vis_diagnostics.json`, its log, and `diagnose_vis.py` preserve that result.
No fitted or generator-only detector response is substituted for missing
GEANT acceptance, and no cross section follows from these yields alone.

## Numerical result and verification

Across 1.10–1.50 GeV, the seven flux-matched UV periods contain **100,641 observed events**. The provisional fitted signal yield is **93,807.95 ± 356.74** (conditional statistical uncertainty), corresponding to a fitted continuum of **6,833.05 events**. The error is not a full physics uncertainty.

| Photon energy (GeV) | Observed | Provisional net yield | Conditional stat. error |
|---|---:|---:|---:|
| 1.10–1.15 | 9675 | 9557.10 | 103.30 |
| 1.15–1.20 | 11540 | 11249.09 | 122.95 |
| 1.20–1.25 | 13606 | 12880.35 | 135.83 |
| 1.25–1.30 | 14782 | 13672.67 | 134.53 |
| 1.30–1.35 | 15176 | 13970.13 | 139.34 |
| 1.35–1.40 | 15124 | 13779.14 | 137.59 |
| 1.40–1.45 | 14713 | 13286.93 | 135.23 |
| 1.45–1.50 | 6025 | 5412.55 | 91.06 |

Validation: 16 focused tests pass (four new mass-yield tests plus existing background tests); source lint passes. The canonical Stage-08 observations-only path reproduces every total-period raw count and signature exactly. All four joint covariance products reproduce their marginal matrices, and all nonempty marginal covariance blocks pass the positive-semidefinite check. The 12-page PDF was rendered and its mass-fit and total-yield pages visually inspected. Verification commands and results are preserved in `verify_products.py` and `verification.log` beside the extraction. These checks establish implementation/contract consistency, not mass-model adequacy.

The chosen differential mass windows exclude 17 observed p_pi0 projections,
1,945 p_eta projections and 951 eta_pi0 projections; the total grid excludes
none. These are explicitly recorded as `outside_grid_events` and must not be
silently interpreted as zero signal outside the mass range. The extended
four-component model changes the individual energy-bin yield by between
+24 and −383 events; several variation fits reach component boundaries.
This illustrates material model dependence without assigning a completed
systematic uncertainty. Across all energy slices, 187 of 192 bootstrap
replicas have interior converged optima (five rejected boundary replicas in
the lowest-energy slice).
