# Pipeline

`run_pipeline.sh` concatena le fasi da dati grezzi a eventi ricostruiti e plot. Questa pagina descrive lo script.

## Uso

```bash
./run_pipeline.sh [--test-data] [--nevents N] [--input-tree NOME]
                   [--signal-channel CANALE] [--signal-prior F]
                   [--partner proton|neutron|deuteron]
                   [--skip-preanalysis] [--force-preanalysis]
                   [--skip-selection]
                   [--skip-mc] [--force-mc]
                   [--skip-features] [--skip-grid-search]
                   [--grid-search-niter N] [--skip-train]
                   [--skip-reco] [--skip-plots] [--help]
```

`--help`/`-h` stampa l'intestazione dello script stesso.
## Flag

| Flag | Effetto | Default |
|---|---|---|
| `--test-data` | rimappa le quattro cartelle dati del rivelatore su `test_data/` (vedi sotto) | disattivo |
| `--nevents N` | eventi generati per ciascuno dei 9 canali MC in fase 3 | `1000000` |
| `--input-tree NOME` | albero letto nelle fasi 4 e 7; `auto` risolve `h85` o il legacy `h80` | `auto` |
| `--signal-channel CANALE` | canale segnale per feature, grid search e training | `eta_pi0` |
| `--signal-prior F` | quota del peso di training assegnata al segnale; è un prior, non una sezione d'urto | `0.5` |
| `--partner NOME` | massa del bersaglio/rinculo usata dalla ricostruzione (`proton`, `neutron`, `deuteron`) | `proton` |
| `--skip-preanalysis` | salta la fase 1 | disattivo |
| `--force-preanalysis` | rifà la fase 1 anche se `pre_analyzed/` (o l'equivalente `--test-data`) contiene già file | disattivo |
| `--skip-selection` | salta la fase 2 | disattivo |
| `--skip-mc` | salta la generazione MC (fase 3), qualunque sia lo stato su disco | disattivo |
| `--force-mc` | rigenera i canali anche se sono già tutti presenti | disattivo |
| `--skip-features` | salta la fase 4 (build feature) | disattivo |
| `--skip-grid-search` | salta la fase 5 (grid search) | disattivo |
| `--grid-search-niter N` | iterazioni della grid search in fase 5 | `30` |
| `--skip-train` | salta la fase 6 (training); **salta anche la fase 5**| disattivo |
| `--skip-reco` | salta la fase 7 | disattivo |
| `--skip-plots` | salta la fase 8 | disattivo |

Le variabili `PYTHON` e `ROOT_EXEC` (env, non flag) scelgono l'interprete Python e l'eseguibile ROOT da usare; di default sono `python` e `root`.

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

## Cartelle dati del rivelatore e `--test-data`

| Variabile | Default | Con `--test-data` |
|---|---|---|
| `RAW_DIR` | `data/graal_data` | `test_data/raw` |
| `PRE_DIR` | `data/pre_analyzed` | `test_data/pre_analyzed` |
| `SELECTED_DIR` | `data/selected` | `test_data/selected` |
| `RECO_DIR` | `results/reco` | `test_data/results/reco` |
| `PLOTS_DIR` | `results/plots` | `test_data/results/plots` |

Altro:
- `data/` è ciò che il rivelatore ha prodotto e che la selezione ne ha fatto: un **ingresso**. 
- `results/` è ciò che l'analisi ha concluso.
- `reco/` gli alberi ricostruiti.
- `plots/` le figure disegnate da quelli. 

Il Monte Carlo (`03_mc_simulation/data`) e il modello BDT (`04_bdt_training/model`) **non** vengono rimappati da `--test-data`: restano sempre quelli veri, in produzione come in collaudo. Duplicarli per il collaudo non proverebbe niente di più e costerebbe ore — vedi [Testing](testing).

## Fase 1 — Pre-analisi (raw → h80)

```bash
${ROOT_EXEC} -l -b -q -e \
  'gROOT->ProcessLine(".L 01_pre_analysis/PreAnalysis.C"); AnalyzeAll("RAW_DIR", "PRE_DIR", "01_pre_analysis/cuts");'
```

**Riuso**: se `PRE_DIR` contiene già almeno un file `pre_*.root`, la fase viene saltata (`--force-preanalysis` per rifarla comunque). 
La pre-analisi legge run grezze intere ed è lunga: non deve ripartire per sbaglio ogni volta che si rilancia la pipeline. 
Se `RAW_DIR` non esiste, lo script si ferma con un errore che, sotto `--test-data`, dice di crearla e cosa copiarci dentro (vedi [Testing](testing)).

**Questa fase usa**: `RAW_DIR/<run>/*.root` (una cartella per run). 
**Produce**: `PRE_DIR/pre_analisi_<run>.root`, un file per run, ciascuno con TTree `h80`.

## Lookup strip→Eγ e integrazione flussi

Questo passaggio usa tutti gli `h80` inclusivi, quindi va eseguito sui file di
pre-analisi e non sugli `h85` selezionati. Prima della farm, il manifest deve
essere valido (`python scripts/build_run_manifest.py --validate
config/run_manifest.csv`).

```bash
python scripts/build_strip_energy_flux.py \
  --preanalysis-dir data/pre_analyzed \
  --manifest config/run_manifest.csv \
  --flux data/flux/flux.root \
  --output-dir results/strip_energy_flux
```

I preset `ajaka_cross_section` e `ajaka_sigma` sono sempre prodotti. Per
aggiungere uno schema ripetibile, si può ripetere `--binning` con
`NOME:BORDO,BORDO,...`, per esempio:

```bash
  --binning fine:1.00,1.05,1.10,1.15
```

Exit `0` significa QA valida. Exit `1` indica un'analisi completata ma QA non
valida, oppure un errore runtime: con una destinazione output valida lascia il
QA diagnostico in `strip_energy_flux_qa.json`; non usare i CSV per l'estrazione fisica finché
`valid` non è `true`. Quando l'analisi ha completato la lettura degli input, la
cartella contiene sempre i quattro artefatti descritti in [Formati dati](data-formats),
anche con QA non valida, così i bin problematici restano ispezionabili. Un
errore anticipato di input (per esempio ROOT illeggibile) produce invece il
solo QA minimo diagnostico.

Exit `2` è un errore di sintassi/uso del comando (per esempio un flag
obbligatorio mancante), rilevato prima dell'elaborazione: non produce artefatti
né QA. L'automazione farm deve quindi correggere il comando, non tentare di
recuperare l'output. Con exit `0` o `1`, riportare dalla farm tutta la cartella
`results/strip_energy_flux/`.

## Fase 2 — Selezione eventi (h80 → h85)

```bash
${PYTHON} -u -m event_selector.select_events \
    --input-dir  "${PRE_DIR}" \
    --output-dir "${SELECTED_DIR}"
```

Nessuna logica di riuso: gira sempre a meno di `--skip-selection`. 
Usa i file `pre_*.root` di `PRE_DIR`; 
produce in `SELECTED_DIR` un file per run (senza il prefisso `pre_`), con l'albero `h85`. 
Dettagli sul perché dell'albero rinominato in [Formati dati](data-formats).

## Fase 3 — Generazione Monte Carlo

```bash
${PYTHON} -m mc_simulation.mc_status --data-dir "${MC_DATA_DIR}"
```

`mc_status` controlla se i canali scelti sono presenti in `03_mc_simulation/data/`.
Attualmente i canali presenti sono `eta_pi0`, `pi0pi0`, `3pi0`, `eta_2pi0`, `omega_pi0`, `etaprime`, `eta_via_3pi0`, `4pi0`, `eta_pi0_via_3pi0` — la lista viene dal registry `00_common/channels.py`, non è ripetuta a mano qui. 

Il suo exit code guida la decisione:

| Exit | Significato | Azione dello script |
|---|---|---|
| 0 | tutti i canali presenti | non rigenera (salvo `--force-mc`) |
| 1 | almeno uno manca | rigenera |
| 2 | errore interno di `mc_status` stesso | **fatale**, la pipeline si ferma |

L'exit 2 è trattato come diverso da "MC mancante" apposta: un interprete `python` che non riesce a importare `mc_simulation` (per esempio perché manca `pip install -e .`) darebbe anch'esso un errore, e se venisse letto come "MC assente" la pipeline partirebbe a rigenerare tutti i canali.
Per questo `set -e` è disattivato solo per questa singola chiamata, quel tanto che basta per
ispezionare l'exit code prima di decidere.

**Riuso**: la generazione è saltata di default se tutti i canali sono già presenti.
`--skip-mc` la salta sempre;
`--force-mc` la rifà sempre. 
Inoltre se i file sono più vecchi di 10 giorni genera solo un warning da promemoria in caso si sia aggiunto nel corso del tempo altro al MC.

Se serve generare, le macro ROOT girano dalla cartella dati stessa (scrivono il `.root` nella directory corrente); la lista dei canali viene letta dal registry (`CHANNEL_NAMES`), così un canale aggiunto lì non può essere dimenticato:

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

Produce: `03_mc_simulation/data/<canale>_mc.root`, uno per canale. 
I generatori estraggono l'energia del fascio piatta fino a un tetto di **1.75 GeV** (vedi [03 — Simulazione MC](03-mc-simulation)).

Un canale deliberatamente **non** generato: `γp → n π⁺ π⁰ π⁰`, escluso finché non esiste una misura della leakage dei pioni carichi attraverso il taglio dE/dx ("banana") del BGO — vedi [03 — Simulazione MC](03-mc-simulation).

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

`--signal-channel` nomina il canale che fa da segnale, e il registry `00_common/channels.py` risolve il suo file e quelli degli altri che diventano il fondo. 
Se trova un canale mancante si ferma printando `missing MC file for '<canale>'`.

La misura dello spettro viene prima perché il MC va riponderato sul fascio che l'esperimento ha davvero avuto, non su quello piatto dei generatori (vedi [03 — Simulazione MC](03-mc-simulation)). 

**`--beam-spectrum` è obbligatorio, e se `SELECTED_DIR` non esiste la fase fallisce**, non prosegue con un fascio piatto come faceva prima:

```
ERRORE: data/selected/ non esiste.
        I pesi dei canali sono sezioni d'urto integrate sul flusso
        del fascio misurato, e senza i dati selezionati non c'e'
        flusso da misurare. Esegui prima lo stage di selezione.
```

I pesi dei canali sono sezioni d'urto integrate su quel flusso (vedi [03 — Simulazione MC](03-mc-simulation) per la formula).

Infine questa fase produce la matrice di feature a 26 colonne usata dalla fase 5 e dalla fase 6 (vedi [04-bdt-training-features](04-bdt-training-features)).

## Fase 5 — Grid search iper-parametri

```bash
${PYTHON} -u -m bdt_training.grid_search_stage1 \
    --features "04_bdt_training/data/features_stage1.npz" \
    --out-dir  "04_bdt_training/model" \
    --n-iter   "${GRID_SEARCH_NITER}"
```

Fase che funziona solo se **né** `--skip-train` **né** `--skip-grid-search` sono attivi: la grid search produce `best_hyperparams.json`, che serve solo alla fase 6.
Richiede che `features_stage1.npz` esista già (fase 4).

## Fase 6 — Training BDT stage-1

```bash
${PYTHON} -u -m bdt_training.train_bdt_stage1 \
    --features "04_bdt_training/data/features_stage1.npz" \
    --out-dir  "04_bdt_training/model" \
    [--hyperparams "04_bdt_training/model/best_hyperparams.json"]
```

Il flag `--hyperparams` viene aggiunto solo se `04_bdt_training/model/best_hyperparams.json` esiste già (cioè se la fase 5 è girata prima, in questo run o in uno precedente). Al termine lo script
stampa la soglia migliore trovata (`stage1_threshold.txt`) e le metriche (`stage1_metrics.txt`).

## Fase 7 — Ricostruzione (chi2 e BDT)

```bash
${PYTHON} -u -m reconstruction.reconstruct_eta_pi0_chi2 \
    --input-dir   "${SELECTED_DIR}" \
    --input-tree  "${INPUT_TREE}" \
    --partner     "${PARTNER}" \
    --output-file "${RECO_DIR}/reco_eta_pi0_chi2.root"

${PYTHON} -u -m reconstruction.reconstruct_eta_pi0_bdt \
    --input-dir   "${SELECTED_DIR}" \
    --input-tree  "${INPUT_TREE}" \
    --partner     "${PARTNER}" \
    --output-file "${RECO_DIR}/reco_eta_pi0_bdt.root" \
    --model-dir   "04_bdt_training/model"
```

I due run condividono lo stesso `SELECTED_DIR` (albero `h85`) e lo stesso taglio chi2; l'unica differenza tra i due output è il gate BDT nel secondo — vedi [Formati dati](data-formats) per lo schema degli alberi di output.

**Il fit cinematico 6C gira di default** su entrambi i run, dopo il chi2 (e dopo il gate, per il secondo): la sua confidence level seleziona l'evento finale al posto della massa mancante.

Qui possono essere utilizzate le due flag:
- `--no-fit` lo disattiva e fa tornare la selezione alla finestra sulla massa mancante (`--missing-mass-window`, default 0.06 GeV); 
- `--fit-cl` cambia la soglia sulla confidence level (default 0.01). Vedi [Fit cinematico](05-reconstruction-kinematic-fit).

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

Usa i due TTree della fase 7; produce in `results/plots/` i Dalitz plot (con l'opzione `colz` di ROOT) per le due ricostruzioni e le due definizioni di protone, il confronto a 4 pannelli, le masse invarianti η/π⁰ sovrapposte, e salva gli istogrammi in un ROOT file `istogrammi.root` per poterli ristilizzare in seguito se necessario. 
Dettagli in [06 — Plot](06-plots).

Subito dopo il Dalitz, se il MC di segnale è su disco, gira anche lo studio di risoluzione del fit cinematico:

```bash
${PYTHON} -u -m plots.kinfit_resolution \
    --signal  "${MC_DATA_DIR}/${SIGNAL_CHANNEL}_mc.root" \
    --bdt     "${RECO_DIR}/reco_eta_pi0_bdt.root" \
    --out-dir "results/plots"
```

Produce le sei figure prima/dopo su M(ηp) e M(π⁰p) (residui sul MC, spettri MC con la verità, spettri sui dati); manca il MC di segnale, si salta con un avviso e le altre figure restano. Dettagli in
[Fit cinematico](05-reconstruction-kinematic-fit).
