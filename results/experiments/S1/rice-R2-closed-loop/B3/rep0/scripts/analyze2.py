import sys; sys.path.insert(0,"/home/test/.local/lib/python3.12/site-packages")
import json, numpy as np
from math import erf, sqrt

rank=json.load(open('/data/mzb/paper2agent/results/experiments/S1/rice-R2-closed-loop/B3/rep0/full_rank_my.json'))
pred={r['id']:r['predicted'] for r in rank}
order=[r['id'] for r in rank]

prior={"IRIS_313.12254":5.0,"IRIS_313.12344":4.6,"IRIS_313.12242":4.5,"IRIS_313.12228":3.8,
 "IRIS_313.11094":3.6,"IRIS_313.12262":3.4,"IRIS_313.11623":3.3,"IRIS_313.12063":3.3,
 "IRIS_313.12352":3.1,"IRIS_313.12342":3.1,"IRIS_313.11086":3.1,"IRIS_313.12330":2.8,
 "IRIS_313.10883":2.7,"IRIS_313.12015":2.6,"IRIS_313.10001":2.6,"IRIS_313.9461":2.2,
 "IRIS_313.11905":2.0,"IRIS_313.11218":1.2,"IRIS_313.10679":3.6,"IRIS_313.12321":3.3,
 "IRIS_313.12134":2.9,"IRIS_313.12349":4.7,"IRIS_313.12129":3.8,"IRIS_313.10653":3.4,
 "IRIS_313.12227":3.3,"IRIS_313.10660":3.4,"IRIS_313.11845":3.3,"IRIS_313.11705":2.9,
 "IRIS_313.12251":2.5,"IRIS_313.12049":2.0}
new={"IRIS_313.10448":2.1,"IRIS_313.11841":3.1,"IRIS_313.12231":3.3,"IRIS_313.9302":3.4,
 "IRIS_313.12185":2.6,"IRIS_313.11388":2.7,"IRIS_313.12225":3.6,"IRIS_313.8586":3.6,
 "IRIS_313.10704":2.9,"IRIS_313.12302":3.0,"IRIS_313.9415":2.1,"IRIS_313.11241":1.7,
 "IRIS_313.12313":3.3,"IRIS_313.9469":2.8,"IRIS_313.12263":2.8,"IRIS_313.10656":3.6,
 "IRIS_313.8638":3.1,"IRIS_313.9123":2.4,"IRIS_313.11755":2.9,"IRIS_313.10784":2.9,
 "IRIS_313.11961":2.8,"IRIS_313.12287":2.6,"IRIS_313.12229":3.7,"IRIS_313.8884":2.7,
 "IRIS_313.11832":2.0,"IRIS_313.11340":3.7,"IRIS_313.10993":2.6,"IRIS_313.10577":2.1,
 "IRIS_313.10441":3.4}
meas={**prior,**new}
print("n unique measured:",len(meas))

x=np.array([pred[i] for i in meas]); y=np.array([meas[i] for i in meas])
def spearman(a,b):
    ra=np.argsort(np.argsort(a)); rb=np.argsort(np.argsort(b))
    return float(np.corrcoef(ra,rb)[0,1])
rho=spearman(x,y)
A=np.vstack([x,np.ones_like(x)]).T; coef,*_=np.linalg.lstsq(A,y,rcond=None); a,b=coef
resid=y-(a*x+b); sd=float(np.std(resid,ddof=2))
r2=1-np.sum(resid**2)/np.sum((y-y.mean())**2)
print(f"n={len(x)} spearman={rho:.3f} r2={r2:.3f} fit meas={a:.3f}*pred{b:+.3f} resid_sd={sd:.3f}")

# bootstrap pool Q75 threshold
allp=np.array([pred[i] for i in order])
rng=np.random.default_rng(0)
def fit(xx,yy):
    A=np.vstack([xx,np.ones_like(xx)]).T
    c,*_=np.linalg.lstsq(A,yy,rcond=None); return c
qs=[]
for _ in range(4000):
    idx=rng.integers(0,len(x),len(x))
    aa,bb=fit(x[idx],y[idx]); qs.append(np.percentile(aa*allp+bb,75))
qs=np.array(qs)
q75=np.percentile(qs,50); lo,hi=np.percentile(qs,2.5),np.percentile(qs,97.5)
print(f"pool Q75={q75:.3f}  CI95=[{lo:.3f},{hi:.3f}]")
print(f"raw pred Q75={np.percentile(allp,75):.3f}")

def p_exceed(mu,thr):
    z=(mu-thr)/(sd*sqrt(2)); return 0.5*(1+erf(z))

# posterior mean & P(>Q75) for all
rows=[]
for r in rank:
    cid=r['id']; p=r['predicted']
    if cid in meas:
        mu=meas[cid]; pe=1.0 if mu>hi else (1.0 if mu>q75 else (0.5 if abs(mu-q75)<1e-9 else 0.0))
        rows.append((cid,mu,pe,True))
    else:
        mu=a*p+b; pe=p_exceed(mu,q75)
        rows.append((cid,mu,pe,False))
rows.sort(key=lambda t:(-t[2],-t[1]))
print("\nTop 22 by posterior (id, est, P>Q75, measured):")
for t in rows[:22]:
    print(f"{t[0]}  est={t[1]:.2f}  P={t[2]:.3f}  meas={t[3]}")
json.dump([{"id":t[0],"est":t[1],"p":t[2],"measured":t[3]} for t in rows], open('/data/mzb/paper2agent/results/experiments/S1/rice-R2-closed-loop/B3/rep0/revised2.json','w'))

# Also rank by measured value for measured lines, tie by pred
morder=sorted([ (c,meas[c],pred[c]) for c in meas], key=lambda t:(-t[1],-t[2]))
print("\nAll measured ranked by value:")
for i,(c,v,pp) in enumerate(morder,1):
    print(f"{i:2d} {c} meas={v:.1f} pred={pp:.3f}")
