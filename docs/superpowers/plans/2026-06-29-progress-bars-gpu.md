# Progress Bars + Device Param — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aggiungere progress bar tqdm (outer per grid search, per-albero per training singolo) e parametro `--device` future-proof per GPU a `grid_search_stage1.py` e `train_bdt_stage1.py`; stage progress con timing a `run_pipeline.sh`.

**Architecture:** `TqdmCallback` in `callbacks.py` aggancia il sistema callback di XGBoost per la barra per-albero; `tqdm` wrappa direttamente il loop config in grid search; `run_pipeline.sh` usa una funzione `stage()` bash con timestamp e timing.

**Tech Stack:** Python 3.9+, XGBoost 3.3.0, tqdm>=4.0, bash

## Global Constraints

- Python: `analysis/` usa `from __future__ import annotations`
- XGBoost callback API: `before_training(model)→model`, `after_iteration(model, epoch, evals_log)→bool`, `after_training(model)→model`
- `evals_log` struttura: `{"validation_0": {"auc": [v1, v2, ...]}, ...}`
- `--device` default `"cpu"`, valori futuri: `"cuda"`, `"mps"` (quando XGBoost li supporterà)
- `--nthread` default `-1` (tutti i core)
- Nessun test per la UI tqdm stessa; test per integrazione callback + passthrough parametri
- 40 test esistenti devono restare verdi

---

## File Map

| File | Azione |
|------|--------|
| `analysis/ml/requirements.txt` | Modifica — aggiunge `tqdm>=4.0` |
| `analysis/ml/callbacks.py` | Crea — `TqdmCallback` |
| `analysis/ml/tests/test_callbacks.py` | Crea — integration test |
| `analysis/ml/grid_search_stage1.py` | Modifica — tqdm outer, `--device`, `--nthread` |
| `analysis/ml/train_bdt_stage1.py` | Modifica — `TqdmCallback`, `--device`, `--nthread`, `--no-verbose` |
| `run_pipeline.sh` | Modifica — funzione `stage()`, timing, grid search step |

---

## Task 1: tqdm in requirements.txt

**Files:**
- Modify: `analysis/ml/requirements.txt`

**Interfaces:**
- Produces: `tqdm` disponibile per tutti i task successivi

- [ ] **Step 1: Aggiungi tqdm a requirements.txt**

Apri `analysis/ml/requirements.txt` e aggiungi `tqdm>=4.0` dopo matplotlib:

```
uproot==5.7.4
awkward==2.9.1
xgboost==3.2.0
scikit-learn==1.9.0
numpy>=2.0
matplotlib>=3.10
tqdm>=4.0
pytest>=8.0
```

- [ ] **Step 2: Installa**

```bash
pip install tqdm
```

Expected: `Successfully installed tqdm-...`

- [ ] **Step 3: Verifica**

```bash
python -c "import tqdm; print(tqdm.__version__)"
```

Expected: versione >= 4.0 stampata.

- [ ] **Step 4: Commit**

```bash
git add analysis/ml/requirements.txt
git commit -m "deps: add tqdm>=4.0 for progress bars"
```

---

## Task 2: TqdmCallback in callbacks.py

**Files:**
- Create: `analysis/ml/callbacks.py`
- Create: `analysis/ml/tests/test_callbacks.py`

**Interfaces:**
- Produces:
  ```python
  class TqdmCallback(xgb.callback.TrainingCallback):
      def __init__(self, n_estimators: int, desc: str = "training", val_metric: str = "auc") -> None
  ```
- Consumes: nulla da task precedenti oltre a tqdm installato

- [ ] **Step 1: Scrivi il test di integrazione (failing)**

Crea `analysis/ml/tests/test_callbacks.py`:

```python
"""Integration test for TqdmCallback — verifies XGBoost integration without errors."""
from __future__ import annotations

import numpy as np
import xgboost as xgb


def _tiny_dataset(n: int = 200, seed: int = 0):
    rng = np.random.default_rng(seed)
    X = rng.standard_normal((n, 5)).astype(np.float32)
    y = (X[:, 0] + rng.standard_normal(n) * 0.5 > 0).astype(np.float32)
    return X, y


def test_tqdm_callback_completes_training():
    """TqdmCallback should allow XGBoost to train to completion without error."""
    from analysis.ml.callbacks import TqdmCallback

    X, y = _tiny_dataset()
    X_tr, X_val = X[:160], X[160:]
    y_tr, y_val = y[:160], y[160:]

    cb = TqdmCallback(n_estimators=10, desc="test", val_metric="auc")
    model = xgb.XGBClassifier(
        n_estimators=10,
        eval_metric="auc",
        random_state=42,
        tree_method="hist",
        verbosity=0,
    )
    model.fit(X_tr, y_tr, eval_set=[(X_val, y_val)], callbacks=[cb], verbose=False)

    assert model.best_iteration >= 0


def test_tqdm_callback_after_iteration_returns_false():
    """after_iteration must return False to not stop training early."""
    from analysis.ml.callbacks import TqdmCallback

    cb = TqdmCallback(n_estimators=5, desc="test", val_metric="auc")

    class _FakeModel:
        pass

    cb.before_training(_FakeModel())
    fake_evals_log = {"validation_0": {"auc": [0.95, 0.96]}}
    result = cb.after_iteration(_FakeModel(), epoch=1, evals_log=fake_evals_log)
    assert result is False
    cb.after_training(_FakeModel())


def test_tqdm_callback_no_crash_missing_metric():
    """TqdmCallback should not crash if val_metric is not in evals_log."""
    from analysis.ml.callbacks import TqdmCallback

    cb = TqdmCallback(n_estimators=5, desc="test", val_metric="auc")

    class _FakeModel:
        pass

    cb.before_training(_FakeModel())
    cb.after_iteration(_FakeModel(), epoch=0, evals_log={"validation_0": {"logloss": [0.5]}})
    cb.after_training(_FakeModel())
```

- [ ] **Step 2: Esegui il test per verificare che fallisce**

```bash
python -m pytest analysis/ml/tests/test_callbacks.py -v
```

Expected: `FAILED` con `ModuleNotFoundError: No module named 'analysis.ml.callbacks'`

- [ ] **Step 3: Crea callbacks.py**

Crea `analysis/ml/callbacks.py`:

```python
"""XGBoost training callbacks."""
from __future__ import annotations

import xgboost as xgb
from tqdm import tqdm


class TqdmCallback(xgb.callback.TrainingCallback):
    """Displays a tqdm progress bar during XGBoost training.

    Usage::

        cb = TqdmCallback(n_estimators=600, desc="training", val_metric="auc")
        model.fit(..., callbacks=[cb], verbose=False)
    """

    def __init__(
        self,
        n_estimators: int,
        desc: str = "training",
        val_metric: str = "auc",
    ) -> None:
        self._n = n_estimators
        self._desc = desc
        self._metric = val_metric
        self._bar: tqdm | None = None

    def before_training(self, model):
        self._bar = tqdm(total=self._n, desc=self._desc, unit="tree")
        return model

    def after_iteration(self, model, epoch: int, evals_log: dict) -> bool:
        if self._bar is not None:
            self._bar.update(1)
            for _dataset, metrics in evals_log.items():
                if self._metric in metrics:
                    val = metrics[self._metric][-1]
                    self._bar.set_postfix({self._metric: f"{val:.4f}"})
                    break
        return False

    def after_training(self, model):
        if self._bar is not None:
            self._bar.close()
        return model
```

- [ ] **Step 4: Esegui i test**

```bash
python -m pytest analysis/ml/tests/test_callbacks.py -v
```

Expected:
```
test_callbacks.py::test_tqdm_callback_completes_training PASSED
test_callbacks.py::test_tqdm_callback_after_iteration_returns_false PASSED
test_callbacks.py::test_tqdm_callback_no_crash_missing_metric PASSED
```

- [ ] **Step 5: Verifica che tutti i test esistenti passano**

```bash
python -m pytest analysis/ml/tests/ -v --tb=short
```

Expected: tutti PASSED (ora 43 test totali).

- [ ] **Step 6: Commit**

```bash
git add analysis/ml/callbacks.py analysis/ml/tests/test_callbacks.py
git commit -m "feat: add TqdmCallback for per-tree XGBoost progress bar"
```

---

## Task 3: grid_search_stage1.py — tqdm outer + --device + --nthread

**Files:**
- Modify: `analysis/ml/grid_search_stage1.py`

**Interfaces:**
- Consumes: `tqdm` (Task 1)
- Produces: `run_search(device="cpu", nthread=-1, ...)`, `_train_single(device, nthread, ...)`

- [ ] **Step 1: Aggiungi import tqdm in cima al file**

Dopo la riga `import random`, aggiungi:

```python
from tqdm import tqdm
```

- [ ] **Step 2: Aggiungi `device` e `nthread` a `_train_single`**

Modifica la firma di `_train_single`:

```python
def _train_single(
    X_tr: np.ndarray,
    y_tr: np.ndarray,
    w_tr: np.ndarray,
    X_val: np.ndarray,
    y_val: np.ndarray,
    w_val: np.ndarray,
    params: dict[str, Any],
    seed: int,
    device: str = "cpu",
    nthread: int = -1,
) -> tuple[float, int]:
    """Train one XGBoost config; return (val_auc, best_n_estimators)."""
    model = xgb.XGBClassifier(
        n_estimators=_N_ESTIMATORS_MAX,
        eval_metric="auc",
        random_state=seed,
        tree_method="hist",
        early_stopping_rounds=_EARLY_STOPPING_ROUNDS,
        device=device,
        nthread=nthread,
        **params,
    )
    model.fit(
        X_tr, y_tr,
        sample_weight=w_tr,
        eval_set=[(X_val, y_val)],
        sample_weight_eval_set=[w_val],
        verbose=False,
    )
    scores = model.predict_proba(X_val)[:, 1]
    auc = float(roc_auc_score(y_val, scores, sample_weight=w_val))
    best_n = int(model.best_iteration) + 1
    return auc, best_n
```

- [ ] **Step 3: Aggiungi `device` e `nthread` a `run_search` e sostituisci il loop con tqdm**

Modifica la firma di `run_search`:

```python
def run_search(
    features_path: str,
    out_dir: str = "analysis/ml/model",
    n_iter: int = 30,
    full_grid: bool = False,
    val_fraction: float = 0.20,
    seed: int = 42,
    device: str = "cpu",
    nthread: int = -1,
) -> None:
```

Dentro `run_search`, sostituisci il blocco del loop (da `print(f"\nSearching...` fino alla fine del `for i, cfg in enumerate(candidates):`) con:

```python
    print(f"\nSearching {len(candidates)} configurations …\n")

    results: list[dict] = []
    best_auc = -1.0
    best_cfg: dict = {}

    pbar = tqdm(candidates, desc="grid search", unit="cfg")
    for i, cfg in enumerate(pbar):
        t0 = time.time()
        try:
            auc, n_est = _train_single(
                X_tr, y_tr, w_tr, X_val, y_val, w_val, cfg, seed,
                device=device, nthread=nthread,
            )
        except Exception as exc:
            tqdm.write(f"  [{i+1}/{len(candidates)}] FAILED: {exc}")
            continue
        elapsed = time.time() - t0
        row = {"auc": auc, "n_estimators": n_est, "time_s": round(elapsed, 1), **cfg}
        results.append(row)

        if auc > best_auc:
            best_auc = auc
            best_cfg = dict(row)
        pbar.set_postfix(best=f"{best_auc:.4f}", last=f"{auc:.4f}")

        marker = " *" if auc == best_auc else ""
        tqdm.write(
            f"  [{i+1:3d}/{len(candidates)}] AUC={auc:.4f}  n_est={n_est:4d}"
            f"  depth={cfg['max_depth']}  lr={cfg['learning_rate']:.3f}"
            f"  sub={cfg['subsample']}  col={cfg['colsample_bytree']}"
            f"  mcw={cfg['min_child_weight']}  gam={cfg['gamma']}"
            f"  ({elapsed:.0f}s){marker}",
        )
```

- [ ] **Step 4: Aggiungi `--device` e `--nthread` a `_cli`**

Nella funzione `_cli()`, dopo `parser.add_argument("--seed", ...)`, aggiungi:

```python
    parser.add_argument("--device",  default="cpu",
                        help="XGBoost device: cpu (default), cuda, mps (future)")
    parser.add_argument("--nthread", type=int, default=-1,
                        help="XGBoost nthread; -1 = all cores")
```

Aggiorna la chiamata a `run_search`:

```python
    run_search(
        features_path=args.features,
        out_dir=args.out_dir,
        n_iter=args.n_iter,
        full_grid=args.full_grid,
        val_fraction=args.val_fraction,
        seed=args.seed,
        device=args.device,
        nthread=args.nthread,
    )
```

- [ ] **Step 5: Verifica visivamente la barra**

```bash
python -u -m analysis.ml.grid_search_stage1 \
    --features features_stage1.npz \
    --n-iter 2 \
    --out-dir /tmp/gs_test
```

Expected: barra tqdm nella forma `grid search:  50%|████░░| 1/2 [00:21<00:21, best=0.9981, last=0.9981]` + riga dettaglio per ogni config sotto.

- [ ] **Step 6: Verifica tutti i test**

```bash
python -m pytest analysis/ml/tests/ -v --tb=short
```

Expected: tutti PASSED.

- [ ] **Step 7: Commit**

```bash
git add analysis/ml/grid_search_stage1.py
git commit -m "feat: add tqdm outer progress bar and --device/--nthread to grid search"
```

---

## Task 4: train_bdt_stage1.py — TqdmCallback + --device + --nthread + --no-verbose

**Files:**
- Modify: `analysis/ml/train_bdt_stage1.py`

**Interfaces:**
- Consumes: `TqdmCallback` da `analysis.ml.callbacks` (Task 2)
- Produces: `train(device="cpu", nthread=-1, verbose=True, ...)`

- [ ] **Step 1: Aggiungi import TqdmCallback**

Dopo gli import esistenti, aggiungi:

```python
from analysis.ml.callbacks import TqdmCallback
```

- [ ] **Step 2: Aggiungi `device`, `nthread`, `verbose` alla firma di `train()`**

```python
def train(
    features_path: str,
    out_dir: str = "analysis/ml/model",
    val_fraction: float = 0.2,
    seed: int = 42,
    n_estimators: int = 300,
    max_depth: int = 5,
    learning_rate: float = 0.05,
    subsample: float = 0.8,
    colsample_bytree: float = 0.8,
    min_child_weight: int = 1,
    gamma: float = 0.0,
    device: str = "cpu",
    nthread: int = -1,
    verbose: bool = True,
) -> None:
```

- [ ] **Step 3: Sostituisci creazione modello e chiamata fit**

Sostituisci il blocco che crea `model` e chiama `model.fit(...)`:

```python
    model = xgb.XGBClassifier(
        n_estimators=n_estimators,
        max_depth=max_depth,
        learning_rate=learning_rate,
        subsample=subsample,
        colsample_bytree=colsample_bytree,
        min_child_weight=min_child_weight,
        gamma=gamma,
        eval_metric="auc",
        random_state=seed,
        tree_method="hist",
        device=device,
        nthread=nthread,
    )

    callbacks = []
    if verbose:
        callbacks.append(
            TqdmCallback(n_estimators=n_estimators, desc="training", val_metric="auc")
        )

    model.fit(
        X_tr, y_tr,
        sample_weight=w_tr,
        eval_set=[(X_val, y_val)],
        sample_weight_eval_set=[w_val],
        callbacks=callbacks,
        verbose=50 if not verbose else False,
    )
```

- [ ] **Step 4: Aggiungi `--device`, `--nthread`, `--no-verbose` a `_cli()`**

Nella funzione `_cli()`, dopo `parser.add_argument("--hyperparams", ...)`, aggiungi:

```python
    parser.add_argument("--device",     default="cpu",
                        help="XGBoost device: cpu (default), cuda, mps (future)")
    parser.add_argument("--nthread",    type=int, default=-1,
                        help="XGBoost nthread; -1 = all cores")
    parser.add_argument("--no-verbose", action="store_true",
                        help="Disable per-tree progress bar")
```

Aggiorna la chiamata a `train()`:

```python
    train(
        features_path=args.features,
        out_dir=args.out_dir,
        val_fraction=args.val_fraction,
        seed=args.seed,
        n_estimators=n_est,
        max_depth=depth,
        learning_rate=lr,
        subsample=sub,
        colsample_bytree=col,
        min_child_weight=mcw,
        gamma=gam,
        device=args.device,
        nthread=args.nthread,
        verbose=not args.no_verbose,
    )
```

- [ ] **Step 5: Testa barra per-albero in standalone**

```bash
python -u -m analysis.ml.train_bdt_stage1 \
    --features features_stage1.npz \
    --out-dir analysis/ml/model \
    --hyperparams analysis/ml/model/best_hyperparams.json
```

Expected: barra `training:  53%|█████░| 320/600 [01:02<00:54, auc=0.9986]`

- [ ] **Step 6: Testa --no-verbose**

```bash
python -u -m analysis.ml.train_bdt_stage1 \
    --features features_stage1.npz \
    --out-dir /tmp/bdt_test \
    --n-estimators 50 \
    --no-verbose
```

Expected: nessuna barra tqdm, solo stampa ogni 50 round (da `verbose=50`).

- [ ] **Step 7: Verifica tutti i test**

```bash
python -m pytest analysis/ml/tests/ -v --tb=short
```

Expected: tutti PASSED (43 test).

- [ ] **Step 8: Commit**

```bash
git add analysis/ml/train_bdt_stage1.py
git commit -m "feat: add TqdmCallback per-tree progress and --device/--nthread to train_bdt_stage1"
```

---

## Task 5: run_pipeline.sh — stage progress + timing + grid search

**Files:**
- Modify: `run_pipeline.sh`

**Interfaces:**
- Consumes: `grid_search_stage1.py` (Task 3), `train_bdt_stage1.py` (Task 4)
- Produces: script con 4 step, funzione `stage()`, timing, flag `--skip-grid-search` e `--grid-search-niter`

- [ ] **Step 1: Aggiorna il commento header e aggiungi variabili**

Sostituisci il blocco commento in cima:

```bash
#!/usr/bin/env bash
# ============================================================
# GRAAL full MC + BDT pipeline
#
# Usage:
#   ./run_pipeline.sh [--nevents N] [--out-dir DIR] [--skip-mc]
#                     [--skip-features] [--skip-grid-search]
#                     [--grid-search-niter N] [--skip-train] [--help]
#
# Steps:
#   1. Generate ROOT MC (signal + 5 background channels)
#   2. Build stage-1 BDT features  (build_background_features.py)
#   3. Grid search iper-parametri  (grid_search_stage1.py)
#   4. Train stage-1 BDT           (train_bdt_stage1.py)
# ============================================================
```

Dopo `SKIP_TRAIN=0`, aggiungi:

```bash
SKIP_GRID_SEARCH=0
GRID_SEARCH_NITER=30
```

- [ ] **Step 2: Aggiungi i nuovi flag al parser CLI**

Nel blocco `while [[ $# -gt 0 ]]; do`, aggiungi prima di `--help`:

```bash
        --skip-grid-search)   SKIP_GRID_SEARCH=1;           shift   ;;
        --grid-search-niter)  GRID_SEARCH_NITER="$2";       shift 2 ;;
```

- [ ] **Step 3: Aggiungi funzione `stage()` e `stage_done()`**

Dopo `ROOT_EXEC="${ROOT_EXEC:-root}"`, aggiungi:

```bash
# ---- helpers ----
_STAGE_T0=0

stage() {
    local n=$1 total=$2 desc=$3
    _STAGE_T0=$(date +%s)
    echo ""
    echo "[${n}/${total}] ${desc}  ($(date '+%H:%M:%S'))"
}

stage_done() {
    local T1
    T1=$(date +%s)
    echo "    -> completato in $((T1 - _STAGE_T0))s"
}

TOTAL_STAGES=4
```

- [ ] **Step 4: Sostituisci Step 1 MC generation**

Sostituisci `echo "" && echo "=== Step 1: MC generation ==="` con:

```bash
    stage 1 $TOTAL_STAGES "MC generation (${NEVENTS} eventi per canale)"
```

Sostituisci `echo "  MC generation done."` con `stage_done`.

Sostituisci `echo "=== Step 1: MC generation skipped ==="` con:

```bash
    echo "[1/${TOTAL_STAGES}] MC generation — saltato"
```

- [ ] **Step 5: Sostituisci Step 2 build features**

Sostituisci `echo "" && echo "=== Step 2: build stage-1 features ==="` con:

```bash
    stage 2 $TOTAL_STAGES "Build features stage-1"
```

Sostituisci `echo "  Features saved to ${FEATURES_FILE}."` con `stage_done`.

Sostituisci `echo "=== Step 2: feature building skipped ==="` con:

```bash
    echo "[2/${TOTAL_STAGES}] Feature building — saltato"
```

- [ ] **Step 6: Sostituisci Step 3 (train) con Step 3 (grid search) + Step 4 (train)**

Sostituisci l'intero blocco `# ---- Step 3: train BDT ----` con:

```bash
# ---- Step 3: grid search (opzionale) ----
if [[ $SKIP_TRAIN -eq 0 && $SKIP_GRID_SEARCH -eq 0 ]]; then
    stage 3 $TOTAL_STAGES "Grid search iper-parametri (n_iter=${GRID_SEARCH_NITER})"

    if [[ ! -f "$FEATURES_FILE" ]]; then
        echo "ERROR: ${FEATURES_FILE} not found (run step 2 first)"
        exit 1
    fi

    python -u -m analysis.ml.grid_search_stage1 \
        --features  "$FEATURES_FILE" \
        --out-dir   "$OUT_DIR" \
        --n-iter    "$GRID_SEARCH_NITER"

    stage_done
elif [[ $SKIP_TRAIN -eq 0 ]]; then
    echo "[3/${TOTAL_STAGES}] Grid search — saltato"
fi

# ---- Step 4: train BDT ----
if [[ $SKIP_TRAIN -eq 0 ]]; then
    stage 4 $TOTAL_STAGES "Training BDT stage-1"

    if [[ ! -f "$FEATURES_FILE" ]]; then
        echo "ERROR: ${FEATURES_FILE} not found (run step 2 first)"
        exit 1
    fi

    HYPERPARAMS_FLAG=""
    if [[ -f "${OUT_DIR}/best_hyperparams.json" ]]; then
        HYPERPARAMS_FLAG="--hyperparams ${OUT_DIR}/best_hyperparams.json"
        echo "  Usando iper-parametri da ${OUT_DIR}/best_hyperparams.json"
    fi

    python -u -m analysis.ml.train_bdt_stage1 \
        --features  "$FEATURES_FILE" \
        --out-dir   "$OUT_DIR" \
        ${HYPERPARAMS_FLAG}

    stage_done
    echo ""
    echo "  Threshold : $(cat "${OUT_DIR}/stage1_threshold.txt")"
    echo ""
    echo "  Metrics:"
    cat "${OUT_DIR}/stage1_metrics.txt"
else
    echo "[4/${TOTAL_STAGES}] BDT training — saltato"
fi
```

- [ ] **Step 7: Testa pipeline rapido con grid search**

```bash
./run_pipeline.sh --nevents 10000 --skip-mc --grid-search-niter 3
```

Expected output (schema):
```
[2/4] Build features stage-1  (14:30:01)
  ...
    -> completato in 45s

[3/4] Grid search iper-parametri (n_iter=3)  (14:30:46)
grid search: 100%|████████| 3/3 [01:02<00:00, best=0.9985, last=0.9982]
    -> completato in 62s

[4/4] Training BDT stage-1  (14:31:48)
training: 100%|████████| 400/400 [00:38<00:00, auc=0.9987]
    -> completato in 38s
```

- [ ] **Step 8: Testa --skip-grid-search**

```bash
./run_pipeline.sh --skip-mc --skip-features --skip-grid-search
```

Expected:
```
[1/4] MC generation — saltato
[2/4] Feature building — saltato
[3/4] Grid search — saltato

[4/4] Training BDT stage-1  (HH:MM:SS)
...
```

- [ ] **Step 9: Verifica tutti i test Python**

```bash
python -m pytest analysis/ml/tests/ -v --tb=short
```

Expected: tutti PASSED (43 test).

- [ ] **Step 10: Commit e push**

```bash
git add run_pipeline.sh
git commit -m "feat: add stage progress, timing, and grid search step to run_pipeline.sh"
git push
```

---

## Verifica finale

- [ ] **Run completo rapido end-to-end**

```bash
./run_pipeline.sh --nevents 10000 --grid-search-niter 5
```

Verifica: 4 stage con timestamp, barra outer grid search, barra per-albero training.
