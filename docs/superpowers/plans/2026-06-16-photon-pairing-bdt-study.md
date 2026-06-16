# Photon-Pairing BDT Study Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Train an XGBoost BDT on the existing labelled MC dataset to assign 4 photons to the correct eta/pi0 pairing, and prove (or disprove) on held-out MC that it beats the current chi2 baseline.

**Architecture:** Three Python scripts in `analysis/ml/`. `build_features.py` reads `eta_pi0_mc.root` via uproot, shuffles the 4 photons, builds the 3 disjoint pairings ordered by chi2, computes a 54-dim feature vector + a truth class label per event, and writes `features.npz`. `train_bdt.py` trains a multiclass `XGBClassifier`. `evaluate_compare.py` reproduces the test split and compares BDT vs chi2 (pairing accuracy + reconstructed mass spectra). Physics math lives in a tested helper module.

**Tech Stack:** Python 3.14, xgboost 3.2, uproot 5.7 + awkward 2.9 (read ROOT without a ROOT dependency), numpy, scikit-learn, matplotlib, pytest. Installed in a project venv `.venv/`.

**Key facts (verified against the repo):**
- MC file: `simulation/eta_pi0_mc.root`, tree `mc`, 1,000,000 entries.
- Photon branches are `TLorentzVector` objects: `eta_gamma1`, `eta_gamma2`, `pi0_gamma1`, `pi0_gamma2`. uproot reads each as a record with fields `fE` (energy) and `fP` (a `TVector3` with `fX`, `fY`, `fZ`).
- Truth: photons 0,1 come from the eta; photons 2,3 from the pi0.
- The 4 photons admit exactly 3 disjoint pairings: `(01)(23)`, `(02)(13)`, `(03)(12)`.
- Nominal masses: `m_pi0 = 0.134977`, `m_eta = 0.547862` GeV. Baseline chi2 resolution: 8%.
- Because every pairing's chi2 assigns the lighter pair to pi0 and the heavier to eta, the chi2 baseline always selects the minimum-chi2 pairing. After ordering the 3 pairings by ascending chi2, **the chi2 prediction is always block 0**, so chi2 accuracy = fraction of test events with label 0.

---

## File Structure

| File | Responsibility |
|------|----------------|
| `analysis/ml/physics.py` | Vectorised 4-vector math: invariant mass, opening/relative angle, energy asymmetry, pT, beta, chi2. No I/O, no model. |
| `analysis/ml/build_features.py` | Read MC, shuffle photons, build 3 chi2-ordered pairings, compute features + truth label, write `features.npz`. Defines `FEATURE_NAMES`. |
| `analysis/ml/train_bdt.py` | Train `XGBClassifier`, save model + training/importance/confusion plots. |
| `analysis/ml/evaluate_compare.py` | Reproduce test split, compare BDT vs chi2 (accuracy + mass spectra), write `metrics.txt`. |
| `analysis/ml/tests/test_physics.py` | Unit tests for `physics.py`. |
| `analysis/ml/tests/test_build_features.py` | Tests for loader, truth label, no-leakage, chi2 ordering. |

Outputs (git-ignored, regeneratable): `analysis/ml/data/features.npz`, `analysis/ml/model/bdt.json`. Figures in `analysis/ml/plots/` (may be committed).

---

## Task 1: Environment setup

**Files:**
- Create: `.venv/` (virtualenv, git-ignored)
- Modify: `.gitignore`
- Create: `analysis/ml/requirements.txt`

- [ ] **Step 1: Create the venv and the ml directory tree**

```bash
cd /Users/tonyf/Work/GRAAL/GRAAL_Analysis
python3 -m venv .venv
mkdir -p analysis/ml/tests analysis/ml/data analysis/ml/model analysis/ml/plots
touch analysis/ml/tests/__init__.py
```

- [ ] **Step 2: Write `analysis/ml/requirements.txt`**

```
uproot==5.7.4
awkward==2.9.1
xgboost==3.2.0
scikit-learn==1.9.0
numpy>=2.0
matplotlib>=3.10
pytest>=8.0
```

- [ ] **Step 3: Install**

Run:
```bash
.venv/bin/pip install -r analysis/ml/requirements.txt
```
Expected: ends with `Successfully installed ... uproot-5.7.4 xgboost-3.2.0 ...` (no errors).

- [ ] **Step 4: Verify imports**

Run:
```bash
.venv/bin/python -c "import uproot, awkward, xgboost, sklearn, numpy, matplotlib; print('ok', xgboost.__version__)"
```
Expected: `ok 3.2.0`

- [ ] **Step 5: Update `.gitignore`** — append these lines:

```
.venv/
analysis/ml/data/
analysis/ml/model/
```

- [ ] **Step 6: Commit**

```bash
git add .gitignore analysis/ml/requirements.txt
git commit -m "chore: set up analysis/ml python env"
```

---

## Task 2: Physics helper module (TDD)

**Files:**
- Create: `analysis/ml/physics.py`
- Test: `analysis/ml/tests/test_physics.py`

Convention: a 4-vector is a numpy array with last axis `[E, px, py, pz]`; functions are vectorised over any leading axes.

- [ ] **Step 1: Write the failing tests**

`analysis/ml/tests/test_physics.py`:
```python
import numpy as np
import pytest
from analysis.ml import physics


def test_invariant_mass_two_back_to_back_photons():
    # two 1-GeV photons going +z and -z -> invariant mass = 2 GeV
    g1 = np.array([1.0, 0.0, 0.0, 1.0])
    g2 = np.array([1.0, 0.0, 0.0, -1.0])
    assert physics.invariant_mass(g1, g2) == pytest.approx(2.0)


def test_invariant_mass_clips_negative():
    # numerically tiny negative m^2 must clip to 0, not NaN
    g1 = np.array([1.0, 1.0, 0.0, 0.0])
    g2 = np.array([1.0, 1.0, 0.0, 0.0])  # collinear -> m=0
    m = physics.invariant_mass(g1, g2)
    assert m == pytest.approx(0.0, abs=1e-9)
    assert not np.isnan(m)


def test_energy_asymmetry():
    g1 = np.array([3.0, 0, 0, 3.0])
    g2 = np.array([1.0, 0, 0, 1.0])
    assert physics.energy_asymmetry(g1, g2) == pytest.approx(0.5)


def test_opening_angle_orthogonal():
    g1 = np.array([1.0, 1.0, 0.0, 0.0])
    g2 = np.array([1.0, 0.0, 1.0, 0.0])
    assert physics.opening_angle(g1, g2) == pytest.approx(np.pi / 2)


def test_cos_angle_orthogonal():
    g1 = np.array([1.0, 1.0, 0.0, 0.0])
    g2 = np.array([1.0, 0.0, 1.0, 0.0])
    assert physics.cos_angle(g1, g2) == pytest.approx(0.0, abs=1e-9)


def test_pt_and_beta():
    v = np.array([5.0, 3.0, 4.0, 0.0])  # |p| = 5, E = 5 -> beta = 1, pt = 5
    assert physics.pt(v) == pytest.approx(5.0)
    assert physics.beta(v) == pytest.approx(1.0)


def test_chi2_zero_at_nominal_masses():
    assert physics.chi2_pairing(physics.MPI0, physics.META) == pytest.approx(0.0)


def test_functions_are_vectorised():
    g1 = np.array([[1.0, 0, 0, 1.0], [2.0, 0, 0, 2.0]])
    g2 = np.array([[1.0, 0, 0, -1.0], [2.0, 0, 0, -2.0]])
    m = physics.invariant_mass(g1, g2)
    assert m.shape == (2,)
    assert m == pytest.approx([2.0, 4.0])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest analysis/ml/tests/test_physics.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'analysis.ml.physics'` (or attribute errors).

- [ ] **Step 3: Write `analysis/ml/physics.py`**

```python
"""Vectorised 4-vector math for the photon-pairing study.

A 4-vector is a numpy array whose last axis is [E, px, py, pz].
All functions broadcast over leading axes.
"""
import numpy as np

MPI0 = 0.134977
META = 0.547862
CHI2_RES = 0.08  # fractional mass resolution used by the baseline chi2


def _p3(v):
    return v[..., 1:4]


def invariant_mass(a, b):
    s = a + b
    e = s[..., 0]
    p2 = np.sum(s[..., 1:4] ** 2, axis=-1)
    m2 = e * e - p2
    return np.sqrt(np.clip(m2, 0.0, None))


def energy_asymmetry(a, b):
    ea, eb = a[..., 0], b[..., 0]
    return np.abs(ea - eb) / (ea + eb)


def cos_angle(a, b):
    pa, pb = _p3(a), _p3(b)
    na = np.linalg.norm(pa, axis=-1)
    nb = np.linalg.norm(pb, axis=-1)
    denom = np.where((na * nb) == 0.0, 1.0, na * nb)
    c = np.sum(pa * pb, axis=-1) / denom
    return np.clip(c, -1.0, 1.0)


def opening_angle(a, b):
    return np.arccos(cos_angle(a, b))


def pt(v):
    return np.sqrt(v[..., 1] ** 2 + v[..., 2] ** 2)


def beta(v):
    p = np.linalg.norm(_p3(v), axis=-1)
    e = v[..., 0]
    return p / e


def chi2_pairing(m_low, m_high):
    return (
        ((m_low - MPI0) / (CHI2_RES * MPI0)) ** 2
        + ((m_high - META) / (CHI2_RES * META)) ** 2
    )
```

- [ ] **Step 4: Add the package marker** so `analysis.ml` imports resolve from repo root:

```bash
touch analysis/__init__.py analysis/ml/__init__.py
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest analysis/ml/tests/test_physics.py -v`
Expected: PASS (8 passed).

- [ ] **Step 6: Commit**

```bash
git add analysis/__init__.py analysis/ml/__init__.py analysis/ml/physics.py analysis/ml/tests/__init__.py analysis/ml/tests/test_physics.py
git commit -m "feat: add vectorised physics helpers for pairing study"
```

---

## Task 3: MC photon loader (TDD)

**Files:**
- Create: `analysis/ml/build_features.py` (loader portion only in this task)
- Test: `analysis/ml/tests/test_build_features.py` (loader test)

- [ ] **Step 1: Write the failing test**

`analysis/ml/tests/test_build_features.py`:
```python
import numpy as np
import pytest
from analysis.ml import build_features as bf
from analysis.ml import physics

MC_PATH = "simulation/eta_pi0_mc.root"


def test_load_photons_shape_and_masses():
    p = bf.load_photons(MC_PATH, n_max=2000)
    assert p.shape == (2000, 4, 4)          # [event, photon, (E,px,py,pz)]
    # photons 0,1 are the eta decay -> reconstruct ~eta mass (smeared)
    m_eta = physics.invariant_mass(p[:, 0], p[:, 1])
    m_pi0 = physics.invariant_mass(p[:, 2], p[:, 3])
    assert 0.45 < np.median(m_eta) < 0.65
    assert 0.10 < np.median(m_pi0) < 0.18
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest analysis/ml/tests/test_build_features.py -v`
Expected: FAIL — `AttributeError: module ... has no attribute 'load_photons'`.

- [ ] **Step 3: Write the loader in `analysis/ml/build_features.py`**

```python
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
```

Note: if uproot exposes the TLorentzVector members under different keys, run
`.venv/bin/python -c "import uproot; print(uproot.open('simulation/eta_pi0_mc.root:mc')['eta_gamma1'].array(entry_stop=1).fields)"`
and adjust the `v[...]` access accordingly. The mass assertions in the test lock the correct access.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest analysis/ml/tests/test_build_features.py::test_load_photons_shape_and_masses -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add analysis/ml/build_features.py analysis/ml/tests/test_build_features.py
git commit -m "feat: add MC photon loader"
```

---

## Task 4: Pairing, truth label, feature block (TDD)

**Files:**
- Modify: `analysis/ml/build_features.py` (add pairing/feature logic)
- Test: `analysis/ml/tests/test_build_features.py` (add cases)

- [ ] **Step 1: Add failing tests** to `analysis/ml/tests/test_build_features.py`:

```python
def test_shuffle_is_permutation():
    photons = bf.load_photons(MC_PATH, n_max=1000)
    P, perm = bf.shuffle_photons(photons, seed=1)
    # every row of perm is a permutation of {0,1,2,3}
    assert np.all(np.sort(perm, axis=1) == np.arange(4))
    # P[n, j] == photons[n, perm[n, j]]
    assert np.allclose(P[np.arange(1000)[:, None], np.arange(4)],
                       photons[np.arange(1000)[:, None], perm])


def test_truth_label_matches_eta_grouping():
    photons = bf.load_photons(MC_PATH, n_max=5000)
    P, perm = bf.shuffle_photons(photons, seed=1)
    truth = bf.truth_pairing_index(perm)
    # the truth pairing groups the two eta photons (orig idx <2) together
    for k in range(3):
        (i, j), (a, b) = bf.PAIRINGS[k]
        sel = truth == k
        is_eta = perm[sel] < 2
        same_pair = is_eta[:, i].astype(int) + is_eta[:, j].astype(int)
        assert np.all((same_pair == 0) | (same_pair == 2))


def test_no_leakage_label_distribution_roughly_uniform():
    photons = bf.load_photons(MC_PATH, n_max=50000)
    X, y, masses, names = bf.build(photons, seed=1)
    counts = np.bincount(y, minlength=3) / len(y)
    # after chi2 ordering, the truth slot must not be trivially predictable
    # by position (each slot gets a non-trivial share)
    assert np.all(counts > 0.05)


def test_feature_matrix_shape_and_names():
    photons = bf.load_photons(MC_PATH, n_max=1000)
    X, y, masses, names = bf.build(photons, seed=1)
    assert X.shape == (1000, 54)
    assert len(names) == 54
    assert masses.shape == (1000, 3, 2)
    assert set(np.unique(y)).issubset({0, 1, 2})


def test_chi2_baseline_is_block_zero():
    # block 0 is the minimum-chi2 pairing by construction; its chi2 feature
    # must be <= the chi2 feature of blocks 1 and 2.
    photons = bf.load_photons(MC_PATH, n_max=2000)
    X, y, masses, names = bf.build(photons, seed=1)
    chi2_cols = [names.index(f"chi2_block{b}") for b in range(3)]
    c0, c1, c2 = X[:, chi2_cols[0]], X[:, chi2_cols[1]], X[:, chi2_cols[2]]
    assert np.all(c0 <= c1 + 1e-9)
    assert np.all(c0 <= c2 + 1e-9)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest analysis/ml/tests/test_build_features.py -v`
Expected: FAIL — `shuffle_photons` / `truth_pairing_index` / `build` not defined.

- [ ] **Step 3: Add the logic to `analysis/ml/build_features.py`** (insert before any `main`):

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest analysis/ml/tests/test_build_features.py -v`
Expected: PASS (all loader + pairing tests).

- [ ] **Step 5: Commit**

```bash
git add analysis/ml/build_features.py analysis/ml/tests/test_build_features.py
git commit -m "feat: add pairing, truth label, and feature builder"
```

---

## Task 5: build_features CLI -> features.npz

**Files:**
- Modify: `analysis/ml/build_features.py` (add `main()` + `__main__`)

- [ ] **Step 1: Add the CLI** to the end of `analysis/ml/build_features.py`:

```python
def main():
    import argparse
    ap = argparse.ArgumentParser(description="Build features.npz from MC")
    ap.add_argument("--input", default="simulation/eta_pi0_mc.root")
    ap.add_argument("--output", default="analysis/ml/data/features.npz")
    ap.add_argument("--n-max", type=int, default=None)
    ap.add_argument("--seed", type=int, default=SEED)
    args = ap.parse_args()

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
```

- [ ] **Step 2: Run on a subset to smoke-test**

Run:
```bash
.venv/bin/python -m analysis.ml.build_features --n-max 20000 --output analysis/ml/data/features_smoke.npz
```
Expected: prints `X=(20000, 54)`, label fractions summing to ~1.0, and a chi2 baseline accuracy (typically ~0.6-0.8).

- [ ] **Step 3: Generate the full dataset**

Run:
```bash
.venv/bin/python -m analysis.ml.build_features
```
Expected: `Wrote analysis/ml/data/features.npz: X=(1000000, 54), ...`. (A few minutes; large file.)

- [ ] **Step 4: Commit** (code only; the npz is git-ignored)

```bash
git add analysis/ml/build_features.py
git commit -m "feat: add build_features CLI"
```

---

## Task 6: Train the BDT

**Files:**
- Create: `analysis/ml/train_bdt.py`

- [ ] **Step 1: Write `analysis/ml/train_bdt.py`**

```python
"""Train a multiclass XGBoost BDT to pick the correct photon pairing."""
import numpy as np
import xgboost as xgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix

FEATURES = "analysis/ml/data/features.npz"
MODEL_OUT = "analysis/ml/model/bdt.json"
PLOT_DIR = "analysis/ml/plots"
SEED = 42


def main():
    d = np.load(FEATURES, allow_pickle=True)
    X, y, names = d["X"], d["y"], list(d["feature_names"])

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=SEED, stratify=y)
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_tr, y_tr, test_size=0.2, random_state=SEED, stratify=y_tr)

    model = xgb.XGBClassifier(
        n_estimators=400, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        objective="multi:softprob", num_class=3,
        eval_metric="mlogloss", early_stopping_rounds=25,
        random_state=SEED, n_jobs=-1)
    model.fit(X_tr, y_tr, eval_set=[(X_tr, y_tr), (X_val, y_val)], verbose=False)
    model.save_model(MODEL_OUT)

    acc = accuracy_score(y_te, model.predict(X_te))
    chi2_acc = np.mean(y_te == 0)
    print(f"BDT test accuracy : {acc:.4f}")
    print(f"chi2 test accuracy: {chi2_acc:.4f}")

    # training curve
    res = model.evals_result()
    plt.figure()
    plt.plot(res["validation_0"]["mlogloss"], label="train")
    plt.plot(res["validation_1"]["mlogloss"], label="val")
    plt.xlabel("boosting round"); plt.ylabel("mlogloss"); plt.legend()
    plt.title("Training curve"); plt.savefig(f"{PLOT_DIR}/training_curve.png", dpi=120)
    plt.close()

    # feature importance (gain)
    imp = model.feature_importances_
    idx = np.argsort(imp)[::-1][:20]
    plt.figure(figsize=(7, 6))
    plt.barh([names[i] for i in idx][::-1], imp[idx][::-1])
    plt.title("Top-20 feature importance (gain)"); plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/feature_importance.png", dpi=120); plt.close()

    # confusion matrix
    cm = confusion_matrix(y_te, model.predict(X_te))
    plt.figure()
    plt.imshow(cm, cmap="Blues"); plt.colorbar()
    for (r, c), v in np.ndenumerate(cm):
        plt.text(c, r, str(v), ha="center", va="center")
    plt.xlabel("predicted slot"); plt.ylabel("true slot")
    plt.title("Confusion matrix"); plt.savefig(f"{PLOT_DIR}/confusion.png", dpi=120)
    plt.close()


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run training**

Run:
```bash
.venv/bin/python -m analysis.ml.train_bdt
```
Expected: prints `BDT test accuracy` and `chi2 test accuracy`; writes `model/bdt.json` and 3 PNGs in `plots/`. Success indicator: BDT accuracy > chi2 accuracy.

- [ ] **Step 3: Commit** (code + plots; model is git-ignored)

```bash
git add analysis/ml/train_bdt.py analysis/ml/plots/training_curve.png analysis/ml/plots/feature_importance.png analysis/ml/plots/confusion.png
git commit -m "feat: train pairing BDT and emit diagnostics"
```

---

## Task 7: Evaluate BDT vs chi2 (mass spectra + metrics)

**Files:**
- Create: `analysis/ml/evaluate_compare.py`

- [ ] **Step 1: Write `analysis/ml/evaluate_compare.py`**

```python
"""Compare BDT vs chi2 on the held-out MC test set: accuracy + mass spectra."""
import numpy as np
import xgboost as xgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

FEATURES = "analysis/ml/data/features.npz"
MODEL = "analysis/ml/model/bdt.json"
PLOT_DIR = "analysis/ml/plots"
SEED = 42


def _peak_width(values, lo, hi):
    sel = values[(values > lo) & (values < hi)]
    return float(np.std(sel)) if len(sel) else float("nan")


def main():
    d = np.load(FEATURES, allow_pickle=True)
    X, y, masses = d["X"], d["y"], d["masses"]  # masses: (N,3,2) -> [pi0, eta]

    idx = np.arange(len(y))
    _, te = train_test_split(idx, test_size=0.2, random_state=SEED, stratify=y)
    X_te, y_te, m_te = X[te], y[te], masses[te]

    model = xgb.XGBClassifier()
    model.load_model(MODEL)
    pred = model.predict(X_te)
    chi2_pred = np.zeros_like(y_te)  # block 0 is min-chi2 by construction

    acc_bdt = accuracy_score(y_te, pred)
    acc_chi2 = accuracy_score(y_te, chi2_pred)

    rows = np.arange(len(te))
    pi0_truth, eta_truth = m_te[rows, y_te, 0], m_te[rows, y_te, 1]
    pi0_chi2, eta_chi2 = m_te[rows, chi2_pred, 0], m_te[rows, chi2_pred, 1]
    pi0_bdt, eta_bdt = m_te[rows, pred, 0], m_te[rows, pred, 1]

    # mass spectra
    for meson, lo, hi, truth, c2, bdt in [
        ("pi0", 0.05, 0.25, pi0_truth, pi0_chi2, pi0_bdt),
        ("eta", 0.35, 0.75, eta_truth, eta_chi2, eta_bdt),
    ]:
        plt.figure()
        bins = np.linspace(lo, hi, 80)
        plt.hist(c2, bins=bins, histtype="step", label="chi2")
        plt.hist(bdt, bins=bins, histtype="step", label="BDT")
        plt.hist(truth, bins=bins, histtype="step", label="truth", linestyle="--")
        plt.xlabel(f"m({meson}) [GeV]"); plt.ylabel("events"); plt.legend()
        plt.title(f"{meson} reconstructed mass")
        plt.savefig(f"{PLOT_DIR}/mass_{meson}.png", dpi=120); plt.close()

    with open(f"{PLOT_DIR}/metrics.txt", "w") as fh:
        fh.write(f"Test events: {len(te)}\n")
        fh.write(f"Pairing accuracy  BDT : {acc_bdt:.4f}\n")
        fh.write(f"Pairing accuracy  chi2: {acc_chi2:.4f}\n")
        fh.write(f"Improvement (abs)     : {acc_bdt - acc_chi2:+.4f}\n\n")
        fh.write("Peak width (std within window):\n")
        fh.write(f"  pi0  chi2={_peak_width(pi0_chi2,0.10,0.17):.4f}  "
                 f"bdt={_peak_width(pi0_bdt,0.10,0.17):.4f}\n")
        fh.write(f"  eta  chi2={_peak_width(eta_chi2,0.50,0.60):.4f}  "
                 f"bdt={_peak_width(eta_bdt,0.50,0.60):.4f}\n")

    print(open(f"{PLOT_DIR}/metrics.txt").read())


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run evaluation**

Run:
```bash
.venv/bin/python -m analysis.ml.evaluate_compare
```
Expected: prints `metrics.txt` (BDT vs chi2 accuracy + improvement + peak widths); writes `plots/mass_pi0.png`, `plots/mass_eta.png`, `plots/metrics.txt`.

- [ ] **Step 3: Commit**

```bash
git add analysis/ml/evaluate_compare.py analysis/ml/plots/mass_pi0.png analysis/ml/plots/mass_eta.png analysis/ml/plots/metrics.txt
git commit -m "feat: compare BDT vs chi2 pairing (accuracy + mass spectra)"
```

---

## Task 8: Document the study

**Files:**
- Modify: `README.md` (extend the `analysis/` section)
- Create: `analysis/ml/README.md`

- [ ] **Step 1: Write `analysis/ml/README.md`**

````markdown
# Photon-pairing BDT study

Trains an XGBoost BDT to assign the 4 photons of a gamma p -> p eta pi0 event
to the correct eta/pi0 pairing, and compares it to the chi2 baseline on MC.

## Run

```bash
python3 -m venv .venv && .venv/bin/pip install -r analysis/ml/requirements.txt
.venv/bin/python -m analysis.ml.build_features        # -> data/features.npz
.venv/bin/python -m analysis.ml.train_bdt             # -> model/bdt.json + plots
.venv/bin/python -m analysis.ml.evaluate_compare      # -> plots/metrics.txt + mass spectra
```

## Method

The 4 photons give 3 disjoint pairings. Per event the photons are shuffled
(no positional leakage), the 3 pairings are ordered by ascending chi2, and a
54-dim feature vector (3 blocks x 18 features: masses, mass distances, energy
asymmetry, opening angles, sorted energies, meson angle/pT/boost, chi2) is fed
to a multiclass `XGBClassifier`. The label is the chi2-ordered slot holding the
truth pairing; the chi2 baseline always picks slot 0. Headline metric: pairing
accuracy on a held-out test set, BDT vs chi2.
````

- [ ] **Step 2: Append to `README.md`** after the `### simulation/` section, a short pointer:

```markdown
### analysis/ml/

XGBoost BDT study for photon pairing (gamma p -> p eta pi0): trains on the
labelled MC and compares pairing accuracy and reconstructed mass resolution
against the chi2 baseline. See `analysis/ml/README.md`. Design and plan in
`docs/superpowers/`.
```

- [ ] **Step 3: Commit**

```bash
git add README.md analysis/ml/README.md
git commit -m "docs: document the photon-pairing BDT study"
```

---

## Done criteria

- `.venv/bin/python -m pytest analysis/ml/tests -v` is green.
- `analysis/ml/plots/metrics.txt` exists and reports the BDT vs chi2 accuracy. BDT beating chi2 is the success gate. If BDT does **not** beat chi2, that is still a valid, reportable result — record it in metrics and note the likely cause (the engineered features carry no information beyond chi2, or smearing makes the problem chi2-saturated).
