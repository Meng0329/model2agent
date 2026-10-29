# Model Card — bert-base-chinese (pilot asset)

- **Base model**: `bert-base-chinese` (Google BERT, Chinese, uncased)
- **Framework**: HuggingFace Transformers + PyTorch
- **Task family**: Chinese text representation / masked language modelling
- **Intended use**: produce contextual embeddings, fill-mask predictions, and
  cosine similarity for Chinese text. This is a *base* (not fine-tuned) model.
- **Inputs**: UTF-8 Chinese strings; a fill-mask input must contain exactly one `[MASK]`.
- **Outputs**:
  - `embed(text)` -> 768-dim mean-pooled last-hidden-state vector (L2-normalised)
  - `fill_mask(text, top_k)` -> top-k `{token, score}` predictions for the `[MASK]`
  - `similarity(a, b)` -> cosine similarity in [-1, 1]
  - `tokenize(text)` -> list of WordPiece tokens
- **Limitations**: base model — no task-specific head; embedding quality is generic;
  fill-mask reflects general Chinese pretraining, not any downstream label space.
- **License**: Apache-2.0
- **Weights**: resolved from the local HF cache (`models--bert-base-chinese`); if absent,
  downloaded from the Hub. SHA256 of config/tokenizer recorded at freeze time.
- **Compute**: single GPU (GPU0) or CPU; segment size 64M params.
