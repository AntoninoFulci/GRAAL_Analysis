# Guida allo studio BDT per γ p → p η π⁰

Questo documento serve a **(1) usare** il codice e **(2) spiegare passo passo** cosa è stato fatto e perché.

---

## Parte 1 — Il problema fisico

### 1.1 Il canale e il problema combinatorio (stage-2)

Nella reazione γ p → p η π⁰ i due mesoni decadono ciascuno in due fotoni
(η → γγ, π⁰ → γγ). Nel rivelatore vediamo **4 fotoni** ma non sappiamo quale
coppia viene dall'η e quale dal π⁰. Le combinazioni possibili sono **3**:

```
(γ1 γ2)(γ3 γ4)      (γ1 γ3)(γ2 γ4)      (γ1 γ4)(γ2 γ3)
```

Il metodo classico è il **χ²**; noi lo confrontiamo con una **BDT stage-2** (multiclasse, 3 classi).

### 1.2 Il problema del fondo (stage-1)

Nei dati reali esistono **canali concorrenti** che mimano il segnale: canali con più fotoni veri (6 o 5) di cui alcune particelle vengono perse nel rivelatore, producendo esattamente 4 fotoni rilevati, identici a prima vista al segnale. I canali modellati sono:

| Canale | Nγ veri | Come imita il segnale |
|--------|---------|----------------------|
| γ p → p π⁰ π⁰ | 4 | diretto — stessa topologia |
| γ p → p 3π⁰ | 6 | perde 2γ → 4γ |
| γ p → p η π⁰ π⁰ | 6 | perde 2γ → 4γ |
| γ p → p ω π⁰ (ω→γπ⁰) | 5 | perde 1γ → 4γ |
| γ p → p η' (η'→η π⁰ π⁰) | 6 | perde 2γ → 4γ |

La **BDT stage-1** (binaria, segnale vs fondo) filtra gli eventi prima dell'accoppiamento.

---

## Parte 2 — Come si usa

### 2.1 Installazione

```bash
python3 -m venv .venv
.venv/bin/pip install -r analysis/ml/requirements.txt
# pacchetti: xgboost, uproot, awkward, scikit-learn, numpy, matplotlib, pytest
```

### 2.2 Pipeline completa (consigliato)

```bash
# dalla radice del progetto
./run_pipeline.sh --nevents 1000000

# per un test veloce
./run_pipeline.sh --nevents 10000
```

Lo script esegue in sequenza:
1. Genera il MC ROOT per tutti e 6 i canali (segnale + 5 fondi)
2. Costruisce le feature stage-1 e allena la BDT stage-1
3. *(opzionale)* allena la BDT stage-2

### 2.3 Esecuzione manuale passo per passo

#### Generazione MC

```bash
# segnale
root -l 'simulation/generate_eta_pi0_dataset.C(1000000)'

# canali di fondo
root -l 'simulation/generate_pi0pi0_dataset.C(1000000)'
root -l 'simulation/generate_3pi0_dataset.C(1000000)'
root -l 'simulation/generate_eta_2pi0_dataset.C(1000000)'
root -l 'simulation/generate_omega_pi0_dataset.C(1000000)'
root -l 'simulation/generate_etaprime_dataset.C(1000000)'
```

#### BDT stage-1 (segnale vs fondo)

```bash
# costruisce le 24 feature globali
python -m analysis.ml.build_background_features \
    --signal      simulation/eta_pi0_mc.root \
    --backgrounds simulation/pi0pi0_mc.root simulation/3pi0_mc.root \
                  simulation/eta_2pi0_mc.root simulation/omega_pi0_mc.root \
                  simulation/etaprime_mc.root \
    --cs-csv      simulation/cross_sections.csv \
    --output      features_stage1.npz

# allena e salva il modello
python -m analysis.ml.train_bdt_stage1 \
    --features features_stage1.npz \
    --out-dir  analysis/ml/model
```

#### BDT stage-2 (scelta combinazione fotoni)

```bash
python -m analysis.ml.build_features
#    -> analysis/ml/data/features.npz

python -m analysis.ml.train_bdt
#    -> analysis/ml/model/bdt.json  +  plot diagnostici

python -m analysis.ml.evaluate_compare
#    -> analysis/ml/plots/metrics.txt  +  mass_pi0.png, mass_eta.png
```

### 2.4 Ricostruzione con gate stage-1

```bash
python analysis/reconstruct_eta_pi0.py
# Il gate BDT stage-1 si attiva automaticamente se model/bdt_stage1.json esiste.
# Se non esiste, procede senza il gate.
```

### 2.5 Output prodotti

| File | Contenuto |
|------|-----------|
| `features_stage1.npz` | X (N×24), y (0=fondo/1=segnale), w (pesi sezione d'urto) |
| `model/bdt_stage1.json` | modello XGBoost stage-1 |
| `model/stage1_threshold.txt` | soglia ottimale (F1 max su validation set) |
| `model/stage1_metrics.txt` | AUC, precisione, recall, F1 |
| `model/stage1_roc.png` | curva ROC |
| `model/stage1_feature_importance.png` | importanza delle 24 feature |
| `model/stage1_score_dist.png` | distribuzione score segnale vs fondo |
| `data/features.npz` | X (N×67), y, masse, nomi feature (stage-2) |
| `model/bdt.json` | modello XGBoost stage-2 |
| `plots/training_curve.png` | curva di apprendimento (train vs val) |
| `plots/feature_importance.png` | importanza feature (stage-2) |
| `plots/confusion.png` | matrice di confusione |
| `plots/mass_pi0.png`, `plots/mass_eta.png` | spettri di massa: truth vs χ² vs BDT |
| `plots/metrics.txt` | accuratezza BDT vs χ², larghezze dei picchi |

### 2.6 Test

```bash
python -m pytest analysis/ml/tests/ -v
# 19 test, tutti verdi
```

### 2.7 Modalità spiegazione (`--explain`)

```bash
# walkthrough della costruzione delle feature stage-2
python -m analysis.ml.build_features --explain
python -m analysis.ml.build_features --explain --explain-events 5

# walkthrough della decisione BDT stage-2
python -m analysis.ml.train_bdt --explain
```

---

## Parte 3 — Cosa è stato fatto, passo passo

### Passo 0 — Dataset Monte Carlo segnale

`simulation/generate_eta_pi0_dataset.C` genera eventi γ p → p η π⁰ con `TGenPhaseSpace`, decadimento η,π⁰ → γγ, smearing gaussiano (σ_E/E = 10%, σ_θ = 5°, σ_φ = 3° per fotoni; σ_p/p = 4% per il protone).

**Perché:** conoscendo la truth si può etichettare ogni evento e allenare in modo supervisionato.

Output: `simulation/eta_pi0_mc.root`, albero `mc`, branch `eta_gamma1/2`, `pi0_gamma1/2`, `beam`, `proton`.

### Passo 0b — Dataset Monte Carlo dei canali di fondo

Cinque nuovi generatori in `simulation/`, tutti basati sullo stesso header `smearing.h`. Ogni generatore usa `TGenPhaseSpace` in cascata per simulare i decadimenti intermedi (es. ω→γπ⁰, η'→ηπ⁰π⁰).

Le sezioni d'urto di riferimento vengono da misure sperimentali (CB-ELSA/TAPS, SAPHIR, CB-ELSA) e moltiplicati per la probabilità di sopravvivenza p_survival calcolata con il modello `photon_loss.py`.

### Passo 0c — Modello di perdita fotoni (`photon_loss.py`)

P_loss(E, θ) = 1 − (1 − P_threshold(E)) × (1 − P_acceptance(θ))

dove entrambi i termini sono sigmoidi con parametri calibrati sull'accettanza di GRAAL. Serve per capire che frazione degli eventi a 6γ veri arriva a 4γ osservati, e quindi quanto "peso" dare ai canali di fondo nel training.

```python
from analysis.ml.photon_loss import LossParams, estimate_survival
p = estimate_survival(Es, thetas, LossParams(), n_keep=4)
```

### Passo 1 — Feature stage-1 (`build_background_features.py`)

24 feature globali (non assumono alcun accoppiamento):

| # | Feature | Significato |
|---|---------|-------------|
| 0–14 | `m_gg_ij` | masse invarianti di tutte le coppie γγ (fino a 15) |
| 15 | `n_pairs_near_pi0` | quante coppie con \|m−m_π⁰\| < 40 MeV |
| 16 | `n_pairs_near_eta` | quante coppie con \|m−m_η\| < 80 MeV |
| 17 | `best_chi2_eta_pi0` | best χ² assumendo η+π⁰ tra i primi 4 fotoni |
| 18 | `missing_mass` | massa del sistema mancante (beam+p_target − protone) |
| 19 | `missing_E` | energia mancante |
| 20 | `total_gamma_E` | somma energie fotoni osservati |
| 21 | `n_gamma_obs` | numero fotoni osservati |
| 22 | `proton_p` | modulo impulso protone |
| 23 | `proton_costheta` | cos(θ) protone |

**Pesatura ibrida:** ogni canale di fondo riceve sample_weight = σ_eff / N_eventi, in modo che la BDT veda la composizione realistica del fondo.

### Passo 2 — Allenamento BDT stage-1 (`train_bdt_stage1.py`)

`XGBClassifier(binary:logistic)` con:
- 300 alberi, profondità 5, learning rate 0.05, subsample 0.8
- early stopping su AUC del validation set (20%)
- soglia ottimale trovata massimizzando F1 sul validation set
- salva modello, soglia, metriche e 3 plot diagnostici

### Passo 3 — Gate nella ricostruzione (`reconstruct_eta_pi0.py`)

```python
# All'inizio dello script
_load_stage1()   # carica bdt_stage1.json + stage1_threshold.txt

# Nel loop eventi, prima di tutto il resto
if chain.gammas.size() >= 4:
    if not _stage1_pass(...):
        continue   # evento scartato: classificato come fondo
```

Se il modello non esiste il gate è disabilitato → backward compatible.

### Passo 4 — Feature stage-2 (`build_features.py`, 67 feature)

Per ogni evento, 3 combinazioni γγ–γγ, ordinate per χ² crescente.
Per ogni combinazione: 22 feature cinetiche (masse, χ², asimmetrie, angoli, β, cos(θ*) nel CM, |p*| nel CM). Concatenate → 66 + 1 colonna globale `beam_E` = **67 feature**.

L'**etichetta** y ∈ {0,1,2} è la posizione in cui si trova la combinazione vera dopo l'ordinamento. y=0 → il χ² ha ragione (caso più frequente, ~97.5%).

### Passo 5 — Allenamento BDT stage-2 (`train_bdt.py`)

`XGBClassifier(multi:softprob, 3 classi)`:
- 400 alberi, profondità 5, learning rate 0.05, subsample 0.8
- early stopping sulla validation
- niente scaling (gli alberi sono invarianti di scala)

### Passo 6 — Confronto BDT vs χ² (`evaluate_compare.py`)

Stesso test set non visto: accuratezza di pairing, spettri di massa η e π⁰, larghezza dei picchi, numero di errori corretti.

---

## Parte 4 — Risultati e interpretazione

### BDT stage-2 (scelta combinazione, 4γ ideali)

Su 1.000.000 di eventi (200.000 nel test set):

| Metodo | Accuratezza di pairing |
|--------|------------------------|
| χ² (baseline) | **97.51 %** |
| BDT stage-2 | **98.33 %** |

Guadagno: +0.82 punti assoluti, ~1/3 degli errori del χ² recuperati.
Le feature del fascio (cos(θ*), |p*| nel CM + beam_E) hanno alzato la BDT dal 98.1% al 98.3%.

**Perché il guadagno è contenuto:** su MC idealizzato a 4γ puliti il χ² è già quasi ottimale (η e π⁰ hanno masse ben separate rispetto allo smearing del 10%). Il vero vantaggio della BDT emerge con molteplicità variabile, fotoni spuri e fondo — che è esattamente il regime dei dati reali dopo il gate stage-1.

### BDT stage-1 (segnale vs fondo)

Il gate stage-1 rigetta eventi con topologia incompatibile con γ p → p η π⁰. La BDT usa le sezioni d'urto fisiche per pesare i contributi relativi dei canali di fondo, dando maggiore importanza ai fondi con σ_eff più alta (π⁰ π⁰ è il dominante con 3.69 μb).

---

## Parte 5 — Mappa dei file

```
analysis/ml/
├── physics.py                    # quadrivettori vettorizzati (massa, angoli, β, χ², boost)
├── build_features.py             # MC segnale → feature 67-dim + etichette (stage-2)
├── build_background_features.py  # segnale+fondi → feature 24-dim + pesi (stage-1)
├── photon_loss.py                # modello sigmoid P_loss(E,θ), stima p_survival
├── train_bdt.py                  # XGBoost multiclasse stage-2 + plot diagnostici
├── train_bdt_stage1.py           # XGBoost binario stage-1 + soglia F1-ottima
├── evaluate_compare.py           # confronto BDT vs χ² + spettri di massa
├── requirements.txt
├── tests/
│   ├── test_physics.py           # 5 test
│   ├── test_build_features.py    # 9 test
│   ├── test_photon_loss.py       # 9 test
│   └── test_build_background_features.py  # 10 test
├── data/                         # features.npz, features_stage1.npz (generati)
├── model/                        # bdt.json, bdt_stage1.json (generati)
└── plots/

simulation/
├── smearing.h                    # SmearPhoton, SmearProton (inline, condivisi)
├── generate_eta_pi0_dataset.C    # segnale (truth + smearing)
├── generate_pi0pi0_dataset.C     # fondo 4γ
├── generate_3pi0_dataset.C       # fondo 6γ
├── generate_eta_2pi0_dataset.C   # fondo 6γ
├── generate_omega_pi0_dataset.C  # fondo 5γ (ω→γπ⁰)
├── generate_etaprime_dataset.C   # fondo 6γ (η'→ηπ⁰π⁰)
└── cross_sections.csv            # σ_ref, p_survival, σ_eff per 5 canali

docs/superpowers/
├── specs/2026-06-24-background-channels-mc-design.md   # specifica di design
└── plans/2026-06-24-background-channels-mc.md          # piano di implementazione

run_pipeline.sh                   # launcher completo (MC + feature + BDT)
```
