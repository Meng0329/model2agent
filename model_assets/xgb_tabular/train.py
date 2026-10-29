import os, json, hashlib
from pathlib import Path
import numpy as np
import xgboost as xgb
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score

HERE = Path(__file__).resolve().parent
SEED = 20261029

def main():
    data = load_breast_cancer()
    X, y = data.data.astype("float32"), data.target.astype("int64")
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)
    clf = xgb.XGBClassifier(
        n_estimators=200, max_depth=4, learning_rate=0.08,
        subsample=0.9, colsample_bytree=0.9, reg_lambda=1.0,
        objective="binary:logistic", eval_metric="logloss",
        tree_method="hist", device="cpu", random_state=SEED, n_jobs=4,
    )
    clf.fit(Xtr, ytr, eval_set=[(Xte, yte)], verbose=False)
    acc = accuracy_score(yte, clf.predict(Xte))
    out = HERE / "model.json"
    clf.save_model(str(out))
    sha = hashlib.sha256(out.read_bytes()).hexdigest()

    # Grounded examples: one per class
    examples = {"predict": [], "predict_proba": []}
    seen = set()
    for i in range(len(yte)):
        lab = int(yte[i])
        if lab in seen: continue
        seen.add(lab)
        examples["predict"].append({"input": Xte[i].tolist(), "true_label": lab})
        examples["predict_proba"].append({"input": Xte[i].tolist(), "true_label": lab})
        if len(seen) == len(set(y.tolist())): break
    (HERE / "examples.json").write_text(json.dumps(examples, ensure_ascii=False, indent=2))
    (HERE / "metrics.json").write_text(json.dumps({
        "test_accuracy": float(acc), "n_train": int(len(Xtr)), "n_test": int(len(Xte)),
        "n_features": int(X.shape[1]), "feature_names": list(data.feature_names),
        "target_names": list(data.target_names),
        "weights_sha256": sha, "weights_path": "model.json", "seed": SEED,
    }, indent=2))
    print(f"trained xgb-breast-cancer: test_acc={acc:.4f} sha256={sha[:16]}... -> {out}")

if __name__ == "__main__":
    main()
