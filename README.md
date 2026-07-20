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
| 3 | Simulazione Monte Carlo | `03_mc_simulation/` | 9 canali: segnale + 8 fondi |
| 4 | Feature stage-1 | `04_bdt_training/` | MC → matrice di feature |
| 5 | Grid search | `04_bdt_training/` | iper-parametri |
| 6 | Training BDT | `04_bdt_training/` | → modello + soglia |
| 7 | Ricostruzione | `05_reconstruction/` | `data/selected/` → `results/reco/` (chi2 **e** BDT) |
| 8 | Plot | `06_plots/` | `results/reco/` → `results/plots/` (Dalitz + masse) |

I dati del rivelatore stanno tutti sotto `data/`. Quello su cui le fasi devono
essere d'accordo — masse dei mesoni, elenco dei canali, sezioni d'urto — sta in
`00_common/`: non è una fase, è il vocabolario comune.

## Scambiare il canale di segnale

Il BDT impara a riconoscere un canale; gli altri otto diventano il suo fondo.
Quale sia è una scelta:

```bash
./run_pipeline.sh --signal-channel pi0pi0
```

Vale per le fasi 4-6; la fase 7 ricostruisce η+π⁰. Il modello si porta dietro il
canale su cui è stato trainato, e il gate rifiuta di filtrare una ricostruzione
che non è la sua.

Quale canale sia il segnale e quale **ipotesi a due mesoni** alimenti il chi2
sono due scelte distinte: solo `eta_pi0` e `pi0pi0` fissano un'ipotesi da soli
(η+π⁰ e 2π⁰); per tutti gli altri — 3π⁰, η2π⁰, ωπ⁰, η′, η(→3π⁰), 4π⁰ ed
ηπ⁰(→3π⁰) — osservati come 4γ sono un sottoinsieme dei mesoni visibili, e il
codice chiede (`--hypothesis`) invece di indovinare.

## Cosa il training non sa, di proposito

La sezione d'urto di γp → pηπ⁰ **non sta nel codice**, ed è deliberato: è quello
che l'analisi misura. Metterla darebbe una risposta in pasto agli eventi da cui
la risposta si estrae. Sette degli otto fondi hanno una sezione d'urto misurata (o
stimata e dichiarata come tale) — quanto della contaminazione sia π⁰π⁰ piuttosto
che η′ è fisica vera. L'ottavo, `eta_pi0_via_3pi0`, è la stessa reazione di
segnale con l'η che decade a 3π⁰ invece che a 2γ: la sua sezione d'urto **è**
quella del segnale, quindi il suo peso è vincolato al segnale via i branching
ratio PDG anziché avere un numero proprio. Il rapporto segnale/fondo è invece
una **scelta**, dichiarata con `--signal-prior` (default 0.5, bilanciato).

Il fascio invece si misura: la fase 4 legge lo spettro del fotone taggato da
`data/selected` e ci riponderа sopra il Monte Carlo — obbligatorio
(`--beam-spectrum`), perché i pesi dei canali sono sezioni d'urto integrate su
quel flusso. I generatori estraggono un fascio piatto fino a 1.75 GeV; GRAAL ha
luce laser retrodiffusa Compton, con un bordo, misurata fino a 1.72 GeV.

Un canale non è nel campione per scelta: `γp → nπ⁺π⁰π⁰`, escluso finché non
esiste una misura della leakage dei pioni carichi nel taglio dE/dx del BGO
(vedi la wiki, [03-mc-simulation](https://github.com/AntoninoFulci/GRAAL_Analysis/wiki/03-mc-simulation)).

La ricostruzione sta dopo il training perché il run BDT ha bisogno del modello, che
esiste solo dopo la fase 6; i plot stanno in fondo perché confrontano le due
ricostruzioni e le vogliono entrambe.

## Test

```bash
pytest
```
