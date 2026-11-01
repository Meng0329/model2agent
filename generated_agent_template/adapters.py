"""Per-asset input adapters: map natural user input to the model's real feature vector.

Every behavior here is declared by the asset, never guessed:
  image  : manifest.image declares ink polarity / pixel scale / canvas; we crop the
           ink bounding box, size-normalize it onto the full canvas (matching how
           the training data was normalized), and scale to the declared range.
           Missing declaration is a hard error (no fallback).
  tabular: CSV must contain every declared feature_name (no padding/guessing).
  raw    : a declared-length numeric vector.
"""
from __future__ import annotations
import csv
import io
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
CFG = json.loads((HERE / "config.json").read_text(encoding="utf-8"))


def _image_cfg() -> dict:
    cfg = CFG.get("image_preprocess")
    if not isinstance(cfg, dict) or not cfg:
        raise RuntimeError(
            "asset does not declare image preprocessing in manifest.image; "
            "refusing to guess polarity/canvas"
        )
    for key in ("ink_polarity", "pixel_scale", "canvas"):
        if key not in cfg:
            raise RuntimeError(f"manifest.image is missing required key: {key}")
    return cfg


def image_to_features_with_trace(img_bytes: bytes, size: int | None = None) -> tuple[list[float], dict]:
    """Decode an uploaded image using the asset's declared convention.

    Returns (features, trace) where trace contains the REAL intermediate values
    (ink bbox, final n*n grid) that the UI visualizes.
    """
    import numpy as np
    try:
        from PIL import Image
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("Pillow is required to decode images (pip install pillow)") from e

    cfg = _image_cfg()
    polarity = cfg["ink_polarity"]
    pixel_scale = float(cfg["pixel_scale"])
    canvas = cfg["canvas"]
    n = int(size or canvas[0])
    if n <= 0 or int(canvas[1]) != n:
        raise RuntimeError(f"declared canvas must be square, got {canvas}")

    img = Image.open(io.BytesIO(img_bytes)).convert("L")
    gray = np.asarray(img, dtype=np.float32)

    # Convert to an "ink intensity" image in the model's training convention.
    if polarity == "ink_on_dark":
        ink = 255.0 - gray          # dark strokes -> high values
    elif polarity == "ink_on_light":
        ink = gray.copy()           # bright strokes -> high values
    else:
        raise RuntimeError(f"unsupported ink_polarity: {polarity}")

    # Crop to the real ink bounding box (rejects scanner/white margins).
    peak = float(ink.max())
    if peak <= 0:
        raise ValueError("uploaded image is blank")
    thr = max(peak * 0.15, 8.0)
    ys, xs = np.where(ink > thr)
    if xs.size == 0:
        raise ValueError("no ink detected in uploaded image")
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1
    pad = max(1, int(round(0.06 * max(x1 - x0, y1 - y0))))
    x0, y0 = max(0, x0 - pad), max(0, y0 - pad)
    x1, y1 = min(ink.shape[1], x1 + pad), min(ink.shape[0], y1 + pad)
    crop = ink[y0:y1, x0:x1]

    # Size-normalize the ink box onto the full n*n canvas.  The asset's training
    # data (UCI/sklearn digits) was produced by centering each 32x32 bitmap by
    # its center of mass, normalizing it to fill the frame, then counting on
    # pixels per non-overlapping 4x4 block.  Stretching the bbox to the whole
    # canvas reproduces that size normalization; preserving aspect ratio would
    # leave an empty row/column and changes the digit's shape statistics.
    resized = np.asarray(
        Image.fromarray(np.clip(crop, 0, 255).astype("uint8")).resize((n, n), Image.LANCZOS),
        dtype=np.float32,
    )
    grid = resized / 255.0 * pixel_scale
    features = [float(v) for v in grid.flatten()]
    trace = {
        "mode": "image",
        "ink_polarity": polarity,
        "pixel_scale": pixel_scale,
        "canvas": [n, n],
        "bbox": [x0, y0, x1, y1],
        "grid": [[round(float(v), 3) for v in row] for row in grid.tolist()],
    }
    return features, trace


def image_to_features(img_bytes: bytes, size: int | None = None) -> list[float]:
    return image_to_features_with_trace(img_bytes, size)[0]


def tabular_rows_to_features(csv_bytes: bytes) -> list[dict]:
    """Parse a CSV with header into per-row feature dicts.

    The asset must declare feature_names; every row must contain all of them.
    No padding, no silent truncation.
    """
    names = CFG.get("feature_names")
    if not isinstance(names, list) or not names:
        raise RuntimeError("tabular asset must declare feature_names in config.json")
    exp = CFG.get("vector_len")
    text = csv_bytes.decode("utf-8-sig", errors="replace")
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        raise ValueError("CSV has no data rows")
    out = []
    for i, r in enumerate(rows):
        missing = [n for n in names if n not in r]
        if missing:
            raise ValueError(f"CSV row {i + 1} is missing columns: {missing}")
        feats = [float(r[n]) for n in names]
        if exp is not None and len(feats) != int(exp):
            raise ValueError(f"CSV row {i + 1} has {len(feats)} features, expected {exp}")
        out.append({"features": feats, "row": dict(r)})
    return out


def raw_to_features(value: str | list) -> list[float]:
    """Parse a declared-length numeric vector (comma/space separated)."""
    if isinstance(value, list):
        feats = [float(x) for x in value]
    else:
        feats = [float(p) for p in value.replace(",", " ").split()]
    exp = CFG.get("vector_len")
    if exp is not None and len(feats) != int(exp):
        raise ValueError(f"expected {exp} values, got {len(feats)}")
    return feats
