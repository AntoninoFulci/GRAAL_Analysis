# Spiegazione di `train_bdt.py`

Allena la BDT (XGBoost) sulle feature prodotte da `build_features.py` e salva il
modello più i grafici diagnostici.

---

## Import e costanti

```python
import numpy as np
import xgboost as xgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, confusion_matrix

FEATURES = "analysis/ml/data/features.npz"
MODEL_OUT = "analysis/ml/model/bdt.json"
PLOT_DIR = "analysis/ml/plots"
SEED = 42
```

- `xgboost`: la libreria della BDT.
- `matplotlib.use("Agg")`: backend **senza finestra grafica** — disegna su file
  PNG, indispensabile per girare da terminale/server. Va impostato **prima** di
  importare `pyplot`.
- `train_test_split`: divide i dati in train/test.
- `accuracy_score`, `confusion_matrix`: metriche.
- Le costanti sono i percorsi di input (feature), output (modello, grafici) e il
  seme.

---

## Caricamento dati e split

```python
def main():
    d = np.load(FEATURES, allow_pickle=True)
    X, y, names = d["X"], d["y"], list(d["feature_names"])

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=SEED, stratify=y)
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_tr, y_tr, test_size=0.2, random_state=SEED, stratify=y_tr)
```

- `np.load(...)`: carica `features.npz` (`allow_pickle=True` perché i nomi delle
  feature sono stringhe).
- Primo split: 80% train+val, **20% test** (mai visto in allenamento).
- Secondo split: del rimanente, ancora 20% per la **validation** (per l'early
  stopping).
- `stratify=y`: mantiene **le stesse proporzioni di classi** in ogni split —
  cruciale qui perché le classi sono molto sbilanciate (~97.5% / 2.4% / 0.1%).
- `random_state=SEED`: split deterministico → `evaluate_compare.py` può
  riprodurre **esattamente** lo stesso test set.

---

## Definizione e allenamento del modello

```python
    model = xgb.XGBClassifier(
        n_estimators=400, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        objective="multi:softprob", num_class=3,
        eval_metric="mlogloss", early_stopping_rounds=25,
        random_state=SEED, n_jobs=-1)
    model.fit(X_tr, y_tr, eval_set=[(X_tr, y_tr), (X_val, y_val)], verbose=False)
    model.save_model(MODEL_OUT)
```

Iperparametri della BDT:

- `n_estimators=400`: fino a 400 alberi in sequenza.
- `max_depth=5`: profondità massima di ogni albero (controlla la complessità).
- `learning_rate=0.05`: ogni albero contribuisce poco → apprendimento graduale e
  stabile.
- `subsample=0.8`, `colsample_bytree=0.8`: ogni albero usa l'80% degli eventi e
  l'80% delle feature, scelti a caso → riduce l'overfitting.
- `objective="multi:softprob"`, `num_class=3`: classificazione **multiclasse** a
  3 classi, con probabilità in uscita.
- `eval_metric="mlogloss"`: metrica monitorata (log-loss multiclasse).
- `early_stopping_rounds=25`: se la validation non migliora per 25 round
  consecutivi, ferma l'allenamento (evita overfitting e tempo sprecato).
- `n_jobs=-1`: usa tutti i core della CPU.

`model.fit(..., eval_set=[(train), (val)])`: allena monitorando sia train sia
validation. `model.save_model(...)`: salva il modello in JSON.

---

## Stampa delle accuratezze

```python
    acc = accuracy_score(y_te, model.predict(X_te))
    chi2_acc = np.mean(y_te == 0)
    print(f"BDT test accuracy : {acc:.4f}")
    print(f"chi2 test accuracy: {chi2_acc:.4f}")
```

- `acc`: accuratezza della BDT sul test set (frazione di combinazioni indovinate).
- `chi2_acc = np.mean(y_te == 0)`: accuratezza del χ², che — per costruzione —
  sceglie sempre il blocco 0, quindi è la frazione di eventi con etichetta 0.
- Le due righe stampate sono il confronto principale.

---

## Grafico 1 — curva di apprendimento

```python
    res = model.evals_result()
    plt.figure()
    plt.plot(res["validation_0"]["mlogloss"], label="train")
    plt.plot(res["validation_1"]["mlogloss"], label="val")
    plt.xlabel("boosting round"); plt.ylabel("mlogloss"); plt.legend()
    plt.title("Training curve"); plt.savefig(f"{PLOT_DIR}/training_curve.png", dpi=120)
    plt.close()
```

- `model.evals_result()`: la log-loss round per round su train (`validation_0`) e
  validation (`validation_1`).
- Disegna le due curve: se la validation risale mentre il train scende → segnale
  di overfitting (qui l'early stopping lo previene).

---

## Grafico 2 — importanza delle feature

```python
    imp = model.feature_importances_
    idx = np.argsort(imp)[::-1][:20]
    plt.figure(figsize=(7, 6))
    plt.barh([names[i] for i in idx][::-1], imp[idx][::-1])
    plt.title("Top-20 feature importance (gain)"); plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/feature_importance.png", dpi=120); plt.close()
```

- `model.feature_importances_`: quanto ogni feature ha contribuito (gain).
- `np.argsort(imp)[::-1][:20]`: indici delle **20 feature più importanti**
  (ordinate dalla più alla meno importante).
- `plt.barh(...)`: barre orizzontali con i nomi delle feature. Il `[::-1]` finale
  mette la più importante in alto.

---

## Grafico 3 — matrice di confusione

```python
    cm = confusion_matrix(y_te, model.predict(X_te))
    plt.figure()
    plt.imshow(cm, cmap="Blues"); plt.colorbar()
    for (r, c), v in np.ndenumerate(cm):
        plt.text(c, r, str(v), ha="center", va="center")
    plt.xlabel("predicted slot"); plt.ylabel("true slot")
    plt.title("Confusion matrix"); plt.savefig(f"{PLOT_DIR}/confusion.png", dpi=120)
    plt.close()
```

- `confusion_matrix`: tabella 3×3 — righe = classe vera, colonne = classe
  predetta. La diagonale sono le predizioni corrette.
- `plt.imshow(cm)`: la disegna come mappa di colore.
- Il ciclo `plt.text(...)` scrive il numero dentro ogni cella.
- Mostra **dove** la BDT sbaglia (es. quante volte la verità era nel blocco 1 ma
  la BDT ha scelto lo 0).

```python
if __name__ == "__main__":
    main()
```

Esegue `main()` solo se lanciato direttamente.
