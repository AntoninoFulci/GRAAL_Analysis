# Design: Background Channels MC + Two-Stage BDT Pipeline

**Date:** 2026-06-24  
**Branch:** main  
**Status:** Approved

---

## Context

Current MC generates only signal `γp → p η π0` (4γ + p, flat phase space). The BDT is a 3-class pairing classifier trained purely on signal — it has never seen background. In real GRAAL data, background channels with the same observed topology (4γ + p) contaminate the sample. This design adds competing background channels to the MC and introduces a two-stage BDT pipeline: stage 1 rejects background, stage 2 picks the correct photon pairing.

---

## Architecture

### Current pipeline

```
generate_eta_pi0_dataset.C → eta_pi0_mc.root → build_features.py → features.npz → train_bdt.py → bdt.json
```

### New pipeline

```
generate_eta_pi0_dataset.C    (unchanged — signal)
generate_pi0pi0_dataset.C     (new)
generate_3pi0_dataset.C       (new)
generate_eta_2pi0_dataset.C   (new)
generate_omega_pi0_dataset.C  (new)
generate_etaprime_dataset.C   (new)
        ↓  (6 ROOT files — all photons, no loss in C++)
build_background_features.py
  → apply photon loss model (Python)
  → discard events not ending with exactly 4γ
  → compute ~25 global features
  → assign label (0=signal, 1=background)
  → apply sample_weight (σ × P_survival per channel)
        ↓
  features_stage1.npz → train_bdt_stage1.py → bdt_stage1.json

  (stage 2 pipeline unchanged)
  build_features.py → features.npz → train_bdt.py → bdt_stage2.json
```

### Inference

```
event (4γ + p + Ebeam)
  → stage1 features (~25)
  → bdt_stage1.predict_proba()
      ├─ P(signal) < threshold → reject
      └─ P(signal) ≥ threshold → stage2 features (67) → bdt_stage2 → pairing 0/1/2
```

---

## Section 1: MC Generators

All generators follow the same structure as the existing signal generator: `TGenPhaseSpace`, Gaussian smearing, `TLorentzVector` branches. Photon loss is **not** applied in C++ — all true photons are written to the tree.

### Shared header: `simulation/smearing.h`

Extracts `SmearPhoton()` and `SmearProton()` from the existing signal generator. All `.C` files include this header. Smearing parameters are identical across all channels:
- Photons: 10% σ_E/E, 5° σ_θ, 3° σ_φ
- Proton: 4% σ_p/p, 3° σ_θ, 2° σ_φ

### Beam energy range

All channels use the beam energy range from their own threshold up to 1.55 GeV (same upper limit as signal). Channels with threshold below signal (π0π0, 3π0) start from their own lower threshold to maximize statistics.

| Channel | Threshold (GeV) | Beam range (GeV) |
|---|---|---|
| η π0 (signal) | 0.931 | 0.931 – 1.550 |
| π0π0 | 0.309 | 0.309 – 1.550 |
| 3π0 | 0.492 | 0.492 – 1.550 |
| η π0π0 | 1.174 | 1.174 – 1.550 |
| ω π0 | 1.366 | 1.366 – 1.550 |
| η' (→ η π0π0) | 1.446 | 1.446 – 1.550 |

### Decay chains

| Channel | Phase space | Decay | Photons in tree |
|---|---|---|---|
| π0π0 | `TGenPhaseSpace(W, 3: π0,π0,p)` | each π0→γγ | 4γ |
| 3π0 | `TGenPhaseSpace(W, 4: π0,π0,π0,p)` | each π0→γγ | 6γ |
| η π0π0 | `TGenPhaseSpace(W, 4: η,π0,π0,p)` | η→γγ, each π0→γγ | 6γ |
| ω π0 | `TGenPhaseSpace(W, 3: ω,π0,p)` → ω→γπ0 | π0→γγ ×2, ω direct γ | 5γ |
| η' | `TGenPhaseSpace(W, 2: η',p)` → η'→ηπ0π0 | η→γγ, each π0→γγ | 6γ |

For ω: only the radiative decay ω→γπ0 (BR 8.28%) is simulated since it produces a real photon in the final state. The ω→γπ0 sub-decay is implemented as a sequential `TGenPhaseSpace`: first generate (ω, π0, p) from the beam, then decay ω→(γ, π0) and each π0→(γ,γ).

For η': only the η'→ηπ0π0 decay mode (BR 22.8%) is simulated. The effective branching ratio entering the loss model is BR(η'→ηπ0π0) × BR(η→γγ) = 0.228 × 0.394 ≈ 9%, already accounted for in `cross_sections.csv`.

### TTree branch naming convention

Background generators write branches `g0` through `gN` (photon index), `proton`, `beam`, and `n_true_gamma` (true photon count before loss). The signal generator keeps its existing branch names (`eta_gamma1`, `eta_gamma2`, `pi0_gamma1`, `pi0_gamma2`) and is not modified. `build_background_features.py` uses a channel-aware loader: one path for the signal tree, one for background trees.

---

## Section 2: Photon Loss Model (`analysis/ml/photon_loss.py`)

Applied in Python after loading the ROOT tree. Each photon is independently tested for loss; events with exactly 4 surviving photons are kept.

### Model

```
P_loss(E, θ) = 1 - (1 - P_threshold(E)) × (1 - P_acceptance(θ))

P_threshold(E)   = sigmoid(-(E - E_thr) / σ_E)
P_acceptance(θ)  = sigmoid((|θ - π/2| - θ_acc) / σ_θ)
```

### Default parameters (GRAAL-motivated)

| Parameter | Value | Meaning |
|---|---|---|
| `E_thr` | 0.050 GeV | photon detection threshold |
| `sigma_E` | 0.020 GeV | energy transition width |
| `theta_acc` | 25° (0.436 rad) | forward angular acceptance cap |
| `sigma_theta` | 5° (0.087 rad) | acceptance edge width |

All parameters are configurable via a `LossParams` dataclass — no hardcoded values.

### Per-event procedure

```python
def apply_loss(photons, params, rng):
    surviving = []
    for p in photons:
        E, theta = p.E, p.theta()
        if rng.uniform() >= p_loss(E, theta, params):
            surviving.append(p)
    return surviving if len(surviving) == 4 else None
```

Channels with N_γ = 4 (π0π0) still pass through this function — their loss probability is non-zero for very soft or very forward photons, keeping the model self-consistent.

### Output

Returns `(N_survived, 4, 4)` numpy array (same shape as `load_photons()` in `build_features.py`) — compatible with stage 2 without modification.

---

## Section 3: Stage 1 Features (`build_background_features.py`)

Global event features — do not depend on knowing the correct pairing.

### Feature list (~25 total)

**Block A — γγ invariant masses (C(4,2)=6 pairs):**
- `m_gg_01`, `m_gg_02`, `m_gg_03`, `m_gg_12`, `m_gg_13`, `m_gg_23`
- `n_pairs_near_pi0`: pairs with |m_gg − m_π0| < 30 MeV
- `n_pairs_near_eta`: pairs with |m_gg − m_η| < 60 MeV
- `best_chi2_pi0eta`: best χ² over all 3 pairings for the (η, π0) hypothesis

**Block B — Global kinematics:**
- `E_beam` (tagger-smeared)
- `E_tot_gamma`: sum of 4γ energies
- `E_proton`
- `missing_mass_sq`: M² = (beam + target − proton − ΣP_γ)²
- `missing_px`, `missing_py`, `missing_pz`
- `pt_imbalance`: |Σ p_T| over all final-state particles

**Block C — Distributions:**
- `E_max_gamma`, `E_min_gamma`, `E_rms_gamma`
- `cos_theta_proton_cm`: proton cosine in CM frame
- `m_4gamma`: invariant mass of all 4 photons combined
- `m_2gamma_best_pi0`: mass of pair closest to m_π0
- `m_2gamma_best_eta`: mass of pair closest to m_η

### Labels and weights

- `y = 0`: signal (η π0)
- `y = 1`: any background (binary classifier)

Sample weights from `simulation/cross_sections.csv`:

| Channel | σ_ref (μb @ 1.3 GeV) | P_survival | σ_eff |
|---|---|---|---|
| η π0 | 1.5 | 1.00 | 1.50 |
| π0π0 | 12.0 | 1.00 | 12.00 |
| 3π0 | 6.0 | 0.08 | 0.48 |
| η π0π0 | 0.5 | 0.08 | 0.04 |
| ω π0 | 0.6 | 0.15 | 0.09 |
| η' | 0.2 | 0.05 | 0.01 |

`sample_weight[i] = σ_eff[channel_i] / σ_eff[signal]`. The CSV is the single source of truth for weights — regenerating MC does not require changing Python code.

**Note:** `P_survival` values in the CSV are estimates based on the default `LossParams`. If `LossParams` is changed, `P_survival` must be re-estimated (run `photon_loss.py --estimate-survival` which samples the loss model and prints updated values). The CSV includes a header comment recording the `LossParams` used to compute the current values.

---

## Section 4: Stage 1 BDT (`train_bdt_stage1.py`)

Binary XGBoost classifier: signal (0) vs background (1).

```python
model = xgb.XGBClassifier(
    objective="binary:logistic",
    eval_metric="auc",
    n_estimators=400, max_depth=5, learning_rate=0.05,
    subsample=0.8, colsample_bytree=0.8,
    early_stopping_rounds=25,
    random_state=42, n_jobs=-1)
```

Split: 60/20/20 train/val/test (same as stage 2).

### Diagnostic outputs

- `plots/roc_stage1.png`: ROC curve with 95% signal efficiency operating point marked
- `plots/score_stage1.png`: P(signal) distribution for signal and each background channel separately
- `plots/feature_importance_stage1.png`: top-20 feature importance (gain)
- `plots/training_curve_stage1.png`: train/val AUC vs boosting round

Operating threshold is chosen manually from the ROC plot and saved to `analysis/ml/model/stage1_threshold.txt` (single float). `reconstruct_eta_pi0.py` reads this file at startup; the CLI `--stage1-threshold` argument overrides it.

---

## Section 5: Inference Pipeline

`analysis/reconstruct_eta_pi0.py` updated to load both models and apply them in sequence:

```python
# Stage 1
feats_s1 = compute_stage1_features(photons, proton, beam)
p_signal = bdt_stage1.predict_proba(feats_s1)[:, 0]
mask = p_signal >= STAGE1_THRESHOLD  # CLI arg, default 0.5

# Stage 2 (only on passing events)
feats_s2 = build_features(photons[mask], beam[mask])  # existing 67-dim
pairing = bdt_stage2.predict(feats_s2)
```

`STAGE1_THRESHOLD` is a CLI argument — tunable after inspecting the ROC.

---

## File Manifest

| File | Status |
|---|---|
| `simulation/smearing.h` | New — shared smearing functions |
| `simulation/generate_pi0pi0_dataset.C` | New |
| `simulation/generate_3pi0_dataset.C` | New |
| `simulation/generate_eta_2pi0_dataset.C` | New |
| `simulation/generate_omega_pi0_dataset.C` | New |
| `simulation/generate_etaprime_dataset.C` | New |
| `simulation/cross_sections.csv` | New — σ_ref and P_survival per channel |
| `analysis/ml/photon_loss.py` | New — energy/angle dependent loss model |
| `analysis/ml/build_background_features.py` | New — merge + loss + features + weights |
| `analysis/ml/train_bdt_stage1.py` | New — binary signal/background BDT |
| `analysis/reconstruct_eta_pi0.py` | Modified — adds stage 1 gate |
| `simulation/generate_eta_pi0_dataset.C` | Unchanged |
| `analysis/ml/build_features.py` | Unchanged |
| `analysis/ml/train_bdt.py` | Unchanged (= stage 2) |

---

## Cross-Section Sources

| Channel | Primary reference |
|---|---|
| γp → p π0π0 | CB-ELSA/TAPS (Sarantsev et al.); MAMI-B (Zehr et al. 2012) |
| γp → p 3π0 | CB-ELSA/TAPS (Thoma et al. 2008, EPJ A 36) |
| γp → p η π0π0 | CB-ELSA/TAPS (Kashevarov et al.) |
| γp → p ω π0 | SAPHIR (Barth et al.); CB-ELSA; PDG for BR(ω→γπ0)=8.28% |
| γp → p η' | CB-ELSA (Crede et al. 2009); PDG for BR(η'→ηπ0π0)=22.8% |

SAID (GWU photoproduction database) and MAID (Mainz) provide parametric fits for intermediate Eγ values where binned data is sparse.
