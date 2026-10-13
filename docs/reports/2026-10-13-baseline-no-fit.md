# Baseline senza fit cinematico — esecuzione del 13 ottobre 2026

## Esito e perimetro

Il piano non era implementato: checkout iniziale `3afff75`, launcher ancora
con campione fitted e CLI con fit attivo. Implementazione nel worktree
`.work/baseline-no-kinfit`, branch `feat/baseline-no-kinfit`, poi commit
`cf2022f` e integrazione fast-forward in `main` il 13 ottobre 2026. Grafo esistente
interrogato con graphify (vocabolario: reconstruction, fit, raw, pipeline,
campaign, provenance), poi verificato sui sorgenti correnti.

Campagna locale nuova: `results/baseline-no-fit-20261013/` nel checkout
principale `/Users/tonyf/Work/GRAAL/GRAAL_Analysis`. Eseguita sugli h85 locali
sotto `test_data`, non sull'intera raccolta sperimentale. Nessun archivio
ROOT/PDF precedente sovrascritto; nessun nuovo training.

Tagli confermati dall'utente: chi2 di pairing < 10, risoluzione relativa 0.08,
finestra missing mass ±0.06 GeV centrata sulla massa del protone. Restano
primi quattro fotoni fra almeno quattro, esattamente un protone, guardia
energetica dei mesoni e dominio energetico del profilo. Stessi input e tagli
per pairing e BDT+pairing; sola differenza è il gate BDT. Nessun 6C né taglio CL.
I fit azimutali ratio/likelihood restano attivi, con 12 bin phi e correzione
finite-bin esistente per il solo ratio.

## Modifiche

- CLI e `RecoConfig`: default senza fit; archivio disponibile con consenso
  operativo esplicito `--with-kinematic-fit`. `--no-fit` resta compatibile.
- Launcher: entrambe le ricostruzioni ricevono `--no-fit` e stesso profilo;
  estrazione riceve soltanto raw/raw_bdt. Nessuna invalidazione artificiale
  delle cache selected/MC/BDT: dipendenze a monte immutate.
- Ricostruzione: `reconstruction_provenance` nel ROOT contiene input e
  sorgenti con SHA-256, revisione, comando, versioni Python/NumPy, tagli,
  identità modello e cutflow per run/stato. Snapshot prima del processing.
- Estrazione: nessuna ricerca automatica del campione fit; confronto archivio
  solo con `--raw-bdt-fit FILE`. Provenienza annota
  `raw_vs_kinematic_fit=disabled`; nessuna covarianza fittizia zero.
- Reader, Dalitz e plotting campagna: default rifiuta provenienza assente,
  `do_fit=true` o rami fitted; nessun misto raw/fitted. Prodotti 6C assenti.
  Diagnostici Stage-07 preferiti al vecchio output plot; file più vecchi
  dell'estrazione ROOT rifiutati. Pubblicazione plot atomica preservata.
- Runbook aggiornato: `docs/runbooks/full-pipeline.md`.

## Input e provenienza

| Profilo | Input selezionato | Entrate | Run |
|---|---|---:|---:|
| UV | `test_data/selected/analisi_1998_uv.root`, h85 | 5.341.787 | 178 |
| VIS | `test_data/vis/selected/analisi_1999_vis.root`, h85 | 3.207.538 | 110 |

Modelli: `04_bdt_training/artifacts/stage1` per UV;
`test_data/vis/bdt/artifacts/stage1` per VIS. Il modello UV è legacy senza
metadati del profilo: riuso ammesso esplicitamente dal contratto esistente
`Stage1Gate.check_profile` per UV, non per VIS. Non è una nuova certificazione
del training. Modello VIS dichiara profilo e intervallo [0.9313, 1.10] GeV.

Flusso calibrato riusato da `data/00_external/flux_calibrated.root`, copiato
nella campagna e identificato insieme a `config/run_manifest.csv` con hash.
La calibrazione non dipende dal fit cinematico; non è stata rigenerata.

Artefatti di audit nella campagna:

- `commands.json`: comandi completi realmente eseguiti.
- `reconstruction_manifest.json`: provenienza estratta dai quattro ROOT riaperti.
- `pipeline_artifacts.json`: modalità, input calibrazione e scelte della campagna.
- `exclusions_and_validation.json`: conteggi run/stato, esclusioni per run/strip,
  bin non emessi, sistematici presenti e confronto storico diagnostico.
- `source_snapshot/`: sorgenti usati dalla ricostruzione, copiati e confrontati
  con tutti gli hash ROOT prima delle correzioni finali di review.
- Log distinti per ricostruzione, estrazione e plotting.

Le correzioni finali riguardano validazione dei lettori, scelta PDF e momento
di acquisizione degli hash; non modificano la selezione degli eventi già
ricostruiti. Gli hash della campagna identificano i sorgenti effettivamente
usati, non vengono riscritti con quelli della revisione finale.

## Risultati misurati

| Profilo/percorso | Ricostruiti senza 6C | Ammessi a Sigma | Esclusi per flusso |
|---|---:|---:|---:|
| UV pairing | 15.164 | 14.440 | 722 |
| UV BDT+pairing | 12.261 | 11.674 | 586 |
| VIS pairing | 6.219 | 6.147 | 72 |
| VIS BDT+pairing | 2.706 | 2.682 | 24 |

La differenza residua UV comprende stati non POL1/POL2: due eventi pairing,
uno BDT. Cutflow completo conserva tutti gli scarti, compresi energia,
molteplicità, protone, pairing, missing mass e gate. Per ogni run/stato è
verificata l'identità input = scritti + tutti gli scarti.

UV: 382 punti Sigma (99 pairing e 92 BDT per ciascuno dei due stimatori).
VIS: 64 punti (17 pairing e 15 BDT per stimatore). Rispettivamente 98 e 56
combinazioni campione/stimatore/proiezione/bin non emesse, elencate nell'audit;
non rappresentano misure nulle. Prodotti: ROOT delle asimmetrie, ROOT Dalitz
per profilo e 42 PDF. Assenti prodotti `comparison_raw_fit_*` e mass comparison
6C. Nessun campione `raw_bdt_fit` nei ROOT delle asimmetrie.

## Prove

Baseline prima delle modifiche: 79 test mirati passati. Nuove regressioni
prima dell'implementazione: 10 failure attesi su default/launcher/plot,
2 su reader/adapter, 1 su provenienza ROOT. Test evento verifica recupero
di un evento bocciato dal fitter storico usando un fitter che fallisce
se chiamato nel percorso no-fit.

Review indipendente: nessuna criticità; due problemi importanti corretti
(PDF vecchi e provenienza Dalitz), più rischio di hash rilevati troppo tardi
riclassificato importante per riproducibilità. Quattro regressioni aggiuntive
osservate fallire, poi passare. Verifica mirata finale: 12 test passati.
Suite completa pre-review: 787 test passati. Suite completa finale: **792
test passati in 108.02 s**, exit 0; `git diff --check` senza errori. Plotting
reale ripetuto con codice finale, exit 0.

Smoke: prime 20.000 entrate h85 di ciascun profilo, file separati sotto
`smoke/`. UV 0/0 selezionati; VIS 50 pairing, 18 BDT. Poi processati entrambi
gli input completi per entrambi i percorsi. Quattro ROOT riaperti: `do_fit=false`,
nessun ramo fit, hash input, tagli e contabilità verificati. Estrattori e
plotting terminati con exit 0. QA visiva eseguita su Figure 4 combinata e
Dalitz UV; controlli automatici su presenza PDF/ROOT e assenza prodotti 6C.

## Limiti e decisioni

1. UV: run 1382, 1388, 1409, 1416, 1425, 1442, 1474 esclusi dai flussi per
   tripletta POL1/POL2/BREM incompleta; 489 esposizioni run/strip fuori dominio
   di polarizzazione. VIS: run 2071 senza BREM. Nessun flusso inventato.
2. Sistematico molteplicità UV non disponibile: selezione esattamente-quattro
   perde otto combinazioni stimatore/bin. Non aggiunto come errore zero.
   VIS conserva componente molteplicità. Controllo fondi non attivato;
   bootstrap resta 0; limiti di covarianza precedenti non risolti da questo passo.
3. Cutflow storico letto solo come diagnostica: vecchio BDT UV 18.498 eventi,
   VIS 2.304, entrambi con rami fit. Uguaglianza input non certificata;
   differenze non attribuite esclusivamente al BDT né al cambio 6C.
4. Decisioni implementative: riuso logica evento e cache a monte, archivio
   accessibile solo esplicitamente, hash prima del processing. Un futuro cambio
   di dipendenze richiederà rivalutare le cache; nessuna modifica fisica extra
   è stata introdotta. Retraining e revisione covarianze restano fuori perimetro.

Il prerequisito software e la nuova baseline locale sono realizzati. Non si
certifica con questo lavoro l'accettanza sperimentale, la completezza dei
flussi, la validità fisica del training legacy o l'intera campagna di produzione.

## Chiusura documentale e integrazione

Commit implementativo `cf2022f`, integrato localmente in `main` tramite
fast-forward. Checklist del piano 00 e indice aggiornati con prove, tagli
approvati e limiti. Nessun piano 01–13 avviato. Artefatti della campagna
mantengono hash e snapshot del codice realmente usato; il commit di chiusura
non riscrive retroattivamente la loro provenienza.

Verifica dopo integrazione, eseguita dal checkout principale con import locali:
`python3 -m pytest -q` → **792 passed in 111.24s**, exit 0. Riaperti inoltre
i quattro ROOT con i lettori integrati: `do_fit=false`, conteggi conservati,
42 PDF e nessun prodotto raw/fit. Collegamenti locali della documentazione
verificati; sei voci della checklist completate.
