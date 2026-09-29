# 04 — Weighting and Photon Loss

Stage-1 weighting combines detector acceptance, the measured beam spectrum,
and channel production information without using the unknown signal
cross-section as an input. The implementation preserves relative physics
weights while rescaling their absolute magnitude for XGBoost.

## Acceptance Model

For photon energy `E` and polar angle `theta`, `photon_loss.py` defines three
sigmoid loss components:

```math
p_{thr}=\operatorname{sigmoid}\left(-\frac{E-E_{thr}}{\sigma_E}\right)
```

```math
p_{fwd}=\operatorname{sigmoid}\left(-\frac{\theta-\theta_{min}}{\sigma_\theta}\right),\qquad
p_{bwd}=\operatorname{sigmoid}\left(\frac{\theta-\theta_{max}}{\sigma_\theta}\right)
```

The angular and total loss probabilities are:

```math
p_{acc}=1-(1-p_{fwd})(1-p_{bwd}),\qquad
p_{loss}=1-(1-p_{thr})(1-p_{acc}).
```

Defaults map directly to `LossParams`:

| Parameter | Default | Meaning |
|---|---:|---|
| `E_thr` | `0.050 GeV` | soft energy-threshold center |
| `sigma_E` | `0.020 GeV` | energy sigmoid width |
| `theta_min_acc` | `0.436 rad` | approximate forward BGO edge, 25° |
| `theta_max_acc` | `2.705 rad` | approximate backward BGO edge, 155° |
| `sigma_theta` | `0.050 rad` | angular transition width, about 3° |

Each photon receives an independent Bernoulli survival draw. An event enters
the dataset only when exactly four photons survive. The same operation applies
to every class, including four-photon signal. `p_surv` is the generated-event
fraction passing this contract.

This is a simplified acceptance model, not a full detector simulation. Its
parameters and independence assumption are part of the training model and must
be treated as such when interpreting performance.

## Beam Reweighting

Generators draw beam energy uniformly between channel threshold and `1.75
GeV`; detector data contains the shaped Compton-backscattered spectrum.
`beam_spectrum.py` measures a normalized histogram from selected ROOT files.
For surviving event `i` in channel `c`:

```math
w^{beam}_{ci}=\frac{p_{data}(E_{ci})}{p_{mc,c}(E_{ci})}.
```

Concrete mapping:

- `E_ci` is `ChannelSample.beam_E[i]`;
- `p_data` is `BeamSpectrum.density` loaded from the required NPZ;
- `p_mc,c` is a histogram measured from that channel's own surviving energies;
- `w_beam` is `ChannelSample.w_beam`.

Each channel needs its own denominator because production thresholds differ.
Events outside the measured range get weight zero. Bins containing fewer than
`MIN_MC_PER_BIN = 200` MC events also get zero weight: their density estimate
is too thin for a stable ratio, especially in tagger-smearing tails below a
reaction threshold. The denominator is floored numerically only after this
reliability mask, keeping returned weights finite.

## Channel Yields

For `N_gen,c` generated events and the subset `S_c` surviving acceptance,
`channel_yield` computes:

```math
Y^{unit}_c=\frac{1}{N_{gen,c}}\sum_{i\in S_c}w^{beam}_{ci}
```

and, when the channel has a cross-section model,

```math
Y^{\sigma}_c=\frac{1}{N_{gen,c}}\sum_{i\in S_c}
\sigma_c(E_{ci})w^{beam}_{ci}.
```

`sigma_c(E)` is `graal_common.physics.cross_sections.sigma_at`, which is zero
below the registry-derived production threshold and shaped relative to the
channel's reference point. `Y_sigma` therefore combines measured beam flux,
threshold-aware production, and acceptance.

The denominator is the generated count, not the survivor count. Dividing by
survivors would erase the survival fraction and make low-acceptance eight-
photon channels look as efficient as four-photon channels. Non-positive
generated counts and zero-overlap yields are fatal.

For an ordinary background `c`, its share of the available ordinary-background
budget `B` is:

```math
s_c=B\frac{Y^\sigma_c}{\sum_{b\in ordinary}Y^\sigma_b}.
```

Within a channel, surviving event weights are scaled as:

```math
\tilde w_{ci}=w^{beam}_{ci}\frac{s_c}{\sum_{j\in S_c}w^{beam}_{cj}}.
```

At that point `s_c` already includes cross-section and acceptance; the final
within-channel normalization sets the desired share without erasing them.

## Signal Prior

For default signal `eta_pi0`, the cross-section is the analysis result being
measured. Using a presumed value to weight training would be circular. The
signal instead receives explicit training choice `pi = --signal-prior`, default
`0.5`:

```math
s_{signal}=\pi.
```

`eta_pi0_via_3pi0` is the same production reaction with a different eta decay.
Its unknown production cross-section cancels against the signal and its share
is slaved through the PDG branching ratio and relative acceptance:

```math
s_{slaved}=\pi\,r_{BR}\,
\frac{Y^{unit}_{slaved}}{Y^{unit}_{signal}},
\qquad r_{BR}=\frac{BR(\eta\rightarrow3\pi^0)}{BR(\eta\rightarrow2\gamma)}.
```

The ordinary-background budget is then
`B = 1 - pi - sum(s_slaved)`. A non-positive budget is rejected. A channel
with neither `sigma_ref_ub` nor `signal_br_ratio` cannot be an ordinary
background and is rejected with guidance to change the channel selection.

### XGBoost scale and effective sample size

After concatenation, all event weights are divided by their global mean. This
keeps every ratio unchanged while making mean event weight one. The absolute
scale matters because XGBoost interprets `min_child_weight` in summed-Hessian
units; weights summing to one across millions of rows can silently prevent all
tree splits.

The builder reports Kish effective sample size:

```math
N_{eff}=\frac{(\sum_i w_i)^2}{\sum_i w_i^2}.
```

It warns when `N_eff` falls below 10% of the stored event count and reports the
number of zero-weight events. This is a diagnostic, not an automatic change to
the weighting model.

Implementation and evidence:

| Path | Contract |
|---|---|
| `04_bdt_training/photon_loss.py` | probability model and exact-survivor sampling |
| `04_bdt_training/beam_spectrum.py` | measured histogram and density-ratio weights |
| `04_bdt_training/dataset/channel_weights.py` | yield integrals and channel shares |
| `04_bdt_training/build_background_features.py` | per-event scaling, mean-one normalization, ESS |
| `04_bdt_training/tests/test_channel_weights.py` | generated-count denominator, acceptance, ordinary/slaved shares |

Related pages: [physics channels](physics-channels),
[dataset and features](04-dataset-and-features), and
[scientific foundations](scientific-foundations).
