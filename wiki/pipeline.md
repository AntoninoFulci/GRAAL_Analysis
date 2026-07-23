# Pipeline

`run_pipeline.sh` incatena le otto fasi da dati grezzi a eventi ricostruiti
e plot. Questa pagina descrive lo script così com'è, non come "dovrebbe"
essere: ogni comando qui sotto è preso dal parsing reale delle opzioni in
`run_pipeline.sh`.

## Uso

```bash
./run_pipeline.sh [--test-data] [--nevents N]
                   [--skip-preanalysis] [--force-preanalysis]
                   [--skip-selection]
                   [--skip-mc] [--force-mc]
                   [--skip-features] [--skip-grid-search]
                   [--grid-search-niter N] [--skip-train]
                   [--skip-reco] [--skip-plots] [--help]
```

`--help`/`-h` stampa l'intestazione dello script stesso (il blocco tra i due
delimitatori `# ====`, con schema delle fasi) ed esce con codice 0.

## Flag

| Flag | Effetto | Default |
|---|---|---|
| `--test-data` | rimappa le quattro cartelle dati del rivelatore su `test_data/` (vedi sotto) | disattivo |
| `--nevents N` | eventi generati per ciascuno dei 9 canali MC in fase 3 | `1000000` |
| `--skip-preanalysis` | salta la fase 1 | disattivo |
| `--force-preanalysis` | rifà la fase 1 anche se `pre_analyzed/` (o l'equivalente `--test-data`) contiene già file | disattivo |
| `--skip-selection` | salta la fase 2 | disattivo |
| `--skip-mc` | salta la generazione MC (fase 3), qualunque sia lo stato su disco | disattivo |
| `--force-mc` | rigenera i 9 canali anche se sono già tutti presenti | disattivo |
| `--skip-features` | salta la fase 4 (build feature) | disattivo |
| `--skip-grid-search` | salta la fase 5 (grid search) | disattivo |
| `--grid-search-niter N` | iterazioni della grid search in fase 5 | `30` |
| `--skip-train` | salta la fase 6 (training); **salta anche la fase 5**, perché la grid search non ha senso senza un training successivo che ne usi il risultato | disattivo |
| `--skip-reco` | salta la fase 7 | disattivo |
| `--skip-plots` | salta la fase 8 | disattivo |

Le variabili `PYTHON` e `ROOT_EXEC` (env, non flag) scelgono l'interprete
Python e l'eseguibile ROOT da usare; di default sono `python` e `root`.

## Preflight: il pacchetto deve essere importabile

Prima di lanciare qualunque fase, lo script prova:

```bash
${PYTHON} -c "import graal_common, event_selector, mc_simulation, bdt_training, reconstruction, plots"
```

Se fallisce, si ferma subito con:

```
ERROR: i pacchetti della pipeline non sono importabili.
       Esegui:  pip install -e .
       (oppure passa il tuo interprete:  PYTHON=.venv/bin/python ./run_pipeline.sh ...)
```

Questo controllo esiste per non scoprire l'errore a metà della fase 2 (o
peggio, dopo ore di fase 3): un `python` che non ha visto `pip install -e .`
non troverà `event_selector` né `bdt_training`, e il fallimento deve essere
immediato e leggibile — vedi [Home](Home) per il perché dei nomi numerati.

## Cartelle dati del rivelatore e `--test-data`

| Variabile | Default | Con `--test-data` |
|---|---|---|
| `RAW_DIR` | `data/graal_data` | `test_data/raw` |
| `PRE_DIR` | `data/pre_analyzed` | `test_data/pre_analyzed` |
| `SELECTED_DIR` | `data/selected` | `test_data/selected` |
| `RECO_DIR` | `results/reco` | `test_data/results/reco` |
| `PLOTS_DIR` | `results/plots` | `test_data/results/plots` |

`data/` è ciò che il rivelatore ha prodotto e che la selezione ne ha fatto: un
**ingresso**. `results/` è ciò che l'analisi ha concluso: `reco/` gli alberi
ricostruiti, `plots/` le figure disegnate da quelli. Stanno separati perché
invecchiano in modo diverso — `data/` è dato, `results/` si rifà ogni volta che
cambia il codice. Per questo `results/` non è versionata.

Il Monte Carlo (`03_mc_simulation/data`) e il modello BDT
(`04_bdt_training/model`) **non** vengono rimappati da `--test-data`: restano
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
ferma con un errore che, sotto `--test-data`, dice di crearla e cosa
copiarci dentro (vedi [Testing](testing)).

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

`mc_status` controlla se i 9 canali (`eta_pi0`, `pi0pi0`, `3pi0`,
`eta_2pi0`, `omega_pi0`, `etaprime`, `eta_via_3pi0`, `4pi0`,
`eta_pi0_via_3pi0` — la lista viene dal registry `00_common/channels.py`, non
è ripetuta a mano qui) sono tutti presenti in `03_mc_simulation/data/`. Il suo
exit code guida la decisione:

| Exit | Significato | Azione dello script |
|---|---|---|
| 0 | tutti e 9 i canali presenti | non rigenera (salvo `--force-mc`) |
| 1 | almeno uno manca | rigenera |
| 2 | errore interno di `mc_status` stesso | **fatale**, la pipeline si ferma |

L'exit 2 è trattato come diverso da "MC mancante" apposta: un interprete
`python` che non riesce a importare `mc_simulation` (per esempio perché
manca `pip install -e .`) darebbe anch'esso un errore, e se venisse letto
come "MC assente" la pipeline partirebbe a rigenerare tutti e nove i canali —
ore di calcolo — che in realtà erano già tutti su disco. Per questo `set -e`
è disattivato solo per questa singola chiamata, quel tanto che basta per
ispezionare l'exit code prima di decidere.

**Riuso**: la generazione è saltata di default se tutti e 9 i canali sono
già presenti (rigenerare costa ore). `--skip-mc` la salta sempre;
`--force-mc` la rifà sempre. La staleness (file più vecchi di 10 giorni) non
cambia mai la decisione — genera solo un warning, non blocca.

Se serve generare, i 9 macro ROOT girano dalla cartella dati stessa (scrivono
il `.root` nella directory corrente); la lista dei canali viene letta dal
registry (`CHANNEL_NAMES`), così un canale aggiunto lì non può essere
dimenticato qui:

```bash
generate_eta_pi0_dataset.C(NEVENTS)
generate_pi0pi0_dataset.C(NEVENTS)
generate_3pi0_dataset.C(NEVENTS)
generate_eta_2pi0_dataset.C(NEVENTS)
generate_omega_pi0_dataset.C(NEVENTS)
generate_etaprime_dataset.C(NEVENTS)
generate_eta_via_3pi0_dataset.C(NEVENTS)
generate_4pi0_dataset.C(NEVENTS)
generate_eta_pi0_via_3pi0_dataset.C(NEVENTS)
```

Produce: `03_mc_simulation/data/<canale>_mc.root`, uno per canale. I
generatori estraggono l'energia del fascio piatta fino a un tetto di
**1.75 GeV** (era 1.55; il fascio reale misurato arriva a 1.72, vedi
[03 — Simulazione MC](03-mc-simulation)).

Un canale deliberatamente **non** generato: `γp → n π⁺ π⁰ π⁰`, escluso finché
non esiste una misura della leakage dei pioni carichi attraverso il taglio
dE/dx ("banana") del BGO — vedi [03 — Simulazione MC](03-mc-simulation).

## Fase 4 — Build feature stage-1

```bash
# prima: misura il fascio vero dai dati
${PYTHON} -u -m bdt_training.beam_spectrum \
    --selected-dir "${SELECTED_DIR}" \
    --tree         "${INPUT_TREE}" \
    --output       "${BEAM_SPECTRUM_FILE}"

${PYTHON} -u -m bdt_training.build_background_features \
    --mc-dir         "${MC_DATA_DIR}" \
    --signal-channel "${SIGNAL_CHANNEL}" \
    --signal-prior   "${SIGNAL_PRIOR}" \
    --beam-spectrum  "${BEAM_SPECTRUM_FILE}" \
    --output         "04_bdt_training/data/features_stage1.npz"
```

Quali file servano non è più scritto qui: `--signal-channel` nomina il canale
che fa da segnale, e il registry `00_common/channels.py` risolve il suo file e
quelli degli altri otto, che diventano il fondo. Un canale mancante si ferma
con `missing MC file for '<canale>'`.

La misura dello spettro viene prima perché il MC va riponderato sul fascio che
l'esperimento ha davvero avuto, non su quello piatto dei generatori (vedi
[03 — Simulazione MC](03-mc-simulation)). Non è cachata: costa poco rispetto
alla costruzione delle feature, e si misura da quello che `SELECTED_DIR`
contiene adesso.

**`--beam-spectrum` è obbligatorio, e se `SELECTED_DIR` non esiste la fase
fallisce**, non prosegue con un fascio piatto come faceva prima:

```
ERRORE: data/selected/ non esiste.
        I pesi dei canali sono sezioni d'urto integrate sul flusso
        del fascio misurato, e senza i dati selezionati non c'e'
        flusso da misurare. Esegui prima lo stage di selezione.
```

Non è un irrigidimento cosmetico: i pesi dei canali sono sezioni d'urto
integrate su quel flusso (vedi [03 — Simulazione MC](03-mc-simulation) per la
formula), e un fascio piatto per costruirli non è un'approssimazione più
grezza, è un numero senza fondamento — proseguire "con un avviso" nascondeva
proprio questo.

Produce la matrice di feature a 26 colonne usata dalla fase 5 e
dalla fase 6 — dettagli in [04-bdt-training-features](04-bdt-training-features).

## Fase 5 — Grid search iper-parametri

```bash
${PYTHON} -u -m bdt_training.grid_search_stage1 \
    --features "04_bdt_training/data/features_stage1.npz" \
    --out-dir  "04_bdt_training/model" \
    --n-iter   "${GRID_SEARCH_NITER}"
```

Gira solo se **né** `--skip-train` **né** `--skip-grid-search` sono attivi:
la grid search produce `best_hyperparams.json`, che serve solo alla fase 6.
Richiede che `features_stage1.npz` esista già (fase 4).

## Fase 6 — Training BDT stage-1

```bash
${PYTHON} -u -m bdt_training.train_bdt_stage1 \
    --features "04_bdt_training/data/features_stage1.npz" \
    --out-dir  "04_bdt_training/model" \
    [--hyperparams "04_bdt_training/model/best_hyperparams.json"]
```

Il flag `--hyperparams` viene aggiunto solo se
`04_bdt_training/model/best_hyperparams.json` esiste già (cioè se la fase 5
è girata prima, in questo run o in uno precedente). Al termine lo script
stampa la soglia (`stage1_threshold.txt`) e le metriche
(`stage1_metrics.txt`).

## Fase 7 — Ricostruzione (chi2 e BDT)

```bash
${PYTHON} -u -m reconstruction.reconstruct_eta_pi0_chi2 \
    --input-dir   "${SELECTED_DIR}" \
    --output-file "${RECO_DIR}/reco_eta_pi0_chi2.root"

${PYTHON} -u -m reconstruction.reconstruct_eta_pi0_bdt \
    --input-dir   "${SELECTED_DIR}" \
    --output-file "${RECO_DIR}/reco_eta_pi0_bdt.root" \
    --model-dir   "04_bdt_training/model"
```

Questa è l'ultima fase e per un motivo preciso: il secondo run ha bisogno
del modello e della soglia scritti dalla fase 6
(`bdt_stage1.json`, `stage1_threshold.txt`), che non esistono prima. Metterla
prima significherebbe fallire ogni volta che il modello non è già stato
addestrato in un run precedente.

I due run condividono lo stesso `SELECTED_DIR` (albero `h85`) e lo stesso
taglio chi2; l'unica differenza tra i due output è il gate BDT nel secondo —
vedi [Formati dati](data-formats) per lo schema degli alberi di output.

**Il fit cinematico 6C gira di default** su entrambi i run, dopo il chi2 (e
dopo il gate, per il secondo): la sua confidence level seleziona l'evento
finale al posto della massa mancante. `--no-fit` lo disattiva e fa tornare
la selezione alla finestra sulla massa mancante (`--missing-mass-window`,
default 0.06 GeV); `--fit-cl` cambia la soglia sulla confidence level
(default 0.01). Vedi [Fit cinematico](05-reconstruction-kinematic-fit).

## Fase 8 — Plot (Dalitz + masse invarianti)

```bash
${PYTHON} -u -m plots.dalitz \
    --chi2    "${RECO_DIR}/reco_eta_pi0_chi2.root" \
    --bdt     "${RECO_DIR}/reco_eta_pi0_bdt.root" \
    --out-dir "results/plots"
```

**Skip automatico**: se manca almeno uno dei due file ricostruiti in
`RECO_DIR/`, la fase si salta da sola, senza fermare la pipeline:

```
[8/8] Plot — saltato: manca almeno un file ricostruito in results/reco/
    (i plot confrontano le due analisi: servono entrambi)
```

Deliberato: il plot esiste solo per confrontare le due ricostruzioni, e un
solo file non basta a produrne uno sensato — per esempio dopo un run con
`--skip-reco`. Consuma i due alberi della fase 7; produce in `results/plots/`
i Dalitz (`colz`) per le due ricostruzioni e le due definizioni di protone,
il confronto a 4 pannelli, le masse invarianti η/π⁰ sovrapposte, e
`istogrammi.root` con tutti gli istogrammi per poterli ristilizzare senza
rifare il loop. Dettagli in [06 — Plot](06-plots), inclusa la spiegazione
di perché le due definizioni di protone (misurato / da `missing`) non sono
equivalenti.

Subito dopo il Dalitz, se il MC di segnale è su disco, gira anche lo studio
di risoluzione del fit cinematico:

```bash
${PYTHON} -u -m plots.kinfit_resolution \
    --signal  "${MC_DATA_DIR}/${SIGNAL_CHANNEL}_mc.root" \
    --bdt     "${RECO_DIR}/reco_eta_pi0_bdt.root" \
    --out-dir "results/plots"
```

Produce le sei figure prima/dopo su M(ηp) e M(π⁰p) (residui sul MC, spettri
MC con la verità, spettri sui dati); manca il MC di segnale, si salta con un
avviso e le altre figure restano. Dettagli in
[Fit cinematico](05-reconstruction-kinematic-fit).
