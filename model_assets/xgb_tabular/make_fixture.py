"""Generate the verification fixture for xgb_tabular (idempotent).

Writes a one-row CSV using the real feature names and the first grounded example,
plus the expected class. This exercises the tabular adapter end to end.
"""
from __future__ import annotations
import csv
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
TEST = HERE / "test"


def main() -> None:
    ex = json.loads((HERE / "examples.json").read_text(encoding="utf-8"))
    names = json.loads((HERE / "metrics.json").read_text(encoding="utf-8"))["feature_names"]
    rec = ex["predict"][0]
    feats = rec["args"]["features"]
    label = int(rec["true_label"])
    TEST.mkdir(parents=True, exist_ok=True)
    with (TEST / "fixture.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(names)
        w.writerow(feats)
    (TEST / "expected.json").write_text(json.dumps({
        "fixture": "fixture.csv",
        "capability": "predict",
        "expected": label,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "fixture": str(TEST / "fixture.csv"), "expected": label}))


if __name__ == "__main__":
    main()
