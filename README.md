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
./run_pipeline.sh --test-data    # collaudo su 1-2 run di prova (vedi wiki, Testing)
./run_pipeline.sh --help         # tutte le flag
```

Ogni fase riusa quello che trova: il Monte Carlo già generato e la pre-analisi già
fatta non vengono rifatti (`--force-mc` e `--force-preanalysis` per forzarli).

## La catena

| # | Fase | Cartella | Da → a |
|---|------|----------|--------|
| 1 | Pre-analisi | `01_pre_analysis/` | `data/graal_data/` → `data/pre_analyzed/` (albero `h80`) |
| 2 | Selezione eventi | `02_event_selector/` | `data/pre_analyzed/` → `data/selected/` (albero `h85`) |
| 3 | Simulazione Monte Carlo | `04_mc_simulation/` | 6 canali: segnale + 5 fondi |
| 4 | Feature stage-1 | `05_analysis_bdt/` | MC → matrice di feature |
| 5 | Grid search | `05_analysis_bdt/` | iper-parametri |
| 6 | Training BDT | `05_analysis_bdt/` | → modello + soglia |
| 7 | Ricostruzione | `03_analysis/` | `data/selected/` → `data/analyzed/` (chi2 **e** BDT) |
| 8 | Plot | `06_plots/` | `data/analyzed/` → `06_plots/plots/` (Dalitz + masse) |

I dati del rivelatore stanno tutti sotto `data/`. Quello su cui le fasi devono
essere d'accordo — masse dei mesoni, elenco dei canali, sezioni d'urto — sta in
`00_common/`: non è una fase, è il vocabolario comune.

## Scambiare il canale di segnale

Il BDT impara a riconoscere un canale; gli altri cinque diventano il suo fondo.
Quale sia è una scelta:

```bash
./run_pipeline.sh --signal-channel pi0pi0
```

Vale per le fasi 4-6; la fase 7 ricostruisce η+π⁰. Il modello si porta dietro il
canale su cui è stato trainato, e il gate rifiuta di filtrare una ricostruzione
che non è la sua.

Quale canale sia il segnale e quale **ipotesi a due mesoni** alimenti il chi2
sono due scelte distinte: per 3π⁰, η2π⁰, ωπ⁰ e η′ il canale non la determina —
osservati come 4γ sono due mesoni visibili su tre — e il codice chiede
(`--hypothesis`) invece di indovinare.

## Cosa il training non sa, di proposito

La sezione d'urto di γp → pηπ⁰ **non sta nel codice**, ed è deliberato: è quello
che l'analisi misura. Metterla darebbe una risposta in pasto agli eventi da cui
la risposta si estrae. I cinque fondi hanno le loro sezioni d'urto misurate —
quanto della contaminazione sia π⁰π⁰ piuttosto che η′ è fisica vera — ma il
rapporto segnale/fondo è una **scelta**, dichiarata con `--signal-prior`
(default 0.5, bilanciato).

Il fascio invece si misura: la fase 4 legge lo spettro del fotone taggato da
`data/selected` e ci riponderа sopra il Monte Carlo. I generatori estraggono un
fascio piatto; GRAAL ha luce laser retrodiffusa Compton, con un bordo.

La ricostruzione sta dopo il training perché il run BDT ha bisogno del modello, che
esiste solo dopo la fase 6; i plot stanno in fondo perché confrontano le due
ricostruzioni e le vogliono entrambe.

## Test

```bash
pytest
```
