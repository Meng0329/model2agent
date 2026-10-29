# Model Card — digits-rf (pilot asset)

- **Base model**: scikit-learn `RandomForestClassifier` (120 trees) trained on `load_digits`
- **Framework**: scikit-learn + NumPy (CPU)
- **Task family**: tabular / 8x8 handwritten-digit image classification (10 classes, 0-9)
- **Inputs**: a 64-dim float vector (8x8 image flattened, pixel values 0..16, as in `load_digits`)
- **Outputs**:
  - `predict(features)` -> digit class 0..9
  - `predict_proba(features)` -> {class_str: prob}
  - `explain(top_k)` -> top-k important pixels (Gini)
  - `classes()` -> trained class labels
- **Frozen weights**: `model.joblib`; SHA256 recorded in `metrics.json` at freeze time
- **Train/test split**: stratified 80/20, seed=20261029; test accuracy recorded in `metrics.json`
- **Limitations**: trained on the small `load_digits` (1797 samples); expects inputs in the
  same 0..16 pixel scale; no real-world robustness to distribution shift.
- **License**: BSD-3-Clause (scikit-learn)
