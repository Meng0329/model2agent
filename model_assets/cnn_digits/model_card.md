# Model Card — cnn-digits (pilot asset)

- **Model**: a small PyTorch CNN (2 conv blocks + MLP head) trained on `load_digits`
- **Framework**: PyTorch (GPU0)
- **Task family**: image classification (8x8 grayscale handwritten digits, 10 classes)
- **Inputs**: a 64-dim float vector (8x8 image flattened, raw pixel values 0..16).
  Internally divided by 16.0 to normalize to [0,1].
- **Outputs**:
  - `predict(features)` -> digit class 0..9
  - `predict_proba(features)` -> {class_str: prob}
  - `saliency(features, top_k)` -> top-k influential pixels (input-gradient for predicted class)
  - `classes()` -> trained class labels
- **Frozen weights**: `cnn_state.pt`; SHA256 in `metrics.json`. 40 epochs, Adam lr=1e-3, seed=20261029.
- **Limitations**: tiny architecture on the small `load_digits` set; expects the same 0..16 input scale.
- **License**: PyTorch BSD-style
