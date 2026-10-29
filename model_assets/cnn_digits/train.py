import os
os.environ.setdefault("CUDA_VISIBLE_DEVICES", "0")
import hashlib, json
from pathlib import Path
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import DataLoader, TensorDataset
from sklearn.datasets import load_digits
from sklearn.model_selection import train_test_split

HERE = Path(__file__).resolve().parent
SEED = 20261029
torch.manual_seed(SEED); np.random.seed(SEED)

class SmallCNN(nn.Module):
    def __init__(self, n_classes=10):
        super().__init__()
        self.features = nn.Sequential(
            nn.Conv2d(1, 16, 3, padding=1), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 8 -> 4
            nn.Conv2d(16, 32, 3, padding=1), nn.ReLU(inplace=True),
            nn.MaxPool2d(2),  # 4 -> 2
        )
        self.head = nn.Sequential(nn.Flatten(), nn.Linear(32*2*2, 64), nn.ReLU(inplace=True), nn.Linear(64, n_classes))
    def forward(self, x):
        return self.head(self.features(x))

def main():
    dev = "cuda:0" if torch.cuda.is_available() else "cpu"
    digits = load_digits()
    X = digits.data.astype("float32") / 16.0      # normalize 0..16 -> 0..1
    y = digits.target.astype("int64")
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=SEED, stratify=y)
    def ds(X, y):
        t = torch.tensor(X).reshape(-1, 1, 8, 8)
        return TensorDataset(t, torch.tensor(y))
    tr_loader = DataLoader(ds(Xtr, ytr), batch_size=64, shuffle=True)
    model = SmallCNN().to(dev)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    lossf = nn.CrossEntropyLoss()
    for epoch in range(40):
        model.train()
        for xb, yb in tr_loader:
            xb, yb = xb.to(dev), yb.to(dev)
            opt.zero_grad(); loss = lossf(model(xb), yb); loss.backward(); opt.step()
    model.eval()
    with torch.no_grad():
        xt = torch.tensor(Xte).reshape(-1,1,8,8).to(dev)
        acc = (model(xt).argmax(1).cpu().numpy() == yte).mean()
    # Save weights + metadata
    out = HERE / "cnn_state.pt"
    torch.save({"state_dict": model.state_dict(), "classes": list(range(10)),
                "image_shape": [8,8], "n_features": 64, "normalize_scale": 16.0,
                "seed": SEED, "test_accuracy": float(acc)}, out)
    sha = hashlib.sha256(out.read_bytes()).hexdigest()
    # Examples: one per class from test set
    examples = {"predict": [], "predict_proba": []}
    seen = set()
    for i in range(len(yte)):
        lab = int(yte[i])
        if lab in seen: continue
        seen.add(lab)
        examples["predict"].append({"input": Xte[i].tolist(), "true_label": lab})
        examples["predict_proba"].append({"input": Xte[i].tolist(), "true_label": lab})
        if len(seen) == 10: break
    (HERE / "examples.json").write_text(json.dumps(examples, ensure_ascii=False, indent=2))
    (HERE / "metrics.json").write_text(json.dumps({"test_accuracy": float(acc), "n_train": int(len(Xtr)),
        "n_test": int(len(Xte)), "weights_sha256": sha, "weights_path": "cnn_state.pt",
        "epochs": 40, "seed": SEED, "device": dev}, indent=2))
    print(f"trained cnn-digits on {dev}: test_acc={acc:.4f} sha256={sha[:16]}... -> {out}")

if __name__ == "__main__":
    main()
