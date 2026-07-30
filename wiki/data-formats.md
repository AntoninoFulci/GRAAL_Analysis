# Data format

| albero | scritto da | contenuto |
|---|---|---|
| `h70` | rivelatore| dati grezzi, fuori da questa repository |
| `h80` | `01_pre_analysis/PreAnalysis.C` | un'entry per evento: `beam`, `gammas`, `protons`, `neutrons`, `deuterons` come quadrivettori |
| `h85` | `02_event_selector/select_events.py` | come `h80`, ma solo gli eventi selezionati dal file |
| `mc` (`<canale>_mc.root`) | `03_mc_simulation/generate_<canale>_dataset.C` | `beam`, `proton`, e i fotoni veri del canale — nome dei rami e conteggio dipendono dal canale, vedi sotto |
| `reco_eta_pi0_chi2` / `reco_eta_pi0_bdt` | i due entrypoint di `05_reconstruction/` | `eta`, `pi0`, i loro fotoni, `missing`, `chi2`, le masse |

## Lookup strip→Eγ e flussi integrati

`scripts/build_strip_energy_flux.py` crea una cartella portabile dalla farm
con quattro artefatti. La sorgente del lookup è l'albero inclusivo `h80`: per
ogni coppia osservata `(run_number, Xstrip)`, `energy_median_gev` è la mediana
di `beam.E()`; non viene fatto pooling tra run, target, tipo di fascio o
gruppo. Le informazioni manifest sono riportate in ogni CSV per mantenere la
separazione: le somme di gruppo non mescolano mai `P`/`D` né `UV`/`VIS`.

Le energie e tutti i bordi energetici sono in **GeV**. `Xstrip` deve essere un
intero nel dominio fisico **1–128**. Un bin energetico usa `[low, high)`;
soltanto il bin finale include anche il proprio bordo destro. Una strip con
lookup sotto o sopra il dominio del binning non viene assegnata implicitamente
al primo o all'ultimo bin.

### `strip_energy_lookup.csv`

Una riga per `(run, strip)` osservata in `h80`, con schema fisso:

```text
run_number,source_period,target,beam_type,group,xstrip,event_count,
energy_median_gev,energy_mad_gev,energy_min_gev,energy_max_gev,provenance
```

`provenance` è attualmente `observed`. Le quantità di energia descrivono le
entry di quella singola `(run, strip)`; `energy_mad_gev` è
`median(abs(E - median(E)))`.

### `flux_by_run_energy.csv`

Una riga per `(binning, run, bin energetico)`:

```text
binning,run_number,source_period,target,beam_type,group,
energy_low_gev,energy_high_gev,pol1,brem,pol2,
pol1_net,pol2_net,total_net,status
```

Le tre colonne raw sono somme dei rispettivi istogrammi ROOT `POL1`, `BREM` e
`POL2` delle strip assegnate al bin. La convenzione fisica corrente è:

```text
pol1_net = pol1 - brem
pol2_net = pol2 - brem
total_net = pol1_net + pol2_net
```

`status` è `invalid` se uno dei due flussi netti è negativo; la riga raw e i
valori netti negativi restano nel CSV per diagnosi.

### `flux_by_group_energy.csv`

Una riga per `(binning, target, beam_type, group, bin energetico)`:

```text
binning,target,beam_type,group,energy_low_gev,energy_high_gev,
pol1,brem,pol2,pol1_net,pol2_net,total_net,status
```

È la somma dei valori per run, senza medie. Se una run contribuente è
`invalid`, anche la corrispondente riga di gruppo rimane `invalid`, persino se
la somma finale netta risultasse positiva.

### `strip_energy_flux_qa.json` (schema v1)

Il report completo ha `schema_version: 1` e queste chiavi top-level:

```text
schema_version, inputs, thresholds, binnings,
manifest_run_count, h80_run_count, flux_run_count, lookup_strip_count,
h80, flux, missing_h80_runs, extra_h80_runs, extra_flux_runs,
malformed_flux_triplets, empty_strips, nonzero_unmapped_strips,
monotonic_inversions, mad_warnings, low_stat_warnings,
underflow_overflow, out_of_range, negative_net_errors,
run_flux_bin_count, errors, valid
```

- `inputs` riporta `preanalysis_dir`, `manifest`, `flux` e `output_dir`;
  `thresholds` riporta `min_events_per_strip`, `max_mad_gev` e
  `monotonic_tolerance_gev`; `binnings` mappa ogni nome ai suoi bordi in GeV.
- `h80` contiene `entries` e `file_count`. `flux` contiene `run_count`,
  `extra_runs`, `malformed_triplets`, `matching_keys` e
  `underflow_overflow`; le liste diagnostiche pertinenti sono replicate anche
  nelle chiavi top-level nominate sopra.
- `out_of_range` è una mappa **per binning**. Ogni valore contiene
  `below_lookup_count`, `above_lookup_count`, `below_lookup_strips`,
  `above_lookup_strips` e `raw_flux_excluded` (`pol1`, `brem`, `pol2`). È
  diagnostico: queste strip non rendono da sole `valid` falso.
- `underflow_overflow` riporta, per ogni istogramma non nullo,
  `histogram`, `underflow` e `overflow`. Anche questo è soltanto un warning:
  i due bin ROOT non entrano nelle somme e non rendono da soli `valid` falso.
- `mad_warnings` (`run_number`, `xstrip`, `energy_mad_gev`) e
  `low_stat_warnings` (`run_number`, `xstrip`, `event_count`) sono warning
  soltanto. `empty_strips`, `nonzero_unmapped_strips`,
  `monotonic_inversions` e le discrepanze di run documentano i controlli;
  gli errori strutturali sono elencati in `errors`.
- `negative_net_errors` conserva una riga diagnostica per ogni bin non valido:
  `binning`, `run_number`, `bin_index`, `energy_low_gev`, `energy_high_gev`,
  `pol1_net`, `pol2_net`. Un flusso netto negativo imposta `valid: false`,
  ma non elimina le righe CSV necessarie a investigarlo.

`valid` è vero solo quando `errors` è vuota. Il comando termina con exit `0`
per una QA valida. Exit `1` segnala una QA non valida dopo l'elaborazione
(conserva tutti e quattro gli artefatti) oppure un errore runtime: se può
scrivere nell'output richiesto, quest'ultimo lascia il QA minimo con
`schema_version`, `inputs`, `valid: false` ed `errors`. Exit `2` è invece un
errore di sintassi/uso rilevato da `argparse` (per esempio argomenti
obbligatori mancanti): avviene prima dell'elaborazione e non crea artefatti né
QA.

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
