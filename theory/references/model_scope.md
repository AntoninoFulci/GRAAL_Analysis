# Supported model scope

Included: The legacy Eq. (43) Figure 11 tree mechanism of Döring et al.,
PRC 73, 045209 (2006), still supports partial total/mass spectra and an
exploratory Figure 4 panel-5 pilot. Separately, `EtaPi0PFullModel` now sums
all seven complete source-linked spin-amplitude families before squaring.
Its direct strong matrix supports real `W ≤ 1.80 GeV` and a validated
parameter-bound interpolation grid is optional. Conditional mass-window
sampling, exact energy onset, analytic global-azimuth projection, numerical
covariance, twelve-panel comparison, and explicit typed masks are implemented.
The PRC73 Figure 18 high-energy solid stroke has been independently traced
only through the 1.80 GeV ceiling.

Not yet established: numerical convergence of every physically accessible
Figure 4 bin, agreement of all twelve curves with the published theoretical
strokes, and a reproduced claim. The PRC65 strong input has qualitative
scattering agreement only through `W≈1.60 GeV`; its source-used extension to
1.80 GeV has no quantified theory uncertainty here. Parameter fitting,
experimental acceptance, Stage 07/08 integration, new channels, and
second-sheet poles are outside this increment. The legacy Eq. (43) pilot
remains partial and does not validate the seven-family result.

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
