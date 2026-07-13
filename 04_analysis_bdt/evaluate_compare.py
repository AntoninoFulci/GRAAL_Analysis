"""Compare BDT vs chi2 on the held-out MC test set: accuracy + mass spectra."""
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


def _peak_width(values, lo, hi):
    sel = values[(values > lo) & (values < hi)]
    return float(np.std(sel)) if len(sel) else float("nan")


def main():
    d = np.load(FEATURES, allow_pickle=True)
    X, y, masses = d["X"], d["y"], d["masses"]  # masses: (N,3,2) -> [pi0, eta]

    idx = np.arange(len(y))
    _, te = train_test_split(idx, test_size=0.2, random_state=SEED, stratify=y)
    X_te, y_te, m_te = X[te], y[te], masses[te]

    model = xgb.XGBClassifier()
    model.load_model(MODEL)
    pred = model.predict(X_te)
    chi2_pred = np.zeros_like(y_te)  # block 0 is min-chi2 by construction

    acc_bdt = accuracy_score(y_te, pred)
    acc_chi2 = accuracy_score(y_te, chi2_pred)

    rows = np.arange(len(te))
    pi0_truth, eta_truth = m_te[rows, y_te, 0], m_te[rows, y_te, 1]
    pi0_chi2, eta_chi2 = m_te[rows, chi2_pred, 0], m_te[rows, chi2_pred, 1]
    pi0_bdt, eta_bdt = m_te[rows, pred, 0], m_te[rows, pred, 1]

    # mass spectra
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


if __name__ == "__main__":
    main()
