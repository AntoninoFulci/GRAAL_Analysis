"""Channel yields and shares for the Stage-1 training mixture."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from graal_common.physics.channels import MCChannel
from graal_common.physics.cross_sections import sigma_at


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
    topology and must not be. Both live in the same survivor count, and normalising
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
