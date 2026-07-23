# GRAAL Analysis

Analisi dei dati dell'esperimento GRAAL per la reazione **γp → p η π⁰**.

L'η e il π⁰ decadono ciascuno in due fotoni: il rivelatore vede quattro fotoni
e un protone, e il primo problema è capire quali due fotoni vengono dall'η e
quali dal π⁰. Il codice lo risolve in due modi pensati per essere confrontati —
la **minimizzazione del chi2** (l'analisi standard) e la stessa minimizzazione
preceduta da un **gate BDT** che scarta il fondo — e su entrambi applica poi un
**fit cinematico** che aggiusta le quantità misurate entro la loro risoluzione.

📖 **[Wiki](https://github.com/AntoninoFulci/GRAAL_Analysis/wiki)** — ogni fase spiegata in dettaglio.

## Installazione

```bash
pip install -e .
```

Le cartelle sono numerate (`01_`, `02_`, …) perché l'ordine della pipeline sia
visibile su disco; l'installazione mappa quei nomi su package importabili
(`00_common` → `graal_common`, e così via). Senza, nessun import funziona.

## Come si lancia

```bash
./run_pipeline.sh                # catena completa sui dati veri
./run_pipeline.sh --test-data    # collaudo su 1-2 run di prova
./run_pipeline.sh --help         # tutte le flag
```

Ogni fase riusa quello che trova: il Monte Carlo già generato e la pre-analisi
già fatta non vengono rifatti (`--force-mc`, `--force-preanalysis` per forzarli).

## La catena

| # | Fase | Cartella | Da → a |
|---|------|----------|--------|
| 1 | Pre-analisi | `01_pre_analysis/` | `data/graal_data/` → `data/pre_analyzed/` (albero `h80`) |
| 2 | Selezione eventi | `02_event_selector/` | `data/pre_analyzed/` → `data/selected/` (albero `h85`) |
| 3 | Simulazione Monte Carlo | `03_mc_simulation/` | 9 canali: segnale + 8 fondi |
| 4-6 | Feature, grid search, training BDT | `04_bdt_training/` | MC → modello + soglia |
| 7 | Ricostruzione | `05_reconstruction/` | `data/selected/` → `results/reco/` (chi2 **e** BDT) |
| 8 | Plot | `06_plots/` | `results/reco/` → `results/plots/` (Dalitz + masse) |

I dati del rivelatore stanno sotto `data/`. Quello su cui le fasi devono essere
d'accordo — masse dei mesoni, elenco dei canali, sezioni d'urto — vive in
`00_common/`: non è una fase dell'analisi ma il vocabolario comune che tutte
condividono.
