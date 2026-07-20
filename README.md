# GRAAL Analysis

Analisi dei dati dell'esperimento GRAAL per la reazione **γp → p η π⁰**.

L'η e il π⁰ decadono ciascuno in due fotoni, quindi il rivelatore vede quattro
fotoni e l'analisi deve capire quali due vengono dall'η e quali dal π⁰.
Il codice lo fa in due modi, pensati per essere confrontati: 
- una **minimizzazione del chi2** (l'analisi standard)
- la stessa minimizzazione preceduta da un **gate BDT** che scarta gli eventi di fondo.

📖 **[Wiki](https://github.com/AntoninoFulci/GRAAL_Analysis/wiki)** — ogni fase spiegata in dettaglio.

## Installazione

```bash
pip install -e .
```

Le cartelle sono numerate (`01_`, `02_`, …) per rendere visibile l'ordine della pipeline l'installazione mappa i nomi importabili sulle cartelle. Senza, nessun import funziona.

## Come si lancia

```bash
./run_pipeline.sh                # catena completa sui dati veri
./run_pipeline.sh --test-data    # collaudo su 1-2 run di prova (vedi wiki, Testing)
./run_pipeline.sh --help         # tutte le flag
```

Ogni fase riusa quello che trova: il Monte Carlo già generato e la pre-analisi già fatta non vengono rifatti (`--force-mc` e `--force-preanalysis` per forzarli).

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

I dati del rivelatore stanno tutti sotto `data/`. 
Quello su cui le fasi devono essere d'accordo — masse dei mesoni, elenco dei canali, sezioni d'urto — sta in `00_common/` (non è una fase dell'analisi ma una sorta di vocabolario comune).

<!-- ## Scambiare il canale di segnale

Il BDT impara a riconoscere un canale; gli altri diventano il suo fondo. Quale
sia è in linea di principio una scelta, ma la catena è costruita attorno a
`eta_pi0` come segnale e questo è l'unico valore che `run_pipeline.sh` fa girare
da capo a fondo:

```bash
./run_pipeline.sh --signal-channel eta_pi0   # il default
```

Il motivo è fisico. `eta_pi0` non ha una sezione d'urto nel registro — misurarla
è lo scopo dell'analisi — e `eta_pi0_via_3pi0` è agganciato a `eta_pi0` tramite
il rapporto di branching. Entrambi hanno senso come fondo solo quando `eta_pi0`
è il segnale; con un altro segnale, `eta_pi0` resterebbe fra i fondi senza nulla
con cui pesarlo, e `build_background_features` si ferma con un errore chiaro che
dice di escluderlo. Per provare un segnale diverso serve lo strumento diretto,
escludendo a mano i canali senza sezione d'urto propria:

```bash
python -m bdt_training.build_background_features \
    --signal-channel pi0pi0 \
    --background-channels 3pi0 eta_2pi0 omega_pi0 etaprime eta_via_3pi0 4pi0 \
    --beam-spectrum 04_bdt_training/data/beam_spectrum.npz \
    --output features.npz
```

Il modello si porta dietro il canale su cui è stato trainato, e il gate rifiuta
di filtrare una ricostruzione che non è la sua.

Quale canale sia il segnale e quale **ipotesi a due mesoni** alimenti il chi2
sono due scelte distinte: solo `eta_pi0` e `pi0pi0` fissano un'ipotesi da soli
(η+π⁰ e 2π⁰); per tutti gli altri — 3π⁰, η2π⁰, ωπ⁰, η′, η(→3π⁰), 4π⁰ ed
ηπ⁰(→3π⁰) — osservati come 4γ sono un sottoinsieme dei mesoni visibili, e il
codice chiede (`--hypothesis`) invece di indovinare. -->
