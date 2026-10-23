# Specifica del refactor della repository

Data: 23 ottobre 2026. Fonte: richieste dell'utente nella conversazione corrente.
Stato: requisiti e tre chiarimenti confermati dall'utente; documento preparato per revisione insieme al piano.

## Obiettivo e perimetro

Consolidare lavoro utile su `main` e `origin/main`, eliminare branch superflui,
rimuovere completamente il fit cinematico 6C e semplificare il sistema mantenendo
gli stage numerati. Ricostruire la documentazione corrente nella wiki, con un solo
README generale. Il piano riguarda manutenzione e preservazione del comportamento
scientifico restante, non il completamento delle ricerche ancora aperte.

## Requisiti confermati

1. Destinazione Git: solo `main` locale e su `origin`; conservare prima il lavoro
   da integrare, incluse modifiche non committate e sorgenti nei worktree.
2. Eliminare implementazione, opzioni, output, grafici, test esclusivi e vecchie
   istruzioni del fit cinematico 6C. Restano pairing chi-quadro, selezione missing
   mass, fit statistici delle asimmetrie, calibrazione e fit dei modelli teorici.
3. Cancellare vecchia documentazione normativa e ricostruire la wiki dal codice
   effettivo. Nessuna seconda guida tecnica parallela nei vecchi runbook.
4. Semplificare orchestrazione, calibrazione ed estrazione con responsabilità
   esplicite e riuso tramite funzioni pubbliche.
5. Un solo `README.md` di progetto, nella radice; nessun README negli stage,
   nella teoria, nelle presentazioni o nella nuova documentazione.
6. Conservare gli stage `00_common`–`08_observable_extraction`; spostare `theory/`
   in `09_theory/`, mantenendo import `graal_theory` e CLI `graal-theory`.
7. `data/`: collegamenti/input dei server e delle farm. `data_test/`: un solo
   dataset di prova, immutabile durante l'esecuzione dei test.
8. `results/`: campagne di produzione e output generati, inclusi eventuali
   artefatti riutilizzabili. `results_test/`: campagne di prova, studi diagnostici,
   report, log, build di verifica, file temporanei dei test e lavoro degli agenti.
9. `docs/papers/`: paper originali. `docs/plans/`: piani attivi, inclusa questa
   specifica. `docs/reference/`: fonti storiche e provenienza documentale.
10. Eliminare `.superpowers/`. Conservare Fortran storico, tagli detector per
    periodo, bibliografia, manifest, bundle BDT con provenienza e snapshot geometrici.
11. Valutare le attività aperte nei documenti vecchi prima di eliminarli;
    trasferire stato e decisioni necessarie nella wiki e nei soli piani attivi.
12. Ricostruire Graphify sul nuovo corpus, eliminando dal grafo attivo vecchi
    documenti, memorie autogenerate e percorsi superati.
13. Esecuzione tramite sub-agent, con proprietà dei file esplicita, verifica di
    ciascun risultato e revisione indipendente.

## Chiarimenti confermati

L'utente ha confermato tutte e tre le scelte seguenti nella conversazione corrente.

| ID | Decisione confermata |
|---|---|
| GIT | Baseline attuale + lavoro teoria; backup verificato degli storici, senza importare pipeline alternativa `08_polarization`. |
| SAMPLE | Un solo dataset ridotto contenente due piccoli file, UV e VIS. |
| THEORY | Comando esplicito dopo stage 08, con input dichiarati; nessun calcolo teorico lungo avviato automaticamente. |

## Architettura di destinazione

```text
README.md
AGENTS.md
pyproject.toml
00_common/ ... 08_observable_extraction/
09_theory/                 # package autonomo graal-theory
graal_workflow/             # orchestrazione installabile, nessun calcolo fisico
plots/                     # rendering e adapter dei prodotti
scripts/                   # entrypoint sottili, setup, farm e manutenzione
config/
wiki/                      # unica documentazione tecnica corrente
docs/
  papers/
  plans/
  reference/
data/                      # input/collegamenti di produzione
data_test/                 # singolo dataset di test
results/
  _cache/                  # output riutilizzabili di produzione
  <campaign>/
results_test/
  <campaign-or-study>/
tests/
presentations/
graphify-out/              # solo output attivi del grafo, rigenerabili
```

Decisioni di dettaglio del pianificatore: `results/_cache/` conserva il riuso
fra campagne senza scrivere output in `data/`; ogni campagna di test possiede
i propri intermedi sotto `results_test/`. Si conservano mapping dei package
numerati, dipendenze esistenti, CLI di stage ancora utili e package autonomo
della teoria. Non si introduce un nuovo scheduler o un motore DAG.

## Contratti che il refactor deve preservare

- Python >=3.10, con interprete compatibile con PyROOT; mantenere funzionamento
  locale e farm, installazione editable e wheel delle risorse dichiarate.
- Stessa selezione attuale di fotoni/protoni/pioni e stessi tagli di pairing,
  missing mass e dominio energetico. Conservare modifiche locali del 23 ottobre.
- Stesso ordine delle 26 feature, ipotesi, soglia, copertura e provenienza BDT.
- Stessi run/stati/esposizioni, esclusioni, finestre laterali e contabilizzazione
  degli eventi. Nessun flusso sintetico adottato in produzione dal refactor.
- Stessi stimatori ratio/likelihood, bordi, convenzioni di segno e divisori
  finite-bin approvati `0.9003`, `0.9549`, `0.9745` per 8/12/16 bin; likelihood
  senza questa correzione. Conservare covarianze e bin non stimabili.
- Semi MC e policy di assegnazione dei thread invariati a parità di input:
  rinominare un'etichetta di stage non deve cambiare casualità o cache grouping.
- Conservare validazione dei confini, lock, staging, rollback, fail-fast e
  integrità degli output validi dopo un errore.
- Nuovi ROOT ricostruiti: provenienza `schema=2` con
  `selection_algorithm="pairing_missing_mass"`; nessun campo di configurazione
  del fitter eliminato. Consumer certificati rifiutano vecchi output privi del
  nuovo contratto: la presenza di vettori raw non prova selezione compatibile.
- I `fit_chi2` dei fit azimutali degli osservabili restano validi; rimozione per
  significato e proprietario, mai con sostituzione globale della parola `fit`.
- I dati e i risultati storici conservano i byte e i manifest originali. Ogni
  spostamento richiede inventario delle dipendenze e verifica degli hash; nessun
  reset, clean o force push usato per cancellare lavoro non integrato.
- Gli artefatti esclusivi del fitter eliminato vengono ritirati dalle campagne
  attive e conservati solo nell'archivio verificato sotto `results_test/`;
  bundle storici indivisibili si archiviano interi, senza riscriverne i ROOT.
- Il campione UV+VIS è una coorte diagnostica di regressione, non una nuova
  misura normalizzata di produzione. Mantiene esposizioni sorgente identificate
  per i run/stati inclusi; nessuna esposizione efficace viene dedotta dalla
  percentuale di eventi trattenuti. Ogni gruppo usato per calibrazione conserva
  almeno cinque strip distinte, comprese 1 e 128, e i requisiti scientifici
  esistenti. Campione, manifest e dipendenze vengono congelati prima della baseline.
- Installazione wheel dell'orchestratore richiede una radice checkout esplicita
  quando non è ricavabile da un'installazione sorgente verificata. Nessuna radice
  derivata da `site-packages`; inventari sorgente della provenienza mai vuoti.

## Attività scientifiche da registrare, senza completarle nel refactor

GEANT4: fase geometrica documentata; trasporto, risposta, digitizzazione e
contratto degli eventi ancora da completare. Conservare profilo storico e
snapshot; accordo geometrico campionato non equivale ad accettanza fisica.

Teoria: preservare i gate di convergenza e di riproduzione fisica. Il lavoro più
recente su base angolare e fit nativo si trova nel worktree `figure4-fit`, con
modifiche e sorgenti non committati. Snapshot locale del 23 ottobre alle
13:02:26 UTC registra un pilot `diagnostic_converged`, array 23 avviato e
`fit_status=not_started`; non rappresenta lo stato live della coda.

Flussi: recovery resta sperimentale; assi energetici indipendenti,
calibrazione di copertura/incertezza e bias sugli osservabili restano necessari.

Altri limiti: BDT VIS per protoni centrali; efficienze/normalizzazioni dei fondi;
validazione BDT su domini estesi/condivisi; correlazioni e sistematici finali;
eventuale contorno 2D; classificazioni raw ambigue e fattibilità canale carico.
La wiki li distingue fra capacità presente, studio diagnostico e lavoro aperto.

## Criteri di accettazione

Suite analisi, teoria e test geometrici pertinenti passate, senza sostituire test
rimossi con controlli vuoti. Eseguibili CLI e installazioni verificati. Confronto
numerico prima/dopo sul campione fissato, separando identità esatte e tolleranze
già previste dagli algoritmi. Un solo README; nessuna funzione/CLI/branch attiva
del fitter rimosso; nessun output di prova nei dati o nei risultati di produzione.
Wiki senza link rotti; grafo senza fonti eliminate o autoingestione. Solo `main`
fra branch del repository e remoto dopo integrazione e backup verificati.
