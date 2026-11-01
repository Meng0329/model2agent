import json, math
import numpy as np
ranked=json.load(open('ranked_e1.json'))
pred={r['id']:r['predicted'] for r in ranked}
# Round1 E3
e3={"IRIS_313.12254":5.0,"IRIS_313.12242":4.5,"IRIS_313.12344":4.6,"IRIS_313.12228":3.8,
"IRIS_313.11094":3.6,"IRIS_313.11623":3.3,"IRIS_313.12063":3.3,"IRIS_313.12352":3.1,
"IRIS_313.12262":3.4,"IRIS_313.12342":3.1,"IRIS_313.10679":3.6,"IRIS_313.12321":3.3,
"IRIS_313.10921":2.7,"IRIS_313.10089":3.5,"IRIS_313.8683":1.9,"IRIS_313.10569":3.0,
"IRIS_313.8567":2.6,"IRIS_313.9108":2.2,"IRIS_313.11734":2.8,"IRIS_313.10294":2.4}
ids=list(e3.keys())
x=np.array([pred[i] for i in ids]); y=np.array([e3[i] for i in ids])
# linear regression y ~ a + b x
n=len(x); b,cov=np.polyfit(x,y,1)
# manual
xm=x.mean(); ym=y.mean()
b=np.sum((x-xm)*(y-ym))/np.sum((x-xm)**2); a=ym-b*xm
resid=y-(a+b*x)
s=np.sqrt(np.sum(resid**2)/(n-2))
print(f"fit: measured = {a:.3f} + {b:.3f}*E1 ; residual sd={s:.3f}, n={n}")
r=np.corrcoef(x,y)[0,1]
print("pearson r(E1,E3)=",round(r,3), " spearman-ish r^2=",round(r*r,3))
# rank corr
def spearman(x,y):
    rx=np.argsort(np.argsort(x)); ry=np.argsort(np.argsort(y))
    return np.corrcoef(rx,ry)[0,1]
print("spearman(E1,E3)=",round(spearman(x,y),3))
# top-12 vs controls
top12=y[:12]; ctrl=y[12:]
print("top12 mean",round(top12.mean(),3),"ctrl mean",round(ctrl.mean(),3))
# estimate quartile threshold via simulation over all lines
N=20000
rng=np.random.default_rng(20261102)
allx=np.array([pred[r['id']] for r in ranked])
mu=a+b*allx
thr_ests=[]
for rep in range(400):
    sim=rng.normal(mu, s)
    thr=np.quantile(sim,0.75)
    thr_ests.append(thr)
thr=np.mean(thr_ests); thr_sd=np.std(thr_ests)
print(f"estimated 75th-pct threshold (measured units): {thr:.3f} +/- {thr_sd:.3f}")
# posterior mean for each line (shrink unmeasured toward model; measured use E3)
json.dump({"a":a,"b":b,"s":s,"thr":thr,"thr_sd":thr_sd}, open('calib.json','w'))
# posterior mean measured: for measured lines use E3; for unmeasured use mu
post={}
for i in ranked:
    mid=i['id']
    if mid in e3:
        post[mid]=e3[mid]
    else:
        post[mid]=a+b*pred[mid]
json.dump(post, open('posterior_mean.json','w'))
# rank all by posterior mean
rp=sorted(post.items(), key=lambda kv:-kv[1])
print("\nTop 25 by posterior mean (marked M=measured):")
for k,(mid,v) in enumerate(rp[:25],1):
    tag='M' if mid in e3 else ' '
    print(f"{k:2d} {tag} {mid} post={v:.3f} E1={pred[mid]:.3f}")
