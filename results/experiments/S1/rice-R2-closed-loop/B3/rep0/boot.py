import json
import numpy as np

rank = json.load(open("full_rank.json"))
pred = {r["id"]: r["predicted"] for r in rank}
meas = {
 "IRIS_313.12254": 5.0, "IRIS_313.12242": 4.5, "IRIS_313.12344": 4.6,
 "IRIS_313.12228": 3.8, "IRIS_313.11094": 3.6, "IRIS_313.11623": 3.3,
 "IRIS_313.12063": 3.3, "IRIS_313.12352": 3.1, "IRIS_313.12262": 3.4,
 "IRIS_313.12342": 3.1, "IRIS_313.12330": 2.8, "IRIS_313.10883": 2.7,
 "IRIS_313.11086": 3.1, "IRIS_313.12015": 2.6, "IRIS_313.9461": 2.2,
 "IRIS_313.11905": 2.0, "IRIS_313.11218": 1.2, "IRIS_313.10001": 2.6,
}
x = np.array([pred[i] for i in meas]); y = np.array([meas[i] for i in meas])
allp = np.array([pred[r["id"]] for r in rank])

def fit(xx, yy):
    A = np.vstack([xx, np.ones_like(xx)]).T
    c, *_ = np.linalg.lstsq(A, yy, rcond=None)
    return c

a, b = fit(x, y)
cal = a * allp + b
q75 = float(np.percentile(cal, 75))
print(f"point estimate Q75 = {q75:.3f}")

rng = np.random.default_rng(0)
qs = []
for _ in range(4000):
    idx = rng.integers(0, len(x), len(x))
    aa, bb = fit(x[idx], y[idx])
    qs.append(np.percentile(aa * allp + bb, 75))
qs = np.array(qs)
print(f"bootstrap Q75 2.5/50/97.5: {np.percentile(qs,2.5):.3f} / {np.percentile(qs,50):.3f} / {np.percentile(qs,97.5):.3f}")

# P(measured value > threshold) for measured lines, with measurement ~ exact + small noise
print("\nMeasured lines vs bootstrapped threshold distribution:")
for cid, v in sorted(meas.items(), key=lambda kv: -kv[1]):
    p = float(np.mean(v > qs))
    print(f"{cid} meas={v:.1f} P(in top quartile)~{p:.3f}")
