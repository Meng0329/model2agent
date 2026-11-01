import json, math, numpy as np
from scipy import stats
E=json.load(open("analysis_b3/e1_full.json"))
pred={r["id"]:r["predicted"] for r in E["predictions"]}
C=json.load(open("analysis_b3/calib.json"))
meas=C["measured"]
unq=[i for i in pred if i not in meas]
P=np.array([pred[i] for i in unq]); obs_max=max(meas.values())
a,b=C["intercept"],C["slope"]
mu=a+b*P
print("obs_max",obs_max,"n_unq",len(unq))
print("unq mu range %.2f..%.2f"%(mu.min(),mu.max()))
def p_exceed(sd,df=None):
    if df is None:
        p=stats.norm.sf((obs_max-mu)/sd)
    else:
        t=stats.t(df); s=sd*math.sqrt((df-2)/df)   # scale to match sd
        p=t.sf((obs_max-mu)/s)
    exp=p.sum(); return exp, math.exp(np.log1p(-p).sum())
for sd in [0.30,0.44,0.55,0.70,0.88]:
    e,pn=p_exceed(sd); print("gaussian sd=%.2f expected#=%.4f P(no unq>obs)=%.4f"%(sd,e,pn))
for df in [3,4,8]:
    for sd in [0.44,0.60,0.80]:
        e,pn=p_exceed(sd,df); print("t df=%d sd=%.2f expected#=%.4f P(no unq>obs)=%.4f"%(df,sd,e,pn))
# --- copula sensitivity: P(global max lies in queried top-k) for rho in {0.35,0.45,0.60}
rng=np.random.default_rng(20261102); n=904
for rho in [0.35,0.45,0.60]:
    m=6000; hit20=hit10=hit1=0
    for _ in range(m):
        z=rng.standard_normal(n)
        e=rng.standard_normal(n)
        t=rho*z+math.sqrt(1-rho*rho)*e
        order=np.argsort(-z)
        j=np.argmax(t)
        r=np.where(order==j)[0][0]
        hit1+= r==0; hit20+= r<20; hit10+= r<10
    print("copula rho=%.2f: P(true argmax = top1 pred)=%.3f  in top10=%.3f  in top20=%.3f"%(rho,hit1/m,hit10/m,hit20/m))
