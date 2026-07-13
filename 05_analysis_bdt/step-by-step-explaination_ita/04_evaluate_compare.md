# Spiegazione di `evaluate_compare.py`

Confronta BDT e χ² sullo **stesso test set** non visto in allenamento, e produce
gli spettri di massa e il file di metriche. È il "verdetto" dello studio.

---

## Import e costanti

```python
import numpy as np
import xgboost as xgb
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

FEATURES = "analysis/ml/data/features.npz"
MODEL = "analysis/ml/model/bdt.json"
PLOT_DIR = "analysis/ml/plots"
SEED = 42
```

Come in `train_bdt.py`: backend grafico `Agg`, percorsi e seme. Qui carichiamo il
modello già allenato (`MODEL`).

---

## Helper: larghezza del picco

```python
def _peak_width(values, lo, hi):
    sel = values[(values > lo) & (values < hi)]
    return float(np.std(sel)) if len(sel) else float("nan")
```

Misura la larghezza di un picco di massa come **deviazione standard** dei valori
dentro una finestra `[lo, hi]` attorno al picco.

- `values[(values > lo) & (values < hi)]`: tiene solo le masse nella finestra
  (esclude code e fondo lontano).
- `np.std(sel)`: la larghezza. Se la finestra è vuota ritorna `nan` (protezione).

---

## Caricamento e riproduzione dello stesso test set

```python
def main():
    d = np.load(FEATURES, allow_pickle=True)
    X, y, masses = d["X"], d["y"], d["masses"]  # masses: (N,3,2) -> [pi0, eta]

    idx = np.arange(len(y))
    _, te = train_test_split(idx, test_size=0.2, random_state=SEED, stratify=y)
    X_te, y_te, m_te = X[te], y[te], masses[te]
```

- Carica feature, etichette e le masse `(N, 3, 2)` (per ogni evento, le coppie
  [m_low≈π⁰, m_high≈η] dei 3 blocchi ordinati per χ²).
- **Punto delicato:** per valutare la BDT solo su dati mai visti, dobbiamo
  riprodurre lo **stesso** test set di `train_bdt.py`. Lì lo split era
  `train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)`. Qui
  facciamo lo split sugli **indici** `np.arange(len(y))` con gli stessi
  parametri: `train_test_split` è deterministico → gli indici `te` sono
  identici a quelli del test set di allenamento. Quindi il modello non vede mai
  i suoi dati di training.
- `X[te], y[te], masses[te]`: estrae il test set.

---

## Predizioni BDT e χ²

```python
    model = xgb.XGBClassifier()
    model.load_model(MODEL)
    pred = model.predict(X_te)
    chi2_pred = np.zeros_like(y_te)  # block 0 is min-chi2 by construction

    acc_bdt = accuracy_score(y_te, pred)
    acc_chi2 = accuracy_score(y_te, chi2_pred)
```

- Carica il modello allenato e predice la classe (0/1/2) di ogni evento di test.
- `chi2_pred = np.zeros_like(y_te)`: il χ² sceglie **sempre il blocco 0** (per
  costruzione è il χ² minimo), quindi la sua "predizione" è un vettore di zeri.
- `acc_bdt`, `acc_chi2`: accuratezze dei due metodi sullo stesso test set.

---

## Masse ricostruite con ciascun metodo

```python
    rows = np.arange(len(te))
    pi0_truth, eta_truth = m_te[rows, y_te, 0], m_te[rows, y_te, 1]
    pi0_chi2, eta_chi2 = m_te[rows, chi2_pred, 0], m_te[rows, chi2_pred, 1]
    pi0_bdt, eta_bdt = m_te[rows, pred, 0], m_te[rows, pred, 1]
```

Per ogni evento, sceglie il blocco indicato da ciascun metodo e ne estrae le due
masse (π⁰ = colonna 0, η = colonna 1):

- `m_te[rows, y_te, 0/1]`: masse usando la combinazione **vera** (riferimento
  ideale).
- `m_te[rows, chi2_pred, 0/1]`: masse usando la combinazione scelta dal **χ²**.
- `m_te[rows, pred, 0/1]`: masse usando la combinazione scelta dalla **BDT**.

L'indicizzazione `m_te[rows, scelta]` prende, riga per riga, il blocco indicato
dall'indice in `scelta`.

---

## Spettri di massa (grafici)

```python
    for meson, lo, hi, truth, c2, bdt in [
        ("pi0", 0.05, 0.25, pi0_truth, pi0_chi2, pi0_bdt),
        ("eta", 0.35, 0.75, eta_truth, eta_chi2, eta_bdt),
    ]:
        plt.figure()
        bins = np.linspace(lo, hi, 80)
        plt.hist(c2, bins=bins, histtype="step", label="chi2")
        plt.hist(bdt, bins=bins, histtype="step", label="BDT")
        plt.hist(truth, bins=bins, histtype="step", label="truth", linestyle="--")
        plt.xlabel(f"m({meson}) [GeV]"); plt.ylabel("events"); plt.legend()
        plt.title(f"{meson} reconstructed mass")
        plt.savefig(f"{PLOT_DIR}/mass_{meson}.png", dpi=120); plt.close()
```

Un ciclo che fa due grafici (π⁰ e η). Per ciascuno:

- `bins = np.linspace(lo, hi, 80)`: 80 intervalli nell'intervallo di massa scelto.
- Tre istogrammi sovrapposti (`histtype="step"` = solo contorno): masse dal χ²,
  dalla BDT, e dalla verità (tratteggiata, riferimento).
- Salva `mass_pi0.png` e `mass_eta.png`. Confrontando le curve si vede quanto i
  due metodi si avvicinano allo spettro vero.

---

## File di metriche

```python
    with open(f"{PLOT_DIR}/metrics.txt", "w") as fh:
        fh.write(f"Test events: {len(te)}\n")
        fh.write(f"Pairing accuracy  BDT : {acc_bdt:.4f}\n")
        fh.write(f"Pairing accuracy  chi2: {acc_chi2:.4f}\n")
        fh.write(f"Improvement (abs)     : {acc_bdt - acc_chi2:+.4f}\n\n")
        fh.write("Peak width (std within window):\n")
        fh.write(f"  pi0  chi2={_peak_width(pi0_chi2,0.10,0.17):.4f}  "
                 f"bdt={_peak_width(pi0_bdt,0.10,0.17):.4f}\n")
        fh.write(f"  eta  chi2={_peak_width(eta_chi2,0.50,0.60):.4f}  "
                 f"bdt={_peak_width(eta_bdt,0.50,0.60):.4f}\n")

    print(open(f"{PLOT_DIR}/metrics.txt").read())
```

Scrive `metrics.txt` con:

- numero di eventi di test;
- accuratezza di pairing BDT e χ², e il miglioramento assoluto (`+0.0057`);
- la larghezza dei picchi π⁰ ed η per i due metodi (finestre [0.10, 0.17] e
  [0.50, 0.60] GeV attorno ai picchi).

Infine ristampa il file a video.

```python
if __name__ == "__main__":
    main()
```

Esegue `main()` solo se lanciato direttamente.
