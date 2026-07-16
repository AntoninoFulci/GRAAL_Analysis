# GRAAL Analysis

Analisi dei dati dell'esperimento GRAAL (Grenoble Anneau Accélérateur Laser)
per la reazione fotoproduzione **γp → p η π⁰**.

L'η e il π⁰ decadono ciascuno in due fotoni (η→γγ, π⁰→γγ), quindi il
rivelatore vede quattro fotoni nello stato finale e l'analisi deve risolvere
un problema combinatorio: capire quali due fotoni vengono dall'η e quali due
dal π⁰. Il codice risolve questo problema in due modi distinti, pensati fin
dall'inizio per essere confrontati fra loro piuttosto che per sostituirsi
l'uno all'altro:

- **ricostruzione chi2** (`reconstruction.reconstruct_eta_pi0_chi2`) —
  l'analisi standard: prova tutti gli accoppiamenti possibili dei quattro
  fotoni e tiene quello che minimizza un chi2 contro le masse nominali di η
  e π⁰;
- **ricostruzione con gate BDT** (`reconstruction.reconstruct_eta_pi0_bdt`) —
  identica alla precedente, ma ogni evento deve prima superare un
  classificatore BDT (stage-1) addestrato a riconoscere il fondo fisico
  (π⁰π⁰, 3π⁰, η2π⁰, ωπ⁰, η′) prima ancora di arrivare al chi2.

Il BDT **non ricostruisce**: non appaia fotoni e non produce masse. Dice solo
sì o no. A ricostruire è sempre e solo il chi2, in entrambi i rami.

Le due ricostruzioni condividono lo stesso codice di I/O e lo stesso taglio
chi2 (`05_reconstruction/reco_core.py`): l'unica differenza tra i due file di
output è il gate BDT, ed è così che il confronto ha senso — qualunque
differenza tra `reco_eta_pi0_chi2` e `reco_eta_pi0_bdt` si può attribuire
al gate e a nient'altro.

## `pip install -e .` è obbligatorio

Questa è la cosa più probabile su cui ci si inciampa al primo avvio. Le
cartelle della pipeline sono numerate (`01_pre_analysis/`,
`02_event_selector/`, …) apposta, per rendere visibile sul filesystem
l'ordine in cui girano le fasi. Ma un nome di pacchetto Python **non può
iniziare con una cifra**, quindi quelle cartelle non sono import validi così
come sono. `pyproject.toml` risolve la contraddizione mappando ogni cartella
numerata su un nome di pacchetto pulito:

| Cartella | Pacchetto importabile |
|---|---|
| `00_common/` | `graal_common` |
| `01_pre_analysis/` | — (macro ROOT, non un pacchetto Python) |
| `02_event_selector/` | `event_selector` |
| `03_mc_simulation/` | `mc_simulation` |
| `04_bdt_training/` | `bdt_training` |
| `05_reconstruction/` | `reconstruction` |
| `06_plots/` | `plots` |

**Il numero è l'ordine in cui la fase gira**, e deve restare tale o non vale
niente. Per un po' non lo è stato: la ricostruzione era `03` ma girava quinta,
dopo il Monte Carlo (`04`) e il training (`05`), perché ha bisogno del modello
che quei due producono. Leggere l'elenco delle cartelle dall'alto insegnava
l'ordine sbagliato.

Anche i nomi mentivano: `analysis` e `analysis_bdt` leggevano come "l'analisi" e
"l'analisi col BDT", cioè due analisi alternative. Non lo sono. La ricostruzione
è **una** — il chi2 — e il BDT è un cancello che le sta davanti.

`00_common/` non è una fase: è ciò su cui le fasi devono essere d'accordo — le
masse dei mesoni, l'elenco dei canali, le sezioni d'urto. È numerato `00` solo
per ordinarsi sopra le fasi che lo usano. Le masse vivevano in tre moduli
contemporaneamente, uno dei quali portava un commento che chiedeva al lettore
di tenerle allineate a mano.

Questa mappatura esiste solo dopo un'installazione editable:

```bash
pip install -e .
```

Senza, ogni `python -m <pacchetto>...` fallisce con `ModuleNotFoundError`. Lo
script `run_pipeline.sh` lo sa e non lascia scoprire il problema a metà
esecuzione: prova a importare tutti i pacchetti della tabella qui sopra prima
di lanciare qualunque fase, e se anche uno solo manca si ferma subito, con un
messaggio che dice esattamente cosa fare. Il controllo li elenca tutti apposta:
lo stage dei plot è l'ultimo della catena, e senza `plots` nel preflight
l'errore salterebbe fuori dopo ore di ricostruzione invece che in partenza.
Vedi [Pipeline](pipeline) per il testo esatto.

Nota per chi aggiorna un clone già esistente: l'installazione editable registra
i pacchetti una volta sola, quindi un `git pull` che ne aggiunge uno nuovo non
basta — va rifatto `pip install -e .`.

## Le otto fasi

`run_pipeline.sh` esegue la catena in otto fasi numerate, in quest'ordine:

| # | Fase | Cartella | Da → a |
|---|------|----------|--------|
| 1 | Pre-analisi | `01_pre_analysis/` | `data/graal_data/` → `data/pre_analyzed/` (albero `h80`) |
| 2 | Selezione eventi | `02_event_selector/` | `data/pre_analyzed/` → `data/selected/` (albero `h85`) |
| 3 | Simulazione Monte Carlo | `03_mc_simulation/` | 6 canali: segnale + 5 fondi |
| 4 | Build feature stage-1 | `04_bdt_training/` | MC → matrice di feature |
| 5 | Grid search iper-parametri | `04_bdt_training/` | → `best_hyperparams.json` |
| 6 | Training BDT stage-1 | `04_bdt_training/` | → modello + soglia |
| 7 | Ricostruzione | `05_reconstruction/` | `data/selected/` → `results/reco/` (chi2 **e** BDT) |
| 8 | Plot | `06_plots/` | `results/reco/` → `results/plots/` (Dalitz + masse) |

L'ordine non è arbitrario: la ricostruzione sta dopo il training perché il run
con gate BDT ha bisogno del modello, che esiste solo dopo la fase 6; e i plot
stanno in fondo perché confrontano le due ricostruzioni, quindi le vogliono
entrambe. Vedi [Pipeline](pipeline) per il dettaglio di ogni fase, dei flag e
della logica di riuso.

## Dove andare da qui

- [Pipeline](pipeline) — `run_pipeline.sh` fase per fase, tutti i flag, la
  logica di riuso di MC e pre-analisi, `--test-data`.
- [Formati dati](data-formats) — la lineage degli alberi ROOT, da `h70`
  grezzo fino a `reco_eta_pi0_chi2`/`reco_eta_pi0_bdt`.
- [Testing](testing) — la suite pytest e il collaudo con `test_data/`.
- Le pagine `01_`…`06_` — una per cartella, con il dettaglio dei cut, della
  fisica di ricostruzione, delle feature BDT e dei plot.
