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


if __name__ == "__main__":
    main()
