"""Train a RandomForest digit classifier on sklearn load_digits and freeze the artifact.

Run:  python -I model_assets/sklearn_digits/train.py
Produces: model.joblib, examples.json, metrics.json (in this directory).
"""
import os, json, hashlib
import numpy as np
from pathlib import Path
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import joblib

HERE = Path(__file__).resolve().parent
SEED = 20261029

def main():
    digits = load_digits()
    X, y = digits.data, digits.target
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)
    clf = RandomForestClassifier(n_estimators=120, max_depth=None, random_state=SEED, n_jobs=-1)
    clf.fit(Xtr, ytr)
    acc = accuracy_score(yte, clf.predict(Xte))

    bundle = {
        "model": clf,
        "target_names": list(digits.target_names.astype(int).tolist()),
        "feature_names": list(digits.feature_names) if hasattr(digits, "feature_names") else [f"pixel_{i}" for i in range(X.shape[1])],
        "n_features": int(X.shape[1]),
        "image_shape": list(digits.images.shape[1:]),
        "classes": list(clf.classes_.tolist()),
        "train_seed": SEED,
        "test_accuracy": float(acc),
    }
    out = HERE / "model.joblib"
    joblib.dump(bundle, out)

    # SHA256 of the frozen weights (provenance)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()

    # Grounded examples: one sample per class from the test set (true label known).
    examples = {"predict": [], "predict_proba": []}
    seen = set()
    rng = np.random.RandomState(SEED)
    order = rng.permutation(len(Xte))
    for i in order:
        lab = int(yte[i])
        if lab in seen:
            continue
        seen.add(lab)
        examples["predict"].append({"input": Xte[i].tolist(), "true_label": lab})
        examples["predict_proba"].append({"input": Xte[i].tolist(), "true_label": lab})
        if len(seen) == len(bundle["classes"]):
            break

    (HERE / "examples.json").write_text(json.dumps(examples, ensure_ascii=False, indent=2))
    (HERE / "metrics.json").write_text(json.dumps({
        "test_accuracy": float(acc),
        "n_train": int(len(Xtr)), "n_test": int(len(Xte)),
        "weights_sha256": sha,
        "weights_path": str(out.name),
        "seed": SEED,
    }, indent=2))
    print(f"trained digits-rf: test_acc={acc:.4f} sha256={sha[:16]}... -> {out}")

if __name__ == "__main__":
    main()
