# Testing

Ci sono due modi di collaudare questa pipeline, e coprono cose diverse: la
suite pytest verifica la fisica e la logica di controllo senza toccare
ROOT né ore di calcolo; `test_data/` con `--test-data` verifica che
l'idraulica dei file — cartelle, nomi, formati — funzioni davvero, usando
dati reali (anche se pochi) e il Monte Carlo/modello veri.

## La suite pytest

```bash
pytest
```

`pyproject.toml` dichiara dove cercare i test:

```toml
[tool.pytest.ini_options]
testpaths = ["00_common/tests", "03_mc_simulation/tests", "04_bdt_training/tests", "05_reconstruction/tests", "06_plots/tests"]
addopts = "--import-mode=importlib"
```

`--import-mode=importlib` non è opzionale: le cartelle `tests/` finirebbero
tutte per collidere sul nome di pacchetto `tests`, perché le loro cartelle
padre sono numerate e quindi non possono comparire come prefisso
nell'import mode di default di pytest.

### Cosa copre

| File | Cosa verifica |
|---|---|
| `00_common/tests/test_channels.py` | il registry dei canali: risoluzione per nome file (mai per posizione in lista), round-trip nome↔file; che il segnale **non** abbia una sezione d'urto (è la misura, non un ingresso) e i fondi sì; che `resolve_hypothesis` rifiuti di indovinare per i canali che non fissano un'ipotesi a due mesoni, e accetti un override esplicito |
| `00_common/tests/test_pairing.py` | l'**unico** chi2: masse di coppia, formula, enumerazione degli accoppiamenti (6 per due mesoni diversi, 3 se degeneri), che riproduca riga per riga la tabella `combinations_*.txt` che stava su disco, e — la regressione che conta — che la feature 8 del BDT e il numero che la ricostruzione minimizza siano lo stesso codice |
| `05_reconstruction/tests/test_packaging.py` | i pacchetti numerati sono importabili sotto i nomi puliti |
| `05_reconstruction/tests/test_reco_physics.py` | le etichette dei branch di ogni canale, e che i canali portino l'ipotesi del registry e non una copia |
| `04_bdt_training/tests/test_beam_spectrum.py` | la misura dello spettro del fascio e la riponderazione: che un campione piatto prenda la forma del bersaglio, che riponderare sul proprio spettro non cambi nulla, e che gli eventi a energie che i dati non hanno mai prodotto pesino zero |
| `05_reconstruction/tests/test_stage1_gate.py` | `Stage1Gate.accepts_many` sopra/sotto/esattamente alla soglia, e che ogni evento del blocco riceva il proprio verdetto nell'ordine giusto; che il modello riceva esattamente le feature di `compute_stage1_features` (regressione contro un disallineamento già successo in passato), costruite sull'ipotesi su cui è stato trainato; `Stage1Gate.load` solleva `FileNotFoundError` se mancano modello, soglia o provenance; `check_hypothesis` rifiuta un modello trainato su un altro stato finale |
| `03_mc_simulation/tests/test_mc_status.py` | stato/staleness dei 9 canali; exit code 0/1/2 della CLI; che `--help` esca con 0 |
| `04_bdt_training/tests/test_photon_loss.py` | il modello di perdita fotoni (`LossParams`, `p_loss`, `apply_loss_events`, `estimate_survival`) |
| `04_bdt_training/tests/test_build_background_features.py` | le 24 feature stage-1; che i nomi e il chi2 seguano l'ipotesi passata (gli stessi quattro fotoni sono un η+π⁰ perfetto e un 2π⁰ pessimo); che `shuffle_photons` non faccia migrare fotoni fra eventi e lasci intatte le feature indipendenti dall'ordine |
| `04_bdt_training/tests/test_callbacks.py` | la callback di progress-bar per il training XGBoost |

### Perché non importa mai ROOT

In tutto il repository, solo due moduli fanno `import ROOT`:
`05_reconstruction/reco_core.py` e `02_event_selector/select_events.py`. Nessuno
dei due sta sotto una cartella di `testpaths`. Questo non è un caso: la fisica
di accoppiamento chi2 vive in `00_common/pairing.py`, il gate BDT in
`05_reconstruction/stage1_gate.py`, le feature in
`04_bdt_training/build_background_features.py` — tutti moduli scritti come
funzioni pure su array numpy, senza I/O, proprio perché potessero essere
testati senza un'installazione di ROOT. `reco_core.py` fa solo da guscio di
I/O: sposta dati dentro e fuori da ROOT, applica il gate, ma non contiene
fisica propria da testare in isolamento.

Il prezzo è che `reco_core.py` **non è coperto**, e con lui il contratto più
importante della catena: che l'unica differenza fra il run chi2 e il run BDT
sia il gate. Oggi quel contratto è verificato solo guardando che i due run
stampino lo stesso `Skipped (not exactly 1 proton)`.

## `test_data/` e `--test-data`

```bash
./run_pipeline.sh --test-data --skip-mc --skip-train
```

`--test-data` rimappa le quattro cartelle dati del rivelatore
(`RAW_DIR`, `PRE_DIR`, `SELECTED_DIR`) e i risultati (`RECO_DIR`,
`PLOTS_DIR`) sotto `test_data/`,
con la stessa struttura che hanno sul server — vedi [Pipeline](pipeline)
per i default esatti. La cartella non è versionata: te la crei e te la
riempi.

```bash
mkdir -p test_data/raw
scp -r <server>:/data/graal/graal_data/<nome_run> test_data/raw/
```

Una o due run intere (non singoli file), scegliendo run piccole: la
pre-analisi le legge tutte. La struttura attesa è una cartella per run con
dentro i `.root` grezzi. Se `test_data/raw/` non c'è, la fase 1 si ferma
dicendolo.

### Cosa prova questo collaudo, e cosa no

Il comando sopra fa girare la catena intera — pre-analisi, selezione,
ricostruzione chi2 e ricostruzione con gate BDT — **usando il Monte Carlo e
il modello BDT veri**, non copie di prova: `--test-data` non li rimappa mai
(vedi [Pipeline](pipeline)). Questo è deliberato: duplicare MC e modello per
il collaudo non proverebbe niente di più su cosa funziona, e la generazione
MC costa ore.

Di conseguenza, un run con `--skip-mc --skip-train` prova che l'idraulica
delle fasi 1, 2 e 7 funziona (cartelle giuste, alberi ROOT letti e scritti
coi nomi giusti, il gate BDT carica un modello vero e produce risultati) —
ma **non** prova che la generazione MC (fase 3) o il training BDT (fasi 5-6)
funzionino: quelle restano scoperte da questo collaudo, e sono responsabilità
della suite pytest (per la logica) o di un run completo senza
`--skip-mc`/`--skip-train` (per l'esecuzione vera, costosa in tempo).

Niente di `test_data/` viene versionato — né i dati né lo scheletro delle
cartelle.
