"""Generate the verification fixture for cnn_digits (idempotent).

The model was trained on sklearn load_digits: ink is HIGH (0..16) on a dark
background. A real user upload is the opposite (black ink on white paper), so this
fixture renders a black-on-white PNG from a REAL labelled example and records the
expected class.
"""
from __future__ import annotations
import json
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
TEST = HERE / "test"
SIZE = 64


def main() -> None:
    ex = json.loads((HERE / "examples.json").read_text(encoding="utf-8"))
    rec = ex["predict"][0]
    feats = rec["args"]["features"]
    label = int(rec["true_label"])
    ink = np.clip(np.asarray(feats, dtype=np.float32).reshape(8, 8) / 16.0, 0.0, 1.0)
    gray = np.round((1.0 - ink) * 255.0).astype(np.uint8)  # dark ink on white paper
    img = Image.fromarray(gray, mode="L").resize((SIZE, SIZE), Image.BICUBIC)
    TEST.mkdir(parents=True, exist_ok=True)
    img.save(TEST / "fixture_9.png")
    (TEST / "expected.json").write_text(json.dumps({
        "fixture": "fixture_9.png",
        "capability": "predict",
        "expected": label,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "fixture": str(TEST / "fixture_9.png"), "expected": label}))


if __name__ == "__main__":
    main()
