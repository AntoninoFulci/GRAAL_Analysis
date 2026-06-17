# Guida allo studio BDT per il photon pairing (γ p → p η π⁰)

Questo documento serve a **(1) usare** il codice e **(2) spiegare passo passo**
cosa è stato fatto e perché, in modo da poterlo presentare.

---

## Parte 1 — Come si usa

### 1.1 Il problema in una frase

Nella reazione γ p → p η π⁰ i due mesoni decadono ciascuno in due fotoni
(η → γγ, π⁰ → γγ). Nel rivelatore vediamo **4 fotoni** ma non sappiamo quale
coppia viene dall'η e quale dal π⁰. Le combinazioni possibili sono **3**:

```
(γ1 γ2)(γ3 γ4)      (γ1 γ3)(γ2 γ4)      (γ1 γ4)(γ2 γ3)
```

Solo una è quella giusta. Scegliere la combinazione corretta è un
*combinatorial assignment problem*. Il metodo classico è il **χ²**; qui lo
confrontiamo con una **BDT (Boosted Decision Tree, XGBoost)**.

### 1.2 Installazione

Dalla cartella radice del progetto:

```bash
python3 -m venv .venv
.venv/bin/pip install -r analysis/ml/requirements.txt
```

Servono: `xgboost`, `uproot`, `awkward`, `scikit-learn`, `numpy`,
`matplotlib`, `pytest`. (`uproot` legge i file `.root` senza bisogno di ROOT.)

### 1.3 Esecuzione (3 passi)

```bash
# 1. costruisce le feature dal Monte Carlo etichettato
.venv/bin/python -m analysis.ml.build_features
#    -> analysis/ml/data/features.npz

# 2. allena la BDT
.venv/bin/python -m analysis.ml.train_bdt
#    -> analysis/ml/model/bdt.json  +  plot diagnostici

# 3. confronta BDT vs χ² e produce gli spettri di massa
.venv/bin/python -m analysis.ml.evaluate_compare
#    -> analysis/ml/plots/metrics.txt  +  mass_pi0.png, mass_eta.png
```

Per provare velocemente su un sottoinsieme:

```bash
.venv/bin/python -m analysis.ml.build_features --n-max 20000 --output analysis/ml/data/prova.npz
```

### 1.4 Output prodotti

| File | Contenuto |
|------|-----------|
| `data/features.npz` | matrice feature `X` (N×54), label `y`, masse, nomi feature |
| `model/bdt.json` | modello XGBoost allenato |
| `plots/training_curve.png` | curva di apprendimento (train vs validation) |
| `plots/feature_importance.png` | importanza delle feature (gain) |
| `plots/confusion.png` | matrice di confusione della BDT |
| `plots/mass_pi0.png`, `plots/mass_eta.png` | spettri di massa η/π⁰: truth vs χ² vs BDT |
| `plots/metrics.txt` | numeri di sintesi (accuratezza BDT vs χ², larghezza dei picchi) |

### 1.5 Test

```bash
.venv/bin/python -m pytest analysis/ml/tests/ -v
```

---

## Parte 2 — Cosa è stato fatto, passo passo

### Passo 0 — Il dataset Monte Carlo (già esistente)

Il file `simulation/generate_eta_pi0_dataset.C` genera 1.000.000 di eventi
γ p → p η π⁰ con `TGenPhaseSpace`, fa decadere η e π⁰ in due fotoni ciascuno, e
applica uno **smearing gaussiano** che imita la risoluzione del rivelatore
(energia dei fotoni ~10%, angoli pochi gradi). Salva sia le quantità "vere"
(truth) sia quelle "misurate" (smeared).

**Perché è importante:** essendo simulazione, sappiamo *con certezza* quali
fotoni vengono dall'η e quali dal π⁰. Questa è l'etichetta (label) che permette
l'apprendimento supervisionato. Senza truth non potremmo allenare nulla.

Output: `simulation/eta_pi0_mc.root`, albero `mc`, con i 4 fotoni
`eta_gamma1`, `eta_gamma2`, `pi0_gamma1`, `pi0_gamma2`.

### Passo 1 — Lettura dei fotoni (`build_features.py`, `load_photons`)

Leggiamo i 4 quadrivettori smeared di ogni evento in un array numpy di forma
`(N, 4, 4)`: N eventi × 4 fotoni × 4 componenti `[E, px, py, pz]`. Per
convenzione i fotoni 0,1 sono quelli dell'η e 2,3 quelli del π⁰ (lo sappiamo dal
truth).

### Passo 2 — Mescolamento (shuffle) per evitare il "barare"

Se lasciassimo i fotoni nell'ordine `[η, η, π⁰, π⁰]`, il modello imparerebbe la
risposta dalla **posizione**, non dalla fisica. Quindi per ogni evento
**permutiamo casualmente** i 4 fotoni (`shuffle_photons`, seed fisso per
riproducibilità). Teniamo traccia della permutazione per sapere, *a posteriori*,
qual era la combinazione vera.

Verifica fatta: prima dell'ordinamento la combinazione vera cade su ciascuna
delle 3 posizioni con probabilità ~1/3 → **nessun leakage posizionale**.

### Passo 3 — Le 3 combinazioni e l'etichetta vera (`truth_pairing_index`)

Per ogni evento costruiamo le 3 combinazioni disgiunte. La combinazione **vera**
è quella che mette insieme i due fotoni dell'η in una coppia e i due del π⁰
nell'altra. `truth_pairing_index` la individua.

### Passo 4 — Le feature fisiche (`_feature_block`)

Per ogni combinazione costruiamo le quantità fisiche discriminanti. All'interno
di ogni coppia ordiniamo per massa (coppia leggera = "low" ≈ π⁰, coppia pesante
= "high" ≈ η) per togliere ambiguità di permutazione. **18 feature per
combinazione**:

| Feature | Significato fisico |
|---------|--------------------|
| `m_low`, `m_high` | masse invarianti delle due coppie γγ |
| `dm_pi0`, `dm_eta` | distanza dalle masse nominali: \|m_low − m_π⁰\|, \|m_high − m_η\| |
| `asym_low`, `asym_high` | asimmetria energetica \|E1−E2\|/(E1+E2) (i decadimenti veri sono più simmetrici) |
| `theta_low`, `theta_high` | angolo di apertura tra i 2 fotoni (legato alla massa: m² ≈ E1·E2·(1−cosθ)) |
| `E1..E4` | energie dei 4 fotoni ordinate |
| `cos_mesons` | coseno dell'angolo tra i due mesoni ricostruiti |
| `pt_low`, `pt_high` | impulso trasverso dei mesoni |
| `beta_low`, `beta_high` | boost β = \|p\|/E dei mesoni |
| `chi2` | il χ² classico della combinazione (usato come feature) |

Tutte derivano dagli stessi quadrivettori (coerenza). Sono esattamente le
feature suggerite dall'analisi HEP standard: massa, distanza dalle masse
nominali, asimmetria energetica, angoli, boost.

### Passo 5 — L'idea chiave: ordinare le 3 combinazioni per χ² (`build`)

Questo è il punto più importante del design.

Il **χ²** misura quanto le masse ricostruite si avvicinano a quelle nominali:

```
χ² = ((m_low − m_π⁰)/(0.08·m_π⁰))²  +  ((m_high − m_η)/(0.08·m_η))²
```

dove 0.08 = risoluzione di massa dell'8%. Il metodo classico sceglie la
combinazione con **χ² minimo**.

Noi **ordiniamo le 3 combinazioni per χ² crescente** e le concateniamo in un
unico vettore di `3 × 18 = 54` feature. Conseguenza elegante:

- il **blocco 0** è sempre la scelta del χ² (χ² minimo);
- l'**etichetta** `y` ∈ {0,1,2} è la posizione in cui finisce la combinazione
  vera dopo l'ordinamento.

Così la BDT impara una domanda precisa: *"la scelta del χ² (blocco 0) è giusta,
oppure devo correggerla scegliendo il blocco 1 o 2?"* Il χ² diventa il baseline
da battere, codificato direttamente nel problema: **accuratezza del χ² =
frazione di eventi con `y = 0`**.

### Passo 6 — Allenamento della BDT (`train_bdt.py`)

Un `XGBClassifier` multiclasse (`multi:softprob`, 3 classi):

- split train / validation / test (stratificato, seed fisso);
- iperparametri: 400 alberi, profondità 5, learning rate 0.05, subsample 0.8,
  early stopping sulla validation;
- niente scaling (gli alberi sono invarianti di scala);
- salva il modello e i plot diagnostici (curva di training, feature importance,
  matrice di confusione).

### Passo 7 — Confronto BDT vs χ² (`evaluate_compare.py`)

Sullo **stesso test set** non visto in allenamento:

- accuratezza di pairing: BDT vs χ² (= sempre blocco 0);
- spettri di massa η e π⁰ ricostruiti con la combinazione scelta da truth / χ² /
  BDT, con larghezza del picco e fondo combinatorio;
- scrive `metrics.txt`.

---

## Parte 3 — Risultati e interpretazione

Su 1.000.000 di eventi (200.000 nel test set non visto):

| Metodo | Accuratezza di pairing |
|--------|------------------------|
| χ² (baseline) | **97.51 %** |
| BDT (XGBoost) | **98.08 %** |

- La BDT **migliora di +0.57 punti** assoluti, recuperando circa **un quarto**
  degli errori del χ².
- Le **larghezze dei picchi** di massa η/π⁰ sono praticamente identiche: la BDT
  corregge i mis-pairing nelle code, non la risoluzione del nucleo del picco.

### Il finding da spiegare

Il guadagno è **modesto perché su questo Monte Carlo il χ² è già quasi
ottimale**. Motivo: le masse di η (0.548 GeV) e π⁰ (0.135 GeV) sono ben separate
rispetto allo smearing del 10%, quindi la combinazione giusta ha quasi sempre il
χ² più piccolo. Questo è un risultato **valido e interessante di per sé**: su
eventi puliti a 4 fotoni il machine learning aggiunge poco rispetto al χ².

### Limiti e prossimo passo

Questo MC è **idealizzato**: esattamente 4 fotoni, niente fondo, niente
splitoff, niente fotoni persi. Nei dati reali del GRAAL il problema combinatorio
è molto più difficile (multiplicità di fotoni variabile, cluster spuri, fondo).
È lì che ci si aspetta il vero vantaggio della BDT. La pipeline è già pronta:
basta darle in pasto un dataset più realistico (o i dati reali con
truth-matching parziale) per misurare il guadagno in quel regime.

---

## Appendice — Mappa dei file

```
analysis/ml/
├── physics.py            # matematica dei quadrivettori (massa, angoli, β, χ²) — vettorizzata
├── build_features.py     # lettura MC, shuffle, 3 combinazioni, feature 54-dim, etichetta + CLI
├── train_bdt.py          # allenamento XGBoost + plot diagnostici
├── evaluate_compare.py   # confronto BDT vs χ² + spettri di massa
├── requirements.txt      # dipendenze
├── README.md             # sintesi breve
├── GUIDA.md              # questo documento
├── tests/                # test (14, tutti verdi)
├── data/                 # features.npz (generato, git-ignored)
├── model/                # bdt.json (generato, git-ignored)
└── plots/                # figure + metrics.txt

simulation/
└── generate_eta_pi0_dataset.C   # generatore MC etichettato

docs/superpowers/
├── specs/  ...-design.md         # specifica di design
└── plans/  ...-bdt-study.md      # piano di implementazione
```
