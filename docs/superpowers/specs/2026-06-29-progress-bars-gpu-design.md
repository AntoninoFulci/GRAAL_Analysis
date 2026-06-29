# Design: Progress Bars e Ottimizzazione CPU/GPU — Stage-1 BDT Pipeline

**Data:** 2026-06-29  
**Scope:** `analysis/ml/grid_search_stage1.py`, `analysis/ml/train_bdt_stage1.py`, `analysis/ml/callbacks.py` (nuovo), `run_pipeline.sh`, `analysis/ml/requirements.txt`

---

## Motivazione

La pipeline stage-1 (grid search + training) gira per ~10 min senza alcun feedback visivo intermedio — solo print dopo ogni config. Aggiunta di:

1. **Progress bar outer** per grid search (tqdm, per-config)
2. **Progress bar inner** per training singolo (XGBoost callback → tqdm per-albero), opzionale durante grid search
3. **Parametro `--device`** future-proof per GPU (default `cpu`; `nthread=-1` esplicito)
4. **Stage progress** in `run_pipeline.sh` con timestamp

---

## Vincoli e contesto

- XGBoost 3.3.0, macOS arm64, `USE_CUDA: False` — nessun backend Metal/MPS disponibile nel pip standard
- `tree_method="hist"` già in uso (ottimale per CPU)
- La barra per-albero è silenziata durante grid search (output sarebbe troppo denso con 30 config × 400 alberi)
- `tqdm` non è ancora in `requirements.txt`

---

## Architettura

### 1. `analysis/ml/callbacks.py` — nuovo file

Modulo con `TqdmCallback`, una sottoclasse di `xgb.callback.TrainingCallback`.

```
TqdmCallback
├── __init__(n_estimators, desc, val_metric)
│       crea tqdm bar con total=n_estimators
├── after_iteration(model, epoch, evals_log)
│       aggiorna bar di 1; imposta postfix con ultima metrica val
└── after_training(model)
        chiude la bar
```

**Interfaccia pubblica:**

```python
from analysis.ml.callbacks import TqdmCallback

cb = TqdmCallback(n_estimators=600, desc="training", val_metric="auc")
model.fit(..., callbacks=[cb])
```

Pensato per essere riutilizzabile anche da `train_bdt.py` (stage-2) in futuro.

---

### 2. `grid_search_stage1.py` — modifiche

**Outer loop:** `tqdm` wrappa `enumerate(candidates)`.

```python
from tqdm import tqdm

pbar = tqdm(candidates, desc="grid search", unit="cfg",
            bar_format="{l_bar}{bar}| {n}/{total} [{elapsed}<{remaining}]")
for cfg in pbar:
    auc, n_est = _train_single(...)
    if auc > best_auc:
        best_auc = auc
    pbar.set_postfix({"best": f"{best_auc:.4f}", "last": f"{auc:.4f}"})
```

**Inner training:** `verbose=False`, nessun `TqdmCallback` — rumore eccessivo.

**Nuovi parametri CLI:**
- `--device` (default `"cpu"`) — passato a `xgb.XGBClassifier(device=...)`
- `--nthread` (default `-1`) — passato a `xgb.XGBClassifier(nthread=...)`

**Output invariato:** `grid_search_results.csv`, `best_hyperparams.json`.

---

### 3. `train_bdt_stage1.py` — modifiche

**Comportamento default (standalone):** mostra barra per-albero via `TqdmCallback`.

```python
callbacks = []
if args.verbose:          # default True
    callbacks.append(TqdmCallback(n_estimators=n_est, desc="training"))

model = xgb.XGBClassifier(
    ...,
    device=args.device,   # default "cpu"
    nthread=args.nthread, # default -1
)
model.fit(..., callbacks=callbacks, verbose=False)
```

**Nuovi parametri CLI:**
- `--device` (default `"cpu"`)
- `--nthread` (default `-1`)
- `--no-verbose` flag per silenziare la barra (utile se chiamato da script)

---

### 4. `run_pipeline.sh` — modifiche

Funzione helper:

```bash
stage() {
    local n=$1 total=$2 desc=$3
    echo ""
    echo "[${n}/${total}] ${desc}  ($(date '+%H:%M:%S'))"
}
```

Usata prima di ogni step:

```bash
TOTAL_STAGES=4
stage 1 $TOTAL_STAGES "Generazione MC (${NEVENTS} eventi per canale)"
# ... root commands ...

stage 2 $TOTAL_STAGES "Build features stage-1"
# ... python build_background_features ...

stage 3 $TOTAL_STAGES "Grid search + training BDT stage-1"
# ... python grid_search_stage1 + train_bdt_stage1 ...

stage 4 $TOTAL_STAGES "Training BDT stage-2 (opzionale)"
# ...
```

Al completamento di ogni stage, stampa il tempo elapsed:

```bash
T0=$(date +%s)
# ... comando ...
T1=$(date +%s)
echo "    -> completato in $((T1-T0))s"
```

---

### 5. `requirements.txt` — aggiunta

```
tqdm>=4.0
```

---

## Flusso dati e interazioni

```
run_pipeline.sh
    │
    ├─[1/4] root generate_*.C        (nessuna barra Python)
    ├─[2/4] build_background_features.py  (print esistenti invariati)
    ├─[3/4] grid_search_stage1.py     ──► tqdm outer [cfg 5/30 | best: 0.9986]
    │           └── _train_single()   ──► verbose=False, nessuna barra interna
    │       train_bdt_stage1.py       ──► TqdmCallback [tree 320/600 | auc: 0.9987]
    └─[4/4] train_bdt.py              (invariato per ora)
```

---

## GPU — strategia

| Situazione | Azione |
|------------|--------|
| macOS arm64, pip XGBoost | `device="cpu"`, `tree_method="hist"`, `nthread=-1` |
| Futuro: XGBoost con Metal | Passare `--device mps` (se supportato) senza modifiche al codice |
| Futuro: macchina CUDA | Passare `--device cuda` |

Il parametro `--device` viene scritto in `best_hyperparams.json` solo se diverso da `"cpu"`.

---

## Testing

Nessun test unitario nuovo richiesto per le progress bar (sono UI). Verificare manualmente:

1. `python -m analysis.ml.train_bdt_stage1 --features features_stage1.npz` → barra per-albero visibile
2. `python -m analysis.ml.grid_search_stage1 --n-iter 5` → barra outer visibile, nessuna barra per-albero
3. `./run_pipeline.sh --nevents 10000` → stage progress con timestamp

Test esistenti (40) devono rimanere verdi — i callback non toccano logica ML.

---

## File modificati / creati

| File | Tipo |
|------|------|
| `analysis/ml/callbacks.py` | nuovo |
| `analysis/ml/grid_search_stage1.py` | modifica (tqdm outer, --device, --nthread) |
| `analysis/ml/train_bdt_stage1.py` | modifica (TqdmCallback, --device, --nthread, --no-verbose) |
| `run_pipeline.sh` | modifica (funzione stage, timing) |
| `analysis/ml/requirements.txt` | modifica (tqdm>=4.0) |

---

## Non in scope

- Progress bar per `build_background_features.py` (già veloce, non necessaria)
- Integrazione `rich` (overhead per scarso beneficio)
- Build XGBoost con Metal SDK (instabile)
- BDT stage-2 (`train_bdt.py`) — invariato per ora
