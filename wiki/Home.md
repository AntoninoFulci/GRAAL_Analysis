# GRAAL Analysis

Analisi dei dati dell'esperimento GRAAL (Grenoble Anneau Accélérateur Laser).

In prima battuta il codice verrà utilizzato per la reazione fotoproduzione **γp → p η π⁰**.

L'η e il π⁰ decadono ciascuno in due fotoni (η→γγ, π⁰→γγ), quindi il rivelatore vede quattro fotoni nello stato finale.
L'analisi deve risolvere un problema combinatorio: capire quali due fotoni vengono dall'η e quali due
dal π⁰.
 Il codice risolve questo problema in due modi distinti, pensati fin dall'inizio per essere confrontati fra loro piuttosto che per sostituirsi l'uno all'altro:

- **ricostruzione chi2** (`reconstruction.reconstruct_eta_pi0_chi2`): l'analisi standard: prova tutti gli accoppiamenti possibili dei quattro fotoni e tiene quello che minimizza un chi2 contro le masse nominali di η e π⁰;
- **ricostruzione con gate BDT** (`reconstruction.reconstruct_eta_pi0_bdt`): identica alla precedente, ma ogni evento deve prima superare un classificatore BDT (stage-1) addestrato a riconoscere il fondo fisico (π⁰π⁰, 3π⁰, η2π⁰, ωπ⁰, η′) prima ancora di arrivare al chi2.

Il BDT **non ricostruisce**: non appaia fotoni e non produce masse. Restituisce
uno score di classificazione; il gate accetta l'evento quando lo score supera
la soglia scelta sul campione di validazione MC. Lo score non è automaticamente
una probabilità calibrata sui dati reali.

## Le varie fasi

`run_pipeline.sh` esegue la catena in otto fasi numerate, in quest'ordine:

| # | Fase | Cartella | Da → a |
|---|------|----------|--------|
| 1 | Pre-analisi | `01_pre_analysis/` | `data/graal_data/` → `data/pre_analyzed/` (albero `h80`) |
| 2 | Selezione eventi | `02_event_selector/` | `data/pre_analyzed/` → `data/selected/` (albero `h85`) |
| 3 | Simulazione Monte Carlo | `03_mc_simulation/` | 9 canali: segnale + 8 fondi |
| 4 | Build feature stage-1 | `04_bdt_training/` | MC → matrice di feature |
| 5 | Grid search iper-parametri | `04_bdt_training/` | → `best_hyperparams.json` |
| 6 | Training BDT stage-1 | `04_bdt_training/` | → modello + soglia |
| 7 | Ricostruzione | `05_reconstruction/` | `data/selected/` → `results/reco/` (chi2 **e** BDT) |
| 8 | Plot | `06_plots/` | `results/reco/` → `results/plots/` (Dalitz + masse) |

## NEXT

- [Pipeline](pipeline) — `run_pipeline.sh` fase per fase, tutti i flag, la logica di riuso di MC e pre-analisi.
- [Formati dati](data-formats) — la lineage degli alberi ROOT, da `h70` grezzo fino a `reco_eta_pi0_chi2`/`reco_eta_pi0_bdt`.
- Le pagine `01_`…`06_` — una per cartella, con il dettaglio dei cut, della fisica di ricostruzione, delle feature BDT e dei plot.
