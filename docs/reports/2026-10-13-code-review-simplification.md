# Review del codice e semplificazione — 13 ottobre 2026

Review dello stato corrente del workspace, comprese modifiche preesistenti e
migrazione degli osservabili in `08_observable_extraction`. Nessun commit,
reset o rigenerazione dei risultati di produzione.

## Follow-up risolto: eventi senza tagger

**P1 — `01_pre_analysis/PreAnalysis.C`, assegnazione di `beam` e `tagger_strip`.**
Il codice leggeva `Eg_tag_strip[0]` e `Xstrip[0]` anche con `Ncstrip == 0`.
ROOT conserva i valori precedenti nei buffer delle array a lunghezza variabile:
l'evento senza tag poteva quindi ricevere energia e strip dell'evento precedente.

Riproduzione sul fixture `test_data/raw/1998_uv/run1321.root`:

- 52.553 eventi con `Ncstrip == 0`, su 585.613;
- entry 20: un tag, energia `1.4767746925354004`, strip `93`;
- entry 21: zero tag, stessi valori ancora presenti nei buffer.

L'utente ha autorizzato lo scarto con conteggio. Ora `Ncstrip` viene letto e
validato prima dei payload: zero causa uno scarto, valori fuori `0..128`
causano errore prima della lettura nei buffer. Sono controllati anche tipi e
count-leaf dei rami tagger. I tag multipli mantengono la scelta del primo elemento.

Il contatore totale della catena viene stampato come `skipped_no_tagger` e
persistito nel ROOT come `TParameter<Long64_t>` chiamato
`preanalysis_skipped_no_tagger`. Anche un input interamente senza tag produce
h80 vuoto e contatore corretto. Identità degli eventi conservati invariata.
Gli h80 e prodotti derivati esistenti richiedono rigenerazione per applicare
la selezione; nessun dato di produzione è stato rigenerato in questa review.

## Difetti corretti

| Priorità | Codice | Difetto e risultato |
|---|---|---|
| P1 | `theory/src/graal_theory/figure4_comparison.py` | La sostituzione cancellava il bundle precedente prima del rename finale. Ora conserva un backup e lo ripristina se la pubblicazione fallisce. |
| P1 | `06_calibration/build_strip_energy_flux.py` | La verifica degli input avveniva dopo la sostituzione del ROOT. Ora avviene prima della pubblicazione; un'identità cambiata lascia intatti output e QA precedenti. |
| P2 | `06_calibration/build_strip_energy_flux.py` | Provenienza limitata ai file nella directory principale, mentre gli scanner leggono ricorsivamente. Inventario e controllo finale includono ora anche gli h80 nelle sottodirectory. |
| P2 | `04_bdt_training/grid_search_stage1.py` | Tutti i training potevano fallire senza errore finale, lasciando artefatti vecchi apparentemente utilizzabili. Ora la ricerca segnala fallimento, senza pubblicare risultati. |
| P2 | `04_bdt_training/training/feature_reporting.py` | Diagnostica dichiarava sempre indisponibili canali, split e varianti del rivelatore, anche nei dataset v2. Ora riporta i metadati realmente persistiti, senza inferire parametri mancanti. |
| P2 | `08_observable_extraction/beam_asymmetry.py` | Metadati della likelihood dipendevano dal successo del fit ratio. Ora conteggi e metadati di esposizione sono indipendenti dalla sua stimabilità; aggregati senza esposizione nel bin conservano la convenzione zero. Stimatori invariati. |
| P2 | `scripts/audit_bdt_backgrounds.py` | `hashlib.file_digest` non esiste in Python 3.10, versione supportata. Hash SHA-256 ora calcolato a blocchi, con identico formato del risultato. |
| P2 | `05_reconstruction/core/kinematic_fit.py` | Controllo delle forme eseguito dopo l'indicizzazione: input malformati causavano `IndexError`. Ora restituiscono `invalid_input` prima della conversione. |
| P2 | `05_reconstruction/core/kinematic_fit.py` | Budget di iterazioni nullo causava `UnboundLocalError`. Budget non positivo ora rifiutato con `ValueError`. |

Ogni correzione ha una regressione osservata fallire prima dell'intervento.
I test esistenti non sono stati indeboliti o riscritti per accettare le modifiche.

## Semplificazioni senza cambio di comportamento

- `00_common/stage1/artifacts.py`: usa l'ordine delle chiavi già definito dal
  contratto, eliminando due elenchi duplicati; validazione e byte JSON invariati.
- `04_bdt_training/photon_loss.py`: un solo campionamento delle sopravvivenze;
  confronto vecchio/nuovo su 50 casi conserva array e stato esatto del generatore casuale.
- `04_bdt_training/training/stage1_training.py`: percorso degli split identificati
  lineare dopo il ritorno anticipato del caso legacy.
- `05_reconstruction/runtime/reco_core.py`: unico blocco per registrare gli scarti
  e aggiornare i contatori prima di ritornare.
- `theory/src/graal_theory/amplitudes/production_loops.py`: controllo di
  convergenza condiviso, con stesso ordine delle operazioni e stessi errori.
- `08_observable_extraction/io/root_input.py`: quattro lettori condividono
  apertura, controllo ed effettiva chiusura del file ROOT.
- `plots/dalitz.py`: dizionario degli istogrammi costruito con un ciclo esplicito;
  ogni riepilogo calcolato una sola volta, metadati invariati.

Un secondo revisore ha controllato i diff delle correzioni e dei refactor,
inclusi limiti dei bin, rollback, contatori e durata dei file ROOT.

## Copertura e limiti

270 file sorgente esaminati: 17 condivisi, 99 preanalisi (incluse 95 macro PID),
2 selezione, 14 simulazione, 17 training, 16 ricostruzione, 7 calibrazione,
8 studi flussi, 27 osservabili, 9 plotting, 8 script, 1 builder presentazioni,
44 teoria, 1 diagnostica in `docs/research`. Inclusi gli `__init__.py`.
Letti i contratti e i test pertinenti; analisi statica estesa anche ai test.

La review verifica codice e contratti computazionali. Non certifica modelli
fisici, purezza, sistematiche o risultati sperimentali. Non è stata rieseguita
un'intera campagna produttiva né ricostruita la presentazione.

## Verifica iniziale

- `python -m pytest -q`: **1014 passati**, un warning preesistente di legenda vuota.
- `python -m pytest -q -c theory/pyproject.toml theory/tests`: **1067 passati**.
- Ambiente: Python 3.14.6, ROOT 6.40.04; integrazioni PyROOT disponibili.
- La compatibilità Python 3.10 dell'hashing è verificata simulando l'assenza
  dell'API introdotta successivamente; non è stata eseguita la suite su Python 3.10.

## Verifica finale

| Controllo | Esito |
|---|---|
| `python -m pytest -q` | **1030 passati**, nessuno saltato, stesso warning di legenda; 148,07 s |
| `python -m pytest -q -c theory/pyproject.toml theory/tests` | **1069 passati**, nessuno saltato; 166,60 s |
| Wheel principale e teoria, `python -m build --wheel --no-isolation` | Entrambe costruite dal codice finale, in `/tmp/graal-review-wheels` |
| Ruff, regole critiche `E9,F63,F7,F82` con `--isolated` | Nessuna segnalazione |
| Ruff con configurazione ambientale completa | 752 segnalazioni prima e dopo; debito preesistente, non dichiarato risolto |
| Parsing sintattico Python 3.10 | 336 file Python del repository validi |
| `bash -n scripts/setup.sh scripts/sync-wiki.sh` | Superato |
| `git diff --check` | Superato |
| Confronto AST dei test già presenti nei 7 file di test modificati | Corpi esistenti invariati |

Totale: **2099 test passati**, 18 casi aggiunti rispetto alla baseline.
I risultati dimostrano copertura delle suite disponibili, non assenza assoluta
di difetti. Questa esecuzione precede il follow-up tagger descritto sopra.

## Verifica del follow-up tagger

Regressioni osservate fallire prima della correzione: catena mista scriveva
1026 righe invece delle 948 con tag; catena interamente senza tag scriveva
4 righe invece di zero. Dopo la correzione, i 14 test di metadati raw passano,
inclusi round-trip h70/h80/h85/ricostruzione, conteggio persistito e stampato,
inizio file senza tag e limiti di capacità 0, 1, 128, -1, 129.

Il test round-trip ora attende solo gli eventi con tag, in accordo con la
modifica di selezione autorizzata dall'utente, e verifica energia e strip
esatte di ogni evento conservato.

- Suite principale completa dopo il follow-up: **1032 passati**, nessuno
  saltato, stesso warning preesistente di legenda vuota; 172,90 s.
- Documentazione: **78 test passati** (`tests/test_wiki.py`).
- `git diff --check`: superato.
- Teoria invariata nel follow-up: resta valida la verifica precedente
  di **1069 test passati**; non rieseguita.
