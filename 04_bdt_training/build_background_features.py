"""Build the stage-1 BDT training set from the Monte Carlo channels.

Stage-1 is a binary classifier: the signal channel against everything else.
Every event, of either class, is presented as EXACTLY 4 observed photons.

Which channel plays signal is a free choice (--signal-channel): the registry in
graal_common.physics.channels knows all nine, and any of them can be class 1. What the
features are built around is a separate choice (--hypothesis) — see that
module's docstring for why the two are not the same question.

Every channel goes through the same photon-loss model, signal included. This is
load-bearing. The signal used to skip it, on the reasoning that eta -> gamma
gamma and pi0 -> gamma gamma already give exactly 4 photons so there was
nothing to drop. But loss is not only about the count: it is the detector's
acceptance. Skipping it left 15% of signal training photons at theta < 25 deg,
inside the beam hole, where the BGO records nothing and where the real data has
literally zero — while every background photon had been filtered to the
acceptance. That makes the detector model a function of the class label, so the
classifier can separate on which loss model was applied rather than on physics,
and it learns a signal shape that no GRAAL event can have. Only 28% of the
signal MC survives the acceptance the backgrounds are held to; the other 72%
were events the experiment could never have recorded as 4 photons.

Three things about the weights are worth knowing before reading main().

The backgrounds are mixed by their cross-sections integrated over the beam flux
and the detector acceptance — not by the flat reference numbers in the registry.
A flat sigma_ref ignores that a channel does not exist below its threshold:
omega_pi0 opens at 1.366 GeV and etaprime at 1.447, in the last few percent of
GRAAL's range, and both were weighted at values measured far above it.

A channel's weight divides by its GENERATED count, not by its survivor total.
Generated count is bookkeeping and must be erased; the survival fraction is the
detector's acceptance for that topology and must not be. Both live in the same
survivor count, and normalising onto the survivor total erased them together —
which weighted the 8-photon channels as though they reconstructed as efficiently
as the 4-photon ones.

The signal's share is NOT a cross-section. Measuring sigma(gamma p -> p eta pi0)
is what this analysis is for, so a number here would be an answer used to weight
the events the answer is extracted from — circular, and quietly so, since the
training would just reproduce whatever prior it was handed. --signal-prior names
that split as what it is: a choice. eta_pi0_via_3pi0 is the same reaction with
the eta decaying to 3pi0; it is slaved to the signal through the PDG branching
ratios, which cancels the unknown sigma rather than assuming it.

And the beam. The generators draw a flat tagged-photon energy; GRAAL's beam is
Compton-backscattered laser light with an edge. --beam-spectrum reweights the MC
onto the beam the experiment really had — see bdt_training.beam_spectrum. It is
required: there is no flux integral without it.

Usage:
    python -m bdt_training.build_background_features \\
        --mc-dir 03_mc_simulation/data \\
        --signal-channel eta_pi0 \\
        --beam-spectrum 04_bdt_training/data/beam_spectrum.npz \\
        --output features_stage1.npz
"""

from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path

import numpy as np

try:
    import uproot
except ImportError as exc:
    raise ImportError("uproot required: pip install uproot") from exc

from graal_common.physics.channels import (
    CHANNEL_NAMES,
    HYPOTHESES,
    get_channel,
    resolve_hypothesis,
)
from graal_common.stage1.features import (
    FEATURE_NAMES_S1,
    N_FEATURES_S1,
    compute_stage1_features,
    feature_names,
)
from bdt_training.beam_spectrum import BeamSpectrum
from bdt_training.dataset.channel_weights import ChannelYield, channel_yield, compute_shares
from bdt_training.dataset.mc_samples import (
    ChannelSample,
    _extract_E_theta,
    _load_4vec,
    build_channel_features,
    load_photons,
    shuffle_photons,
)
from bdt_training.photon_loss import LossParams
from bdt_training.dataset.stage1_dataset import (
    Stage1Dataset,
    Stage1DatasetMetadata,
    save_stage1_dataset,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mc-dir", default="03_mc_simulation/data",
                        help="folder holding the <channel>_mc.root files")
    parser.add_argument("--signal-channel", default="eta_pi0", choices=CHANNEL_NAMES,
                        help="which channel is class 1 (default: eta_pi0)")
    parser.add_argument("--background-channels", nargs="+", default=None,
                        choices=CHANNEL_NAMES,
                        help="class 0 (default: every channel except the signal)")
    parser.add_argument("--hypothesis", default=None, choices=sorted(HYPOTHESES),
                        help="two mesons the features are built around; "
                             "defaults to the one the signal channel fixes, and "
                             "is required when it fixes none")
    parser.add_argument("--beam-spectrum", required=True,
                        help="npz from bdt_training.beam_spectrum. REQUIRED: the "
                             "channel weights are cross-sections integrated over "
                             "the measured beam flux, and there is no flux "
                             "without it")
    parser.add_argument("--signal-prior", type=float, default=0.5,
                        help="fraction of the total training weight given to the "
                             "signal class (default 0.5, balanced). A CHOICE, not "
                             "a measurement: the signal cross-section is what this "
                             "analysis is for, so it cannot also be an input to it")
    parser.add_argument("--output", default="features_stage1.npz")
    parser.add_argument("--loss-seed", type=int, default=42,
                        help="RNG seed for photon-loss sampling")
    args = parser.parse_args()

    if not 0.0 < args.signal_prior < 1.0:
        raise ValueError(
            f"--signal-prior must be strictly between 0 and 1, got {args.signal_prior}; "
            "at 0 or 1 one class carries no weight and there is nothing to learn"
        )

    mc_dir = Path(args.mc_dir)
    signal = get_channel(args.signal_channel)
    hypothesis = resolve_hypothesis(signal, args.hypothesis)

    if args.background_channels is None:
        background_names = [c for c in CHANNEL_NAMES if c != signal.name]
    else:
        background_names = list(args.background_channels)
    if signal.name in background_names:
        raise ValueError(
            f"channel {signal.name!r} is both the signal and a background; "
            "an event cannot be its own contamination"
        )
    backgrounds = [get_channel(name) for name in background_names]

    beam_target = BeamSpectrum.load(args.beam_spectrum)
    print(f"beam       : reweighting onto {args.beam_spectrum}")

    print(f"signal     : {signal.name}")
    print(f"backgrounds: {', '.join(c.name for c in backgrounds)}")
    print(f"hypothesis : {hypothesis.name}")
    print(f"signal prior: {args.signal_prior:.3f} of the total training weight")

    rng = np.random.default_rng(args.loss_seed)
    params = LossParams()

    channels = [signal] + backgrounds

    samples: dict[str, ChannelSample] = {}
    yields: list[ChannelYield] = []

    for channel in channels:
        path = mc_dir / channel.mc_filename
        if not path.exists():
            raise FileNotFoundError(f"missing MC file for {channel.name!r}: {path}")

        with uproot.open(path) as f:
            sample = build_channel_features(
                f["mc"], channel, hypothesis, rng, params, beam_target
            )
        samples[channel.name] = sample

        y = channel_yield(channel, sample.beam_E, sample.w_beam, sample.n_gen)
        if channel is signal:
            y = replace(y, is_signal=True)
        yields.append(y)

    shares = compute_shares(yields, args.signal_prior)

    all_X, all_y, all_w = [], [], []
    for channel in channels:
        sample = samples[channel.name]
        is_signal = channel is signal
        share = shares[channel.name]

        # Normalise per channel so the share is exactly what lands, whatever the
        # beam reweighting did to the totals. Safe here in a way it was not
        # before: `share` now already carries the flux, the cross-section and
        # the acceptance, so this only sets a scale rather than erasing physics.
        total = sample.w_beam.sum()
        if total <= 0:
            raise ValueError(
                f"channel {channel.name!r} has no weight left after reweighting: "
                "its beam energies do not overlap the measured spectrum at all"
            )
        w = sample.w_beam * (share / total)

        print(f"  {channel.name:16s} {'signal' if is_signal else 'bkg':6s} "
              f"{len(sample.X):8d} events  survival {sample.p_surv:.3f}  "
              f"share {share:.4f}")

        all_X.append(sample.X)
        all_y.append(np.full(len(sample.X), 1 if is_signal else 0, dtype=np.int8))
        all_w.append(w.astype(np.float32))

    X_out = np.concatenate(all_X, axis=0)
    y_out = np.concatenate(all_y, axis=0)
    w_out = np.concatenate(all_w, axis=0)

    # Put the weights on a mean of 1, keeping every ratio between them.
    #
    # Only the ratios carry physics, so the absolute scale ought to be
    # arbitrary. It is not: XGBoost measures min_child_weight in summed-hessian
    # units, which scale with sample_weight. At the shares above — each channel
    # summing to a fraction of 1, so ~5e-7 an event — no split can ever reach
    # min_child_weight >= 1, xgboost returns a stump, and every configuration in
    # the grid search comes back at AUC 0.5000. It fails silently, and it looks
    # like the features are worthless rather than the weights being small.
    w_out = w_out / w_out.mean()

    # Kish effective sample size: how many equally-weighted events this sample
    # is worth. Reweighting always costs some, but a handful of events carrying
    # most of the weight is a training set that looks like millions of events
    # and behaves like thousands — and nothing else in the chain would say so.
    ess = w_out.sum() ** 2 / (w_out**2).sum()
    print(f"\nEffective sample size: {ess:.0f} of {len(w_out)} "
          f"({100 * ess / len(w_out):.1f}%)")
    if ess < 0.1 * len(w_out):
        print("  WARNING: the reweighting has thrown away most of the statistical")
        print("  power of this sample. A few events carry most of the weight, and")
        print("  the model will be decided by them. Check the beam spectrum.")
    zero = int((w_out == 0).sum())
    print(f"Dropped by reweighting: {zero} events "
          f"({100 * zero / len(w_out):.2f}%) at beam energies the data never had, "
          f"or where the MC is too thin to give a density")

    # signal_channel and hypothesis travel with the features so the trainer can
    # stamp them on the model, and the gate can refuse a mismatch instead of
    # scoring a model on features built around different mesons. signal_prior
    # and beam_reweighted travel too because they are assumptions, not settings:
    # a model is only as meaningful as the prior it was handed and the beam it
    # was shown, and neither is recoverable from the booster afterwards.
    save_stage1_dataset(
        args.output,
        Stage1Dataset(
            X=X_out,
            y=y_out,
            w=w_out,
            metadata=Stage1DatasetMetadata(
                feature_names=tuple(feature_names(hypothesis)),
                signal_channel=signal.name,
                hypothesis=hypothesis.name,
                signal_prior=args.signal_prior,
                beam_reweighted=beam_target is not None,
            ),
        ),
    )
    n_sig = (y_out == 1).sum()
    n_bkg = (y_out == 0).sum()
    print(f"Saved {len(X_out)} events ({n_sig} signal, {n_bkg} background) → {args.output}")


if __name__ == "__main__":
    main()
