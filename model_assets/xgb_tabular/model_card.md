# Model Card — xgb-breast-cancer (pilot asset)

- **Model**: XGBoost `XGBClassifier` (200 trees, max_depth 4) trained on sklearn `load_breast_cancer`
- **Framework**: XGBoost + scikit-learn + NumPy (CPU)
- **Task family**: tabular binary classification (malignant / benign breast-tumor diagnosis)
- **Inputs**: a 30-dim float feature vector following the `load_breast_cancer` schema
  (mean radius, mean texture, ... worst fractal dimension)
- **Outputs**:
  - `predict(features)` -> 0 (malignant) or 1 (benign)
  - `predict_proba(features)` -> {"0": p, "1": p}
  - `explain(top_k)` -> top-k features by XGBoost gain importance
  - `classes()` -> [0, 1]
- **Frozen weights**: `model.json` (XGBoost native format); SHA256 in `metrics.json`
- **Split**: stratified 80/20, seed=20261029; test accuracy recorded in `metrics.json`
- **Limitations**: small tabular dataset; expects the same 30-feature schema and scale as training.
- **License**: Apache-2.0 (xgboost); dataset BSD (scikit-learn)
