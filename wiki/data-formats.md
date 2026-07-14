# Formati dati

La cosa che nessuno si ricorda a memoria: quale albero ROOT viene scritto da
quale fase, e perché il suo nome cambia lungo la catena anche quando il
contenuto no.

| albero | scritto da | contenuto |
|---|---|---|
| `h70` | il rivelatore (DAQ) | dati grezzi, fuori da questo repository |
| `h80` | `01_pre_analysis/PreAnalysis.C` | un'entry per evento: `beam`, `gammas`, `protons`, `neutrons`, `deuterons` come quadrivettori |
| `h85` | `02_event_selector/select_events.py` | come `h80`, ma solo gli eventi con più di un fotone ed esattamente un barione ricostruito |
| `reco_eta_pi0_chi2` / `reco_eta_pi0_bdt` | i due entrypoint di `03_analysis/` | `eta`, `pi0`, i loro fotoni, `missing`, `chi2`, le masse |

## `h80` — pre-analisi

Scritto da `PreAnalysis::Loop` in `01_pre_analysis/PreAnalysis.C`. I rami
principali, quelli che il resto della pipeline legge, sono quadrivettori
`ROOT::Math::PxPyPzEVector` (o vettori di essi):

```cpp
output_tree->Branch("beam",      "ROOT::Math::LorentzVector<...>", &beam);
output_tree->Branch("gammas",    "vector<ROOT::Math::LorentzVector<...>>", &gammas);
output_tree->Branch("neutrons",  "vector<ROOT::Math::LorentzVector<...>>", &neutrons);
output_tree->Branch("protons",   "vector<ROOT::Math::LorentzVector<...>>", &protons);
output_tree->Branch("deuterons", "vector<ROOT::Math::LorentzVector<...>>", &deuterons);
```

Oltre a questi, `h80` porta anche i rami di servizio usati per diagnostica
e per i cut (angoli, tempo di volo, perdita di energia, polarizzazione,
numero di run): `gamma_theta`/`gamma_phi`, `pions_theta`/`pions_phi`,
`deuterons_theta`/`deuterons_phi`, `fcharged_theta`/`fcharged_phi`/
`fcharged_beta`/`fcharged_tof`/`fcharded_de`, `Polarization`, `RunNumber`.
Un file per run: `pre_analyzed/pre_analisi_<run>.root`.

## `h85` — selezione eventi

`02_event_selector/select_events.py` legge ogni `pre_*.root`, clona
l'albero `h80` (`tree.CloneTree(0)`) e tiene solo gli eventi che soddisfano:

```python
event.gammas.size() > 1 and
event.protons.size() + event.neutrons.size() + event.deuterons.size() == 1
```

cioè più di un fotone (necessario per ricostruire due mesoni) ed esattamente
un barione di rinculo, di qualunque specie tra protone/neutrone/deutone.

Lo schema dei rami è identico a `h80` — nessuna colonna aggiunta o rimossa,
solo eventi filtrati. Il nome dell'albero cambia comunque: `CloneTree`
eredita il nome dell'albero sorgente, quindi il clone si chiamerebbe ancora
`h80` se non venisse rinominato esplicitamente:

```python
selected_tree = tree.CloneTree(0)
selected_tree.SetName(OUTPUT_TREE)   # "h85"
selected_tree.SetTitle(OUTPUT_TREE)
```

Questo è l'intero motivo per cui `h85` esiste come nome distinto: non
descrive un contenuto diverso, descrive lo stesso schema dopo un filtro,
reso riconoscibile perché altrimenti un file "selezionato" e uno
"pre-analizzato" conterrebbero entrambi un albero chiamato `h80` e
sarebbero indistinguibili senza aprire il file.

## `reco_eta_pi0_chi2` / `reco_eta_pi0_bdt` — ricostruzione

Scritti da `03_analysis/reco_core.py::run_reconstruction`, letti da
`h85` in `SELECTED_DIR`. Il nome dell'albero di output è passato come
parametro dai due entrypoint (`reconstruct_eta_pi0_chi2.py`,
`reconstruct_eta_pi0_bdt.py`) e coincide col nome del file: `reco_eta_pi0_chi2`
nel primo caso, `reco_eta_pi0_bdt` nel secondo. I rami, identici nei due
file (l'unica differenza è quali eventi sopravvivono, per via del gate BDT
nel secondo):

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

Un evento arriva a questo stadio solo se ha almeno 4 fotoni ricostruiti ed
esattamente 1 protone (mai 0, mai 2+): un evento senza protone viene
scartato, non completato con un protone fittizio a zero, perché un protone
a `(0,0,0,0)` produce una massa mancante artificiosa (~1.87 GeV contro i
~0.75 GeV di un protone vero) che porterebbe il run BDT — ma non quello
chi2 — a scartare silenziosamente proprio quegli eventi. Il requisito è
applicato identicamente a entrambi i run, prima del gate e prima
dell'accoppiamento chi2, così i due campioni restano identici tranne che
per il gate, che è l'unico punto del confronto.
