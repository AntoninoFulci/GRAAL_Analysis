"""Shared Stage-1 feature schema and computation for training and inference."""

from __future__ import annotations

import numpy as np

from graal_common.physics.channels import ETA_PI0_HYP, M_PROTON, Hypothesis
from graal_common.physics.pairing import (
    PAIR_IDX,
    best_pairing_indices,
    chi2_per_pairing,
    pair_masses,
)


# ---------------------------------------------------------------------------
# 26 features — computed on exactly 4 photons, after the loss model
# ---------------------------------------------------------------------------
# 6 invariant masses of the C(4,2) photon pairs
# + pair counts near the two mass poles of the hypothesis
# + best chi2 for the hypothesis
# + missing kinematics
# + photon energy statistics
# + proton kinematics
# ---------------------------------------------------------------------------
N_FEATURES_S1 = 26


def feature_names(hypothesis: Hypothesis = ETA_PI0_HYP) -> list[str]:
    """The 26 feature names, in the order compute_stage1_features emits them.

    Several are named after the hypothesis (the two pole counts, the chi2, and
    the two meson-candidate kinematics), so a model trained against one
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
        # kinematics of the chi2-best pairing's two meson candidates
        f"{hypothesis.heavy_label}_E_asym",
        f"{hypothesis.heavy_label}_{hypothesis.light_label}_angle",
    ]
    assert len(names) == N_FEATURES_S1, f"Expected {N_FEATURES_S1}, got {len(names)}"
    return names


# The eta_pi0 default, which is what the pipeline trains.
FEATURE_NAMES_S1: list[str] = feature_names(ETA_PI0_HYP)

_TARGET = np.array([0.0, 0.0, 0.0, M_PROTON])


def compute_stage1_features(
    photons: np.ndarray,   # (N, 4, 4) — exactly 4 photons, [px,py,pz,E]
    proton: np.ndarray,    # (N, 4)
    beam: np.ndarray,      # (N, 4)
    hypothesis: Hypothesis = ETA_PI0_HYP,
) -> np.ndarray:
    """Compute the 26 stage-1 features — vectorised, no Python loops over events.

    Args:
        photons: shape (N, 4, 4), columns [px, py, pz, E]
        proton:  shape (N, 4)
        beam:    shape (N, 4)
        hypothesis: the two mesons the pole counts and the chi2 are built
            around. Must be the one the model was trained against — Stage1Gate
            enforces that.

    Returns:
        Feature matrix of shape (N, 26), dtype float32
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
    out[:, 23] = np.divide(
        proton[:, 2],
        p_mom,
        out=np.zeros_like(p_mom),
        where=p_mom > 0,
    )

    # -- kinematics of the chi2-best pairing's two meson candidates -----------
    # Both features name "the eta pair" and "the eta/pi0 candidates". The four
    # photons carry no parent label (they are shuffled), so the candidates come
    # from the pairing that minimises the chi2 — the same one best_chi2 (col 8)
    # scores. heavy = eta candidate, light = pi0 candidate.
    heavy_idx, light_idx = best_pairing_indices(pair_m, hypothesis)   # (N,2),(N,2)
    row = np.arange(N)
    g_h1 = photons[row, heavy_idx[:, 0], :]      # (N, 4) [px,py,pz,E]
    g_h2 = photons[row, heavy_idx[:, 1], :]
    g_l1 = photons[row, light_idx[:, 0], :]
    g_l2 = photons[row, light_idx[:, 1], :]

    # Normalised energy asymmetry of the eta pair. A real eta shares energy more
    # evenly than a random pair; normalising by the pair energy strips the eta's
    # lab boost, leaving the decay asymmetry the beam energy would otherwise mask.
    E_sum = g_h1[:, 3] + g_h2[:, 3]
    out[:, 24] = np.divide(
        np.abs(g_h1[:, 3] - g_h2[:, 3]),
        E_sum,
        out=np.zeros_like(E_sum),
        where=E_sum > 0,
    )

    # Cosine of the lab angle between the two reconstructed mesons. A genuine
    # eta pi0 has the boost-fixed opening angle; a combinatorial fake does not.
    heavy_p = g_h1[:, :3] + g_h2[:, :3]          # (N, 3)
    light_p = g_l1[:, :3] + g_l2[:, :3]
    nh = np.linalg.norm(heavy_p, axis=1)
    nl = np.linalg.norm(light_p, axis=1)
    cos_meson = (heavy_p * light_p).sum(axis=1) / np.clip(nh * nl, 1e-9, None)
    out[:, 25] = np.clip(cos_meson, -1.0, 1.0)

    return out
