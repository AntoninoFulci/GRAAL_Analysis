# Compton Beam and Polarization

GRAAL used laser photons backscattered from the ESRF electron beam. The
resulting energy spectrum, Compton edge, and linear-polarization transfer enter
training weights, calibration interpretation, and beam-asymmetry extraction.

## GRAAL Beam

`00_common/physics/compton.py` uses these operating constants:

| Constant | Value |
|---|---:|
| ESRF electron energy | 6027.6 MeV |
| Green laser wavelength | 514 nm |
| UV laser wavelength | 351 nm |
| Electron mass | 0.51099895 MeV |
| $hc$ | $1.239841984\times10^{-3}$ MeV nm |

Laser photon energy is

$$
E_L=\frac{hc}{\lambda}.
$$

All functions on this page use MeV for energy and nm for wavelength. This is
different from the GeV convention used in most reconstruction and channel
code; callers must not mix the units.

The measured detector beam spectrum is stored separately as an NPZ artifact
and used to reweight flat-energy Monte Carlo. The analytic calculations here
describe the Compton kinematic edge and polarization transfer, not the
run-by-run flux normalization.

## Compton Edge

The dimensionless inverse-Compton parameter is

$$
x=\frac{4E_eE_L}{m_e^2},
$$

implemented by `compton_x`. The maximum backscattered photon energy is

$$
E_{\gamma,\max}=E_e\frac{x}{1+x},
$$

implemented by `compton_edge_mev`. Tests pin the two configured laser lines to
the expected GRAAL energy range and verify that shorter wavelength produces
the higher edge.

## Polarization Transfer

For

$$
y=\frac{E_\gamma}{E_e},
\qquad
r=\frac{y}{x(1-y)},
$$

`linear_polarization_transfer` returns

$$
T(E_\gamma)=
\frac{2r^2}
{\frac{1}{1-y}+(1-y)-4r(1-r)}.
$$

The allowed domain is

$$
0\le y\le\frac{x}{1+x}.
$$

Input below zero or above the Compton edge raises `ValueError`; the function
does not extrapolate. The transfer is zero at zero photon energy and rises
toward the edge. Observable extraction combines the appropriate transfer or
calibrated polarization information with run and strip exposure.

## Figure 7 Reproduction

`plots/fig7_compton_polarization.py` samples 201 energies from zero to each
laser's edge and draws both transfer curves. It also marks the 550 MeV tagging
threshold.

Run:

```bash
python plots/fig7_compton_polarization.py
```

Default outputs are:

- `results/plots/fig7_compton_polarization.pdf` — rendered figure;
- `results/plots/fig7_compton_polarization.root` — graphs, edge lines,
  threshold line, and canvas.

The ROOT file preserves objects for inspection or reuse; generated files under
`results/` are not required source artifacts.

Verification:

```bash
pytest 00_common/tests/test_compton.py \
       plots/tests/test_fig7_compton_polarization.py -q
```

See [Plotting and diagnostics](plotting-and-diagnostics) for output ownership
and [Beam-asymmetry estimators](07-beam-asymmetry-estimators) for downstream
polarization use.
