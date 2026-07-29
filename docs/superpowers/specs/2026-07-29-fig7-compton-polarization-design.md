# Fig. 7 Compton polarization plot

## Goal

Provide standalone PyROOT script reproducing theoretical curves in Fig. 7 of
Bartalini et al. (2005).

## Location and output

- Script: `06_plots/fig7_compton_polarization.py`
- Output: `06_plots/fig7_compton_polarization.pdf`
- No ROOT data file, PNG, or experiment-event input.

## Physics model

Use electron energy `E_e = 6027.6 MeV`, laser wavelengths 514 nm and 351 nm,
and fully linearly polarized input laser (`P_L = 1`).

For each wavelength, use:

\[
x = 4 E_e E_L/m_e^2,\quad y=E_\gamma/E_e,\quad
r=y/[x(1-y)]
\]

and:

\[
P_\gamma^{\rm th}(y)=\frac{2r^2}
{(1-y)^{-1}+(1-y)-4r(1-r)}.
\]

Plot only physical domain `0 <= y <= x/(1+x)`.

## Plot

- Two smooth `TGraph` curves.
- X axis: photon energy `E_gamma (MeV)`, from 0 to 1600.
- Y axis: `P_gamma^th`, from 0 to about 1.05.
- Vertical/annotated tagging threshold at 550 MeV.
- Legend identifies 514 nm and 351 nm curves.

## Verification

Script prints calculated Compton edge and edge polarization. Values must agree
with paper within rounding: about 1.10 GeV / 0.980 for 514 nm, and 1.48 GeV /
0.962 for 351 nm.
