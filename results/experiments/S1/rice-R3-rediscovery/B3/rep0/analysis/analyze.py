import json, math
import numpy as np
from scipy import stats

E1 = {r['id']: r['predicted'] for r in json.load(open('analysis/e1_full.json'))}
E3 = {
"IRIS_313.12254":5.0,"IRIS_313.12242":4.5,"IRIS_313.12344":4.6,"IRIS_313.12228":3.8,
"IRIS_313.11094":3.6,"IRIS_313.11623":3.3,"IRIS_313.12063":3.3,"IRIS_313.12352":3.1,
"IRIS_313.12262":3.4,"IRIS_313.12342":3.1,"IRIS_313.10679":3.6,"IRIS_313.12321":3.3,
"IRIS_313.12134":2.9,"IRIS_313.12349":4.7,"IRIS_313.12129":3.8,"IRIS_313.10653":3.4,
"IRIS_313.12227":3.3,"IRIS_313.10660":3.4,"IRIS_313.11845":3.3,"IRIS_313.12330":2.8}

rows = sorted(E3.items(), key=lambda kv: -E1[kv[0]])
print(f"{'id':18s} {'pred':>6s} {'meas':>5s} {'resid':>6s}")
print(f"Spearman(pred,meas) = {stats.spearmanr([E1[i] for i in E3],[E3[i] for i in E3]).statistic:.4f}")
print(f"Pearson  (pred,meas) = {stats.pearsonr([E1[i] for i in E3],[E3[i] for i in E3]).statistic:.4f}")
xs=np.array([E1[i] for i in E3]); ys=np.array([E3[i] for i in E3])
print(f"pred range {xs.min():.3f}-{xs.max():.3f} sd {xs.std(ddof=1):.3f}; meas range {ys.min()}-{ys.max()} sd {ys.std(ddof=1):.3f} mean {ys.mean():.3f}")

# linear calibration y = a + b x
b, a = np.polyfit(xs, ys, 1)
res = ys - (a + b*xs)
n=len(xs); s2 = res@res/(n-2); s = math.sqrt(s2)
se_b = s/math.sqrt(((xs-xs.mean())**2).sum()); se_a = s*math.sqrt(1/n + xs.mean()**2/((xs-xs.mean())**2).sum())
print(f"calibration: meas = {a:.3f} + {b:.3f}*pred ; residual sd {s:.3f}; se_b {se_b:.3f} (t={b/se_b:.2f})")
for i,meas in rows: print(f"{i:18s} {E1[i]:6.3f} {meas:5.1f} {meas-(a+b*E1[i]):6.3f}")

# posterior: probability an unqueried line beats the observed max
Mmax = max(ys); topid=[i for i in E3 if E3[i]==Mmax][0]
print(f"\nobserved max {Mmax} at {topid}")

def logit_p_above(threshold, mu, sd):
    z=(threshold-mu)/sd
    return 1-stats.norm.cdf(z)

# --- Monte Carlo over calibration-parameter uncertainty, bivariate normal on (a,b)
rng=np.random.default_rng(7)
S = np.cov(np.vstack([res, res]), ddof=0)
X = np.column_stack([np.ones(n), xs]); cov_beta = s2*np.linalg.inv(X.T@X)
unq = [i for i in E1 if i not in E3]
pu = np.array([E1[i] for i in unq])
Ns=20000
probs=[]; expected=[]
for k in range(Ns):
    beta = rng.multivariate_normal([a,b], cov_beta)
    sig = s*math.sqrt(rng.chisquare(n-2)/(n-2))
    mu = beta[0]+beta[1]*pu
    p = 1-stats.norm.cdf((Mmax-mu)/sig)
    expected.append(p.sum()); probs.append(np.prod(1-p))
probs=np.array(probs); expected=np.array(expected)
print(f"P(no unqueried line exceeds {Mmax}) = {np.mean(probs):.3f}  [2.5%,97.5%] = {np.percentile(probs,[2.5,97.5]).round(3)}")
print(f"E[#unqueried above {Mmax}] = {np.mean(expected):.2f} (median {np.median(expected):.2f})")

# which unqueried lines are the main risks (mean p, using point estimate)
p_point = 1-stats.norm.cdf((Mmax-(a+b*pu))/s)
order=np.argsort(-p_point)[:10]
print("\nTop risk lines (point-estimate P(meas>max)):")
for j in order: print(f"  {unq[j]:18s} pred {E1[unq[j]]:.3f}  P={p_point[j]:.4f}")
print("sum of point-estimate probabilities =",round(p_point.sum(),3))
