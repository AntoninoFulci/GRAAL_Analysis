# Fig. 7 edge markers and ROOT output

## Goal

Extend the Figure 7 PyROOT plot with visible Compton-edge markers and a
ROOT-native output file.

## Outputs

- Keep `06_plots/fig7_compton_polarization.pdf`.
- Add `06_plots/fig7_compton_polarization.root`.

## Plot changes

For each laser line, calculate its Compton edge with the existing helper and
draw a vertical dashed line from `P=0` to that curve's calculated edge
polarization. Add one legend entry per edge marker. The 550 MeV tagging line
remains unchanged.

## ROOT file contents

Write the rendered `TCanvas`, both `TGraph` curves, the 550 MeV threshold
line, and both Compton-edge lines into the ROOT file with stable names.

## Verification

Tests check default ROOT path and edge-marker definitions. Running the script
must produce a one-page PDF and a readable ROOT file containing all six named
objects.
