# Figure 4 theoretical curves: publication-reproduction design

## Goal and boundary

Reproduce the **calculated** beam-asymmetry curves in all twelve panels of
Ajaka et al., *Phys. Rev. Lett.* **100**, 052003 (2008), for
`gamma p -> eta pi0 p`. This is the next milestone of the standalone
`theory/` project. The subsequent comparison with our higher-statistics,
finer-binned asymmetries is a separate milestone, reached only after the
publication-binning calculation has been validated. Stage 07/08 code and
outputs remain untouched in this milestone.

Success means a sourced, independently calculated coherent amplitude whose
cross sections, invariant-mass spectra, and twelve beam-asymmetry curves can
be compared quantitatively with the papers. Tracing a published line from a
PDF is a reference dataset, not a calculation. The existing Eq. (43) pilot
remains explicitly labeled a **partial tree contribution**; it cannot be
relabeled as the Ajaka theoretical result.

## Primary sources and known limits

- Döring, Oset, and Strottman, *Phys. Rev. C* **73**, 045209 (2006),
  DOI `10.1103/PhysRevC.73.045209`: amplitudes, coherent sum, Fig. 14
  component checks, Figs. 18–20 spectra and cross section. Local PDF:
  `tmp/pdfs/10.1103@PhysRevC.73.045209.pdf`.
- Döring, Oset, and Strottman, *Phys. Lett. B* **639**, 59 (2006),
  DOI `10.1016/j.physletb.2006.06.022`: complementary channel and
  `Delta*(1700)` coupling conventions. Local PDF:
  `tmp/pdfs/10.1016@j.physletb.2006.06.022.pdf`.
- Ajaka et al., *Phys. Rev. Lett.* **100**, 052003 (2008),
  DOI `10.1103/PhysRevLett.100.052003`: twelve-panel target, four photon-
  energy intervals, ten mass bins per pair, and twelve azimuth bins. Local
  PDF: `tmp/pdfs/PhysRevLett.100.052003.pdf`.
- Ajaka et al., *Phys. Rev. Lett.* **81**, 1797 (1998),
  DOI `10.1103/PhysRevLett.81.1797`: Ref. [14] of Ajaka 2008. Its Eqs. (1)
  and (2) give the vertical-polarization sign and the flux-normalized
  vertical/horizontal yield ratio fitted to `cos(2 phi)`. Local PDF:
  `tmp/pdfs/PhysRevLett.81.1797.pdf`.

Ref. [14] does **not** specify fit weights or whether finite azimuth bins use
centers or bin-averaged cosine. It documents the experimental extraction,
not how the 2008 theoretical line was evaluated. The nominal Stage 07
center-fit is therefore a testable convention, not a proven exact replica.
The 2006 coherent calculation also depends on earlier scattering-amplitude
and coupling references. Each dependency must have an identified source and
convention before its term is implemented. If a source or phase is
unrecoverable, report the missing term and do not claim full reproduction.

## Chosen approach

Work in three ordered parts within this milestone:

1. Create reviewed numerical reference curves for all twelve published
   theoretical lines, independently of model output. Record source-page,
   axis calibration, tracing method, line-overlap/reading uncertainty, and
   PDF checksum. Keep existing digitized experimental points separate.
2. Extend the existing reaction-specific amplitude, term by term, to the
   **complex coherent sum** documented in the 2006 papers. Validate
   unpolarized components and interference before comparing asymmetries.
3. Integrate polarized cross sections with the published pair-angle and
   binning conventions, generate all twelve panels, and report residuals
   against the digitized theoretical curves. Do not tune source parameters
   to those curves or to our data.

Digitization alone would yield a visual overlay but no predictive model.
Extending Eq. (43) alone would yield a predictive *partial* curve but not the
published full-model line. Both remain useful checks; neither meets the goal.

## Components and ownership

The existing `theory/src/graal_theory/` package owns the work. Reuse its
kinematics, three-body sampler, provenance records, and Eq. (43) regression
tests. Reaction-specific amplitude terms live under `amplitudes/` and are
combined in `models/eta_pi0_p.py` as complex spin amplitudes **before**
spin sums or squaring. No generic second-channel plugin, cross-package
import, or Stage 07 API is introduced for one reaction.

An amplitude inventory records, for every required diagram or coupled-
channel transition: paper equation/figure, input parameters and phase
conventions, local or external source, implementation status, and isolated
regression target. This inventory is the gate for adding each term; a
plausible numerical value is not a substitute for provenance.

The observable layer takes polarized event weights and one of three pair
definitions (`p_pi0`, `p_eta`, `eta_pi0`). For each pair, `phi` is the
azimuth of the **sum of its two momenta** around the photon axis, measured
from the horizontal plane as in Ajaka 2008. The primary theory observable
is the coefficient of the vertical-minus-horizontal `cos(2 phi)` term from
polarized cross sections. A separate synthetic-yield comparison may apply
Ref. [14]'s flux-normalized ratio and the nominal Stage 07 twelve-bin fit;
its center-versus-bin-average sensitivity must be reported, not hidden in
the primary line.

The publication comparison owns its own reference data and figures under
`theory/`. Outputs include a 4-by-3 figure, machine-readable predictions
and residuals, numerical uncertainties, source hashes, and explicit model
scope. It never imports the Stage 07 plotting package. Existing
`test_data/beam_asymmetry/figure4_comparison_ajaka2008.pdf` is a visual
reference for later overlays, not a source of numerical black points.

## Integration and kinematic edges

Published energy ranges are `[1.10, 1.20)`, `[1.20, 1.30)`,
`[1.30, 1.40)`, and `[1.40, 1.50]` GeV. Each has ten nominal mass bins
for each pair; bins beyond physical support are absent, never zero-valued
predictions. For a partially accessible bin, integrate only over its
kinematically allowed energy–mass region with the correct phase-space
Jacobian. Use mass-stratified or equivalent conditional sampling so the
high-mass edge is not estimated from a tiny accidental tail of whole-space
Sobol samples. Preserve the nominal mass interval for comparison, but
record its accessible support and weighted mass position; a geometric
center outside support is not a physical evaluation point. Require a
resolution/convergence check for every reported edge value.

The paper does not fully document how its theoretical curves were averaged
over each photon-energy interval. Keep energy averaging explicit and record
the chosen spectrum. Compare uniform weighting with measured-flux weighting
where the calibrated flux exists; do not select whichever matches the paper
better without independent justification. Existing theory flux loading may
be reused, but publication reproduction must not silently assume its run
set equals the selected reconstructed-event run set of Stage 07.

## Verification and claim gate

- Preserve the already validated Eq. (43) partial cross section and spectra;
  adding terms cannot change its isolated result.
- Check each new amplitude against its sourced component where the papers
  expose one, then check coherent spectra and total cross section. Squared
  component sums must not be substituted for a coherent sum.
- Check four-momentum conservation, polarized spin sums, V/H interchange
  and azimuthal sign, `|Sigma| <= 1`, and agreement between integrated mass
  spectra and total cross section.
- Compare successive integration resolutions for every populated panel
  bin. Report uncertainty and mask any unconverged result; no line segment
  may silently bridge a masked bin.
- Compare all twelve calculated curves with the independently digitized
  theoretical lines, using their recorded reading uncertainty plus numerical
  uncertainty. Publish panel-by-panel residuals and discrepancies. Claim
  reproduction only if the curves are compatible within these uncertainties
  and all included terms have sourced conventions; otherwise label the
  result incomplete and identify why.
- Run standalone theory tests. No Stage 07/08 test or output is modified by
  this milestone.

## Handoff to our higher-statistics analysis

Once the publication comparison passes review, a separate design will map
the same amplitude and observable integrator to **our** energy/mass bins,
selected runs, measured V/H fluxes and polarizations, estimator, and
covariance. It will read or regenerate native analysis output; it will not
redigitize black points from the comparison PDF. The absent local
`results/beam_asymmetry/beam_asymmetry.root` is a data-availability task for
that later milestone, not permission to alter Stage 07 now.
