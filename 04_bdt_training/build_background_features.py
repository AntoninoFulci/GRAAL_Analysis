"""Build the stage-1 BDT training set from the Monte Carlo channels.

Stage-1 is a binary classifier: the signal channel against everything else.
Every event, of either class, is presented as EXACTLY 4 observed photons.

Which channel plays signal is a free choice (--signal-channel): the registry in
graal_common.channels knows all nine, and any of them can be class 1. What the
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
from dataclasses import dataclass, replace
from pathlib import Path

import numpy as np

try:
    import uproot
except ImportError as exc:
    raise ImportError("uproot required: pip install uproot") from exc

from graal_common.channels import (
    CHANNEL_NAMES,
    ETA_PI0_HYP,
    HYPOTHESES,
    M_PROTON,
    Hypothesis,
    MCChannel,
    get_channel,
    resolve_hypothesis,
)
from graal_common.cross_sections import sigma_at
from graal_common.pairing import PAIR_IDX, chi2_per_pairing, pair_masses
from bdt_training.beam_spectrum import BeamSpectrum
from bdt_training.beam_spectrum import reweight as beam_reweight
from bdt_training.photon_loss import LossParams, sample_surviving_photons

# ---------------------------------------------------------------------------
# 24 features — computed on exactly 4 photons, after the loss model
# ---------------------------------------------------------------------------
# 6 invariant masses of the C(4,2) photon pairs
# + pair counts near the two mass poles of the hypothesis
# + best chi2 for the hypothesis
# + missing kinematics
# + photon energy statistics
# + proton kinematics
# ---------------------------------------------------------------------------
N_FEATURES_S1 = 24


def feature_names(hypothesis: Hypothesis = ETA_PI0_HYP) -> list[str]:
    """The 24 feature names, in the order compute_stage1_features emits them.

    Two of them are named after the hypothesis, so a model trained against one
    hypothesis carries the fact in its own feature list rather than leaving it
    to be remembered.
    """
    names = [
        # C(4,2)=6 invariant masses
        "m_gg_01", "m_gg_02", "m_gg_03",
        "m_gg_12", "m_gg_13",
        "m_gg_23",
        # pair counts near the two mass poles
        f"n_pairs_near_{hypothesis.light_label}",
        f"n_pairs_near_{hypothesis.heavy_label}",
        # best chi2 for any assignment of the 4 photons to the two mesons
        f"best_chi2_{hypothesis.name}",
        # missing kinematics  (beam + target − proton)
        "missing_mass",
        "missing_E",
        "missing_pz",
        "missing_pt",
        # photon energy statistics
        "total_gamma_E",
        "beam_E",
        "max_gamma_E",
        "min_gamma_E",
        "gamma_E_rms",          # rms spread of photon energies
        # photon angular statistics
        "sum_opening_angles",   # sum of all 6 opening angles
        "min_pair_mass",
        "max_pair_mass",
        "total_pt_gamma",       # scalar sum of photon pT
        # proton
        "proton_p",
        "proton_costheta",
    ]
    assert len(names) == N_FEATURES_S1, f"Expected {N_FEATURES_S1}, got {len(names)}"
    return names


# The eta_pi0 default, which is what the pipeline trains.
FEATURE_NAMES_S1: list[str] = feature_names(ETA_PI0_HYP)

_TARGET = np.array([0.0, 0.0, 0.0, M_PROTON])


def _load_4vec(tree, name: str) -> np.ndarray:
    """Load TLorentzVector branch as (N,4) array [px,py,pz,E]."""
    arr = tree[name].array(library="ak")
    px = np.asarray(arr["fP"]["fX"])
    py = np.asarray(arr["fP"]["fY"])
    pz = np.asarray(arr["fP"]["fZ"])
    E  = np.asarray(arr["fE"])
    return np.stack([px, py, pz, E], axis=1)


def load_photons(tree, channel: MCChannel) -> np.ndarray:
    """Load a channel's true photons → (N, n_true, 4) [px,py,pz,E].

    Handles both conventions the generators use, because which one a file
    follows is a property of the file, not of the role it is playing: the
    eta pi0 generator writes named branches, and it has to load the same way
    whether it is the signal or one of the backgrounds.
    """
    if channel.photon_branches is not None:
        branches = list(channel.photon_branches)
    else:
        n_true_arr = tree["n_true_gamma"].array(library="np")
        n_true = int(n_true_arr[0]) if len(n_true_arr) > 0 else 4
        branches = [f"g{i}" for i in range(n_true)]

    return np.stack([_load_4vec(tree, b) for b in branches], axis=1)


def _extract_E_theta(photons: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Extract energy and polar angle arrays from (N, M, 4) photon array."""
    px, py, pz = photons[:, :, 0], photons[:, :, 1], photons[:, :, 2]
    E           = photons[:, :, 3]
    pt          = np.sqrt(px**2 + py**2)
    theta       = np.arctan2(pt, pz)
    return E, theta


def compute_stage1_features(
    photons: np.ndarray,   # (N, 4, 4) — exactly 4 photons, [px,py,pz,E]
    proton: np.ndarray,    # (N, 4)
    beam: np.ndarray,      # (N, 4)
    hypothesis: Hypothesis = ETA_PI0_HYP,
) -> np.ndarray:
    """Compute the 24 stage-1 features — vectorised, no Python loops over events.

    Args:
        photons: shape (N, 4, 4), columns [px, py, pz, E]
        proton:  shape (N, 4)
        beam:    shape (N, 4)
        hypothesis: the two mesons the pole counts and the chi2 are built
            around. Must be the one the model was trained against — Stage1Gate
            enforces that.

    Returns:
        Feature matrix of shape (N, 24), dtype float32
    """
    N = photons.shape[0]
    out = np.zeros((N, N_FEATURES_S1), dtype=np.float32)

    m_heavy, m_light = hypothesis.heavy_mass, hypothesis.light_mass

    # -- invariant masses of all 6 pairs (vectorised) -----------------------
    pair_m = pair_masses(photons)                     # (N,6)

    out[:, 0:6] = pair_m

    # -- pair counts near the two mass poles ---------------------------------
    # For a degenerate hypothesis (2pi0) these two are the same number by
    # construction. Left in rather than special-cased: the feature vector keeps
    # a fixed width and a fixed meaning per column, and a duplicated column
    # costs a tree split, not a wrong answer.
    out[:, 6] = (np.abs(pair_m - m_light) < hypothesis.light_window).sum(axis=1)
    out[:, 7] = (np.abs(pair_m - m_heavy) < hypothesis.heavy_window).sum(axis=1)

    # -- best chi2 for the hypothesis --------------------------------------
    # The same chi2, over the same pairings, that the reconstruction minimises
    # to choose one. It used to be re-derived here, which made the number the
    # BDT is handed and the number the reconstruction acts on two independent
    # expressions that happened to agree.
    out[:, 8] = chi2_per_pairing(pair_m, hypothesis).min(axis=-1)

    # -- missing kinematics --------------------------------------------------
    target = _TARGET[None, :]                        # (1, 4)
    tot    = beam + target                            # (N, 4)
    miss   = tot - proton                             # (N, 4)
    miss_m2 = miss[:, 3]**2 - (miss[:, 0]**2 + miss[:, 1]**2 + miss[:, 2]**2)
    out[:, 9]  = np.sqrt(np.clip(miss_m2, 0, None))  # missing mass
    out[:, 10] = miss[:, 3]                            # missing E
    out[:, 11] = miss[:, 2]                            # missing pz
    out[:, 12] = np.sqrt(miss[:, 0]**2 + miss[:, 1]**2)  # missing pT

    # -- photon energy statistics --------------------------------------------
    gamma_E = photons[:, :, 3]                        # (N, 4)
    out[:, 13] = gamma_E.sum(axis=1)                  # total gamma E
    out[:, 14] = beam[:, 3]                            # beam E
    out[:, 15] = gamma_E.max(axis=1)
    out[:, 16] = gamma_E.min(axis=1)
    E_mean = gamma_E.mean(axis=1, keepdims=True)
    out[:, 17] = np.sqrt(((gamma_E - E_mean)**2).mean(axis=1))  # rms

    # -- photon angular statistics -------------------------------------------
    def _cos_pair(i: int, j: int) -> np.ndarray:
        p1  = photons[:, i, :3]
        p2  = photons[:, j, :3]
        n1  = np.linalg.norm(p1, axis=1, keepdims=True)
        n2  = np.linalg.norm(p2, axis=1, keepdims=True)
        cos = (p1 * p2).sum(axis=1) / np.clip(n1[:, 0] * n2[:, 0], 1e-9, None)
        return np.clip(cos, -1, 1)

    opening = np.stack([np.arccos(_cos_pair(i, j)) for i, j in PAIR_IDX], axis=1)
    out[:, 18] = opening.sum(axis=1)                   # sum of opening angles
    out[:, 19] = pair_m.min(axis=1)
    out[:, 20] = pair_m.max(axis=1)

    # -- total transverse momentum of photons --------------------------------
    pt_g = np.sqrt(photons[:, :, 0]**2 + photons[:, :, 1]**2)  # (N,4)
    out[:, 21] = pt_g.sum(axis=1)

    # -- proton kinematics ---------------------------------------------------
    p_mom = np.sqrt((proton[:, :3]**2).sum(axis=1))
    out[:, 22] = p_mom
    out[:, 23] = np.where(p_mom > 0, proton[:, 2] / p_mom, 0.0)

    return out


def shuffle_photons(photons: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Randomise the photon order within each event.

    In real data the detected photons carry no parent label, and the pair-mass
    slots must mean nothing on their own. Without this, m_gg_01 would trivially
    equal the eta mass for every signal event, because the generator writes the
    eta's photons first — the BDT would learn the writing order.

    Applied to every channel for the same reason: any ordering convention a
    generator happens to have is an artefact, and the model must not see one.
    """
    idx = np.argsort(rng.random((len(photons), 4)), axis=1)
    return photons[np.arange(len(photons))[:, None], idx]


@dataclass(frozen=True)
class ChannelSample:
    """One channel's surviving events, and what it took to get them."""

    X: np.ndarray        # (N_surv, 24) features
    w_beam: np.ndarray   # (N_surv,) p_data(E)/p_mc(E)
    beam_E: np.ndarray   # (N_surv,) tagged photon energy [GeV]
    p_surv: float        # fraction of generated events that survived
    n_gen: int           # generated count, before the acceptance


def build_channel_features(
    tree,
    channel: MCChannel,
    hypothesis: Hypothesis,
    rng: np.random.Generator,
    params: LossParams,
    beam_target: BeamSpectrum,
) -> ChannelSample:
    """Features for one channel: load, apply the acceptance, shuffle, compute.

    Identical for signal and background — that is the point.
    """
    photons_all = load_photons(tree, channel)
    proton_all  = _load_4vec(tree, "proton")
    beam_all    = _load_4vec(tree, "beam")
    n_gen = len(beam_all)

    ph_E, ph_theta = _extract_E_theta(photons_all)
    photons_4, event_mask = sample_surviving_photons(
        photons_all, ph_E, ph_theta, rng, params, n_keep=4
    )
    proton_sel = proton_all[event_mask]
    beam_sel   = beam_all[event_mask]

    photons_4 = shuffle_photons(photons_4, rng)

    X = compute_stage1_features(photons_4, proton_sel, beam_sel, hypothesis)
    beam_E = beam_sel[:, 3]

    return ChannelSample(
        X=X,
        w_beam=beam_reweight(beam_E, beam_target),
        beam_E=beam_E,
        p_surv=float(event_mask.mean()),
        n_gen=n_gen,
    )


@dataclass(frozen=True)
class ChannelYield:
    """What one channel is worth in the mixture, before shares are struck.

    y_sigma:
        int p_data(E) sigma(E) A(E) dE, up to a constant common to every
        channel. Flux, cross-section and acceptance, all three. None for a
        channel with no cross-section of its own.

    y_unit:
        The same integral with sigma set to 1: flux and acceptance alone. This
        is what lets the slaved channel be weighted against the signal without
        anyone naming sigma(gamma p -> p eta pi0).
    """

    channel: MCChannel
    y_sigma: float | None
    y_unit: float
    is_signal: bool


def channel_yield(
    channel: MCChannel,
    beam_E: np.ndarray,
    w_beam: np.ndarray,
    n_gen: int,
) -> ChannelYield:
    """Integrate one channel's flux, cross-section and acceptance.

    beam_E and w_beam cover the SURVIVING events only; n_gen is how many were
    generated. Dividing by n_gen rather than by the survivor total is the whole
    point: the generated count is an arbitrary bookkeeping choice and must be
    erased, while the survival fraction is the detector's acceptance for this
    topology and must not be. Both live in the survivor count, and normalising
    onto the survivor total erases them together — which weighted an 8-photon
    channel as though it reconstructed as efficiently as a 4-photon one.

    Events that beam_spectrum.reweight zeroed carry w_beam = 0 and contribute
    nothing, which is correct: the data never produced them, or the MC there is
    too thin to give a density.

    Returns is_signal=False; the caller says which channel is the signal, since
    that is a choice (--signal-channel) and not a property of the file.
    """
    if n_gen <= 0:
        raise ValueError(
            f"channel {channel.name!r}: n_gen must be positive, got {n_gen}"
        )

    y_unit = float(w_beam.sum()) / n_gen

    if channel.sigma_ref_ub is None:
        y_sigma = None
    else:
        y_sigma = float((sigma_at(channel, beam_E) * w_beam).sum()) / n_gen

    return ChannelYield(
        channel=channel, y_sigma=y_sigma, y_unit=y_unit, is_signal=False
    )


def compute_shares(
    yields: list[ChannelYield], signal_prior: float
) -> dict[str, float]:
    """How much of the total training weight each channel is meant to carry.

    Three kinds of channel, weighted three ways:

      The signal takes `signal_prior` flat. Not a cross-section: measuring
      sigma(gamma p -> p eta pi0) is what this analysis is for, so a number here
      would be an answer used to weight the events the answer comes from.

      A slaved background — the signal reaction with a different decay — takes
      signal_prior x BR_ratio x (its acceptance / the signal's). sigma(signal)
      is unknown but identical top and bottom, so it cancels and never has to be
      named. The acceptance ratio is not a refinement: on the BR alone the
      channel would take 0.415 of the weight at prior 0.5 and crush every real
      background into what was left.

      Ordinary backgrounds split what remains in proportion to their yields.
      That ratio is real physics — how much of the contamination is pi0pi0
      rather than etaprime — and the BDT should know it.
    """
    if not 0.0 < signal_prior < 1.0:
        raise ValueError(
            f"signal_prior must be strictly between 0 and 1, got {signal_prior}"
        )

    signals = [y for y in yields if y.is_signal]
    if len(signals) != 1:
        raise ValueError(
            f"expected exactly one signal channel, got "
            f"{[y.channel.name for y in signals]}"
        )
    signal = signals[0]
    if signal.y_unit <= 0.0:
        raise ValueError(
            f"no weight left for signal channel {signal.channel.name!r} after "
            f"reweighting: its beam energies do not overlap the measured "
            f"spectrum at all"
        )

    shares: dict[str, float] = {signal.channel.name: signal_prior}

    slaved_total = 0.0
    for y in yields:
        if y.is_signal or y.channel.signal_br_ratio is None:
            continue
        share = signal_prior * y.channel.signal_br_ratio * (y.y_unit / signal.y_unit)
        shares[y.channel.name] = share
        slaved_total += share

    plain = [
        y for y in yields if not y.is_signal and y.channel.signal_br_ratio is None
    ]

    # An ordinary background is weighted by its cross-section, so it must have
    # one. A channel with neither a sigma_ref_ub nor a signal_br_ratio has no
    # weight basis at all, and its y_sigma is None. This is not hypothetical:
    # eta_pi0 carries no cross-section by design (measuring it is the point of
    # the analysis), so the moment anything OTHER than eta_pi0 is the signal,
    # eta_pi0 lands here. Catch it with a message that says what to do, rather
    # than letting the sum below fail with a bare TypeError on None.
    weightless = [y.channel.name for y in plain if y.y_sigma is None]
    if weightless:
        raise ValueError(
            f"background channel(s) {weightless} have no cross-section to be "
            f"weighted by (neither sigma_ref_ub nor signal_br_ratio). This "
            f"happens when a channel whose cross-section is unknown — eta_pi0, "
            f"whose measurement is the point of the analysis — is left in the "
            f"background set while a different channel is the signal. Drop it "
            f"with --background-channels, or make it the signal."
        )

    budget = 1.0 - signal_prior - slaved_total
    if budget <= 0.0:
        raise ValueError(
            f"no weight left for the ordinary backgrounds: signal_prior "
            f"{signal_prior} plus the slaved channels' {slaved_total:.3f} "
            f"already accounts for all of it"
        )

    total_y = sum(y.y_sigma for y in plain)
    if total_y <= 0.0:
        raise ValueError(
            "no weight left across the ordinary backgrounds: their yields sum "
            "to zero, so none of them overlaps the measured beam spectrum"
        )

    for y in plain:
        shares[y.channel.name] = budget * (y.y_sigma / total_y)

    return shares


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
    np.savez(
        args.output,
        X=X_out, y=y_out, w=w_out,
        feature_names=np.array(feature_names(hypothesis)),
        signal_channel=np.array(signal.name),
        hypothesis=np.array(hypothesis.name),
        signal_prior=np.array(args.signal_prior),
        beam_reweighted=np.array(beam_target is not None),
    )
    n_sig = (y_out == 1).sum()
    n_bkg = (y_out == 0).sum()
    print(f"Saved {len(X_out)} events ({n_sig} signal, {n_bkg} background) → {args.output}")


if __name__ == "__main__":
    main()
