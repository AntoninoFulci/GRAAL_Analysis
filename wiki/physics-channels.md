# Physics Channels

The channel registry is the shared catalog used by Monte Carlo generation,
training-dataset construction, and status reporting. It binds channel names to
generator files, final-state hypotheses, thresholds, cross sections, and decay
information.

## Channel Registry

`00_common/physics/channels.py` is the only channel catalog. `CHANNELS` maps a
stable name to an immutable `MCChannel`, and `CHANNEL_NAMES` preserves registry
and generation order. The derived `mc_filename` is always
`<channel>_mc.root`.

| Channel | Production final state after the recoil proton | Default hypothesis | Weight anchor |
|---|---|---|---|
| `eta_pi0` | eta, pi0 | `eta_pi0` | No cross-section; primary measurement |
| `pi0pi0` | pi0, pi0 | `2pi0` | 4.5 ub at 2.2 GeV |
| `3pi0` | pi0, pi0, pi0 | Caller must choose | 1.8 ub at 1.26 GeV |
| `eta_2pi0` | eta, pi0, pi0 | Caller must choose | 0.3 ub estimate at 1.90 GeV |
| `omega_pi0` | omega, pi0 | Caller must choose | 0.49 ub at 1.60 GeV |
| `etaprime` | eta-prime | Caller must choose | 0.35 ub at 1.60 GeV |
| `eta_via_3pi0` | eta | Caller must choose | 0.65 ub at 1.03 GeV |
| `4pi0` | four pi0 mesons | Caller must choose | 0.2 ub upper-bound estimate at 1.45 GeV |
| `eta_pi0_via_3pi0` | eta, pi0 | Caller must choose | Signal-relative branching ratio |

The table reports values represented in code, including entries explicitly
marked there as estimates. Consult source comments for literature provenance
and limitations; an estimate must not be relabeled as a measurement.

`channel_from_filename` resolves ownership from the filename rather than from
list position. Reordering background arguments therefore cannot silently bind
a ROOT file to another channel's physics metadata.

## Signal and Background Roles

The registry describes reactions; it does not permanently label a class as
signal or background. `build_background_features.py` accepts any registered
channel as the signal and uses every other channel by default as background.
The default signal is `eta_pi0`.

The signal share is controlled by `--signal-prior`. It is a classifier-training
choice, not a measurement of the eta-pi0 cross section. Assigning a measured or
assumed eta-pi0 cross section in the registry would feed the desired answer
back into the classifier that selects events used to extract that answer.

`eta_pi0_via_3pi0` is the same production reaction with another eta decay. Its
weight is slaved to the signal through

$$
\frac{\mathrm{BR}(\eta\rightarrow 3\pi^0)}
     {\mathrm{BR}(\eta\rightarrow 2\gamma)}
=\frac{0.327}{0.394},
$$

so the unknown production cross section cancels. Every background is weighted
exactly one way: by a reference cross section or by this signal-relative
branching ratio, never both and never neither.

## Thresholds and Cross Sections

Production threshold is derived from the production masses, including the
recoil proton:

$$
E_{\gamma,\mathrm{thr}}=
\frac{\left(\sum_i m_i\right)^2-m_p^2}{2m_p}.
$$

The registry tests pin the derived thresholds to the generator calculations:

| Channel | Threshold (approximately GeV) |
|---|---:|
| `pi0pi0` | 0.309 |
| `3pi0` | 0.492 |
| `4pi0` | 0.695 |
| `eta_via_3pi0` | 0.708 |
| `eta_pi0` and `eta_pi0_via_3pi0` | 0.931 |
| `eta_2pi0` | 1.174 |
| `omega_pi0` | 1.366 |
| `etaprime` | 1.447 |

For a channel with reference value $\sigma_{\rm ref}$ at $E_{\rm ref}$,
`00_common/physics/cross_sections.py` implements

$$
\sigma(E)=\sigma_{\rm ref}
\min\left(1,
\frac{\Phi_n(W(E))}{\Phi_n(W(E_{\rm ref}))}\right),
\qquad
W(E)=\sqrt{m_p^2+2m_pE}.
$$

$\Phi_n$ is an n-body production phase-space volume used only through ratios.
The result is zero at or below threshold, rises toward the reference point,
and saturates rather than inventing growth above the measured anchor. The model
restores threshold behavior but does not model resonance structure; this is a
documented limitation.

## Adding a Channel

Adding a reaction requires a coherent change:

1. add an `MCChannel` with a unique name, production masses, and exactly one
   supported background-weight mechanism;
2. add or update its generator macro and ensure the output filename matches
   `<name>_mc.root`;
3. declare named photon branches or preserve the generator's `g0..gN` and
   `n_true_gamma` convention;
4. assign a hypothesis only when the reaction determines it unambiguously;
5. cite and label the reference cross section or estimate, including its
   reference energy above threshold;
6. extend registry, generator-physics, weighting, and status tests.

Useful verification:

```bash
pytest 00_common/tests/test_channels.py \
       00_common/tests/test_cross_sections.py \
       03_mc_simulation/tests/test_generator_physics.py \
       04_bdt_training/tests/test_channel_weights.py -q
```

See [Monte Carlo simulation](03-monte-carlo-simulation) for generation and
[Weighting and photon loss](04-weighting-and-photon-loss) for dataset use.
