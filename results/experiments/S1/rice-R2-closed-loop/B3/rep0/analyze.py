import json
import numpy as np

rank = json.load(open("full_rank.json"))
pred = {r["id"]: r["predicted"] for r in rank}

# Round 1 measurements (E3, oracle)
meas = {
 "IRIS_313.12254": 5.0, "IRIS_313.12242": 4.5, "IRIS_313.12344": 4.6,
 "IRIS_313.12228": 3.8, "IRIS_313.11094": 3.6, "IRIS_313.11623": 3.3,
 "IRIS_313.12063": 3.3, "IRIS_313.12352": 3.1, "IRIS_313.12262": 3.4,
 "IRIS_313.12342": 3.1, "IRIS_313.12330": 2.8, "IRIS_313.10883": 2.7,
 "IRIS_313.11086": 3.1, "IRIS_313.12015": 2.6, "IRIS_313.9461": 2.2,
 "IRIS_313.11905": 2.0, "IRIS_313.11218": 1.2, "IRIS_313.10001": 2.6,
}
x = np.array([pred[i] for i in meas])
y = np.array([meas[i] for i in meas])

# Spearman
def spearman(a, b):
    ra = np.argsort(np.argsort(a)); rb = np.argsort(np.argsort(b))
    return float(np.corrcoef(ra, rb)[0, 1])
rho = spearman(x, y)

# linear fit y = a*x + b
A = np.vstack([x, np.ones_like(x)]).T
coef, *_ = np.linalg.lstsq(A, y, rcond=None)
a, b = coef
resid = y - (a * x + b)
sd = float(np.std(resid, ddof=2))
r2 = 1 - np.sum(resid**2) / np.sum((y - y.mean())**2)

print(f"n={len(x)} spearman={rho:.3f} r2={r2:.3f} fit: meas={a:.3f}*pred+{b:.3f} resid_sd={sd:.3f}")
print("residuals:", np.round(resid, 2).tolist())

# Calibrate all 904 predictions -> expected measured value; pool 75th pct = threshold
allp = np.array([pred[r["id"]] for r in rank])
cal = a * allp + b
q75 = float(np.percentile(cal, 75))
q90 = float(np.percentile(cal, 90))
print(f"estimated pool Q75 threshold={q75:.3f}  Q90={q90:.3f}")
print(f"raw Q75 pred={np.percentile(allp,75):.3f}")

# posterior P(true > threshold) for unqueried, given prediction and resid_sd
from math import erf, sqrt
def p_exceed(p, thr):
    mu = a * p + b
    z = (mu - thr) / (sd * sqrt(2))
    return 0.5 * (1 + erf(z))

ranked = []
for r in rank:
    cid = r["id"]
    p = r["predicted"]
    if cid in meas:
        # observed actual; posterior mean = measurement with small measurement sd
        ranked.append((cid, meas[cid], 1.0 if meas[cid] > q75 else 0.0, 1.0))
    else:
        ranked.append((cid, a * p + b, p_exceed(p, q75), 0.0))
ranked.sort(key=lambda t: -t[2])
print("\nTop 25 revised (pred_meas, P>Q75, measured?):")
for t in ranked[:25]:
    print(f"{t[0]}  est={t[1]:.2f}  P={t[2]:.3f}  measured={bool(t[3])}")
json.dump([{"id": t[0], "est": t[1], "p": t[2], "measured": bool(t[3])} for t in ranked], open("revised.json","w"))
