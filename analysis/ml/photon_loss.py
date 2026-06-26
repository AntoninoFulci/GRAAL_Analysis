"""Photon-loss model for background MC events.

Models detector inefficiency as independent loss probability per photon:
  P_loss(E, theta) = 1 - (1-P_thr(E)) * (1-P_fwd(theta)) * (1-P_bwd(theta))

P_thr:  sigmoid in energy — photons below E_thr are lost (soft threshold).
P_fwd:  forward sigmoid — photons at theta < theta_min_acc lost (beam hole).
P_bwd:  backward sigmoid — photons at theta > theta_max_acc lost (back hole).

GRAAL BGO crystal ball acceptance: ~25° (0.436 rad) to ~155° (2.705 rad).
Photons inside this window survive; those outside are dropped.
After loss, events are kept only if exactly 4 photons remain.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np


@dataclass
class LossParams:
    """Parameters for the photon-loss model."""
    E_thr: float = 0.050           # energy threshold centre [GeV]
    sigma_E: float = 0.020         # energy sigmoid width [GeV]
    theta_min_acc: float = 0.436   # forward acceptance edge [rad] (~25 deg)
    theta_max_acc: float = 2.705   # backward acceptance edge [rad] (~155 deg)
    sigma_theta: float = 0.050     # angular sigmoid width [rad] (~3 deg)


def p_loss(E: np.ndarray, theta: np.ndarray, params: LossParams) -> np.ndarray:
    """Per-photon loss probability (vectorised).

    Args:
        E: photon energies, shape (...,)
        theta: photon polar angles [rad], shape (...,)
        params: LossParams instance

    Returns:
        loss probability, same shape as E
    """
    p_thr = 1.0 / (1.0 + np.exp((E - params.E_thr) / params.sigma_E))
    # Forward hole (beam): high loss for theta < theta_min_acc
    p_fwd = 1.0 / (1.0 + np.exp((theta - params.theta_min_acc) / params.sigma_theta))
    # Backward hole: high loss for theta > theta_max_acc
    p_bwd = 1.0 / (1.0 + np.exp(-(theta - params.theta_max_acc) / params.sigma_theta))
    p_acc = 1.0 - (1.0 - p_fwd) * (1.0 - p_bwd)
    return 1.0 - (1.0 - p_thr) * (1.0 - p_acc)


def apply_loss_events(
    photon_Es: np.ndarray,
    photon_thetas: np.ndarray,
    rng: np.random.Generator,
    params: LossParams | None = None,
    n_keep: int = 4,
) -> np.ndarray:
    """Apply stochastic photon loss and return boolean mask of kept events.

    An event is kept if exactly `n_keep` photons survive after independent
    Bernoulli drops.

    Args:
        photon_Es:     shape (N_events, N_photons), energies [GeV]
        photon_thetas: shape (N_events, N_photons), polar angles [rad]
        rng:           numpy Generator for reproducibility
        params:        LossParams (defaults used if None)
        n_keep:        required surviving photon count (default 4)

    Returns:
        Boolean array of shape (N_events,); True = event survives.
    """
    if params is None:
        params = LossParams()

    p = p_loss(photon_Es, photon_thetas, params)          # (N, M)
    survive = rng.random(p.shape) >= p                     # True = photon kept
    n_surviving = survive.sum(axis=1)                      # (N,)
    return n_surviving == n_keep


def sample_surviving_photons(
    photons: np.ndarray,
    photon_Es: np.ndarray,
    photon_thetas: np.ndarray,
    rng: np.random.Generator,
    params: LossParams | None = None,
    n_keep: int = 4,
) -> tuple[np.ndarray, np.ndarray]:
    """Apply photon loss and return the surviving n_keep photons.

    For events where exactly n_keep photons survive, the surviving photon
    4-vectors are returned in a dense array.  Events with != n_keep survivors
    are dropped.

    Args:
        photons:       shape (N, M, 4), columns [px, py, pz, E]
        photon_Es:     shape (N, M)
        photon_thetas: shape (N, M)
        rng:           numpy Generator
        params:        LossParams (defaults if None)
        n_keep:        required survivors (default 4)

    Returns:
        kept_photons:  (N_good, n_keep, 4)
        event_mask:    (N,) bool — True for events that survived
    """
    if params is None:
        params = LossParams()

    p = p_loss(photon_Es, photon_thetas, params)   # (N, M)
    survive = rng.random(p.shape) >= p             # (N, M) bool
    n_surviving = survive.sum(axis=1)              # (N,)
    event_mask = n_surviving == n_keep             # (N,) bool

    good_survive = survive[event_mask]             # (N_good, M)
    good_photons = photons[event_mask]             # (N_good, M, 4)

    # Sort so surviving photons (True=1) come first, then slice first n_keep
    order = np.argsort(~good_survive, axis=1)      # descending by survive flag
    sorted_photons = good_photons[
        np.arange(len(good_photons))[:, None], order
    ]                                              # (N_good, M, 4)
    kept_photons = sorted_photons[:, :n_keep, :]  # (N_good, n_keep, 4)

    return kept_photons, event_mask


def estimate_survival(
    photon_Es: np.ndarray,
    photon_thetas: np.ndarray,
    params: LossParams | None = None,
    n_keep: int = 4,
    n_trials: int = 10,
    seed: int = 42,
) -> float:
    """Monte-Carlo estimate of P(survive) for a set of events.

    Runs `n_trials` independent loss simulations and returns the mean
    fraction of events surviving.
    """
    if params is None:
        params = LossParams()

    rng = np.random.default_rng(seed)
    fractions = []
    for _ in range(n_trials):
        mask = apply_loss_events(photon_Es, photon_thetas, rng, params, n_keep)
        fractions.append(mask.mean())
    return float(np.mean(fractions))


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Estimate photon-survival fraction")
    parser.add_argument("--n-photons", type=int, default=6,
                        help="True photons per event (default 6)")
    parser.add_argument("--n-events", type=int, default=100_000)
    parser.add_argument("--n-keep", type=int, default=4,
                        help="Required surviving photons (default 4)")
    parser.add_argument("--E-thr", type=float, default=0.050)
    parser.add_argument("--sigma-E", type=float, default=0.020)
    parser.add_argument("--theta-min-acc", type=float, default=0.436)
    parser.add_argument("--theta-max-acc", type=float, default=2.705)
    parser.add_argument("--sigma-theta", type=float, default=0.050)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    params = LossParams(
        E_thr=args.E_thr,
        sigma_E=args.sigma_E,
        theta_min_acc=args.theta_min_acc,
        theta_max_acc=args.theta_max_acc,
        sigma_theta=args.sigma_theta,
    )
    rng = np.random.default_rng(args.seed)
    # Uniform toy photons: E in [0.05, 0.8] GeV, theta in [0.1, 2.8] rad
    Es = rng.uniform(0.05, 0.8, (args.n_events, args.n_photons))
    thetas = rng.uniform(0.1, 2.8, (args.n_events, args.n_photons))

    p = estimate_survival(Es, thetas, params, n_keep=args.n_keep)
    print(f"p_survival = {p:.4f}")


if __name__ == "__main__":
    _cli()
