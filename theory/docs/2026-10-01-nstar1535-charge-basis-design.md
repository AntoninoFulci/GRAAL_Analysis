# Reduced N*(1535) charge-basis diagnostic: design

## Purpose

Resolve what can be learned from the discrepancy between the calculated
charge-`+1` reduced `S11` and the dashed line in Döring, Oset and Strottman,
*Phys. Rev. C* **73**, 045209 (2006), Fig. 1. Inoue, Oset and Vicente
Vacas, *Phys. Rev. C* **65**, 035204 (2002), constructs the underlying
basic two-body model in a **charge-zero** basis. P73 does not say whether
Fig. 1 was recomputed in charge `+1` or copied from that charge-zero
calculation; neither paper tabulates every numerical mass used. The current
charge-`+1` result therefore remains a documented calculation, not an
exact reproduction claim. Source audit:
[`nstar1535_mass_input_audit.md`](../references/nstar1535_mass_input_audit.md).

This milestone calculates the P65 **charge-zero reduced model** with the
same explicit PDG 2024 mass policy and P65 Eq. (9) constants already used
for charge `+1`. It compares both charge bases to the *existing, frozen*
P73 Fig. 1 dashed reference. It does not tune a mass, subtraction constant,
phase, or reading error to improve agreement. A result may be a remaining
discrepancy or a convention block; either is a valid outcome if evidenced.

The longer objective is a coherent photoproduction model that can predict
our own binned observables and **be fitted to our data**. This diagnostic
must preserve that route; it is not the fit itself.

## Chosen approach and alternatives

Extend the existing six-channel calculation only where two real bases now
share mathematics: a private WT/loop/linear-solve core receives a fixed
coefficient matrix and an immutable parameter record. Thin charge-`+1`
and charge-zero wrappers own their own printed channel order, coefficient
table and source-linked mass mapping. The existing charge-`+1` public API
and numerical results stay unchanged. This is a two-basis N*(1535) core,
not a configurable coupled-channel framework.

Changing charge-`+1` masses alone is cheaper but cannot test the unresolved
charge-basis question. Adding VMD and `pi pi N` now would combine the
present discrepancy with new physics and obscure its origin. Those remain
later, separate milestones.

## Inputs and source boundaries

- P65 Sec. II A lists the charge-zero states in prose as `pi- p`,
  `pi0 n`, `eta n`, `K+ Sigma-`, `K0 Sigma0`, `K0 Lambda`, but its Table I
  prints `C` in the different order `K+ Sigma-`, `K0 Sigma0`,
  `K0 Lambda`, `pi- p`, `pi0 n`, `eta n`. Use the **Table I order** for
  charge-zero arrays, with an explicit index map for the `pi N -> eta n`
  projection. Transcribe P65's own symmetric `C`; never rename P73's
  charge-`+1` table or silently use the prose order with table entries.
- Reuse P65 Eqs. (5)-(7), (9), (10): `f_pi=93 MeV`,
  `f_K/f_pi=1.22`, `f_eta/f_pi=1.3`, `mu=1200 MeV`, and reduced
  `(a_piN,a_etaN,a_KLambda,a_KSigma)=(2.0,0.2,1.6,-2.8)`.
- Reuse existing source-linked PDG 2024 species values where present;
  add `Sigma-` mass with its own PDG 2024 locator. Do not change the
  existing charge-`+1` parameter JSON schema or call modern masses the
  authors' unprinted original values. Source PDF hashes remain recorded.
- Keep `W` real, finite, scalar and within the existing reduced-model
  domain. Each basis uses its own lightest physical threshold. `V` and
  `T` are in `GeV^-1`; `G` is in `GeV`; rescaled `S11` is dimensionless.

## Comparison and checks

For charge zero, construct the `pi N(I=1/2) -> eta n` projection from
explicit Clebsch-Gordan and P65 charge-state conventions, then apply
P65 Eq. (10). Record the relative `eta N` phase assumption. If the
available papers do not fix an overall signed convention, label signed
comparison **convention-blocked**; do not choose sign by matching Fig. 1.
The charge-`+1` projection remains as implemented.

Use the eight energies, dashed-stroke values and reading bounds already
frozen in [`p73_fig1_reduced.csv`](../references/p73_fig1_reduced.csv).
Report, for both bases, channel thresholds, predicted real/imaginary
`S11`, model-minus-reference residuals and which components exceed their
reading bound. The comparison tests the charge-basis hypothesis; a better
residual is evidence, not proof of which basis P73 used. No new fit target
or PDF digitization is introduced.

Test both bases against their printed `C` entries, exact channel order,
WT symmetry, threshold behavior, P65 Eq. (7) open-channel sign, two-body
unitarity and stable linear solve. Include a regression on the existing
charge-`+1` numerical grid before/after extraction. Reject malformed,
complex, nonfinite or mutable parameter inputs. Run the standalone
`theory/` suite; leave dirty user files untouched.

## Fit-ready continuation, not part of this milestone

The charge-`+1` strong `T` remains a pure function of energy and explicit
physics parameters. PDF traces and historical comparison logic stay
outside the physics kernel. Later milestones add P65/P73 full strong
corrections, a coherent `gamma p -> eta pi0 p` amplitude, and polarized
cross-section integration; only after validation against the published
components and twelve Ajaka panels will a fit adapter evaluate predictions
in **our** native bins. That adapter must keep physics parameters separate
from luminosity, beam polarization, acceptance and other experimental
nuisances, and use the measured covariance/uncertainties. Which couplings
can vary, their bounds/priors and whether asymmetries alone identify them
are later inference decisions, not assumptions hidden in this diagnostic.

No Stage 07/08 integration, full-model claim, Ajaka-panel overlay, new
CLI, optimizer, or fit to our data occurs in this milestone. Its output
is a trustworthy two-basis diagnostic and an explicit next decision:
resolve remaining source/convention gaps if necessary, then specify the
full strong model without changing the reduced input record.
