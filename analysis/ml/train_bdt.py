"""Train a multiclass XGBoost BDT to pick the correct photon pairing."""
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


def main():
    d = np.load(FEATURES, allow_pickle=True)
    X, y, names = d["X"], d["y"], list(d["feature_names"])

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=SEED, stratify=y)
    X_tr, X_val, y_tr, y_val = train_test_split(
        X_tr, y_tr, test_size=0.2, random_state=SEED, stratify=y_tr)

    model = xgb.XGBClassifier(
        n_estimators=400, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8,
        objective="multi:softprob", num_class=3,
        eval_metric="mlogloss", early_stopping_rounds=25,
        random_state=SEED, n_jobs=-1)
    model.fit(X_tr, y_tr, eval_set=[(X_tr, y_tr), (X_val, y_val)], verbose=False)
    model.save_model(MODEL_OUT)

    acc = accuracy_score(y_te, model.predict(X_te))
    chi2_acc = np.mean(y_te == 0)
    print(f"BDT test accuracy : {acc:.4f}")
    print(f"chi2 test accuracy: {chi2_acc:.4f}")

    # training curve
    res = model.evals_result()
    plt.figure()
    plt.plot(res["validation_0"]["mlogloss"], label="train")
    plt.plot(res["validation_1"]["mlogloss"], label="val")
    plt.xlabel("boosting round"); plt.ylabel("mlogloss"); plt.legend()
    plt.title("Training curve"); plt.savefig(f"{PLOT_DIR}/training_curve.png", dpi=120)
    plt.close()

    # feature importance (gain)
    imp = model.feature_importances_
    idx = np.argsort(imp)[::-1][:20]
    plt.figure(figsize=(7, 6))
    plt.barh([names[i] for i in idx][::-1], imp[idx][::-1])
    plt.title("Top-20 feature importance (gain)"); plt.tight_layout()
    plt.savefig(f"{PLOT_DIR}/feature_importance.png", dpi=120); plt.close()

    # confusion matrix
    cm = confusion_matrix(y_te, model.predict(X_te))
    plt.figure()
    plt.imshow(cm, cmap="Blues"); plt.colorbar()
    for (r, c), v in np.ndenumerate(cm):
        plt.text(c, r, str(v), ha="center", va="center")
    plt.xlabel("predicted slot"); plt.ylabel("true slot")
    plt.title("Confusion matrix"); plt.savefig(f"{PLOT_DIR}/confusion.png", dpi=120)
    plt.close()


def explain(n_events=20000, n_show=8, seed=SEED):
    """Test mode: train a small/fast model on a subset and print, step by step,
    how the BDT decides — per-class probabilities for a few events, the
    prediction vs chi2 vs truth, and a text confusion matrix."""
    from analysis.ml import build_features as bf

    print("=" * 78)
    print(f"TEST MODE — training a small BDT on {n_events} events to show its decisions")
    print("=" * 78)

    photons = bf.load_photons("simulation/eta_pi0_mc.root", n_max=n_events)
    X, y, _, names = bf.build(photons, seed=seed)

    X_tr, X_te, y_tr, y_te = train_test_split(
        X, y, test_size=0.2, random_state=seed, stratify=y)

    frac = np.bincount(y, minlength=3) / len(y)
    print("\n[1] Class distribution (slot = which chi2-ordered block holds truth):")
    print(f"    slot0={frac[0]:.4f}   slot1={frac[1]:.4f}   slot2={frac[2]:.4f}")
    print("    slot0 = the chi2 pick is correct; slots 1,2 = chi2 is wrong.")

    print("\n[2] Training a quick model (100 trees) ...")
    model = xgb.XGBClassifier(
        n_estimators=100, max_depth=5, learning_rate=0.1,
        objective="multi:softprob", num_class=3,
        eval_metric="mlogloss", random_state=seed, n_jobs=-1)
    model.fit(X_tr, y_tr)

    proba = model.predict_proba(X_te)
    pred = proba.argmax(axis=1)
    acc_bdt = accuracy_score(y_te, pred)
    acc_chi2 = np.mean(y_te == 0)
    print(f"\n[3] Accuracy on the small test set:  BDT={acc_bdt:.4f}   chi2={acc_chi2:.4f}")

    # show a mix: some events where chi2 is right (truth slot 0) and some
    # where chi2 is wrong (truth slot 1/2) — the interesting cases.
    half = max(1, n_show // 2)
    easy = np.where(y_te == 0)[0][:half]
    hard = np.where(y_te != 0)[0][:n_show - len(easy)]
    show_idx = np.concatenate([easy, hard])
    print(f"\n[4] Per-event decisions ({len(easy)} where chi2 is right + "
          f"{len(hard)} where chi2 is wrong):")
    print("    The BDT outputs a probability for each of the 3 slots; it picks the argmax.")
    print("    ev    P(slot0)  P(slot1)  P(slot2)   pred   chi2   truth   match")
    for e in show_idx:
        p = proba[e]
        match = "ok" if pred[e] == y_te[e] else "X"
        print(f"    {e:<5} {p[0]:>9.3f} {p[1]:>9.3f} {p[2]:>9.3f}"
              f"   {pred[e]:^4} {0:^6} {y_te[e]:^6}   {match}")

    print("\n[5] Confusion matrix (rows = true slot, cols = predicted slot):")
    cm = confusion_matrix(y_te, pred, labels=[0, 1, 2])
    print("            pred0     pred1     pred2")
    for r in range(3):
        print(f"    true{r}" + "".join(f"{cm[r, c]:>10}" for c in range(3)))
    print("\n    Diagonal = correct. Off-diagonal on rows 1,2 = events where chi2 was")
    print("    wrong and the BDT did (or did not) recover them.")
    print("=" * 78)


if __name__ == "__main__":
    import sys
    if "--explain" in sys.argv:
        explain()
    else:
        main()
