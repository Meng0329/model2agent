"""Per-asset input adapters: map natural user input to the model's real feature vector.

image  : uploaded image -> resize to (NxN grayscale, normalized) -> flat vector
tabular: CSV rows -> reorder columns to the model's feature_names -> row vectors
raw    : direct numeric vector (advanced mode)
"""
from __future__ import annotations
import json
import io
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))


def _cfg():
    return CFG


def image_to_features(img_bytes: bytes, size: int | None = None) -> list[float]:
    """Convert an uploaded image to the model's feature vector.

    For an 8x8 digit CNN: grayscale -> resize to size (default from vector_len,
    sqrt) -> scale pixels to the training range (0..16) -> flatten.
    """
    import numpy as np
    try:
        from PIL import Image
    except ImportError:
        Image = None

    if Image is not None:
        img = Image.open(io.BytesIO(img_bytes)).convert("L")
    else:
        # fallback: use torchvision-free decode via numpy (PNG/JPEG via PIL preferred)
        raise RuntimeError("Pillow is required to decode images (pip install pillow)")

    vlen = CFG.get("vector_len") or 64
    n = size or int(round(vlen ** 0.5)) or 8
    img = img.resize((n, n))
    arr = np.asarray(img, dtype=np.float32)          # 0..255
    arr = arr / 255.0 * 16.0                         # map to training range 0..16
    return [float(x) for x in arr.flatten()]


def tabular_rows_to_features(csv_bytes: bytes) -> list[dict]:
    """Parse CSV (with header) into per-row feature dicts ordered by feature_names.

    Returns [{"features": [..], "row": {col: val}}]. Reorders columns to the
    model's feature_names (or uses column order if not declared).
    """
    import csv
    import io as _io
    text = csv_bytes.decode("utf-8", errors="replace")
    rows = list(csv.DictReader(_io.StringIO(text)))
    names = CFG.get("feature_names")
    out = []
    for r in rows:
        if names:
            feats = [float(r[n]) for n in names if n in r]
            # pad/truncate to expected length
            exp = CFG.get("vector_len") or len(feats)
            feats = feats[:exp] + [0.0] * max(0, exp - len(feats))
        else:
            feats = [float(v) for v in r.values() if v != ""]
        out.append({"features": feats, "row": dict(r)})
    return out


def raw_to_features(value: str | list) -> list[float]:
    """Advanced mode: parse a space/comma-separated numeric string or list."""
    if isinstance(value, list):
        return [float(x) for x in value]
    parts = value.replace(",", " ").split()
    return [float(p) for p in parts]
