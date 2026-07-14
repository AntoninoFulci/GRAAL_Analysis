# Pipeline

`run_pipeline.sh` incatena le sette fasi da dati grezzi a eventi ricostruiti.
Questa pagina descrive lo script così com'è, non come "dovrebbe" essere:
ogni comando qui sotto è preso dal parsing reale delle opzioni in
`run_pipeline.sh`.

## Uso

```bash
./run_pipeline.sh [--test-data] [--nevents N]
                   [--skip-preanalysis] [--force-preanalysis]
                   [--skip-selection]
                   [--skip-mc] [--force-mc]
                   [--skip-features] [--skip-grid-search]
                   [--grid-search-niter N] [--skip-train]
                   [--skip-reco] [--help]
```

`--help`/`-h` stampa le righe 2-27 dello script stesso (l'intestazione con
schema delle fasi) ed esce con codice 0.

## Flag

| Flag | Effetto | Default |
|---|---|---|
| `--test-data` | rimappa le quattro cartelle dati del rivelatore su `test_data/` (vedi sotto) | disattivo |
| `--nevents N` | eventi generati per ciascuno dei 6 canali MC in fase 3 | `1000000` |
| `--skip-preanalysis` | salta la fase 1 | disattivo |
| `--force-preanalysis` | rifà la fase 1 anche se `pre_analyzed/` (o l'equivalente `--test-data`) contiene già file | disattivo |
| `--skip-selection` | salta la fase 2 | disattivo |
| `--skip-mc` | salta la generazione MC (fase 3), qualunque sia lo stato su disco | disattivo |
| `--force-mc` | rigenera i 6 canali anche se sono già tutti presenti | disattivo |
| `--skip-features` | salta la fase 4 (build feature) | disattivo |
| `--skip-grid-search` | salta la fase 5 (grid search) | disattivo |
| `--grid-search-niter N` | iterazioni della grid search in fase 5 | `30` |
| `--skip-train` | salta la fase 6 (training); **salta anche la fase 5**, perché la grid search non ha senso senza un training successivo che ne usi il risultato | disattivo |
| `--skip-reco` | salta la fase 7 | disattivo |

Le variabili `PYTHON` e `ROOT_EXEC` (env, non flag) scelgono l'interprete
Python e l'eseguibile ROOT da usare; di default sono `python` e `root`.

## Preflight: il pacchetto deve essere importabile

Prima di lanciare qualunque fase, lo script prova:

```bash
${PYTHON} -c "import mc_simulation, analysis, analysis_bdt, event_selector"
```

Se fallisce, si ferma subito con:

```
ERROR: i pacchetti della pipeline non sono importabili.
       Esegui:  pip install -e .
       (oppure passa il tuo interprete:  PYTHON=.venv/bin/python ./run_pipeline.sh ...)
```

Questo controllo esiste per non scoprire l'errore a metà della fase 2 (o
peggio, dopo ore di fase 3): un `python` che non ha visto `pip install -e .`
non troverà `event_selector` né `analysis_bdt`, e il fallimento deve essere
immediato e leggibile — vedi [Home](Home) per il perché dei nomi numerati.

## Cartelle dati del rivelatore e `--test-data`

Quattro cartelle sono, di default, quelle di produzione:

| Variabile | Default | Con `--test-data` |
|---|---|---|
| `RAW_DIR` | `graal_data` | `test_data/raw` |
| `PRE_DIR` | `pre_analyzed` | `test_data/pre_analyzed` |
| `SELECTED_DIR` | `selected` | `test_data/selected` |
| `ANALYZED_DIR` | `analyzed` | `test_data/analyzed` |

Nota: il default di produzione per i dati grezzi è `graal_data/`, **non**
`test_data/raw/` — quella seconda directory esiste solo sotto `--test-data`.

Il Monte Carlo (`04_mc_simulation/data`) e il modello BDT
(`05_analysis_bdt/model`) **non** vengono rimappati da `--test-data`: restano
sempre quelli veri, in produzione come in collaudo. Duplicarli per il
collaudo non proverebbe niente di più e costerebbe ore — vedi
[Testing](testing).

## Fase 1 — Pre-analisi (raw → h80)

```bash
${ROOT_EXEC} -l -b -q -e \
  'gROOT->ProcessLine(".L 01_pre_analysis/PreAnalysis.C"); AnalyzeAll("RAW_DIR", "PRE_DIR", "01_pre_analysis/cuts");'
```

**Riuso**: se `PRE_DIR` contiene già almeno un file `pre_*.root`, la fase
viene saltata (`--force-preanalysis` per rifarla comunque). La pre-analisi
legge run grezze intere ed è lunga: non deve ripartire per sbaglio ogni
volta che si rilancia la pipeline. Se `RAW_DIR` non esiste, lo script si
ferma con un errore che, sotto `--test-data`, rimanda esplicitamente a
`test_data/README.md`.

Consuma: `RAW_DIR/<run>/*.root` (una cartella per run). Produce:
`PRE_DIR/pre_analisi_<run>.root`, un file per run, ciascuno con l'albero
`h80`.

## Fase 2 — Selezione eventi (h80 → h85)

```bash
${PYTHON} -u -m event_selector.select_events \
    --input-dir  "${PRE_DIR}" \
    --output-dir "${SELECTED_DIR}"
```

Nessuna logica di riuso: gira sempre a meno di `--skip-selection`. Consuma i
file `pre_*.root` di `PRE_DIR`; produce in `SELECTED_DIR` un file per run
(senza il prefisso `pre_`), con l'albero `h85`. Dettagli sul perché
dell'albero rinominato in [Formati dati](data-formats).

## Fase 3 — Generazione Monte Carlo

```bash
${PYTHON} -m mc_simulation.mc_status --data-dir "${MC_DATA_DIR}"
```

`mc_status` controlla se i 6 canali (`eta_pi0`, `pi0pi0`, `3pi0`,
`eta_2pi0`, `omega_pi0`, `etaprime`) sono tutti presenti in
`04_mc_simulation/data/`. Il suo exit code guida la decisione:

| Exit | Significato | Azione dello script |
|---|---|---|
| 0 | tutti e 6 i canali presenti | non rigenera (salvo `--force-mc`) |
| 1 | almeno uno manca | rigenera |
| 2 | errore interno di `mc_status` stesso | **fatale**, la pipeline si ferma |

L'exit 2 è trattato come diverso da "MC mancante" apposta: un interprete
`python` che non riesce a importare `mc_simulation` (per esempio perché
manca `pip install -e .`) darebbe anch'esso un errore, e se venisse letto
come "MC assente" la pipeline partirebbe a rigenerare sei canali — ore di
calcolo — che in realtà erano già tutti su disco. Per questo `set -e` è
disattivato solo per questa singola chiamata, quel tanto che basta per
ispezionare l'exit code prima di decidere.

**Riuso**: la generazione è saltata di default se tutti e 6 i canali sono
già presenti (rigenerare costa ore). `--skip-mc` la salta sempre;
`--force-mc` la rifà sempre. La staleness (file più vecchi di 10 giorni) non
cambia mai la decisione — genera solo un warning, non blocca.

Se serve generare, i 6 macro ROOT girano dalla cartella dati stessa (scrivono
il `.root` nella directory corrente):

```bash
generate_eta_pi0_dataset.C(NEVENTS)
generate_pi0pi0_dataset.C(NEVENTS)
generate_3pi0_dataset.C(NEVENTS)
generate_eta_2pi0_dataset.C(NEVENTS)
generate_omega_pi0_dataset.C(NEVENTS)
generate_etaprime_dataset.C(NEVENTS)
```

Produce: `04_mc_simulation/data/<canale>_mc.root`, uno per canale.

## Fase 4 — Build feature stage-1

```bash
${PYTHON} -u -m analysis_bdt.build_background_features \
    --signal      "${MC_DATA_DIR}/eta_pi0_mc.root" \
    --backgrounds "${MC_DATA_DIR}/pi0pi0_mc.root" \
                  "${MC_DATA_DIR}/3pi0_mc.root" \
                  "${MC_DATA_DIR}/eta_2pi0_mc.root" \
                  "${MC_DATA_DIR}/omega_pi0_mc.root" \
                  "${MC_DATA_DIR}/etaprime_mc.root" \
    --cs-csv      "04_mc_simulation/cross_sections/cross_sections.csv" \
    --output      "05_analysis_bdt/data/features_stage1.npz"
```

Prima di lanciarlo, lo script verifica che tutti e 6 i file MC esistano; se
manca qualcosa si ferma con `ERROR: missing MC file ... (run without
--skip-mc)`. Produce la matrice di feature a 24 colonne usata dalla fase 5 e
dalla fase 6 — dettagli in [05-analysis-bdt-features](05-analysis-bdt-features).

## Fase 5 — Grid search iper-parametri

```bash
${PYTHON} -u -m analysis_bdt.grid_search_stage1 \
    --features "05_analysis_bdt/data/features_stage1.npz" \
    --out-dir  "05_analysis_bdt/model" \
    --n-iter   "${GRID_SEARCH_NITER}"
```

Gira solo se **né** `--skip-train` **né** `--skip-grid-search` sono attivi:
la grid search produce `best_hyperparams.json`, che serve solo alla fase 6.
Richiede che `features_stage1.npz` esista già (fase 4).

## Fase 6 — Training BDT stage-1

```bash
${PYTHON} -u -m analysis_bdt.train_bdt_stage1 \
    --features "05_analysis_bdt/data/features_stage1.npz" \
    --out-dir  "05_analysis_bdt/model" \
    [--hyperparams "05_analysis_bdt/model/best_hyperparams.json"]
```

Il flag `--hyperparams` viene aggiunto solo se
`05_analysis_bdt/model/best_hyperparams.json` esiste già (cioè se la fase 5
è girata prima, in questo run o in uno precedente). Al termine lo script
stampa la soglia (`stage1_threshold.txt`) e le metriche
(`stage1_metrics.txt`).

## Fase 7 — Ricostruzione (chi2 e BDT)

```bash
${PYTHON} -u -m analysis.reconstruct_eta_pi0_chi2 \
    --input-dir   "${SELECTED_DIR}" \
    --output-file "${ANALYZED_DIR}/reco_eta_pi0_chi2.root"

${PYTHON} -u -m analysis.reconstruct_eta_pi0_bdt \
    --input-dir   "${SELECTED_DIR}" \
    --output-file "${ANALYZED_DIR}/reco_eta_pi0_bdt.root" \
    --model-dir   "05_analysis_bdt/model"
```

Questa è l'ultima fase e per un motivo preciso: il secondo run ha bisogno
del modello e della soglia scritti dalla fase 6
(`bdt_stage1.json`, `stage1_threshold.txt`), che non esistono prima. Metterla
prima significherebbe fallire ogni volta che il modello non è già stato
addestrato in un run precedente.

I due run condividono lo stesso `SELECTED_DIR` (albero `h85`) e lo stesso
taglio chi2; l'unica differenza tra i due output è il gate BDT nel secondo —
vedi [Formati dati](data-formats) per lo schema degli alberi di output.
