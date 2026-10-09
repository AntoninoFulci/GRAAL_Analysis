# 07 — Beam-Asymmetry Estimators

Stage 07 implements two estimators for the same linearly polarized beam
asymmetry `Sigma`: a binned flux-normalized ratio and an event-level
conditional likelihood. They share event selection, kinematic bins,
polarization convention, and calibrated exposures, but make different use of
the run/strip structure. Agreement is a physics cross-check, not an identity.

## Exposure Strata

The smallest exposure unit is `(run_number, xstrip)`. Each `FluxExposure`
contains strip energy, vertical/horizontal/BREM flux, and vertical/horizontal
linear polarization. The calibration adapter maps:

| Stored state | Physics label | Event value |
|---|---|---:|
| `POL1` | vertical | `Polarization == 1` |
| `POL2` | horizontal | `Polarization == 2` |
| `BREM` | unpolarized control | `Polarization == 0` |

Both selected polarized fluxes must be finite and positive. Polarizations
must lie in `(0,1]` for a ratio fit; the exposure data model permits zero so
that invalid rows can be diagnosed before an estimator rejects them.

For each subsystem and energy/mass bin, the ratio estimator sums all calibrated
exposure strata in that energy bin, including valid strata with no selected
events. Its effective polarization is flux-weighted separately for vertical
and horizontal states:

```math
P_V = \frac{\sum_s F_{V,s}P_{V,s}}{\sum_s F_{V,s}},\qquad
P_H = \frac{\sum_s F_{H,s}P_{H,s}}{\sum_s F_{H,s}}.
```

The conditional likelihood instead retains the exposure values of each event's
own `(run_number, xstrip)` stratum. Missing strata are rejected before fitting.

## Normalized-Ratio Fit

For each of the requested 8, 12, or 16 azimuth bins (default 12), observed counts are divided by integrated
exposure:

```math
y_V(\phi)=\frac{N_V(\phi)}{F_V},\qquad
y_H(\phi)=\frac{N_H(\phi)}{F_H}.
```

The fitted observable is

```math
R(\phi)=
\frac{y_V(\phi)-y_H(\phi)}
     {P_H y_V(\phi)+P_V y_H(\phi)}.
```

With the repository's vertical/horizontal convention, the nominal model is

```math
R(\phi)=A_\phi\cos(2\phi).
```

The center-fit amplitude `A_phi` is attenuated by averaging over a finite
azimuth bin. The reported physical `Sigma` is `A_phi / d`, using exactly the
approved rounded divisors:

| phi bins | divisor `d` |
|---|---:|
| 8 | 0.9003 |
| 12 (default) | 0.9549 |
| 16 | 0.9745 |

The statistical error is divided by the same divisor. These are rounded
values of `sin(Delta_phi)/Delta_phi` for uniform bins over `[0, 2 pi]`;
the formula is not evaluated at runtime. This assumes approximately constant
acceptance within each bin and common acceptance for both polarizations.
See [Zachariou et al., PRC 91, 055202 (2015), Eqs. (15)-(17)](https://arxiv.org/pdf/1503.05435)
and the [verification note](../docs/research/2026-10-09-finite-phi-bin-correction.md).
The name "Hannick" was supplied by the user; its attribution is unverified.
No finite-bin rescaling is applied to the event-level conditional likelihood.

Count errors are propagated assuming independent Poisson variances
`Var(N_V)=N_V` and `Var(N_H)=N_H`. If `D=P_H y_V+P_V y_H`, the derivatives
used by the code are

```math
\frac{\partial R}{\partial N_V}
=\frac{(P_H+P_V)y_H}{D^2 F_V},\qquad
\frac{\partial R}{\partial N_H}
=-\frac{(P_H+P_V)y_V}{D^2 F_H},
```

and

```math
\operatorname{Var}(R)=
\left(\frac{\partial R}{\partial N_V}\right)^2N_V+
\left(\frac{\partial R}{\partial N_H}\right)^2N_H.
```

Only finite ratio bins with finite positive uncertainty enter weighted least
squares. The one-parameter nominal fit needs at least two populated phi bins
and a full-rank normal matrix. It stores `Sigma`, its symmetric statistical
error, `chi2`, degrees of freedom, and p-value.

### Diagnostic harmonic fallback

When the nominal p-value is below `0.01`, the bin is refitted with

```math
R(\phi)=c_0+A_\phi\cos(2\phi)+s_{2,\mathrm{fit}}\sin(2\phi).
```

This diagnostic fit requires at least four usable phi bins. It reports
`used_fallback`, `c0`, `s2`, and the refitted diagnostics. `c0` or `s2` is
flagged when its magnitude exceeds three standard deviations. The returned
Sigma is the cosine coefficient divided by `d`. The sine diagnostic stored
with the physical point is also divided by `d`, so its systematic covariance
has physical Sigma units. `c0`, chi-square, p-value, and significance flags
are unchanged. Fallback points use square markers in Figure 4. Raw fit
amplitudes and diagnostics remain available in `RatioBinResult.fit`; ROOT
azimuthal curves retain the raw cosine amplitude so they fit the displayed
observed ratios.

Invalid count shape, non-finite or negative counts, non-positive flux,
polarization outside `(0,1]`, too few usable bins, or a rank-deficient design
raises `ValueError`. At grid level, an individual ratio bin that cannot satisfy
these conditions is skipped.

## Conditional Likelihood

For event `i` with azimuth `phi_i` and its own exposure stratum `s(i)`, the
vertical and horizontal rates are proportional to

```math
\lambda_{V,i}\propto F_{V,s(i)}
\left[1+P_{V,s(i)}\Sigma\cos(2\phi_i)\right],
```

```math
\lambda_{H,i}\propto F_{H,s(i)}
\left[1-P_{H,s(i)}\Sigma\cos(2\phi_i)\right].
```

The probability that the observed event belongs to the vertical state,
conditional on being in either polarized state, is

```math
p_{V,i}=\frac{\lambda_{V,i}}{\lambda_{V,i}+\lambda_{H,i}}.
```

For vertical events the log-likelihood contribution is `log(p_V)`; for
horizontal events it is `log(1-p_V)`. Conditioning removes a common unknown
event-rate normalization while preserving relative flux and polarization for
every run/strip.

The fitter minimizes negative log likelihood in the physical interval
`Sigma in [-1,1]`. Statistical limits are profile points where
`NLL = NLL_min + 0.5`; when the crossing lies outside the physical interval,
the reported limit stops at `-1` or `+1`. The resulting errors can therefore
be asymmetric.

A grid bin is attempted only when it contains at least four events and both
polarization states. Input arrays must be matching, finite, one-dimensional,
and non-empty; state labels other than `1` and `2` are rejected. Every event
must have a calibrated exposure.

## Physical Domain

The physical fit is bounded to `[-1,1]`, matching the `SigmaPoint` public
contract. A second diagnostic minimization explores the largest interval in
which every event rate remains positive. For coefficients

```math
a_i=P_{V,i}\cos(2\phi_i),\qquad
b_i=-P_{H,i}\cos(2\phi_i),
```

the domain is the intersection of `1+a_i Sigma > 0` and
`1+b_i Sigma > 0` for all events. A small epsilon keeps the numerical search
strictly inside this boundary.

The diagnostic result records the extended-domain best fit and NLL. Boundary
pressure is true when the physical optimum lies near `-1` or `+1` and the
extended-domain optimum would continue beyond that boundary. It is evidence
that the data prefer an unphysical magnitude; it is not permission to publish
an unbounded Sigma.

## Estimator Comparison

| Property | Normalized ratio | Conditional likelihood |
|---|---|---|
| data representation | 8, 12, or 16 binned phi counts per state | individual event labels and phi values |
| exposure treatment | summed by energy bin, flux-weighted polarization | exact run/strip exposure per event |
| statistical error | weighted least-squares covariance | `Delta NLL = 0.5` profile interval |
| physical bound | enforced by `SigmaPoint` output contract | enforced during minimization |
| extra diagnostic | `c0` and `s2` harmonic fallback | extended positivity-domain fit |
| minimum population | two usable phi bins; four for fallback | four events and both states |

The ROOT output keeps a `diagnostics/ratio_vs_likelihood` graph whenever both
estimators exist for the same sample and bin. The difference also contributes
an optional systematic shift; neither estimator silently replaces the other.

## Source and Test Map

| Responsibility | Source | Tests |
|---|---|---|
| exposure and result contracts | `07_observable_extraction/core/models.py` | `test_models.py` |
| normalized ratio and harmonic fits | `07_observable_extraction/core/ratio_fit.py` | `test_ratio_fit.py` |
| event-level likelihood and profiles | `07_observable_extraction/core/conditional_likelihood.py` | `test_conditional_likelihood.py` |
| fixed grid | `07_observable_extraction/core/binning.py` | `test_binning.py` |
