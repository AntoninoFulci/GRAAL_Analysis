# 04 — Training BDT

`04_bdt_training/` addestra il classificatore che il gate di [`05_reconstruction/stage1_gate.py`](05-reconstruction-bdt-gate) applica prima della combinatoria chi2: un BDT binario (XGBoost) che impara a distinguere il segnale η π⁰ dal fondo fisico prima ancora che si tenti di ricostruirlo.

## A cosa serve

Rigettare eventi di fondo palesemente non-segnale *prima* della ricostruzione, riducendo la contaminazione nel campione finale rispetto al solo taglio chi2.

## Dati di addestramento

Costruiti da `build_background_features.py` (vedi [Feature stage-1](04-bdt-training-features) per il dettaglio delle 26 feature) a partire dai nove canali Monte Carlo di [03 — Simulazione MC](03-mc-simulation). 

## Metriche correnti

Da `04_bdt_training/model/stage1_metrics.txt`:

```
Signal:    eta_pi0
Hypothesis:eta_pi0
Prior:     0.5  (a training choice, not a cross-section)
Beam rewt: True
AUC:       0.9991
Threshold: 0.9654
Precision: 0.8558
Recall:    0.9073
F1:        0.8808
N_train:   2112953
N_val:     528239
```

La soglia operativa (`04_bdt_training/model/stage1_threshold.txt`) è scelta massimizzando l'F1 su un set di validazione (`_find_best_threshold` in `train_bdt_stage1.py`, ricerca su 200 punti tra 0.01 e 0.99).
Questo valore viene ricalcolato ad ogni training.

## Grid search

```bash
python -m bdt_training.grid_search_stage1 \
    --features 04_bdt_training/data/features_stage1.npz \
    --out-dir  04_bdt_training/model \
    --n-iter   30
```

Cerca su una griglia di iperparametri:

```python
_PARAM_GRID = {
    "max_depth":        [3, 4, 5, 6],
    "learning_rate":    [0.05, 0.10, 0.15, 0.20],
    "subsample":        [0.7, 0.8, 1.0],
    "colsample_bytree": [0.7, 0.8, 1.0],
    "min_child_weight": [1, 5, 20],
    "gamma":            [0.0, 0.1, 0.3],
}
```

Di default esegue una ricerca randomizzata (`--n-iter` configurazioni campionate a caso, 30 di default), con `--full-grid` per enumerarle tutte. Ogni configurazione usa XGBoost early stopping (`_EARLY_STOPPING_ROUNDS = 20`, cap a `_N_ESTIMATORS_MAX = 400` alberi) per restare veloce. Il risultato migliore va in `best_hyperparams.json`, il riepilogo completo in `grid_search_results.csv`.

## Training

```bash
python -m bdt_training.train_bdt_stage1 \
    --features 04_bdt_training/data/features_stage1.npz \
    --out-dir  04_bdt_training/model \
    [--hyperparams 04_bdt_training/model/best_hyperparams.json]
```

Se `--hyperparams` è passato, il JSON prodotto dalla grid search sovrascrive `--n-estimators`, `--max-depth`, `--lr` e gli altri iperparametri di default.
Il training usa `sample_weight` dalle sezioni d'urto, valuta AUC su un set di validazione (`--val-fraction`, 0.2 di default), sceglie la soglia operativa per F1 massimo, e scrive:

| File | Contenuto |
|---|---|
| `bdt_stage1.json` | il booster XGBoost |
| `stage1_threshold.txt` | soglia operativa (scalare) |
| `stage1_metrics.txt` | AUC, soglia, precision, recall, F1, N_train, N_val |
| `stage1_roc.png` | curva ROC |
| `stage1_feature_importance.png` | importanza delle 26 feature (gain) |
| `stage1_score_dist.png` | distribuzione degli score, segnale vs fondo |

## Come ri-addestrare

`run_pipeline.sh` concatena le tre fasi (build feature → grid search → training) come fasi 4-6 — vedi [Pipeline](pipeline) per i flag
(`--skip-features`, `--skip-grid-search`, `--grid-search-niter`, `--skip-train`).
Per rifare solo l'addestramento senza rigenerare l'MC o le feature, i due comandi sopra bastano da soli, a patto che `04_bdt_training/data/features_stage1.npz` esista già.
