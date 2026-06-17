"""Build the feature matrix + truth labels for the photon-pairing BDT study.

Reads the labelled MC (tree `mc` of eta_pi0_mc.root), shuffles the four
photons per event, builds the three disjoint pairings ordered by chi2, and
emits a 54-dim feature row plus a class label (which chi2-ordered slot holds
the truth pairing) per event.
"""
import numpy as np
import uproot

from analysis.ml import physics

SEED = 42
PAIRINGS = [((0, 1), (2, 3)), ((0, 2), (1, 3)), ((0, 3), (1, 2))]
PHOTON_BRANCHES = ["eta_gamma1", "eta_gamma2", "pi0_gamma1", "pi0_gamma2"]


def load_photons(root_path, tree="mc", n_max=None):
    """Return photons as a (N, 4, 4) array; last axis is [E, px, py, pz].

    Photon order matches truth: index 0,1 -> eta decay; 2,3 -> pi0 decay.
    """
    t = uproot.open(f"{root_path}:{tree}")
    arrays = t.arrays(PHOTON_BRANCHES, entry_stop=n_max, library="ak")
    n = len(arrays)
    out = np.empty((n, 4, 4), dtype=np.float64)
    for i, name in enumerate(PHOTON_BRANCHES):
        v = arrays[name]
        out[:, i, 0] = np.asarray(v["fE"])
        out[:, i, 1] = np.asarray(v["fP"]["fX"])
        out[:, i, 2] = np.asarray(v["fP"]["fY"])
        out[:, i, 3] = np.asarray(v["fP"]["fZ"])
    return out


# --- per-block feature names (18 each) -------------------------------------
_BLOCK_FEATURES = [
    "m_low", "m_high", "dm_pi0", "dm_eta",
    "asym_low", "asym_high", "theta_low", "theta_high",
    "E1", "E2", "E3", "E4", "cos_mesons",
    "pt_low", "pt_high", "beta_low", "beta_high", "chi2",
]


def _feature_names():
    names = []
    for b in range(3):
        for f in _BLOCK_FEATURES:
            names.append("chi2_block{}".format(b) if f == "chi2" else "{}_block{}".format(f, b))
    return names


FEATURE_NAMES = _feature_names()


def shuffle_photons(photons, seed=SEED):
    """Randomly permute the 4 photons per event. Returns (P, perm).

    P[n, j] = photons[n, perm[n, j]]; perm[n] is a permutation of {0,1,2,3}.
    """
    rng = np.random.default_rng(seed)
    n = photons.shape[0]
    perm = np.argsort(rng.random((n, 4)), axis=1)
    P = np.take_along_axis(photons, perm[:, :, None], axis=1)
    return P, perm


def truth_pairing_index(perm):
    """Index in PAIRINGS whose one pair contains exactly the two eta photons."""
    n = perm.shape[0]
    is_eta = perm < 2  # eta photons had original index 0,1
    truth = np.full(n, -1, dtype=np.int64)
    for k, ((i, j), _) in enumerate(PAIRINGS):
        in_pair = is_eta[:, i].astype(int) + is_eta[:, j].astype(int)
        grouped = (in_pair == 2) | (in_pair == 0)
        truth = np.where(grouped & (truth < 0), k, truth)
    return truth


def _feature_block(P, pairing):
    """Return (block (N,18), chi2 (N,), m_low (N,), m_high (N,)) for one pairing."""
    (i, j), (k, l) = pairing
    mA = physics.invariant_mass(P[:, i], P[:, j])
    mB = physics.invariant_mass(P[:, k], P[:, l])
    a_low = mA <= mB

    def sel(a, b):
        return np.where(a_low, a, b)

    asymA = physics.energy_asymmetry(P[:, i], P[:, j])
    asymB = physics.energy_asymmetry(P[:, k], P[:, l])
    thA = physics.opening_angle(P[:, i], P[:, j])
    thB = physics.opening_angle(P[:, k], P[:, l])
    mesonA = P[:, i] + P[:, j]
    mesonB = P[:, k] + P[:, l]
    ptA, ptB = physics.pt(mesonA), physics.pt(mesonB)
    beA, beB = physics.beta(mesonA), physics.beta(mesonB)

    m_low, m_high = np.minimum(mA, mB), np.maximum(mA, mB)
    asym_low, asym_high = sel(asymA, asymB), sel(asymB, asymA)
    th_low, th_high = sel(thA, thB), sel(thB, thA)
    pt_low, pt_high = sel(ptA, ptB), sel(ptB, ptA)
    be_low, be_high = sel(beA, beB), sel(beB, beA)
    cos_mes = physics.cos_angle(mesonA, mesonB)
    chi2 = physics.chi2_pairing(m_low, m_high)
    e_sorted = np.sort(P[:, :, 0], axis=1)[:, ::-1]  # (N,4) energies desc

    block = np.column_stack([
        m_low, m_high, np.abs(m_low - physics.MPI0), np.abs(m_high - physics.META),
        asym_low, asym_high, th_low, th_high,
        e_sorted[:, 0], e_sorted[:, 1], e_sorted[:, 2], e_sorted[:, 3], cos_mes,
        pt_low, pt_high, be_low, be_high, chi2,
    ])
    return block, chi2, m_low, m_high


def build(photons, seed=SEED):
    """Return (X (N,54), y (N,), masses (N,3,2), feature_names list)."""
    P, perm = shuffle_photons(photons, seed=seed)
    n = P.shape[0]
    blocks, chi2s, masses = [], [], []
    for pairing in PAIRINGS:
        blk, c, ml, mh = _feature_block(P, pairing)
        blocks.append(blk)
        chi2s.append(c)
        masses.append(np.column_stack([ml, mh]))  # (N,2): [pi0-ish, eta-ish]
    blocks = np.stack(blocks, axis=1)   # (N,3,18)
    chi2s = np.stack(chi2s, axis=1)     # (N,3)
    masses = np.stack(masses, axis=1)   # (N,3,2)

    order = np.argsort(chi2s, axis=1)   # (N,3) ascending chi2
    rows = np.arange(n)[:, None]
    blocks_ord = blocks[rows, order]    # (N,3,18)
    masses_ord = masses[rows, order]    # (N,3,2)
    X = blocks_ord.reshape(n, -1)       # (N,54)

    truth = truth_pairing_index(perm)
    y = np.argmax(order == truth[:, None], axis=1).astype(np.int64)  # slot of truth
    return X, y, masses_ord, FEATURE_NAMES


def _fmt_row(label, values, width=9, prec=4):
    """One formatted table row: a label then numeric columns."""
    cells = "".join(f"{v:>{width}.{prec}f}" for v in values)
    return f"{label:<14}{cells}"


def explain(photons, seed=SEED, n_show=3):
    """Test/teaching mode: walk through the pipeline on a few events, printing
    the intermediate matrices and tables so the logic is transparent."""
    np.set_printoptions(precision=4, suppress=True, linewidth=120)
    sub = photons[:n_show]
    X, y, masses, names = build(sub, seed=seed)
    P, perm = shuffle_photons(sub, seed=seed)          # same seed -> same shuffle
    truth = truth_pairing_index(perm)

    print("=" * 70)
    print(f"TEST MODE — walking through {n_show} events")
    print("Photon 4-vectors are [E, px, py, pz] (GeV).")
    print("Truth: photons 0,1 come from the eta; 2,3 from the pi0.")
    print("=" * 70)

    for e in range(n_show):
        print(f"\n################## EVENT {e} ##################")

        print("\n[1] Raw photons (truth order):")
        print("  idx  origin        E       px       py       pz")
        for i in range(4):
            origin = "eta" if i < 2 else "pi0"
            print(f"  {i:<3}  {origin:<6}" + "".join(f"{v:>9.4f}" for v in sub[e, i]))

        print(f"\n[2] Shuffle (perm = {perm[e]}):  pos j holds original photon perm[j]")
        print("  pos  origIdx  isEta        E       px       py       pz")
        for j in range(4):
            oi = int(perm[e, j])
            print(f"  {j:<3}  {oi:<7}  {str(oi < 2):<5}" +
                  "".join(f"{v:>9.4f}" for v in P[e, j]))

        print("\n[3] The 3 pairings (by shuffled position), masses and chi2:")
        print("  k  pairs        m_low    m_high      chi2")
        chi2_each = []
        for k, ((i, j), (a, b)) in enumerate(PAIRINGS):
            mA = physics.invariant_mass(P[e, i], P[e, j])
            mB = physics.invariant_mass(P[e, a], P[e, b])
            m_low, m_high = min(mA, mB), max(mA, mB)
            c = physics.chi2_pairing(m_low, m_high)
            chi2_each.append(c)
            tag = f"({i}{j})({a}{b})"
            print(f"  {k}  {tag:<10}{m_low:>8.4f}{m_high:>10.4f}{c:>10.3f}")

        order = np.argsort(chi2_each)
        print(f"\n[4] chi2 ascending order: {order.tolist()}  ->  block 0 = min-chi2 = the chi2 choice")
        print(f"[5] truth pairing index (groups the two eta photons): {int(truth[e])}")
        print(f"[6] label y = slot of truth after chi2 ordering: {int(y[e])}")
        chi2_ok = "YES" if y[e] == 0 else "NO  (chi2 wrong -> BDT must correct)"
        print(f"    chi2 picks block 0; truth sits in block {int(y[e])}.  chi2 correct? {chi2_ok}")

        print("\n[7] Feature row (54 values) shown as 3 chi2-ordered blocks x 18 features:")
        block = X[e].reshape(3, 18)
        header = "  " + "feature".ljust(14) + "".join(f"{'block'+str(b):>9}" for b in range(3))
        print(header)
        for f_idx, fname in enumerate(_BLOCK_FEATURES):
            print("  " + _fmt_row(fname, block[:, f_idx]))

    # ---- aggregate table over a larger sample -----------------------------
    n_stat = min(len(photons), 20000)
    Xs, ys, _, _ = build(photons[:n_stat], seed=seed)
    frac = np.bincount(ys, minlength=3) / len(ys)
    print("\n" + "=" * 70)
    print(f"AGGREGATE over {n_stat} events — label distribution (= which slot holds truth):")
    print("  slot 0 (chi2 right)   slot 1            slot 2")
    print(f"  {frac[0]:>8.4f}             {frac[1]:>8.4f}          {frac[2]:>8.4f}")
    print(f"\n  => chi2 baseline accuracy (slot 0) = {frac[0]:.4f}")
    print("  The BDT tries to recover the slot-1/slot-2 events that chi2 gets wrong.")
    print("=" * 70)


def main():
    import argparse
    ap = argparse.ArgumentParser(description="Build features.npz from MC")
    ap.add_argument("--input", default="simulation/eta_pi0_mc.root")
    ap.add_argument("--output", default="analysis/ml/data/features.npz")
    ap.add_argument("--n-max", type=int, default=None)
    ap.add_argument("--seed", type=int, default=SEED)
    ap.add_argument("--explain", action="store_true",
                    help="test mode: walk through a few events step by step "
                         "(prints matrices/tables, writes nothing)")
    ap.add_argument("--explain-events", type=int, default=3,
                    help="how many events to walk through in --explain mode")
    args = ap.parse_args()

    if args.explain:
        n_load = max(args.explain_events, 20000)
        print(f"Loading photons from {args.input} (test mode) ...")
        photons = load_photons(args.input, n_max=n_load)
        explain(photons, seed=args.seed, n_show=args.explain_events)
        return

    print(f"Loading photons from {args.input} ...")
    photons = load_photons(args.input, n_max=args.n_max)
    print(f"Loaded {len(photons)} events; building features ...")
    X, y, masses, names = build(photons, seed=args.seed)
    np.savez_compressed(args.output, X=X, y=y, masses=masses,
                        feature_names=np.array(names))
    frac = np.bincount(y, minlength=3) / len(y)
    print(f"Wrote {args.output}: X={X.shape}, label fractions={frac.round(3)}")
    print(f"chi2 baseline accuracy (label==0): {frac[0]:.4f}")


if __name__ == "__main__":
    main()
