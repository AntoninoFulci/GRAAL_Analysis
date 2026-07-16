# GRAAL Analysis

Analisi dei dati dell'esperimento GRAAL per la reazione **γp → p η π⁰**.

L'η e il π⁰ decadono ciascuno in due fotoni, quindi il rivelatore vede quattro
fotoni e l'analisi deve capire quali due vengono dall'η e quali dal π⁰. Il codice
lo fa in due modi, pensati per essere confrontati: una **minimizzazione del chi2**
(l'analisi standard) e la stessa minimizzazione preceduta da un **gate BDT** che
scarta gli eventi di fondo.

📖 **[Wiki](https://github.com/AntoninoFulci/GRAAL_Analysis/wiki)** — ogni fase
spiegata in dettaglio.

## Installazione

```bash
pip install -e .
```

Obbligatorio. Le cartelle sono numerate (`01_`, `02_`, …) per rendere visibile
l'ordine della pipeline, ma un nome di pacchetto Python non può iniziare con una
cifra: l'installazione editable mappa i nomi importabili sulle cartelle. Senza,
nessun import funziona.

## Come si lancia

```bash
./run_pipeline.sh                # catena completa sui dati veri
./run_pipeline.sh --test-data    # collaudo su 1-2 run di prova (vedi test_data/README.md)
./run_pipeline.sh --help         # tutte le flag
```

Ogni fase riusa quello che trova: il Monte Carlo già generato e la pre-analisi già
fatta non vengono rifatti (`--force-mc` e `--force-preanalysis` per forzarli).

## La catena

| # | Fase | Cartella | Da → a |
|---|------|----------|--------|
| 1 | Pre-analisi | `01_pre_analysis/` | `raw/` → `pre_analyzed/` (albero `h80`) |
| 2 | Selezione eventi | `02_event_selector/` | `pre_analyzed/` → `selected/` (albero `h85`) |
| 3 | Simulazione Monte Carlo | `04_mc_simulation/` | 6 canali: segnale + 5 fondi |
| 4 | Feature stage-1 | `05_analysis_bdt/` | MC → matrice di feature |
| 5 | Grid search | `05_analysis_bdt/` | iper-parametri |
| 6 | Training BDT | `05_analysis_bdt/` | → modello + soglia |
| 7 | Ricostruzione | `03_analysis/` | `selected/` → `analyzed/` (chi2 **e** BDT) |
| 8 | Plot | `06_plots/` | `analyzed/` → `06_plots/plots/` (Dalitz + masse) |

La ricostruzione sta dopo il training perché il run BDT ha bisogno del modello, che
esiste solo dopo la fase 6; i plot stanno in fondo perché confrontano le due
ricostruzioni e le vogliono entrambe.

## Test

```bash
pytest
```
