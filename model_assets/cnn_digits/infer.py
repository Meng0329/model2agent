"""Native inference entry for the cnn-digits asset (part of the model asset, NOT agent code)."""
import os
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
from pathlib import Path
import torch
import torch.nn as nn

_HERE = Path(__file__).resolve().parent

class SmallCNN(nn.Module):
    def __init__(self, n_classes=10):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(inplace=True), nn.MaxPool2d(2),
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(inplace=True), nn.MaxPool2d(2))
        self.head = nn.Sequential(nn.Flatten(), nn.Linear(32*2*2, 64), nn.ReLU(inplace=True), nn.Linear(64, n_classes))
    def forward(self, x): return self.head(self.features(x))

_cache = {}

def _load():
    if "model" not in _cache:
        dev = "cuda:0" if torch.cuda.is_available() else "cpu"
        ckpt = torch.load(_HERE / "cnn_state.pt", map_location=dev)
        m = SmallCNN().to(dev); m.load_state_dict(ckpt["state_dict"]); m.eval()
        _cache.update(model=m, device=dev, meta=ckpt)
    return _cache["model"], _cache["device"], _cache["meta"]

def _prep(features):
    import numpy as np
    scale = 16.0
    arr = torch.tensor(features, dtype=torch.float32).reshape(-1,1,8,8) / scale
    return arr

@torch.no_grad()
def predict(features: list) -> int:
    """Predict the digit class (0-9) for a 64-dim pixel-flattened input (values 0..16)."""
    m, dev, _ = _load()
    return int(m(_prep(features).to(dev)).argmax(1)[0].item())

@torch.no_grad()
def predict_proba(features: list) -> dict:
    """Return class -> probability for a 64-dim input."""
    m, dev, _ = _load()
    probs = torch.softmax(m(_prep(features).to(dev)), dim=-1)[0]
    return {str(i): float(p) for i, p in enumerate(probs)}

def saliency(features: list, top_k: int = 8) -> list:
    """Input-gradient saliency for the predicted class — top-k influential pixels."""
    m, dev, meta = _load()
    x = _prep(features).to(dev).requires_grad_(True)
    out = m(x)
    cls = int(out.argmax(1)[0].item())
    m.zero_grad()
    out[0, cls].backward()
    grad = x.grad[0,0].detach().cpu().numpy().reshape(-1)
    import numpy as np
    idx = np.argsort(np.abs(grad))[::-1][:top_k]
    return [{"pixel": int(i), "grad": float(grad[int(i)])} for i in idx]

def classes() -> list:
    """Return the list of class labels the model was trained on."""
    _, _, meta = _load()
    return list(meta["classes"])
