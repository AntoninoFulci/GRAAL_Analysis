# Data format

| albero | scritto da | contenuto |
|---|---|---|
| `h70` | rivelatore| dati grezzi, fuori da questa repository |
| `h80` | `01_pre_analysis/PreAnalysis.C` | un'entry per evento: `beam`, `gammas`, `protons`, `neutrons`, `deuterons` come quadrivettori |
| `h85` | `02_event_selector/select_events.py` | come `h80`, ma solo gli eventi selezionati dal file |
| `mc` (`<canale>_mc.root`) | `03_mc_simulation/generate_<canale>_dataset.C` | `beam`, `proton`, e i fotoni veri del canale — nome dei rami e conteggio dipendono dal canale, vedi sotto |
| `reco_eta_pi0_chi2` / `reco_eta_pi0_bdt` | i due entrypoint di `05_reconstruction/` | `eta`, `pi0`, i loro fotoni, `missing`, `chi2`, le masse |

## `h80` — pre-analisi

Scritto da `PreAnalysis::Loop` in `01_pre_analysis/PreAnalysis.C`. 
I branch principali sono quadrivettori `ROOT::Math::PxPyPzEVector` (o vettori di essi):

```cpp
output_tree->Branch("beam",      "ROOT::Math::LorentzVector<...>", &beam);
output_tree->Branch("gammas",    "vector<ROOT::Math::LorentzVector<...>>", &gammas);
output_tree->Branch("neutrons",  "vector<ROOT::Math::LorentzVector<...>>", &neutrons);
output_tree->Branch("protons",   "vector<ROOT::Math::LorentzVector<...>>", &protons);
output_tree->Branch("deuterons", "vector<ROOT::Math::LorentzVector<...>>", &deuterons);
```

Oltre a questi, `h80` porta anche i rami di servizio usati per diagnostica e per i cut (angoli, tempo di volo, perdita di energia, polarizzazione, numero di run): 
- `gamma_theta`/`gamma_phi`
- `pions_theta`/`pions_phi`
- `deuterons_theta`/`deuterons_phi`
- `fcharged_theta`/`fcharged_phi`/ `fcharged_beta`/`fcharged_tof`/`fcharded_de`
- `Polarization`
- `RunNumber`.

## `h85` — selezione eventi

`02_event_selector/select_events.py` legge ogni `pre_*.root`, clona l'albero `h80` (`tree.CloneTree(0)`) e tiene solo gli eventi che soddisfano la condizione nel file.

Attualmente c'è solo questa condizione.
Successivamente verrà cambiata con altre.

```python
event.gammas.size() > 1 and
event.fcharged_theta.size() == 1
```

cioè più di un fotone (necessario per ricostruire due mesoni) ed esattamente una traccia carica forward (il barione di rinculo come lo vede il rivelatore forward; un rinculo neutro non produce una traccia carica e non è contato).

Lo schema dei rami è identico a `h80` — nessuna colonna aggiunta o rimossa, solo eventi filtrati. 
Il nome dell'albero cambia comunque: `CloneTree` eredita il nome dell'albero sorgente, quindi il clone si chiamerebbe ancora `h80` se non venisse rinominato esplicitamente:

```python
selected_tree = tree.CloneTree(0)
selected_tree.SetName(OUTPUT_TREE)   # "h85"
selected_tree.SetTitle(OUTPUT_TREE)
```

Questo è l'intero motivo per cui `h85` esiste come nome distinto: non descrive un contenuto diverso, descrive lo stesso schema dopo un filtro, reso riconoscibile perché altrimenti un file "selezionato" e uno "pre-analizzato" conterrebbero entrambi un albero chiamato `h80` e sarebbero indistinguibili senza aprire il file.

## `mc` — i nove file `<canale>_mc.root`

Ogni generatore (`03_mc_simulation/generate_<canale>_dataset.C`) scrive un albero `mc` con `beam` e `proton` come `TLorentzVector`, più i fotoni veri del canale. 
Il **numero** di fotoni non è lo stesso per tutti i canali — dipende da quanti mesoni lo stato finale prodotto contiene e in cosa decadono — e per questo il layout dei rami segue due convenzioni diverse:

**Rami nominati.** Solo `eta_pi0` (il segnale): sempre esattamente 4 fotoni, con un nome che dice a quale genitore appartengono.

```cpp
tree->Branch("eta_gamma1", &eta_gamma1);
tree->Branch("eta_gamma2", &eta_gamma2);
tree->Branch("pi0_gamma1", &pi0_gamma1);
tree->Branch("pi0_gamma2", &pi0_gamma2);
```

`build_background_features.py::load_photons` riconosce questo caso da `channel.photon_branches` nel registry, e li carica per nome.

**Rami `*_true` (solo `eta_pi0`).** 
`generate_eta_pi0_dataset.C` scrive, accanto ai quadrivettori smearati sopra, gli stessi quadrivettori **prima** dello smearing:
- `eta_gamma1_true`
- `eta_gamma2_true`
- `pi0_gamma1_true`
- `pi0_gamma2_true`
- `proton_true`
- `beam_true`.

Servono solo alla validazione del fit cinematico (`validate_kinematic_fit.py`, vedi [Fit cinematico](05-reconstruction-kinematic-fit)): il calcolo degli pull richiede di confrontare il fittato con la verità del generatore, che senza questi rami non sarebbe recuperabile a partire dal solo MC smearato. Gli altri canali di fondo non li hanno — non serve la loro verità, solo il loro chi2 del fit per lo studio di reiezione.

**Rami `g0..gN` + `n_true_gamma`.** 
Per tutti gli altri canali il numero di fotoni varia, e il file stesso dichiara quanti ce ne sono con un ramo scalare `n_true_gamma/I`, letto a runtime invece che assunto:

```cpp
int n_true_gamma = 8;
tree->Branch("g0",&g0); tree->Branch("g1",&g1); /* ... */ tree->Branch("g7",&g7);
tree->Branch("n_true_gamma", &n_true_gamma, "n_true_gamma/I");
```

| canale | rami | `n_true_gamma` |
|---|---|---|
| `eta_pi0` | `eta_gamma1`, `eta_gamma2`, `pi0_gamma1`, `pi0_gamma2` | (nominati, sempre 4) |
| `pi0pi0` | `g0..g3` | 4 |
| `omega_pi0` | `g0..g4` | 5 |
| `3pi0` | `g0..g5` | 6 |
| `eta_2pi0` | `g0..g5` | 6 |
| `etaprime` | `g0..g5` | 6 |
| `eta_via_3pi0` | `g0..g5` | 6 |
| `4pi0` | `g0..g7` | **8** |
| `eta_pi0_via_3pi0` | `g0..g7` | **8** |

`4pi0` ed `eta_pi0_via_3pi0` sono gli unici due file a 8 fotoni.
Prima del gate a 4 fotoni stage-1, ognuno di questi passa per il modello di perdita fotoni (`04_bdt_training/photon_loss.py`), che tiene solo gli eventi in cui **esattamente 4** dei fotoni veri sopravvivono (vedi [03 — Simulazione MC](03-mc-simulation)).

## `reco_eta_pi0_chi2` / `reco_eta_pi0_bdt` — ricostruzione

Scritti da `05_reconstruction/reco_core.py::run_reconstruction`, letti da `h85` in `SELECTED_DIR`.
Il nome dell'albero di output è passato come parametro dai due entrypoint (`reconstruct_eta_pi0_chi2.py`, `reconstruct_eta_pi0_bdt.py`) e coincide col nome del file.
I rami, identici nei due file (l'unica differenza è quali eventi sopravvivono, per via del gate BDT nel secondo):

```cpp
chi2/F
eta_mass/F, pi0_mass/F

beam,   TLorentzVector   // fascio
target, TLorentzVector   // protone bersaglio, fermo
proton, TLorentzVector   // barione di rinculo ricostruito
neutron,TLorentzVector   // (0,0,0,0) se non c'era un neutrone nell'evento

eta,        TLorentzVector   // somma dei due fotoni assegnati all'eta
eta_gamma1, TLorentzVector
eta_gamma2, TLorentzVector

pi0,        TLorentzVector   // somma dei due fotoni assegnati al pi0
pi0_gamma1, TLorentzVector
pi0_gamma2, TLorentzVector

missing, TLorentzVector      // (beam + target) - (eta + pi0)
```

**Rami del fit cinematico**, creati solo quando il fit è attivo (default).

```cpp
eta_fit,        TLorentzVector   // somma dei due fotoni fittati dell'eta
pi0_fit,        TLorentzVector   // somma dei due fotoni fittati del pi0
proton_fit,     TLorentzVector   // protone fittato

eta_fit_gamma1, TLorentzVector
eta_fit_gamma2, TLorentzVector
pi0_fit_gamma1, TLorentzVector
pi0_fit_gamma2, TLorentzVector

fit_chi2/F        // chi2 del fit, ndf = 6
fit_ndf/I         // sempre 6
fit_converged/I   // 0/1
```

Con il fit attivo, la selezione finale dell'evento è la sua confidence level (`--fit-cl`, default 0.01), non più la massa mancante.

Un evento arriva a questo stadio solo se ha almeno 4 fotoni ricostruiti ed esattamente 1 protone (mai 0, mai 2+): un evento senza protone viene scartato, non completato con un protone fittizio a zero, perché un protone a `(0,0,0,0)` produce una massa mancante artificiosa (~1.87 GeV contro i ~0.75 GeV di un protone vero) che porterebbe il run BDT — ma non quello chi2 — a scartare silenziosamente proprio quegli eventi. Il requisito è applicato identicamente a entrambi i run, prima del gate e prima dell'accoppiamento chi2, così i due campioni restano identici tranne che per il gate, che è l'unico punto del confronto.
