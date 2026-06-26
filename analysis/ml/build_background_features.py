"""Build stage-1 BDT features from background and signal MC ROOT files.

Stage-1 BDT is a binary classifier (signal=1 vs background=0).  Both signal
and background are presented with EXACTLY 4 observed photons:
  - Signal MC: 4 photons by construction (η→γγ, π⁰→γγ)
  - Background MC: photon-loss model is applied to randomly drop photons until
    exactly 4 survive, mimicking detector acceptance and threshold effects.

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
from pathlib import Path

import numpy as np

try:
    import uproot
except ImportError as exc:
    raise ImportError("uproot required: pip install uproot") from exc

from analysis.ml.photon_loss import LossParams, sample_surviving_photons

# ---------------------------------------------------------------------------
# 24 features — computed on exactly 4 photons (after loss for background)
# ---------------------------------------------------------------------------
# 6 invariant masses of the C(4,2) photon pairs
# + pair counts near meson poles
# + best chi2 for eta+pi0 assignment
# + missing kinematics
# + photon energy statistics
# + proton kinematics
# ---------------------------------------------------------------------------
FEATURE_NAMES_S1: list[str] = [
    # C(4,2)=6 invariant masses
    "m_gg_01", "m_gg_02", "m_gg_03",
    "m_gg_12", "m_gg_13",
    "m_gg_23",
    # pair counts near meson poles
    "n_pairs_near_pi0",     # |m_gg - 0.135| < 0.040 GeV
    "n_pairs_near_eta",     # |m_gg - 0.548| < 0.080 GeV
    # best chi2 for any assignment of 4γ to η+π⁰
    "best_chi2_eta_pi0",
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

assert len(FEATURE_NAMES_S1) == 24, f"Expected 24, got {len(FEATURE_NAMES_S1)}"

_MPROT = 0.938272
_MPI0  = 0.134977
_META  = 0.547862
_TARGET = np.array([0.0, 0.0, 0.0, _MPROT])

# Pair indices for exactly 4 photons: C(4,2)=6
_PAIR_IDX = [(0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3)]
# The 3 ways to partition 4 photons into 2 disjoint pairs
# listed as indices into _PAIR_IDX
_COMBOS = [(0, 5), (1, 4), (2, 3)]   # (01|23), (02|13), (03|12)


def _load_4vec(tree, name: str) -> np.ndarray:
    """Load TLorentzVector branch as (N,4) array [px,py,pz,E]."""
    arr = tree[name].array(library="ak")
    px = np.asarray(arr["fP"]["fX"])
    py = np.asarray(arr["fP"]["fY"])
    pz = np.asarray(arr["fP"]["fZ"])
    E  = np.asarray(arr["fE"])
    return np.stack([px, py, pz, E], axis=1)


def load_bg_photons(tree, n_gamma: int) -> np.ndarray:
    """Load g0..g{n_gamma-1} branches → (N, n_gamma, 4) [px,py,pz,E]."""
    arrays = [_load_4vec(tree, f"g{i}") for i in range(n_gamma)]
    return np.stack(arrays, axis=1)


def load_signal_photons(tree) -> np.ndarray:
    """Load signal photons from named branches → (N, 4, 4) [px,py,pz,E]."""
    branches = ["eta_gamma1", "eta_gamma2", "pi0_gamma1", "pi0_gamma2"]
    arrays = [_load_4vec(tree, b) for b in branches]
    return np.stack(arrays, axis=1)


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
) -> np.ndarray:
    """Compute 24 stage-1 features — vectorised, no Python loops over events.

    Args:
        photons: shape (N, 4, 4), columns [px, py, pz, E]
        proton:  shape (N, 4)
        beam:    shape (N, 4)

    Returns:
        Feature matrix of shape (N, 24), dtype float32
    """
    N = photons.shape[0]
    out = np.zeros((N, 24), dtype=np.float32)

    # -- invariant masses of all 6 pairs (vectorised) -----------------------
    def _m_pair(i: int, j: int) -> np.ndarray:
        s  = photons[:, i] + photons[:, j]          # (N, 4)
        m2 = s[:, 3]**2 - (s[:, 0]**2 + s[:, 1]**2 + s[:, 2]**2)
        return np.sqrt(np.clip(m2, 0, None))

    pair_m = np.stack([_m_pair(i, j) for i, j in _PAIR_IDX], axis=1)  # (N,6)

    out[:, 0:6] = pair_m

    # -- pair counts near meson poles ----------------------------------------
    out[:, 6] = (np.abs(pair_m - _MPI0) < 0.040).sum(axis=1)
    out[:, 7] = (np.abs(pair_m - _META) < 0.080).sum(axis=1)

    # -- best chi2 for η+π⁰ assignment (3 disjoint-pair combos) ------------
    def _chi2_combo(pi: int, pj: int) -> np.ndarray:
        ma, mb = pair_m[:, pi], pair_m[:, pj]
        c1 = ((ma - _META)/(0.08*_META))**2 + ((mb - _MPI0)/(0.08*_MPI0))**2
        c2 = ((ma - _MPI0)/(0.08*_MPI0))**2 + ((mb - _META)/(0.08*_META))**2
        return np.minimum(c1, c2)

    chi2s = np.stack([_chi2_combo(pi, pj) for pi, pj in _COMBOS], axis=1)  # (N,3)
    out[:, 8] = chi2s.min(axis=1)

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

    opening = np.stack([np.arccos(_cos_pair(i, j)) for i, j in _PAIR_IDX], axis=1)
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--signal", required=True)
    parser.add_argument("--backgrounds", nargs="+", required=True)
    parser.add_argument("--cs-csv", required=True)
    parser.add_argument("--output", default="features_stage1.npz")
    parser.add_argument("--loss-seed", type=int, default=42,
                        help="RNG seed for photon-loss sampling")
    args = parser.parse_args()

    import csv
    cs_map: dict[str, float] = {}
    with open(args.cs_csv) as f:
        for row in csv.DictReader(filter(lambda ln: not ln.startswith("#"), f)):
            cs_map[row["channel"]] = float(row["sigma_eff"])

    total_sigma = sum(cs_map.values()) or 1.0
    rng = np.random.default_rng(args.loss_seed)

    all_X, all_y, all_w = [], [], []

    # --- signal (already 4 photons — no loss applied) ----------------------
    with uproot.open(args.signal) as f:
        tree = f["mc"]
        photons = load_signal_photons(tree)
        proton  = _load_4vec(tree, "proton")
        beam    = _load_4vec(tree, "beam")
        # Shuffle photon order per event so pair (0,1) is not always the eta pair.
        # Without this, m_gg_01 would trivially equal m_eta for all signal events.
        idx = np.argsort(rng.random((len(photons), 4)), axis=1)
        photons = photons[np.arange(len(photons))[:, None], idx]
        X = compute_stage1_features(photons, proton, beam)
        all_X.append(X)
        all_y.append(np.ones(len(X), dtype=np.int8))
        all_w.append(np.ones(len(X), dtype=np.float32))

    # --- backgrounds (apply photon loss → exactly 4 survivors) -------------
    channel_order = ["pi0pi0", "3pi0", "eta2pi0", "omega_pi0", "etaprime"]
    params = LossParams()

    for bg_file, channel in zip(args.backgrounds, channel_order):
        with uproot.open(bg_file) as f:
            tree = f["mc"]
            n_true_arr = tree["n_true_gamma"].array(library="np")
            n_true = int(n_true_arr[0]) if len(n_true_arr) > 0 else 4
            photons_all = load_bg_photons(tree, n_true)   # (N, n_true, 4)
            proton_all  = _load_4vec(tree, "proton")
            beam_all    = _load_4vec(tree, "beam")

        # Apply photon loss: keep only events with exactly 4 survivors
        ph_E, ph_theta = _extract_E_theta(photons_all)
        photons_4, event_mask = sample_surviving_photons(
            photons_all, ph_E, ph_theta, rng, params, n_keep=4
        )
        proton_sel = proton_all[event_mask]
        beam_sel   = beam_all[event_mask]

        # Shuffle photon order per event so ordering convention is symmetric
        # across channels (pi0pi0 generator may order by decay chain).
        bg_idx = np.argsort(rng.random((len(photons_4), 4)), axis=1)
        photons_4 = photons_4[np.arange(len(photons_4))[:, None], bg_idx]

        n_survived = event_mask.sum()
        p_surv = n_survived / len(event_mask)
        print(f"  {channel}: {n_survived}/{len(event_mask)} events "
              f"survive loss ({p_surv:.3f})")

        X = compute_stage1_features(photons_4, proton_sel, beam_sel)
        all_X.append(X)
        all_y.append(np.zeros(len(X), dtype=np.int8))
        sigma_eff = cs_map.get(channel, 1.0)
        # per-event weight: channel contribution ∝ sigma_eff / total_sigma
        # (O(0.1) values — numerically stable)
        all_w.append(np.full(len(X), sigma_eff / total_sigma, dtype=np.float32))

    X_out = np.concatenate(all_X, axis=0)
    y_out = np.concatenate(all_y, axis=0)
    w_out = np.concatenate(all_w, axis=0)

    np.savez(args.output, X=X_out, y=y_out, w=w_out,
             feature_names=np.array(FEATURE_NAMES_S1))
    n_sig = (y_out == 1).sum()
    n_bkg = (y_out == 0).sum()
    print(f"Saved {len(X_out)} events ({n_sig} signal, {n_bkg} background) → {args.output}")


if __name__ == "__main__":
    main()
