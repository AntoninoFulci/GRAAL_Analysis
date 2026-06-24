"""Build stage-1 BDT features from background and signal MC ROOT files.

Stage-1 BDT is a binary classifier (signal=1 vs background=0) operating on
24 global event features that do NOT assume any particular photon pairing.

Usage:
    python -m analysis.ml.build_background_features \\
        --signal signal_mc.root \\
        --backgrounds pi0pi0_mc.root 3pi0_mc.root eta_2pi0_mc.root \\
                       omega_pi0_mc.root etaprime_mc.root \\
        --cs-csv simulation/cross_sections.csv \\
        --output features_stage1.npz
"""

from __future__ import annotations

import argparse
from itertools import combinations as itertools_combinations
from pathlib import Path

import numpy as np

try:
    import uproot
except ImportError as exc:
    raise ImportError("uproot required: pip install uproot") from exc

FEATURE_NAMES_S1: list[str] = [
    # invariant masses of all C(N,2) photon pairs (up to 10 for 5 photons, padded)
    "m_gg_01", "m_gg_02", "m_gg_03", "m_gg_04", "m_gg_05",
    "m_gg_12", "m_gg_13", "m_gg_14", "m_gg_15",
    "m_gg_23", "m_gg_24", "m_gg_25",
    "m_gg_34", "m_gg_35",
    "m_gg_45",
    # pair counts near meson masses
    "n_pairs_near_pi0",     # |m_gg - 0.135| < 0.040 GeV
    "n_pairs_near_eta",     # |m_gg - 0.548| < 0.080 GeV
    # best chi2 assuming eta+pi0 pairing
    "best_chi2_eta_pi0",
    # kinematics
    "missing_mass",         # |beam+target - proton| mass
    "missing_E",            # missing energy
    "total_gamma_E",        # sum of photon energies
    "n_gamma_obs",          # number of observed photons (after loss)
    # proton
    "proton_p",             # proton momentum magnitude
    "proton_costheta",      # cos(theta_proton)
]

assert len(FEATURE_NAMES_S1) == 24, f"Expected 24 features, got {len(FEATURE_NAMES_S1)}"

_MPROT = 0.938272
_MPI0  = 0.134977
_META  = 0.547862


def _inv_mass(p4s: list[np.ndarray]) -> float:
    """Invariant mass from sum of (px,py,pz,E) arrays."""
    tot = np.sum(p4s, axis=0)
    m2 = tot[3]**2 - tot[0]**2 - tot[1]**2 - tot[2]**2
    return float(np.sqrt(max(m2, 0.0)))


def _load_4vec(tree, name: str) -> np.ndarray:
    """Load TLorentzVector branch as (N,4) array [px,py,pz,E]."""
    px = tree[f"{name}/fP/fP.fX"].array(library="np")
    py = tree[f"{name}/fP/fP.fY"].array(library="np")
    pz = tree[f"{name}/fP/fP.fZ"].array(library="np")
    E  = tree[f"{name}/fE"].array(library="np")
    return np.stack([px, py, pz, E], axis=1)


def load_bg_photons(tree, n_gamma: int) -> np.ndarray:
    """Load g0..g{n_gamma-1} branches → (N, n_gamma, 4)."""
    arrays = [_load_4vec(tree, f"g{i}") for i in range(n_gamma)]
    return np.stack(arrays, axis=1)


def load_signal_photons(tree) -> np.ndarray:
    """Load signal photons from named branches → (N, 4, 4)."""
    branches = ["eta_gamma1", "eta_gamma2", "pi0_gamma1", "pi0_gamma2"]
    arrays = [_load_4vec(tree, b) for b in branches]
    return np.stack(arrays, axis=1)


def _pairs_indices(n: int) -> list[tuple[int, int]]:
    return list(itertools_combinations(range(n), 2))


def _best_chi2_eta_pi0(gammas: np.ndarray) -> float:
    """Min chi2 over all ways to assign 4 photons into two pairs targeting eta and pi0."""
    N = gammas.shape[0]
    if N < 4:
        return 999.0
    best = 999.0
    indices = list(range(N))
    for i, j in itertools_combinations(indices, 2):
        pair1 = gammas[[i, j]]
        remaining = [k for k in indices if k not in (i, j)]
        for k, l in itertools_combinations(remaining[:4], 2):
            pair2 = gammas[[k, l]]
            m12 = _inv_mass([pair1[0], pair1[1]])
            m34 = _inv_mass([pair2[0], pair2[1]])
            for m_eta, m_pi0 in [(_META, _MPI0), (_MPI0, _META)]:
                c = ((m12 - m_eta) / (0.08 * m_eta))**2 + ((m34 - m_pi0) / (0.08 * m_pi0))**2
                if c < best:
                    best = c
    return best


def compute_stage1_features(
    photons: np.ndarray,   # (N, M, 4) — M photons per event
    proton: np.ndarray,    # (N, 4)
    beam: np.ndarray,      # (N, 4)
) -> np.ndarray:
    """Compute 24 stage-1 features for N events.

    Args:
        photons: shape (N, M, 4) with columns [px, py, pz, E]
        proton:  shape (N, 4)
        beam:    shape (N, 4)

    Returns:
        Feature matrix of shape (N, 24)
    """
    N, M, _ = photons.shape
    out = np.zeros((N, 24), dtype=np.float32)
    target = np.array([0.0, 0.0, 0.0, _MPROT])

    for ev in range(N):
        gs = photons[ev]          # (M, 4)
        pr = proton[ev]           # (4,)
        bm = beam[ev]             # (4,)

        # --- invariant masses of all pairs, padded to 15 slots ---
        all_pair_masses = []
        for (i, j) in itertools_combinations(range(min(M, 6)), 2):
            all_pair_masses.append(_inv_mass([gs[i], gs[j]]))
        # fill up to 15 with 0
        pair_vec = np.zeros(15, dtype=np.float32)
        for k, m in enumerate(all_pair_masses[:15]):
            pair_vec[k] = m
        out[ev, :15] = pair_vec

        # --- pair counts ---
        n_pi0 = sum(1 for m in all_pair_masses if abs(m - _MPI0) < 0.040)
        n_eta = sum(1 for m in all_pair_masses if abs(m - _META) < 0.080)
        out[ev, 15] = n_pi0
        out[ev, 16] = n_eta

        # --- best chi2 ---
        out[ev, 17] = _best_chi2_eta_pi0(gs[:4])

        # --- kinematics ---
        tot = bm + target
        miss = tot - pr
        miss_m2 = miss[3]**2 - miss[0]**2 - miss[1]**2 - miss[2]**2
        out[ev, 18] = np.sqrt(max(miss_m2, 0.0))
        out[ev, 19] = miss[3]
        out[ev, 20] = float(gs[:, 3].sum())
        out[ev, 21] = float(M)

        # --- proton ---
        p_mom = np.sqrt(pr[0]**2 + pr[1]**2 + pr[2]**2)
        out[ev, 22] = p_mom
        p_costh = pr[2] / p_mom if p_mom > 0 else 0.0
        out[ev, 23] = p_costh

    return out


def _channel_from_n_true(n_true: int) -> str:
    return {4: "pi0pi0", 5: "omega_pi0", 6: "6gamma"}.get(n_true, "unknown")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signal", required=True)
    parser.add_argument("--backgrounds", nargs="+", required=True)
    parser.add_argument("--cs-csv", required=True,
                        help="cross_sections.csv for sample_weight")
    parser.add_argument("--output", default="features_stage1.npz")
    args = parser.parse_args()

    import csv
    cs_map: dict[str, float] = {}
    with open(args.cs_csv) as f:
        for row in csv.DictReader(filter(lambda ln: not ln.startswith("#"), f)):
            cs_map[row["channel"]] = float(row["sigma_eff"])

    all_X, all_y, all_w = [], [], []

    # --- signal ---
    with uproot.open(args.signal) as f:
        tree = f["mc"]
        photons = load_signal_photons(tree)
        proton  = _load_4vec(tree, "proton")
        beam    = _load_4vec(tree, "beam")
        X = compute_stage1_features(photons, proton, beam)
        all_X.append(X)
        all_y.append(np.ones(len(X), dtype=np.int8))
        all_w.append(np.ones(len(X), dtype=np.float32))

    # --- backgrounds ---
    channel_order = ["pi0pi0", "3pi0", "eta2pi0", "omega_pi0", "etaprime"]
    for bg_file, channel in zip(args.backgrounds, channel_order):
        with uproot.open(bg_file) as f:
            tree = f["mc"]
            n_true_arr = tree["n_true_gamma"].array(library="np")
            n_true = int(n_true_arr[0]) if len(n_true_arr) > 0 else 4
            photons = load_bg_photons(tree, n_true)
            proton  = _load_4vec(tree, "proton")
            beam    = _load_4vec(tree, "beam")
            X = compute_stage1_features(photons, proton, beam)
            all_X.append(X)
            all_y.append(np.zeros(len(X), dtype=np.int8))
            sigma_eff = cs_map.get(channel, 1.0)
            all_w.append(np.full(len(X), sigma_eff / len(X), dtype=np.float32))

    X_out = np.concatenate(all_X, axis=0)
    y_out = np.concatenate(all_y, axis=0)
    w_out = np.concatenate(all_w, axis=0)

    np.savez(args.output, X=X_out, y=y_out, w=w_out,
             feature_names=np.array(FEATURE_NAMES_S1))
    print(f"Saved {len(X_out)} events → {args.output}")


if __name__ == "__main__":
    main()
