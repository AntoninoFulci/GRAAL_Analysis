"""Monte Carlo decoding and per-channel Stage-1 feature sampling."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from graal_common.physics.channels import Hypothesis, MCChannel
from graal_common.stage1.features import compute_stage1_features
from bdt_training.beam_spectrum import BeamSpectrum
from bdt_training.beam_spectrum import reweight as beam_reweight
from bdt_training.photon_loss import LossParams, sample_surviving_photons


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

    X: np.ndarray        # (N_surv, 26) features
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
