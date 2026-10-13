# Piano 07 — distribuzioni delle variabili di training

Implementato il 13 ottobre 2026. Verifica iniziale tramite graphify sul grafo
esistente (2.480 nodi), poi lettura diretta: `Stage1Dataset`, contratto comune,
`TrainingResult` e reporting erano presenti; l'export delle 26 distribuzioni
in ROOT non era implementato. Nessun retraining dei dati reali.

## Consegna

Output finali in `results/training-features-20261013/final/vis/`:

- `training_features.root`: 104 TH1 di yield e 104 TH1 di shape;
- `training_features.pdf`: 27 pagine, copertina e 26 feature;
- `training_features.json`: dizionario, impronte e audit completo, identico
  al JSON incorporato in `TNamed("training_features_metadata", ...)` nel ROOT.

La prima esecuzione di verifica resta in `results/training-features-20261013/vis/`;
la directory `final/vis/` contiene gli output della versione consegnata.

Comando effettivamente eseguito per la consegna:

```bash
MPLCONFIGDIR=/private/tmp/graal-plan07-mpl python3 -m bdt_training.plot_training_features \
  --features test_data/vis/bdt/features_stage1.npz \
  --out-dir results/training-features-20261013/final/vis
```

## Inventario verificato

Input `test_data/vis/bdt/features_stage1.npz`, 177.475.174 byte.
SHA256 `c846711503d11c649827a95ffbb3c1beb2e49faebee43c8d02a75acd1ec3a474`.
`X`: (1.628.169, 26), float32; `y`: (1.628.169,), int8;
`w`: (1.628.169,), float32. Nomi e ordine coincidono con il contratto
`eta_pi0`. Profilo registrato VIS, range 0.9313–1.1 GeV, prior 0.5,
beam reweighting attivo. Nessun NaN/infinito nel campione effettivo.

| Classe | Eventi | Σw | Σw² |
|---|---:|---:|---:|
| Segnale | 288.654 | 814084.5425986052 | 2590827.848842415 |
| Fondo | 1.339.515 | 814084.5349374724 | 1313437.88826661 |

Pesi non unitari; alcuni sono zero e gli eventi corrispondenti restano nei
conteggi. Le somme sono pesi di training, non sezioni d'urto misurate.

Il modello storico in `test_data/vis/bdt/artifacts/stage1/` ha provenienza
compatibile per nomi/ipotesi/profilo, ma non contiene legame crittografico col
NPZ né indici del training: nessuna attribuzione retroattiva certificata.

## Metodo e scelte

- Dizionario fisico condiviso in `00_common/stage1/feature_descriptions.py`,
  nomi derivati da `features.feature_names(hypothesis)`, entrambe le ipotesi
  supportate. Formule, unità, tipo, famiglia, dominio fisico e bordi espliciti.
- Finestre diagnostiche fisse e comuni fra classi/profili, indipendenti da
  tutte le righe dei dataset. Bin centrati sugli interi per contatori;
  bordo superiore fisico incluso per coseni. Code in under/overflow, mai
  eliminate; NaN contabilizzati separatamente con eventi, Σw e Σw².
- Yield conservati; shape scritte come copie con somma unitaria includendo
  flow, senza dividere per larghezza bin. Se somma finita non positiva,
  shape indefinita e assente. Errori shape a normalizzazione fissata.
- Istogrammi calcolati una sola volta e condivisi da ROOT/PDF. Float64 per
  accumulazione; TH1 errori `sqrt(Σw²)` e numero di eventi esplicito.
- Output preparati in directory temporanea; pubblicazione rifiuta file
  esistenti, senza sovrascrivere evidenze o bundle runtime.
- Hook training esplicito e opzionale, prima del fit; PyROOT non diventa
  requisito dei normali comandi di training. Output in directory distinta.
- Hash dei moduli realmente caricati; Git non richiesto a runtime.
  Revisione di base `f568c6b`; impronte registrano sorgenti non ancora committati,
  inclusa validazione dataset modificata dal piano parallelo.

`missing_mass` delle feature usa `beam + target - proton`, distinto dalla
missing mass del rinculo. `eta_pi0_angle` è un coseno, non radianti.
`total_pt_gamma` è somma scalare dei pT.

## Limiti dei dati e decisioni

Non trovato NPZ UV locale: nessuna distribuzione UV reale prodotta o simulata.
La separazione UV/VIS con bordi comuni è verificata su fixture di test.
NPZ senza indici persistiti di split, identità canale per evento, seed training,
configurazione photon-loss o versione storica delle formule: report limita
categorie a profilo/classe sull'intero dataset e dichiara assenze. Nessuno split
casuale viene presentato come quello storico. Non applicati tagli aggiuntivi.
Le masse e formule documentano il contratto comune corrente; non certificano
retroattivamente il codice che generò il NPZ. Il punto 09 potrà ampliare queste
categorie. Decisioni non bloccanti previste dal piano 07.

## File di questo intervento

- `00_common/stage1/feature_descriptions.py` — dizionario fisico;
- `04_bdt_training/training/feature_reporting.py` — validazione, accumulazione,
  ROOT, PDF e metadati;
- `04_bdt_training/plot_training_features.py` — CLI senza retraining;
- `04_bdt_training/train_bdt_stage1.py` — hook opzionale;
- `04_bdt_training/tests/test_training_feature_root.py` — contratti e round-trip;
- `wiki/04-training-artifacts.md` — uso, struttura, normalizzazione e limiti;
- piano 07 e questa relazione.

Lavoro svolto nel checkout condiviso con proprietà disgiunta dei file; nessun
reset, stash o commit di modifiche altrui. Lasciati all'altro agente dataset,
profili energetici, launcher e ricostruzione. Indice generale dei piani non
modificato perché già interessato da lavoro parallelo.

## Verifiche

TDD: 13 test inizialmente falliti per exporter assente, poi passati; due test
inizialmente falliti per hook assente, poi passati; due regressioni di
portabilità riprodotte e corrette (Git assente e layout di installazione).

Comando mirato finale: **55 passati**.

```bash
python3 -m pytest -q 04_bdt_training/tests/test_training_feature_root.py \
  04_bdt_training/tests/test_stage1_reporting.py \
  04_bdt_training/tests/test_stage1_dataset.py \
  04_bdt_training/tests/test_stage1_training.py tests/test_stage1_contracts.py
```

Test d'integrazione su fixture piccola: training con/senza diagnostica produce
modello JSON, soglia e provenance identici byte per byte. Round-trip ROOT reale
con pesi non unitari, contatori, feature costante, zero/signed weights nella
rappresentazione intermedia, NaN e overflow. Input invalidi/schema errato
rifiutati prima della pubblicazione.

Sul VIS reale: 104 yield e 104 shape riaperti e confrontati contro NPZ;
conteggi e Σw conservati, residuo assoluto massimo Σw=0;
residuo massimo Σw²=1.4314427971839905e-6 (relativo <1e-11).
Ogni shape ha integrale uno includendo flow. Nessun evento nel flow sulle
finestre scelte per questo dataset. JSON ROOT/sidecar identici.
Tutte le 27 pagine renderizzate, contact sheet controllato; copertina, χ² e
coseno finale ispezionati ad alta risoluzione. Render finale confrontato con
quello verificato visivamente.

Review finale indipendente: nessun rilievo Critical/Important su formule,
normalizzazione, serializzazione o provenienza. Guard ROOT nei test opzionali
corretto; comando salvato qui. Suggerimenti non bloccanti rimasti: automatizzare
anche il round-trip ROOT dei pesi signed/zero e il rollback su errore PDF;
il reviewer ha verificato direttamente conservazione entries/errori nel ROOT.

Suite generale finale `python3 -m pytest -q`: **889 passati, 2 falliti,
1 warning**, in 113.64 s. I due fallimenti sono in file non modificati da
questo piano e riguardano mock non aggiornati alla nuova firma del piano
energetico in parallelo:

- `05_reconstruction/tests/test_cli_contracts.py::test_eta_pi0_bdt_vis_profile_checks_gate_and_sets_exact_energy_range`:
  `_Gate.check_profile() got an unexpected keyword argument 'energy_range_gev'`;
- `05_reconstruction/tests/test_cli_options.py::test_bdt_profile_mismatch_stops_before_reconstruction`:
  `_RejectingGate.check_profile() got an unexpected keyword argument 'energy_range_gev'`.

Il warning esterno proviene da
`07_observable_extraction/tests/test_gate_comparison.py::test_closed_gate_writes_full_coverage_report`
(legenda senza artisti in `compare_gate.py`). Nessuno dei test del piano 07
fallisce. Nessuna correzione applicata ai file dell'altro agente.

Una prima suite, prima della correzione di portabilità e mentre l'altro agente
lavorava, aveva 878 passati e 8 falliti: ai due sopra si aggiungevano
`tests/test_run_pipeline.py::test_run_calls_preflight_prepare_plan_and_execute_in_order`,
`test_two_test_campaign_runs_replace_results_without_touching_production` e
le quattro parametrizzazioni `[n]`, `[]`, `[maybe]`, `[None]` di
`test_confirmation_refusal_preserves_test_results_and_skips_execution`.
Errore comune: keyword `energy_binnings` non accettata dai mock. Questi sei
casi passano nella suite finale, dopo modifiche concorrenti esterne al piano 07.

Impronte degli output finali:

| File | Byte | SHA256 |
|---|---:|---|
| ROOT | 315727 | `6f757700ed353ae5cd3cf883880282b65c4a114259541407196dee65406fdc5b` |
| PDF | 339826 | `65bdde0122b950c0e2dc2e8295e0086cef4c9aef0a95dbe8798e147b3ea0ffc0` |
| JSON | 120434 | `2fbe9db8b32b7e62395093951085faab5b10fc8416f2327805199f51cb5e1e15` |

Hash sorgenti incorporati verificati contro i moduli correnti; tutti coincidenti.
`git diff --check` senza errori. Nessun commit o merge effettuato nel checkout
condiviso. Log e ledger del solo piano 07 conservati in
`.superpowers/sdd/07-variabili-allenamento-root/`; memoria graphify aggiornata
con percorso e risultati, senza ricostruire il grafo condiviso.
