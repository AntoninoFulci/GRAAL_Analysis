# Supported model scope

Included: Figure 11 tree mechanism in Döring et al., PRC 73, 045209 (2006),
Eq. (43): γp → Δ*(1700) → ηΔ(1232) → ηπ⁰p. Central source-linked couplings,
energy-dependent resonance widths, complete Eq. (39) production spin matrix,
unpolarized partial total cross section, and three partial invariant-mass
spectra are calculated. The Figure 14 *dotted* curve is the direct spectrum
validation target.

Excluded: Eq. (39) inserted into rescattering Eq. (26), other Figure 14
components, their coherent sum, parameter/uncertainty bands, reproduction of
the full Figure 19 curve, beam asymmetry, acceptance effects, experimental
Figure 4 overlay, and all integration with Stage 07/08. Figure 19 supplies
one digitized full-model point solely for the stated tree/full ratio check.

Generic kinematics, phase-space sampling, observable integration, and run
serialization are reusable. The `eta_pi0_p` model and its amplitude remain
reaction-specific; another channel needs its own explicitly sourced amplitude
and regression targets. Passing these tests does not validate another channel.

Known convention: evaluating Eq. (37) with Nacher couplings yields roughly
0.216 GeV at the Δ*(1700) pole, whereas the cited PDG-average nominal width is
roughly 0.300 GeV. The code does not rescale the partial components to force
agreement. The nominal input is used for the Nπ component as specified in
the parameter record. Electromagnetic couplings g′₁ and g′₂ are used directly
after their mₙ⁻¹ and mₙ⁻² conversion; no extra electric-charge factor is
inserted into Eq. (39).
