import os
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")  # GPU0 only
import torch
from transformers import AutoTokenizer, AutoModel

_MODEL_ID = "bert-base-chinese"
_cache = {}

def _load():
    if "tok" not in _cache:
        tok = AutoTokenizer.from_pretrained(_MODEL_ID)
        model = AutoModel.from_pretrained(_MODEL_ID, output_hidden_states=False)
        device = "cuda:0" if torch.cuda.is_available() else "cpu"
        model.to(device).eval()
        _cache["tok"], _cache["model"], _cache["device"] = tok, model, device
    return _cache["tok"], _cache["model"], _cache["device"]

@torch.no_grad()
def embed(text: str) -> list:
    """Return an L2-normalised 768-dim mean-pooled contextual embedding for Chinese text."""
    tok, model, device = _load()
    enc = tok(text, return_tensors="pt", truncation=True, max_length=256).to(device)
    out = model(**enc).last_hidden_state
    mask = enc["attention_mask"].unsqueeze(-1).float()
    vec = (out * mask).sum(1) / mask.sum(1).clamp(min=1e-6)
    vec = torch.nn.functional.normalize(vec, dim=-1)
    return vec[0].tolist()

@torch.no_grad()
def fill_mask(text: str, top_k: int = 5) -> list:
    """Predict the token filling the single [MASK] position. Returns [{token, score}]."""
    tok, model, device = _load()
    if "[MASK]" not in text:
        raise ValueError("fill_mask requires exactly one [MASK] token")
    enc = tok(text, return_tensors="pt").to(device)
    logits = model(**enc).last_hidden_state[0]
    mask_pos = (enc["input_ids"][0] == tok.mask_token_id).nonzero(as_tuple=True)[0]
    if len(mask_pos) != 1:
        raise ValueError("fill_mask requires exactly one [MASK] token")
    probs = torch.softmax(logits[mask_pos[0]], dim=-1)
    vals, idxs = torch.topk(probs, k=top_k)
    return [{"token": tok.convert_ids_to_tokens(int(i)), "score": float(v)} for v, i in zip(vals, idxs)]

@torch.no_grad()
def similarity(a: str, b: str) -> float:
    """Cosine similarity between the mean-pooled embeddings of two texts."""
    va = torch.tensor(embed(a)); vb = torch.tensor(embed(b))
    return float(torch.dot(va, vb))  # both already L2-normalised

@torch.no_grad()
def tokenize(text: str) -> list:
    """Return WordPiece tokens for Chinese text."""
    tok, _, _ = _load()
    return tok.tokenize(text)
