# Flussi calibrati: ibrido, esclusioni e confronto tra modelli

Studio del 19 ottobre 2026. **L'ibrido migliora tipicamente la forma rispetto
all'interpolazione; non corregge gli errori della sua normalizzazione.** Extra
Trees e Kernel Ridge ibridi hanno risultati vicini. La regolarizzazione conta
molto per Ridge. Nessun metodo è ancora adottato per sostituire flussi mancanti.

## Campione e qualità

276 run complete (168 UV, 108 VIS), 828 spettri, dagli stessi due h80 del
[pilot precedente](2026-10-19-calibrated-flux-neighbors.md). Restano le ipotesi
autorizzate: 15 minuti per run e condizioni strumentali stabili. Conteggi
inclusivi per run/stato, senza selezione di canale. Griglia comune di 128 bin
tra 0,5 e 2 GeV; ribinning conservativo.

La [policy condivisa](../../config/run_quality_exclusions.json) esclude intere
run quando almeno uno stato, nel campione diagnosticato, ha rapporto tra
flusso/evento e mediana del periodo/stato fuori da [0,01; 100]:

| Run | Stati anomali | Rapporto rispetto alla mediana |
|---|---|---|
| 1322 | BREM, POL1 | 6740,59; 0,000194857 |
| 1482 | BREM | 1742,47 |
| 1970 | BREM, POL1 | 1167,71; 0,000538467 |

Esclusione applicata a tutti gli stati delle tre run: training, vicini donatori,
valutazione, eventi ed esposizioni dell'estrazione degli osservabili. La policy
contiene evidenza numerica e hash degli input; file mancante o malformato causa
un errore esplicito. Il diagnostico può segnalare altri casi ma non modifica
silenziosamente la lista. La soglia identifica anomalie grossolane, non
certifica la qualità di ogni run restante. Non sono stati scambiati gli stati.

Gli output di osservabili già esistenti non vengono riscritti: la nuova
estrazione applica le esclusioni e ne conserva la provenienza. I file ROOT di
flusso di produzione restano invariati.

## Metodo e grid search

Le 387 feature restano: spettri per evento del vicino precedente e successivo
(128+128), loro interpolazione (128), due distanze assunte e posizione relativa.
Il modello predice flusso/evento; il conteggio del bersaglio ripristina la scala.
Per l'ibrido, la previsione positiva viene normalizzata a uno e moltiplicata
per l'integrale dell'interpolazione. Una previsione di forma nulla è dichiarata
non disponibile, senza divisione per zero né sostituzione nascosta.

| Famiglia | Parametri esplorati | Controllo fisso |
|---|---|---|
| Ridge | alpha: 0,001; 0,01; 0,1; 1; 10; 100; 1000 | alpha=1 |
| Kernel Ridge RBF | alpha: 0,01; 1; 100 × gamma: 0,0003; 0,003; 0,03 | alpha=1, gamma=0,003 |
| Extra Trees | min_samples_leaf: 1; 3; 8 × max_features: 0,5; 1 | leaf=1, features=1 |

22 configurazioni per gruppo, 3 fold interni, 6 gruppi periodo/stato, 2 disegni
con blocchi: 792 valutazioni configurazione/fold. Extra Trees usa 64 alberi,
seed fisso e un worker. Ridge e Kernel Ridge standardizzano esclusivamente sui
dati di training. I controlli sono riferimenti fissati per questo studio;
"default" non significa sempre default della libreria.

Selezione separata per diretto e ibrido, minimizzando L1 spettrale media nei fold
interni; i candidati devono coprire tutti i bersagli valutabili. Donatori
ricostruiti dentro ogni fold; nessun flusso del fold nascosto entra nelle
feature. Train/validation/test disgiunti per run; validazione usata soltanto
per bande empiriche. L'universo prima delle esclusioni conserva le assegnazioni
del pilot. Blocchi da 1 o 3 run non garantiscono buchi di quella lunghezza:
blocchi nascosti adiacenti possono produrre lacune maggiori.

Questi periodi e le anomalie sono già stati esaminati: **holdout di sviluppo,
non conferma indipendente**. Il confronto fra famiglie su questi risultati
non sostituisce una verifica su nuove run.

## Risultati complessivi

L1 spettrale = somma degli scarti assoluti bin per bin / integrale vero.
Errore integrale = valore assoluto di (integrale stimato / vero − 1).
L1 forma confronta spettri entrambi normalizzati a uno. Tutti i valori nelle
tabelle sono espressi in percentuale; i denominatori sono spettri, non run
indipendenti.

### Blocchi da 1: 156 spettri (52 run)

| Metodo | L1 mediana | L1 media | L1 p90 | Errore integrale mediano | L1 forma mediana |
|---|---:|---:|---:|---:|---:|
| Interpolazione | 8.52 | 16.80 | 26.59 | 2.75 | 7.47 |
| Ridge diretto | 7.74 | 15.60 | 31.36 | 3.73 | 6.45 |
| Ridge ibrido | 7.29 | 15.73 | 26.55 | 2.75 | 6.45 |
| Kernel Ridge diretto | 8.56 | 15.56 | 30.01 | 4.70 | 7.25 |
| Kernel Ridge ibrido | 7.11 | 15.67 | 26.54 | 2.75 | 6.33 |
| Extra Trees diretto | 7.15 | 13.90 | 24.32 | 2.86 | 6.36 |
| Extra Trees ibrido | 7.12 | 15.65 | 26.56 | 2.75 | 6.26 |

### Blocchi da 3: 162 spettri (54 run)

| Metodo | L1 mediana | L1 media | L1 p90 | Errore integrale mediano | L1 forma mediana |
|---|---:|---:|---:|---:|---:|
| Interpolazione | 9.66 | 27.95 | 40.20 | 4.81 | 7.63 |
| Ridge diretto | 7.79 | 27.79 | 62.50 | 5.59 | 6.16 |
| Ridge ibrido | 7.88 | 26.94 | 39.96 | 4.81 | 6.16 |
| Kernel Ridge diretto | 12.48 | 16.81 | 34.17 | 7.59 | 6.14 |
| Kernel Ridge ibrido | 7.80 | 26.91 | 39.90 | 4.81 | 6.13 |
| Extra Trees diretto | 7.86 | 28.96 | 40.01 | 5.02 | 6.16 |
| Extra Trees ibrido | 7.68 | 26.88 | 39.90 | 4.81 | 6.12 |

Ibridi: stessa normalizzazione dell'interpolazione entro precisione numerica.
Extra Trees ibrido migliora L1 rispetto all'interpolazione nell'89,1% dei casi
con blocchi da 1 e nell'88,3% con blocchi da 3. La sua L1 mediana scende
rispettivamente di circa 16,5% e 20,5% rispetto al riferimento.

Non emerge un vincitore universale. Con blocchi da 3, Kernel Ridge diretto ha
L1 media 16,81%, contro 26,88% di Extra Trees ibrido, ma mediana peggiore
(12,48% contro 7,68%). Questo riflette code molto diverse. L'ibrido eredita gli
errori dell'integrale interpolato; il miglioramento della forma non li elimina.

### Separazione dell'effetto delle esclusioni

Confronto con il pilot precedente sugli stessi bersagli: 156 spettri per
blocchi da 1, 162 per blocchi da 3. L'interpolazione e i suoi donatori sono
identici prima/dopo per tutti questi bersagli. Quindi il miglioramento dei
modelli non va attribuito a una migliore interpolazione dovuta alla pulizia.
Il primo disegno perde due run valutabili perché, tolti donatori esclusi,
manca una parentesi di training; nessuna nuova assegnazione degli split.
La variazione di Ridge rispetto al pilot combina pulizia del training e
ampliamento della griglia: qui non se ne separano causalmente gli effetti.

### Controllo dei parametri: mediana L1, riferimento fisso → grid search

| Metodo | Blocchi 1 | Blocchi 3 |
|---|---:|---:|
| Ridge diretto | 11.48 → 7.74 | 14.13 → 7.79 |
| Ridge ibrido | 9.31 → 7.29 | 13.23 → 7.88 |
| Kernel Ridge diretto | 8.73 → 8.56 | 13.56 → 12.48 |
| Kernel Ridge ibrido | 7.01 → 7.11 | 7.86 → 7.80 |
| Extra Trees diretto | 7.36 → 7.15 | 8.52 → 7.86 |
| Extra Trees ibrido | 7.32 → 7.12 | 8.05 → 7.68 |

La scelta dei parametri è una parte importante del problema per Ridge. Per
Kernel Ridge ibrido il tuning non migliora sempre la mediana del controllo:
la selezione ottimizza la media nei fold interni, non la mediana sull'holdout.
Ridge ibrido seleziona alpha=1000 in tutti i gruppi; è il bordo superiore della
griglia, quindi non si può affermare di aver trovato l'ottimo globale.

## Diagnostica per periodo e stato

| Blocco | Periodo | Stato | n | Interpolazione L1 mediana | Extra Trees ibrido L1 mediana | Extra Trees ibrido L1 p90 |
|---|---|---|---:|---:|---:|---:|
| 1 | 1998_uv | POL1 | 31 | 7.75 | 6.34 | 9.83 |
| 1 | 1998_uv | POL2 | 31 | 7.68 | 6.28 | 8.32 |
| 1 | 1998_uv | BREM | 31 | 21.73 | 19.09 | 56.49 |
| 1 | 1999_vis | POL1 | 21 | 6.62 | 6.05 | 9.79 |
| 1 | 1999_vis | POL2 | 21 | 6.96 | 6.02 | 8.04 |
| 1 | 1999_vis | BREM | 21 | 18.12 | 16.31 | 145.30 |
| 3 | 1998_uv | POL1 | 33 | 8.24 | 6.46 | 20.78 |
| 3 | 1998_uv | POL2 | 33 | 8.09 | 6.70 | 20.88 |
| 3 | 1998_uv | BREM | 33 | 27.42 | 25.38 | 64.79 |
| 3 | 1999_vis | POL1 | 21 | 7.56 | 6.62 | 9.77 |
| 3 | 1999_vis | POL2 | 21 | 7.35 | 6.55 | 10.69 |
| 3 | 1999_vis | BREM | 21 | 19.85 | 19.16 | 337.82 |

BREM resta il limite principale. Con blocchi da 1 gli errori integrali
interpolati maggiori includono run 1988 (+271,4%), 2055 (+185,9%) e 2064
(+145,3%). Non vengono automaticamente escluse in base all'errore di previsione:
questo selezionerebbe i risultati del test. Servono verifiche fisiche dedicate.

## Bande e copertura

Bande empiriche dai residui del campione di validazione, non incertezze
validate né copertura simultanea dello spettro. Media delle coperture dei bin
attivi per spettro; copertura dell'integrale valutata separatamente.

| Blocco | Metodo | Bin 68% | Bin 95% | Integrale 68% | Integrale 95% |
|---|---|---:|---:|---:|---:|
| 1 | Interpolazione | 63.49 | 93.48 | 66.67 | 93.59 |
| 1 | Extra Trees ibrido | 64.30 | 93.84 | 66.67 | 93.59 |
| 3 | Interpolazione | 59.74 | 92.11 | 48.15 | 87.65 |
| 3 | Extra Trees ibrido | 58.52 | 92.02 | 48.15 | 87.65 |

La sottocopertura, soprattutto dell'integrale nei blocchi da 3, impedisce di
trattare queste bande come errori già pronti per propagazione agli osservabili.

## Artefatti e riproduzione

Output: [`results/hybrid-flux-model-search-20261019/`](../../results/hybrid-flux-model-search-20261019/).
Ogni cartella `block_1`/`block_3` contiene:

- `overlays_1998_uv.pdf`, `overlays_1999_vis.pdf`: una pagina per bersaglio,
  con verità, interpolazione, tre modelli diretti e relativi ibridi; forma,
  rapporto e residui. In totale 318 pagine, indicizzate da `overlay_index.json`.
- `diagnostics.pdf`, `model_comparison.pdf`, `grid_search.pdf`: normalizzazione,
  split, errori, gap, bin energetici, coperture, controllo dei parametri e griglie.
- PNG riepilogativi ed esempi di errore mediano/massimo; `fits.json` contiene
  configurazioni, score e audit dei donatori nei fold.
- `predictions.csv`, `spectra.npz`, `splits.json`; ordine delle righe condiviso
  fra CSV e array NPZ. `summary.json` conserva ipotesi, esclusioni e confronti
  appaiati; `input_integrity.json` verifica gli input prima/dopo.

Comando eseguito:

```bash
MPLCONFIGDIR=/tmp/graal-mpl XDG_CACHE_HOME=/tmp/graal-cache \
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 \
python3 -m flux_studies.study_calibrated_neighbors \
  --calibrated-flux data/00_external/flux_calibrated.root \
  --h80 test_data/pre_analyzed/pre_analisi_1998_uv.root \
  --h80 test_data/pre_analyzed/pre_analisi_1999_vis.root \
  --output-dir results/hybrid-flux-model-search-20261019
```

## Verifica software

Revisione indipendente: nessun problema critico o importante. Controllati
isolamento degli holdout, ricostruzione dei donatori nei fold, denominatori,
invarianza dell'integrale ibrido, policy e confini eventi/esposizioni.
Test mirati: 55 dello stage flussi; 100 qualità/pipeline; 173 integrazione
calibrazione/osservabili; 11 periodi escluso un caso ROOT isolato. I gruppi
si sovrappongono e non vanno sommati. Smoke test dei plot con tutte le famiglie
completato. Il test ROOT isolato `test_unconverged_period_fit_is_recorded_but_not_published`
ha mostrato un crash `TGraph::SetName` riproducibile anche con il modulo originale
in HEAD. Nella suite completa il problema isolato non si riproduce:
`python3 -m pytest -q` → **1189 passed**, un warning di legenda vuota,
163,08 secondi. Nessun test escluso dalla suite completa.

Verificati gli hash prima/dopo (input invariati), l'assenza delle tre run da
bersagli e donatori salvati, l'invarianza dell'integrale di tutti gli ibridi,
gli indici e la leggibilità dei PDF (318 pagine di overlay, 40 di diagnostica).
Ispezione visiva degli overlay e delle griglie; migliorato il contrasto delle
etichette nelle heatmap, senza cambiare fitting o risultati numerici.
