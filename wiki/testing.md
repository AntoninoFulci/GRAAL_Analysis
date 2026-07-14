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
testpaths = ["03_analysis/tests", "04_mc_simulation/tests", "05_analysis_bdt/tests"]
addopts = "--import-mode=importlib"
```

`--import-mode=importlib` non è opzionale: le tre cartelle `tests/` finirebbero
tutte per collidere sul nome di pacchetto `tests`, perché le loro cartelle
padre sono numerate e quindi non possono comparire come prefisso
nell'import mode di default di pytest.

### Cosa copre

| File | Cosa verifica |
|---|---|
| `03_analysis/tests/test_packaging.py` | i pacchetti numerati sono importabili sotto i nomi puliti |
| `03_analysis/tests/test_reco_physics.py` | massa invariante, formula del chi2, `best_combination` (accoppiamento vincente), `assign_pairs` (scambio eta/pi0 quando il target pesante arriva per secondo) |
| `03_analysis/tests/test_stage1_gate.py` | `Stage1Gate.accepts` sopra/sotto/esattamente alla soglia; che il modello riceva esattamente le feature di `compute_stage1_features` (regressione contro un disallineamento già successo in passato); `Stage1Gate.load` solleva `FileNotFoundError` se mancano modello o soglia |
| `04_mc_simulation/tests/test_mc_status.py` | stato/staleness dei 6 canali; exit code 0/1/2 della CLI; che `--help` esca con 0 |
| `05_analysis_bdt/tests/test_physics.py` | massa invariante, asimmetria di energia, angolo di apertura, boost al sistema del centro di massa — tutto vettorizzato |
| `05_analysis_bdt/tests/test_photon_loss.py` | il modello di perdita fotoni (`LossParams`, `p_loss`, `apply_loss_events`, `estimate_survival`) |
| `05_analysis_bdt/tests/test_build_background_features.py` | le 24 feature stage-1, `channel_from_filename` (il canale deve venire dal nome file, mai dalla posizione in lista) |
| `05_analysis_bdt/tests/test_build_features.py` | forma/etichette della matrice di feature, assenza di leakage posizionale prima dell'ordinamento chi2 |
| `05_analysis_bdt/tests/test_callbacks.py` | la callback di progress-bar per il training XGBoost |

### Perché non importa mai ROOT

In tutto il repository, solo due moduli fanno `import ROOT`:
`03_analysis/reco_core.py` e `02_event_selector/select_events.py`. Nessuno
dei due sta sotto una delle tre cartelle `testpaths`. Questo non è un caso:
la fisica di accoppiamento chi2 vive in `03_analysis/reco_physics.py`, il
gate BDT in `03_analysis/stage1_gate.py`, le feature in
`05_analysis_bdt/build_background_features.py` — tutti moduli scritti come
funzioni pure su array numpy, senza I/O, proprio perché potessero essere
testati senza un'installazione di ROOT. `reco_core.py` fa solo da guscio di
I/O attorno a `reco_physics.py`: sposta dati dentro e fuori da ROOT, applica
il gate, ma non contiene fisica propria da testare in isolamento.

## `test_data/` e `--test-data`

```bash
./run_pipeline.sh --test-data --skip-mc --skip-train
```

`--test-data` rimappa le quattro cartelle dati del rivelatore
(`RAW_DIR`, `PRE_DIR`, `SELECTED_DIR`, `ANALYZED_DIR`) sotto `test_data/`,
con la stessa struttura che hanno sul server — vedi [Pipeline](pipeline)
per i default esatti. Cosa copiarci dentro, da
`test_data/README.md`:

```bash
scp -r <server>:/data/graal/graal_data/<nome_run> test_data/raw/
```

Una o due run intere (non singoli file), scegliendo run piccole: la
pre-analisi le legge tutte. La struttura attesa è una cartella per run con
dentro i `.root` grezzi.

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

Nessun output di `test_data/` esce dalla cartella né viene versionato: solo
`test_data/README.md` e lo scheletro delle sottocartelle stanno in git.
