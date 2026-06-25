# GRAAL Analysis

Codice di analisi per l'esperimento GRAAL: ricostruzione degli eventi, identificazione delle particelle e filtraggio con BDT per il canale γ p → p η π⁰.

---

## Struttura del repository

```
GRAAL_Analysis/
├── pre_analysis/
│   ├── PreAnalysis.h               # classe TTree generata da ROOT (variabili rivelatore)
│   ├── PreAnalysis.C               # logica di analisi: Loop(), AnalyzeAll()
│   ├── CutManager.h                # caricamento dinamico dei tagli grafici (TCutG)
│   └── cuts/                       # tagli TCutG per particella/periodo/dataset
├── analysis/
│   ├── select_events.py            # preselezione eventi (fotoni + barione di rinculo)
│   ├── reconstruct_2pi0.py         # γ p → p π⁰ π⁰: accoppiamento fotoni + chi2
│   ├── reconstruct_eta_pi0.py      # γ p → p η π⁰: accoppiamento + gate BDT stage-1
│   └── ml/
│       ├── physics.py              # matematica dei quadrivettori (vettorizzata, numpy)
│       ├── build_features.py       # feature 67-dim per BDT stage-2 (photon pairing)
│       ├── build_background_features.py  # feature 24-dim per BDT stage-1 (segnale/fondo)
│       ├── train_bdt.py            # BDT stage-2: multiclasse (scelta combinazione)
│       ├── train_bdt_stage1.py     # BDT stage-1: binario (segnale vs fondo)
│       ├── evaluate_compare.py     # confronto BDT vs χ² + spettri di massa
│       ├── photon_loss.py          # modello di perdita fotoni per MC di fondo
│       ├── requirements.txt
│       ├── tests/                  # 19+ test pytest (tutti verdi)
│       ├── data/                   # features.npz (generato, ignorato da git)
│       ├── model/                  # bdt.json, bdt_stage1.json (generati)
│       ├── plots/                  # figure diagnostiche
│       └── step-by-step-explaination_ita/  # documentazione dettagliata in italiano
├── simulation/
│   ├── smearing.h                       # header condiviso: SmearPhoton, SmearProton
│   ├── generate_eta_pi0_dataset.C       # segnale: γ p → p η π⁰ (MC etichettato)
│   ├── generate_pi0pi0_dataset.C        # fondo: γ p → p π⁰ π⁰  (4γ)
│   ├── generate_3pi0_dataset.C          # fondo: γ p → p 3π⁰    (6γ)
│   ├── generate_eta_2pi0_dataset.C      # fondo: γ p → p η π⁰ π⁰ (6γ)
│   ├── generate_omega_pi0_dataset.C     # fondo: γ p → p ω π⁰   (5γ)
│   ├── generate_etaprime_dataset.C      # fondo: γ p → p η'      (6γ)
│   └── cross_sections.csv              # sezioni d'urto efficaci per pesatura ibrida
├── docs/superpowers/
│   ├── specs/  2026-06-24-background-channels-mc-design.md
│   └── plans/  2026-06-24-background-channels-mc.md
└── run_pipeline.sh                 # launcher completo: MC → feature → BDT
```

---

## Pipeline completa

```
[dati raw ROOT]
      │
      ▼
1. pre_analysis/PreAnalysis.C    →  h80 trees (un file per run)
      │
      ▼
2. analysis/select_events.py     →  selected/*.root  (preselezione)
      │
      ▼
3a. simulation/generate_*.C      →  *_mc.root  (Monte Carlo segnale + 5 canali di fondo)
      │
      ├──► 3b. analysis/ml/build_background_features.py → features_stage1.npz
      │         analysis/ml/train_bdt_stage1.py         → model/bdt_stage1.json
      │
      ├──► 3c. analysis/ml/build_features.py            → data/features.npz
      │         analysis/ml/train_bdt.py                → model/bdt.json
      │
      ▼
4. analysis/reconstruct_eta_pi0.py  →  reco_eta_pi0.root
   (con gate BDT stage-1 + accoppiamento chi2/BDT stage-2)
```

### Avvio rapido (tutto in un colpo)

```bash
# pipeline completa con 1M eventi per canale
./run_pipeline.sh

# test veloce su 10k eventi
./run_pipeline.sh --nevents 10000

# salta la generazione MC (già fatta)
./run_pipeline.sh --skip-mc

# solo ri-allenamento BDT
./run_pipeline.sh --skip-mc --skip-features
```

---

## Moduli principali

### 1. PreAnalysis.h / PreAnalysis.C

Converte gli alberi grezzi `h70` del rivelatore in alberi `h80` per evento con 4-vettori ricostruiti.

Pipeline per evento:
1. fascio dal tagger (`Eg_tag_strip[0]`)
2. rivelatore centrale (`Itipo_track`): 11 = fotone, 13/14 = protone/pione (tagli grafici su Eclusc vs dE/dx)
3. rivelatore in avanti (`Iass_trf`): neutrone (TOF ≥ 12 ns), fotone (7.5–12.5 ns), protone/pione/deuterone (tagli su TOF vs ΔE)
4. ricostruzione cinematica + scrittura branch `beam`, `gammas`, `protons`, `neutrons`, `deuterons`

```bash
root -l pre_analysis/PreAnalysis.C
# poi da ROOT:
AnalyzeAll("/percorso/dati", "/percorso/output")
```

### 2. CutManager.h

Carica e organizza i tagli `TCutG` all'avvio. Chiave: `Particella → Rivelatore → RunID`. Convenzione nomi file: `{Particella}{Rivelatore}Cut_{Anno}_{Dataset}.cpp`.

### 3. select_events.py

Filtro di preselezione tra pre-analisi e ricostruzione. Tiene solo gli eventi con >1 fotone e esattamente 1 barione di rinculo.

```bash
python analysis/select_events.py
```

### 4. reconstruct_2pi0.py / reconstruct_eta_pi0.py

Accoppiamento fotoni con minimizzazione del χ²:

```
χ² = ((m₁₂ − m_meson1) / (0.08·m_meson1))² + ((m₃₄ − m_meson2) / (0.08·m_meson2))²
```

`reconstruct_eta_pi0.py` ha in più un **gate BDT stage-1**: gli eventi classificati come fondo vengono scartati prima dell'accoppiamento. Il gate si attiva automaticamente se `analysis/ml/model/bdt_stage1.json` esiste; se non c'è il codice prosegue normalmente.

```bash
python analysis/reconstruct_2pi0.py
python analysis/reconstruct_eta_pi0.py
```

---

## Generatori Monte Carlo (`simulation/`)

Tutti i generatori usano `TGenPhaseSpace` di ROOT e applicano lo smearing gaussiano del rivelatore tramite `smearing.h` (`SmearPhoton`, `SmearProton`).

| File | Canale | Nγ veri | Output | Soglia [GeV] |
|------|--------|---------|--------|--------------|
| `generate_eta_pi0_dataset.C` | γ p → p η π⁰ (segnale) | 4 | `eta_pi0_mc.root` | 0.926 |
| `generate_pi0pi0_dataset.C` | γ p → p π⁰ π⁰ | 4 | `pi0pi0_mc.root` | 0.309 |
| `generate_3pi0_dataset.C` | γ p → p 3π⁰ | 6 | `3pi0_mc.root` | 0.492 |
| `generate_eta_2pi0_dataset.C` | γ p → p η π⁰ π⁰ | 6 | `eta_2pi0_mc.root` | 1.174 |
| `generate_omega_pi0_dataset.C` | γ p → p ω π⁰ (ω→γπ⁰) | 5 | `omega_pi0_mc.root` | 1.366 |
| `generate_etaprime_dataset.C` | γ p → p η' (η'→η π⁰ π⁰) | 6 | `etaprime_mc.root` | 1.446 |

```bash
root -l 'simulation/generate_eta_pi0_dataset.C(1000000)'
# oppure con lo script wrapper:
./run_pipeline.sh --nevents 1000000
```

I canali di fondo **mimano il segnale**: con 6γ veri, perderne 2 dà esattamente 4γ nel rivelatore, identici a prima vista al segnale.

---

## Pipeline ML (`analysis/ml/`)

### Stage-1 BDT — classificazione segnale/fondo

BDT binario (XGBoost `binary:logistic`) che opera su **24 feature globali** dell'evento: masse invarianti di tutte le coppie γγ, conteggi vicino a m_π⁰/m_η, best χ², massa mancante, cinematica del protone, numero di fotoni osservati. Viene allenato su segnale + 5 canali di fondo con pesatura proporzionale alla sezione d'urto efficace σ_eff.

```bash
# costruisce le feature di stage-1
python -m analysis.ml.build_background_features \
    --signal        simulation/eta_pi0_mc.root \
    --backgrounds   simulation/pi0pi0_mc.root simulation/3pi0_mc.root \
                    simulation/eta_2pi0_mc.root simulation/omega_pi0_mc.root \
                    simulation/etaprime_mc.root \
    --cs-csv        simulation/cross_sections.csv \
    --output        features_stage1.npz

# allena il BDT stage-1
python -m analysis.ml.train_bdt_stage1 \
    --features features_stage1.npz \
    --out-dir  analysis/ml/model
```

Output: `model/bdt_stage1.json`, `model/stage1_threshold.txt`, 3 plot diagnostici, `model/stage1_metrics.txt`.

### Stage-2 BDT — scelta della combinazione fotoni

BDT multiclasse (3 classi) che decide quale delle 3 combinazioni γγ–γγ sia quella giusta (η vs π⁰). Usa **67 feature** per evento: 3 blocchi × 22 feature cinetiche (masse, asimmetrie, angoli, boost, cos(θ*) nel CM) + energia del fascio.

```bash
python -m analysis.ml.build_features
python -m analysis.ml.train_bdt
python -m analysis.ml.evaluate_compare
```

Risultati su 1M eventi (test set non visto):

| Metodo | Accuratezza pairing |
|--------|---------------------|
| χ² (baseline) | 97.51 % |
| BDT stage-2 | 98.33 % |

### Modello di perdita fotoni (`photon_loss.py`)

Modella l'inefficienza del rivelatore come probabilità di perdita indipendente per fotone:

```
P_loss(E, θ) = 1 − (1 − P_threshold(E)) × (1 − P_acceptance(θ))
```

entrambi i termini sono funzioni sigmoidi. Usato per stimare la frazione di sopravvivenza di ciascun canale di fondo e calcolare σ_eff in `cross_sections.csv`.

```bash
# stima la sopravvivenza per un canale a 6γ con default LossParams
python -m analysis.ml.photon_loss --n-photons 6 --n-keep 4
```

### Test

```bash
python -m pytest analysis/ml/tests/ -v
# 19 test, tutti verdi
```

---

## Sezioni d'urto (pesatura BDT stage-1)

File `simulation/cross_sections.csv`:

| Canale | σ_ref [μb] | p_survival | σ_eff [μb] | Fonte |
|--------|-----------|------------|------------|-------|
| π⁰ π⁰ | 4.5 | 0.82 | 3.69 | CB-ELSA/TAPS, Sarantsev+05 |
| 3π⁰ | 1.8 | 0.61 | 1.10 | CB-ELSA/TAPS, Thoma+08 |
| η π⁰ π⁰ | 0.6 | 0.55 | 0.33 | CB-ELSA, Kashevarov+17 |
| ω π⁰ | 1.2 | 0.58 | 0.70 | SAPHIR, Barth+03 |
| η' | 0.35 | 0.52 | 0.18 | CB-ELSA, Crede+09 |

---

## Prerequisiti

- ROOT 6.x con `TGenPhaseSpace`
- Python ≥ 3.9
- `pip install xgboost uproot awkward scikit-learn numpy matplotlib pytest`
- Dati GRAAL (alberi ROOT con tree name `h70`)

---

## Formato degli alberi di output

### `h80` (pre-analisi)

| Branch | Tipo | Contenuto |
|--------|------|-----------|
| `beam` | `PxPyPzEVector` | 4-vettore fascio |
| `gammas` | `vector<PxPyPzEVector>` | fotoni |
| `protons` | `vector<PxPyPzEVector>` | protoni |
| `neutrons` | `vector<PxPyPzEVector>` | neutroni |
| `deuterons` | `vector<PxPyPzEVector>` | deuteroni |
| `Polarization` | `Int_t` | stato di polarizzazione |
| `RunNumber` | `Int_t` | numero di run |

### `reco_eta_pi0` (ricostruzione finale)

| Branch | Tipo | Contenuto |
|--------|------|-----------|
| `chi2` | `Float_t` | χ² della combinazione scelta |
| `eta_mass`, `pi0_mass` | `Float_t` | masse ricostruite [GeV] |
| `beam`, `proton`, `eta`, `pi0` | `TLorentzVector` | 4-vettori |
| `eta_gamma1/2`, `pi0_gamma1/2` | `TLorentzVector` | fotoni delle coppie |
| `missing` | `TLorentzVector` | 4-vettore mancante |

---

## Documentazione dettagliata

Spiegazione passo-passo in italiano (teoria + codice):

```
analysis/ml/step-by-step-explaination_ita/
├── GUIDA.md            # visione d'insieme + come si usa + risultati
├── README.md           # ordine di lettura
├── 01_physics.md       # physics.py: quadrivettori vettorizzati
├── 02_build_features.md # build_features.py: feature 67-dim stage-2
├── 03_train_bdt.md     # train_bdt.py: allenamento XGBoost
└── 04_evaluate_compare.md # evaluate_compare.py: BDT vs chi2
```

Specifica di design e piano di implementazione: `docs/superpowers/`.
