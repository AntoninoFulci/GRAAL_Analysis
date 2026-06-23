# Beam Kinematic Features for the Pairing BDT — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add beam-derived CM-frame features (cos(theta*) and p* per meson per pairing, plus a global beam energy) to the existing photon-pairing BDT and measure whether they beat the current model (98.08%) and the chi2 baseline (97.51%).

**Architecture:** Extend the existing `analysis/ml` pipeline. Add one vectorised Lorentz `boost` to `physics.py`. In `build_features.py` add a `beam` loader, grow each per-pairing feature block from 18 to 22 (adding `cosstar_low/high`, `pstar_low/high` computed in the beam+target CM frame), and append one global `beam_E` column, so the feature vector goes 54 -> 67. Retrain and re-evaluate (those scripts are feature-count-agnostic).

**Tech Stack:** Python 3.14 (venv `.venv/`), numpy, uproot+awkward, xgboost, scikit-learn, matplotlib, pytest.

## Global Constraints

- All commands run from repo root `/Users/tonyf/Work/GRAAL/GRAAL_Analysis` using `.venv/bin/python`.
- Branch: `ml-photon-pairing-bdt`.
- A 4-vector is a numpy array with last axis `[E, px, py, pz]`; helpers vectorise over leading axes.
- Deterministic: `SEED = 42`; the photon shuffle and train/test split must stay reproducible.
- MC: `simulation/eta_pi0_mc.root`, tree `mc`, 1,000,000 events; git-ignored. `beam` branch is a `TLorentzVector` `(0,0,E_beam,E_beam)`; target is a proton at rest. uproot member access: `fE`, `fP.fX/fY/fZ`.
- `analysis/ml/data/` and `analysis/ml/model/` are git-ignored (regenerated). Plot PNGs and `metrics.txt` in `analysis/ml/plots/` are committed.
- Per-block feature order is fixed by `_BLOCK_FEATURES`; the column_stack order in `_feature_block` must match it exactly.

---

## Task 1: Vectorised Lorentz boost in `physics.py` (TDD)

**Files:**
- Modify: `analysis/ml/physics.py`
- Test: `analysis/ml/tests/test_physics.py`

**Interfaces:**
- Produces: `physics.boost(vec, beta)` — `vec` array `(..., 4)` `[E,px,py,pz]`, `beta` array `(..., 3)` 3-velocity of the target frame relative to the lab; returns the 4-vector expressed in that frame, same leading shape, last axis 4.

- [ ] **Step 1: Add failing tests** to the end of `analysis/ml/tests/test_physics.py`:

```python
def test_boost_to_rest_frame():
    # particle with m^2 = 25 - 9 = 16 -> m = 4; boosting by its own velocity
    # must bring it to rest (zero 3-momentum, energy = mass).
    v = np.array([5.0, 0.0, 0.0, 3.0])
    beta = v[1:4] / v[0]
    r = physics.boost(v, beta)
    assert r[0] == pytest.approx(4.0)
    assert np.allclose(r[1:4], 0.0, atol=1e-9)


def test_boost_zero_beta_is_identity():
    v = np.array([2.0, 1.0, 0.0, 0.0])
    r = physics.boost(v, np.zeros(3))
    assert np.allclose(r, v)


def test_boost_is_vectorised():
    v = np.array([[5.0, 0.0, 0.0, 3.0], [5.0, 0.0, 0.0, -3.0]])
    beta = v[:, 1:4] / v[:, 0:1]
    r = physics.boost(v, beta)
    assert r.shape == (2, 4)
    assert np.allclose(r[:, 1:4], 0.0, atol=1e-9)
    assert np.allclose(r[:, 0], 4.0)
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest analysis/ml/tests/test_physics.py -k boost -v`
Expected: FAIL — `AttributeError: module 'analysis.ml.physics' has no attribute 'boost'`.

- [ ] **Step 3: Add `boost` to `analysis/ml/physics.py`** (after `chi2_pairing`):

```python
def boost(vec, beta):
    """Express the 4-vector(s) `vec` ([E, px, py, pz]) in the frame moving with
    3-velocity `beta` relative to the lab. Vectorised over leading axes."""
    vec = np.asarray(vec, dtype=float)
    beta = np.asarray(beta, dtype=float)
    e = vec[..., 0]
    p = vec[..., 1:4]
    b2 = np.sum(beta * beta, axis=-1)
    safe_b2 = np.where(b2 == 0.0, 1.0, b2)
    gamma = 1.0 / np.sqrt(1.0 - b2)
    bp = np.sum(beta * p, axis=-1)
    factor = (gamma - 1.0) * bp / safe_b2 - gamma * e
    p_new = p + factor[..., None] * beta
    e_new = gamma * (e - bp)
    return np.concatenate([e_new[..., None], p_new], axis=-1)
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/python -m pytest analysis/ml/tests/test_physics.py -v`
Expected: PASS (all previous physics tests + 3 new = 11 passed).

- [ ] **Step 5: Commit**

```bash
git add analysis/ml/physics.py analysis/ml/tests/test_physics.py
git commit -m "feat: add vectorised Lorentz boost to physics"
```

---

## Task 2: Beam features in `build_features.py` (TDD)

**Files:**
- Modify: `analysis/ml/build_features.py`
- Test: `analysis/ml/tests/test_build_features.py`

**Interfaces:**
- Consumes: `physics.boost`, `physics.invariant_mass`, existing `PAIRINGS`, `shuffle_photons`, `truth_pairing_index`.
- Produces:
  - `load_beam(root_path, tree="mc", n_max=None) -> np.ndarray (N, 4)` `[E,px,py,pz]`.
  - module constant `TARGET = np.array([0.938272, 0.0, 0.0, 0.0])`.
  - `build(photons, beam, seed=SEED) -> (X (N,67), y (N,), masses (N,3,2), feature_names list[67])`; `feature_names[-1] == "beam_E"`.
  - `_feature_block(P, pairing, beam) -> (block (N,22), chi2 (N,), m_low (N,), m_high (N,))`.

- [ ] **Step 1: Update the two existing `build` tests and add beam tests** in `analysis/ml/tests/test_build_features.py`.

Replace `test_feature_matrix_shape_and_names` with:
```python
def test_feature_matrix_shape_and_names():
    photons = bf.load_photons(MC_PATH, n_max=1000)
    beam = bf.load_beam(MC_PATH, n_max=1000)
    X, y, masses, names = bf.build(photons, beam, seed=1)
    assert X.shape == (1000, 67)
    assert len(names) == 67
    assert names[-1] == "beam_E"
    assert masses.shape == (1000, 3, 2)
    assert set(np.unique(y)).issubset({0, 1, 2})
```

Replace `test_chi2_baseline_is_block_zero` with:
```python
def test_chi2_baseline_is_block_zero():
    # block 0 is the minimum-chi2 pairing by construction; its chi2 feature
    # must be <= the chi2 feature of blocks 1 and 2.
    photons = bf.load_photons(MC_PATH, n_max=2000)
    beam = bf.load_beam(MC_PATH, n_max=2000)
    X, y, masses, names = bf.build(photons, beam, seed=1)
    chi2_cols = [names.index(f"chi2_block{b}") for b in range(3)]
    c0, c1, c2 = X[:, chi2_cols[0]], X[:, chi2_cols[1]], X[:, chi2_cols[2]]
    assert np.all(c0 <= c1 + 1e-9)
    assert np.all(c0 <= c2 + 1e-9)
```

Append these new tests:
```python
def test_load_beam_shape():
    beam = bf.load_beam(MC_PATH, n_max=2000)
    assert beam.shape == (2000, 4)          # [E, px, py, pz]
    # beam is along +z: |pz| ~ E, px ~ py ~ 0
    assert np.allclose(beam[:, 1], 0.0, atol=1e-6)
    assert np.allclose(beam[:, 2], 0.0, atol=1e-6)
    assert np.allclose(beam[:, 3], beam[:, 0], atol=1e-6)


def test_beam_features_present_and_physical():
    photons = bf.load_photons(MC_PATH, n_max=3000)
    beam = bf.load_beam(MC_PATH, n_max=3000)
    X, y, masses, names = bf.build(photons, beam, seed=1)
    for b in range(3):
        cs_lo = X[:, names.index(f"cosstar_low_block{b}")]
        cs_hi = X[:, names.index(f"cosstar_high_block{b}")]
        ps_lo = X[:, names.index(f"pstar_low_block{b}")]
        ps_hi = X[:, names.index(f"pstar_high_block{b}")]
        assert np.all((cs_lo >= -1.0001) & (cs_lo <= 1.0001))
        assert np.all((cs_hi >= -1.0001) & (cs_hi <= 1.0001))
        assert np.all(ps_lo >= 0.0)
        assert np.all(ps_hi >= 0.0)
    # the global beam energy column equals the loaded beam energy
    assert np.allclose(X[:, names.index("beam_E")], beam[:, 0])
```

- [ ] **Step 2: Run to verify they fail**

Run: `.venv/bin/python -m pytest analysis/ml/tests/test_build_features.py -v`
Expected: FAIL — `load_beam` undefined and `build()` missing the `beam` argument / wrong shape.

- [ ] **Step 3: Edit `analysis/ml/build_features.py`.**

(3a) Add the target constant after the `PHOTON_BRANCHES` line (near line 15):
```python
TARGET = np.array([0.938272, 0.0, 0.0, 0.0])  # proton at rest, [E, px, py, pz]
```

(3b) Add the beam loader right after `load_photons` (after line 33):
```python
def load_beam(root_path, tree="mc", n_max=None):
    """Return the beam 4-vector per event as a (N, 4) array [E, px, py, pz]."""
    t = uproot.open(f"{root_path}:{tree}")
    v = t.arrays(["beam"], entry_stop=n_max, library="ak")["beam"]
    out = np.empty((len(v), 4), dtype=np.float64)
    out[:, 0] = np.asarray(v["fE"])
    out[:, 1] = np.asarray(v["fP"]["fX"])
    out[:, 2] = np.asarray(v["fP"]["fY"])
    out[:, 3] = np.asarray(v["fP"]["fZ"])
    return out
```

(3c) Extend `_BLOCK_FEATURES` (currently 18 names ending in `"chi2"`) by appending the four new names:
```python
_BLOCK_FEATURES = [
    "m_low", "m_high", "dm_pi0", "dm_eta",
    "asym_low", "asym_high", "theta_low", "theta_high",
    "E1", "E2", "E3", "E4", "cos_mesons",
    "pt_low", "pt_high", "beta_low", "beta_high", "chi2",
    "cosstar_low", "cosstar_high", "pstar_low", "pstar_high",
]
```

(3d) Make `_feature_names()` append the single global name. Replace the function with:
```python
def _feature_names():
    names = []
    for b in range(3):
        for f in _BLOCK_FEATURES:
            names.append("chi2_block{}".format(b) if f == "chi2" else "{}_block{}".format(f, b))
    names.append("beam_E")
    return names
```

(3e) Add a CM-kinematics helper just above `_feature_block`:
```python
def _cm_cos_pstar(meson, beta_cm):
    """cos(theta*) (vs beam +z axis) and |p*| of `meson` in the CM frame."""
    m_cm = physics.boost(meson, beta_cm)
    p3 = m_cm[:, 1:4]
    pstar = np.linalg.norm(p3, axis=-1)
    safe = np.where(pstar == 0.0, 1.0, pstar)
    cosstar = m_cm[:, 3] / safe          # pz component / |p|
    return cosstar, pstar
```

(3f) Change `_feature_block` to take `beam` and append the 4 new columns. The final `column_stack` must list the 4 new features after `chi2`:
```python
def _feature_block(P, pairing, beam):
    """Return (block (N,22), chi2 (N,), m_low (N,), m_high (N,)) for one pairing."""
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

    # CM frame of beam + target (boost is along z for this MC)
    W = beam + TARGET
    beta_cm = W[:, 1:4] / W[:, 0:1]
    csA, psA = _cm_cos_pstar(mesonA, beta_cm)
    csB, psB = _cm_cos_pstar(mesonB, beta_cm)

    m_low, m_high = np.minimum(mA, mB), np.maximum(mA, mB)
    asym_low, asym_high = sel(asymA, asymB), sel(asymB, asymA)
    th_low, th_high = sel(thA, thB), sel(thB, thA)
    pt_low, pt_high = sel(ptA, ptB), sel(ptB, ptA)
    be_low, be_high = sel(beA, beB), sel(beB, beA)
    cosstar_low, cosstar_high = sel(csA, csB), sel(csB, csA)
    pstar_low, pstar_high = sel(psA, psB), sel(psB, psA)
    cos_mes = physics.cos_angle(mesonA, mesonB)
    chi2 = physics.chi2_pairing(m_low, m_high)
    e_sorted = np.sort(P[:, :, 0], axis=1)[:, ::-1]  # (N,4) energies desc

    block = np.column_stack([
        m_low, m_high, np.abs(m_low - physics.MPI0), np.abs(m_high - physics.META),
        asym_low, asym_high, th_low, th_high,
        e_sorted[:, 0], e_sorted[:, 1], e_sorted[:, 2], e_sorted[:, 3], cos_mes,
        pt_low, pt_high, be_low, be_high, chi2,
        cosstar_low, cosstar_high, pstar_low, pstar_high,
    ])
    return block, chi2, m_low, m_high
```

(3g) Change `build` to take `beam` and append the global `beam_E` column. Replace `build`:
```python
def build(photons, beam, seed=SEED):
    """Return (X (N,67), y (N,), masses (N,3,2), feature_names list).

    X = 3 chi2-ordered blocks of 22 features each, plus a final global beam_E.
    """
    P, perm = shuffle_photons(photons, seed=seed)
    n = P.shape[0]
    blocks, chi2s, masses = [], [], []
    for pairing in PAIRINGS:
        blk, c, ml, mh = _feature_block(P, pairing, beam)
        blocks.append(blk)
        chi2s.append(c)
        masses.append(np.column_stack([ml, mh]))  # (N,2): [pi0-ish, eta-ish]
    blocks = np.stack(blocks, axis=1)   # (N,3,22)
    chi2s = np.stack(chi2s, axis=1)     # (N,3)
    masses = np.stack(masses, axis=1)   # (N,3,2)

    order = np.argsort(chi2s, axis=1)   # (N,3) ascending chi2
    rows = np.arange(n)[:, None]
    blocks_ord = blocks[rows, order]    # (N,3,22)
    masses_ord = masses[rows, order]    # (N,3,2)
    X = np.column_stack([blocks_ord.reshape(n, -1), beam[:, 0]])  # (N,67)

    truth = truth_pairing_index(perm)
    y = np.argmax(order == truth[:, None], axis=1).astype(np.int64)  # slot of truth
    return X, y, masses_ord, FEATURE_NAMES
```

- [ ] **Step 4: Run to verify they pass**

Run: `.venv/bin/python -m pytest analysis/ml/tests/ -v`
Expected: all PASS (physics + build feature tests). `explain`/`main` are not under test, so the signature change there is exercised in Task 3.

- [ ] **Step 5: Commit**

```bash
git add analysis/ml/build_features.py analysis/ml/tests/test_build_features.py
git commit -m "feat: add beam CM features (cosstar/pstar) and global beam_E"
```

---

## Task 3: Wire beam through the CLI and the `--explain` modes

**Files:**
- Modify: `analysis/ml/build_features.py` (`explain`, `main`)
- Modify: `analysis/ml/train_bdt.py` (`explain`)

**Interfaces:**
- Consumes: `load_photons`, `load_beam`, `build` (new signature), `_BLOCK_FEATURES` (22 entries).

- [ ] **Step 1: Update `explain` in `build_features.py`** to accept and use `beam`.

Change the signature line `def explain(photons, seed=SEED, n_show=3):` to:
```python
def explain(photons, beam, seed=SEED, n_show=3):
```
Change the start of the body (was `sub = photons[:n_show]` then `X, y, masses, names = build(sub, seed=seed)`):
```python
    sub = photons[:n_show]
    sub_beam = beam[:n_show]
    X, y, masses, names = build(sub, sub_beam, seed=seed)
```
Replace the `[7]` block (the `reshape(3, 18)` section) with:
```python
        print("\n[7] Feature row (67 values): 3 chi2-ordered blocks x 22 features"
              " + 1 global beam_E:")
        block = X[e][:66].reshape(3, 22)
        header = "  " + "feature".ljust(14) + "".join(f"{'block'+str(b):>9}" for b in range(3))
        print(header)
        for f_idx, fname in enumerate(_BLOCK_FEATURES):
            print("  " + _fmt_row(fname, block[:, f_idx]))
        print(f"  {'beam_E (global)':<14}{X[e][66]:>9.4f}")
```
Change the aggregate build call near the end (was `Xs, ys, _, _ = build(photons[:n_stat], seed=seed)`):
```python
    n_stat = min(len(photons), 20000)
    Xs, ys, _, _ = build(photons[:n_stat], beam[:n_stat], seed=seed)
```

- [ ] **Step 2: Update `main` in `build_features.py`** to load beam in both branches.

Replace the explain branch:
```python
    if args.explain:
        n_load = max(args.explain_events, 20000)
        print(f"Loading photons + beam from {args.input} (test mode) ...")
        photons = load_photons(args.input, n_max=n_load)
        beam = load_beam(args.input, n_max=n_load)
        explain(photons, beam, seed=args.seed, n_show=args.explain_events)
        return
```
Replace the normal branch's load + build (the `print("Loading photons ...")`, `photons = ...`, `print("Loaded ...")`, `X, y, masses, names = build(...)` lines):
```python
    print(f"Loading photons + beam from {args.input} ...")
    photons = load_photons(args.input, n_max=args.n_max)
    beam = load_beam(args.input, n_max=args.n_max)
    print(f"Loaded {len(photons)} events; building features ...")
    X, y, masses, names = build(photons, beam, seed=args.seed)
```

- [ ] **Step 3: Update `explain` in `train_bdt.py`.** Replace the two lines that load photons and build (currently `photons = bf.load_photons("simulation/eta_pi0_mc.root", n_max=n_events)` then `X, y, _, names = bf.build(photons, seed=seed)`):
```python
    photons = bf.load_photons("simulation/eta_pi0_mc.root", n_max=n_events)
    beam = bf.load_beam("simulation/eta_pi0_mc.root", n_max=n_events)
    X, y, _, names = bf.build(photons, beam, seed=seed)
```

- [ ] **Step 4: Smoke-test both explain modes**

Run:
```bash
.venv/bin/python -m analysis.ml.build_features --explain --explain-events 2
.venv/bin/python -m analysis.ml.train_bdt --explain
```
Expected: `build_features --explain` prints, in section [7], 22 feature rows including `cosstar_low/high`, `pstar_low/high`, then a `beam_E (global)` line; no error. `train_bdt --explain` prints the per-event probability table and confusion matrix (now trained on 67 features).

- [ ] **Step 5: Confirm the test suite still passes**

Run: `.venv/bin/python -m pytest analysis/ml/tests/ -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add analysis/ml/build_features.py analysis/ml/train_bdt.py
git commit -m "feat: wire beam through build_features CLI/explain and train explain"
```

---

## Task 4: Regenerate, retrain, re-evaluate

**Files:**
- Regenerates: `analysis/ml/data/features.npz` (git-ignored), `analysis/ml/model/bdt.json` (git-ignored)
- Updates (committed): `analysis/ml/plots/*.png`, `analysis/ml/plots/metrics.txt`

- [ ] **Step 1: Rebuild the full feature set (now 67-dim)**

Run: `.venv/bin/python -m analysis.ml.build_features`
Expected: `Wrote analysis/ml/data/features.npz: X=(1000000, 67), ...` and `chi2 baseline accuracy (label==0): 0.975x`.

- [ ] **Step 2: Retrain**

Run: `.venv/bin/python -m analysis.ml.train_bdt`
Expected: prints `BDT test accuracy` and `chi2 test accuracy`; rewrites `model/bdt.json` and the 3 diagnostic PNGs. Note whether any `cosstar_*`/`pstar_*`/`beam_E` feature appears in `feature_importance.png`.

- [ ] **Step 3: Re-evaluate (BDT vs chi2 + mass spectra)**

Run: `.venv/bin/python -m analysis.ml.evaluate_compare`
Expected: prints and writes `analysis/ml/plots/metrics.txt` with the new BDT accuracy, chi2 accuracy, improvement, and peak widths. Compare to the previous run (BDT 0.9808 / chi2 0.9751).

- [ ] **Step 4: Commit the updated artifacts**

```bash
git add analysis/ml/plots/training_curve.png analysis/ml/plots/feature_importance.png \
        analysis/ml/plots/confusion.png analysis/ml/plots/mass_pi0.png \
        analysis/ml/plots/mass_eta.png analysis/ml/plots/metrics.txt
git commit -m "chore: regenerate BDT diagnostics with beam features"
```

---

## Task 5: Update documentation

**Files:**
- Modify: `analysis/ml/spiegazione/01_physics.md` (document `boost`)
- Modify: `analysis/ml/spiegazione/02_build_features.md` (document `load_beam`, beam block, `beam_E`)
- Modify: `analysis/ml/spiegazione/GUIDA.md` (update results / feature count)
- Modify: `analysis/ml/README.md` and `README.md` (update headline numbers if they changed)

- [ ] **Step 1: Append a `boost` section to `analysis/ml/spiegazione/01_physics.md`:**

````markdown
---

```python
def boost(vec, beta):
    ...
    return np.concatenate([e_new[..., None], p_new], axis=-1)
```

Boost di Lorentz: esprime il 4-vettore `vec` nel sistema che si muove con
3-velocità `beta` rispetto al laboratorio. Serve per portare i mesoni nel
sistema CM (riposo di beam+target) e misurarne cos(theta*) e |p*|. `gamma` è il
fattore di Lorentz, `bp = beta·p`; `safe_b2` evita la divisione per zero quando
`beta = 0` (in quel caso la trasformazione è l'identità).
````

- [ ] **Step 2: Add a beam section to `analysis/ml/spiegazione/02_build_features.md`** after the `load_photons` section:

````markdown
## `load_beam` e le feature del fascio

`load_beam` legge il ramo `beam` (un `TLorentzVector` `(0,0,E,E)`) e ritorna
`(N,4)`. Il `TARGET` (protone a riposo) è una costante.

In `_feature_block`, dopo aver costruito i due mesoni, si calcola il sistema
CM `W = beam + target`, il suo boost `beta_cm = W_p3 / W_E`, e si portano i due
mesoni nel CM con `physics.boost`. Da lì:

- `cosstar_low/high` = cos(theta*), angolo polare del mesone rispetto all'asse
  del fascio (avanti/indietro);
- `pstar_low/high` = modulo dell'impulso nel CM.

Queste 4 colonne portano il blocco da 18 a 22 feature. In `build`, dopo i 3
blocchi ordinati per chi2 (66 colonne), si aggiunge **una** colonna globale
`beam_E` (energia del fascio): il vettore finale è di **67** feature. La massa
mancante *totale* non è usata perché è identica per le 3 combinazioni (somma dei
4 fotoni) e non discrimina il pairing.
````

- [ ] **Step 2b: Update the reshape/feature-count references** in `02_build_features.md`: search the file for `54`, `(N,54)`, and `3 × 18` / `3x18` and change them to `67`, `(N,67)`, `3 × 22 + 1` so the doc matches the code.

- [ ] **Step 3: Update results in `analysis/ml/spiegazione/GUIDA.md`** — search GUIDA.md for `54`, `18`, and `98.08` / `0.9808`. Change the feature count to 67 (3×22 + global beam_E), add the beam features (cosθ*, p*, beam_E) to the feature list, and set the BDT accuracy to the value printed in Task 4's `metrics.txt`.

- [ ] **Step 4: Update headline numbers** in `analysis/ml/README.md` and the `### analysis/ml/` paragraph of the top-level `README.md` if the BDT accuracy changed from 98.1% (use the new `metrics.txt` value).

- [ ] **Step 5: Commit**

```bash
git add analysis/ml/spiegazione/01_physics.md analysis/ml/spiegazione/02_build_features.md \
        analysis/ml/spiegazione/GUIDA.md analysis/ml/README.md README.md
git commit -m "docs: document beam features and update results"
```

---

## Done criteria

- `.venv/bin/python -m pytest analysis/ml/tests -v` is green (physics boost + beam feature tests included).
- `analysis/ml/data/features.npz` is `(1000000, 67)`; `analysis/ml/plots/metrics.txt` reports the new BDT vs chi2 accuracy.
- `build_features --explain` shows the cosstar/pstar rows and the global `beam_E`.
- Docs reflect 67 features and the new accuracy number. Whether the beam features improve, match, or barely move the accuracy, the measured number is the deliverable (a near-zero gain on this signal-only phase-space MC is a valid, reportable result, per the spec).
