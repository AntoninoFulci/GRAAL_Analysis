"""Photon-loss model for background MC events.

Models detector inefficiency as independent loss probability per photon:
  P_loss(E, theta) = 1 - (1 - P_threshold(E)) * (1 - P_acceptance(theta))

where P_threshold uses a sigmoid in energy and P_acceptance uses a sigmoid
in polar angle.  After loss, events are kept only if exactly 4 photons remain
(matching signal topology).
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass

import numpy as np


@dataclass
class LossParams:
    """Parameters for the photon-loss model."""
    E_thr: float = 0.050       # energy threshold centre [GeV]
    sigma_E: float = 0.020     # energy sigmoid width [GeV]
    theta_acc: float = 0.436   # acceptance edge [rad] (~25 deg)
    sigma_theta: float = 0.087 # angular sigmoid width [rad] (~5 deg)


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
    p_acc = 1.0 / (1.0 + np.exp(-(theta - params.theta_acc) / params.sigma_theta))
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
    parser.add_argument("--theta-acc", type=float, default=0.436)
    parser.add_argument("--sigma-theta", type=float, default=0.087)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    params = LossParams(
        E_thr=args.E_thr,
        sigma_E=args.sigma_E,
        theta_acc=args.theta_acc,
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
