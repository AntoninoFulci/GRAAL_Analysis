# 05 — BDT stage-1

`05_analysis_bdt/` addestra il classificatore che il gate di
[`03_analysis/stage1_gate.py`](03-analysis-bdt-gate) applica prima della
combinatoria chi2: un BDT binario (XGBoost) che impara a distinguere il
segnale η π⁰ dal fondo fisico prima ancora che si tenti di ricostruirlo.

## A cosa serve

Rigettare eventi di fondo palesemente non-segnale *prima* della
ricostruzione, riducendo la contaminazione nel campione finale rispetto al
solo taglio chi2. Il modello non sostituisce il chi2 — lavora a monte:
`reconstruct_eta_pi0_bdt.py` applica prima il gate, poi la stessa
combinatoria chi2 che usa `reconstruct_eta_pi0_chi2.py` (vedi
[03 — Analisi](03-analysis)).

## Dati di addestramento

Costruiti da `build_background_features.py` (vedi
[Feature stage-1](05-analysis-bdt-features) per il dettaglio delle 24
feature) a partire dai sei canali Monte Carlo di
[04 — Simulazione MC](04-mc-simulation): segnale = `eta_pi0` (etichetta 1),
fondo = gli altri cinque canali, pesati per sezione d'urto efficace
(`sigma_eff` dal CSV) e uniti in un unico set (etichetta 0).

## Metriche correnti

Da `05_analysis_bdt/model/stage1_metrics.txt` (valori reali, non da fidarsi
di numeri citati altrove — questo file è la fonte):

```
AUC:       0.9985
Threshold: 0.8423
Precision: 0.9764
Recall:    0.9856
F1:        0.9809
N_train:   2119915
N_val:     529979
```

La soglia operativa (`05_analysis_bdt/model/stage1_threshold.txt`, `0.842261`)
è scelta massimizzando l'F1 su un set di validazione (`_find_best_threshold`
in `train_bdt_stage1.py`, ricerca su 200 punti tra 0.01 e 0.99) — non è un
valore fissato a mano, viene ricalcolata a ogni training.

## Grid search

```bash
python -m analysis_bdt.grid_search_stage1 \
    --features 05_analysis_bdt/data/features_stage1.npz \
    --out-dir  05_analysis_bdt/model \
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

La griglia completa (prodotto dei sei elenchi sopra) è 4×4×3×3×3×3 = 1296
combinazioni — più delle "108 combos" citate nel docstring del modulo, che
è rimasto indietro rispetto alla griglia effettiva. Di default esegue una
ricerca randomizzata (`--n-iter` configurazioni campionate a caso, 30 di
default), con `--full-grid` per enumerarle tutte. Ogni configurazione usa
XGBoost early stopping (`_EARLY_STOPPING_ROUNDS = 20`, cap a
`_N_ESTIMATORS_MAX = 400` alberi) per restare veloce. Il risultato migliore
va in `best_hyperparams.json`, il riepilogo completo in
`grid_search_results.csv`.

## Training

```bash
python -m analysis_bdt.train_bdt_stage1 \
    --features 05_analysis_bdt/data/features_stage1.npz \
    --out-dir  05_analysis_bdt/model \
    [--hyperparams 05_analysis_bdt/model/best_hyperparams.json]
```

Se `--hyperparams` è passato, il JSON prodotto dalla grid search sovrascrive
`--n-estimators`, `--max-depth`, `--lr` e gli altri iperparametri di
default. Il training usa `sample_weight` dalle sezioni d'urto, valuta AUC su
un set di validazione (`--val-fraction`, 0.2 di default), sceglie la soglia
operativa per F1 massimo, e scrive:

| File | Contenuto |
|---|---|
| `bdt_stage1.json` | il booster XGBoost |
| `stage1_threshold.txt` | soglia operativa (scalare) |
| `stage1_metrics.txt` | AUC, soglia, precision, recall, F1, N_train, N_val |
| `stage1_roc.png` | curva ROC |
| `stage1_feature_importance.png` | importanza delle 24 feature (gain) |
| `stage1_score_dist.png` | distribuzione degli score, segnale vs fondo |

## Come ri-addestrare

`run_pipeline.sh` incatena le tre fasi (build feature → grid search →
training) come fasi 4-6 — vedi [Pipeline](pipeline) per i flag
(`--skip-features`, `--skip-grid-search`, `--grid-search-niter`,
`--skip-train`). Per rifare solo l'addestramento senza rigenerare l'MC o le
feature, i due comandi sopra bastano da soli, a patto che
`05_analysis_bdt/data/features_stage1.npz` esista già.

## Dove andare da qui

- [Feature stage-1](05-analysis-bdt-features) — le 24 feature nell'ordine
  reale del vettore, e la regola contro cui il bug del gate ha reagito.
