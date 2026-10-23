# Finite azimuth-bin correction for beam asymmetry

Verified 2026-10-09; rounded-value implementation approved on the same date.

## Primary literature directly inspected

N. Zachariou et al. (CLAS), *Determination of the beam-spin asymmetry of deuteron photodisintegration in the energy region Eγ = 1.1–2.3 GeV*, Physical Review C **91**, 055202 (2015), [DOI: 10.1103/PhysRevC.91.055202](https://doi.org/10.1103/PhysRevC.91.055202). The [author manuscript](https://arxiv.org/pdf/1503.05435) was directly opened and inspected.

Section V, manuscript p. 10, Eq. (15), integrates each polarized yield over a bin centered at φ:

\[
Y_{\parallel,\perp}(\phi)\propto
F_{\parallel,\perp}A\left[\Delta\phi\pm
P_{\parallel,\perp}\Sigma\sin(\Delta\phi)\cos(2\phi)\right].
\]

Eq. (16) inserts the attenuation into the polarized-yield ratio; Eq. (17) defines its fitted amplitude. On manuscript p. 11 the identification is

\[
C=\bar P\Sigma\frac{\sin(\Delta\phi)}{\Delta\phi}.
\]

Section VI.B, manuscript p. 12, explicitly requires constant acceptance within each bin and matching acceptance between the two polarization settings. Section V, p. 11 discusses variable widths and a Monte Carlo calibration instead of one universal factor. Section VI.D, p. 12 explicitly writes the conversion \(\Sigma=(C/\bar P)\Delta\phi/\sin(\Delta\phi)\). These page numbers refer to this manuscript, not the journal typesetting. [Primary manuscript](https://arxiv.org/pdf/1503.05435).

## Independent mathematical consequence

For a bin of full width Δφ in radians, centered at φc,

\[
\frac{1}{\Delta\phi}\int_{\phi_c-\Delta\phi/2}^{\phi_c+\Delta\phi/2}
\cos[2(\phi-\phi_0)]\,d\phi
=\frac{\sin(\Delta\phi)}{\Delta\phi}
\cos[2(\phi_c-\phi_0)].
\]

Therefore a fit using the center cosine, without this factor in its model, measures Σfit = f Σtrue. For Nφ equal bins covering 2π, Δφ = 2π/Nφ:

| Nφ | Δφ | f = sin(2π/Nφ)/(2π/Nφ) | Σcorrected/Σfit |
| --- | --- | --- | --- |
| 8 | 45° | 0.900316316157 | 1.110720734540 |
| 12 | 30° | 0.954929658551 | 1.047197551197 |
| 16 | 22.5° | 0.974495358404 | 1.026172152977 |

The proposed rounded values 0.9003, 0.9549, and 0.9745 match this formula. The full-circle assumption is needed to infer width from Nφ; the integral identity itself applies to an individual bin of any center.

## Implemented convention

At the user's explicit request, production uses the literal divisors
**8 → 0.9003**, **12 → 0.9549**, **16 → 0.9745**. No analytic sinc is
evaluated at runtime and no extra correction flag is needed. The default
12-bin extraction therefore also changes its reported ratio Sigma and error.

`observable_extraction.core.binning.PHI_BIN_DIVISORS` owns these values.
`extract_ratio_grid` applies the divisor exactly once when converting the
raw `RatioFitResult` into a physical `SigmaPoint`. Sigma and its statistical
errors are divided by the divisor; the fallback sine diagnostic is scaled
to the same physical units. The constant diagnostic, chi-square, degrees of
freedom, p-value, and significance flags retain their raw-fit values.
Uniform 8/12/16 bins covering `[0, 2 pi]` are required for this correction.

`RatioBinResult.fit` and the azimuthal ROOT graph/curve retain the observed
center-fit amplitude. `sigma_points`, publication plots, sideband Sigma,
bootstrap, multiplicity studies, and covariance construction use the
corrected physical points. `sigma_uncorrected` retains its existing meaning:
Sigma before **background** correction, already corrected for finite phi
bins. The unbinned conditional-likelihood Sigma is not rescaled.

ROOT provenance records `phi_bin_correction=ratio_only_rounded` and the
actual `phi_bin_divisor`. Old outputs without a divisor remain readable as
uncorrected results; reads and plot regeneration never silently change them.
UV/VIS composition rejects corrected/uncorrected mixtures. Rerun extraction
to obtain corrected results from an older campaign; existing ROOT files and
published Ajaka points are not rewritten.

Regression checks cover all three literal divisors, error scaling, recovery
of a known Sigma from analytically integrated polarized yields, fallback
diagnostics, unchanged likelihood, ROOT overlay amplitudes and statistical
covariance, and legacy/metadata validation.

## Consequences for analysis (mathematical inference)

- Apply Σcorrected = Σfit/f only when the fitted angular model omits the bin integration. If f is included in the model, the fit already returns physical Σ. A binned likelihood that integrates its model also needs no second correction.
- The factor belongs inside both polarized yields before their ratio is formed. Integrating a nonlinear ratio function directly is generally different from taking the ratio of integrated yields. Unequal fluxes or polarizations do not invalidate the factor when the ratio model is constructed from the integrated yields.
- For known geometric f, standard errors and confidence interval endpoints scale by 1/f; variance scales by 1/f². Rescale covariance entries involving Σ accordingly. An additional uncertainty is needed only if the effective correction is estimated, e.g. from acceptance simulation.
- Matching acceptance between polarization states does not by itself make the within-bin weight uniform. With common weight w(φ), replace the center cosine by \(\int w\cos(2(\phi-\phi_0))d\phi/\int w d\phi\). This need not be a universal sinc factor. Energy/kinematic averaging must also support the assumed Σ and polarization model.
- An unbinned likelihood using each event's actual φ has no histogram averaging and receives no finite-bin sinc correction. Detector angular resolution is a separate issue. Creating a display histogram after an unbinned fit does not change this.

## Attribution and GRAAL applicability

This verifies the generic finite-bin method. It does **not** establish that the actual GRAAL ηπ⁰ sample has uniform acceptance within each φ bin; that remains an analysis assumption to assess separately.

No inspected primary source attributes this correction to **Hannick**, **Henning**, or **Hennig**. Targeted searches did not establish any of these names; absence from those searches does not prove absence from all literature. Use the descriptive term **finite azimuth-bin correction** pending an original attribution reference.

The result follows from the cos(2φ) modulation, so its relevance to GRAAL ηπ⁰ is mathematical rather than reaction-specific. The GRAAL ω paper [Vegna et al., arXiv:1306.5943](https://arxiv.org/pdf/1306.5943) was also opened, but did not establish this factor or attribution. Ajaka et al.'s ηπ⁰ paper is [PRL 100, 052003 (2008)](https://doi.org/10.1103/PhysRevLett.100.052003); its full text was not accessible in this check, so it is not claimed as confirmation of the correction.
