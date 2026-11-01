import json, math, statistics as st
from scipy import stats
E=json.load(open("analysis_b3/e1_full.json"))
pred={r["id"]:r["predicted"] for r in E["predictions"]}
meas={
"IRIS_313.12254":5.0,"IRIS_313.12242":4.5,"IRIS_313.12344":4.6,"IRIS_313.12228":3.8,
"IRIS_313.11094":3.6,"IRIS_313.11623":3.3,"IRIS_313.12063":3.3,"IRIS_313.12352":3.1,
"IRIS_313.12262":3.4,"IRIS_313.12342":3.1,"IRIS_313.10679":3.6,"IRIS_313.12321":3.3,
"IRIS_313.12134":2.9,"IRIS_313.12349":4.7,"IRIS_313.12129":3.8,"IRIS_313.10653":3.4,
"IRIS_313.12227":3.3,"IRIS_313.10660":3.4,"IRIS_313.11845":3.3,"IRIS_313.12330":2.8}
ids_q=list(meas)
pv=[pred[i] for i in ids_q]; mv=[meas[i] for i in ids_q]
sp=stats.spearmanr(pv,mv); pe=stats.pearsonr(pv,mv)
print("n_queried",len(ids_q),"spearman",round(sp.statistic,4),"p",round(sp.pvalue,4),"pearson",round(pe.statistic,4))
# OLS meas ~ pred
res=stats.linregress(pv,mv)
print("slope",round(res.slope,4),"intercept",round(res.intercept,4),"r",round(res.rvalue,4),"p",round(res.pvalue,4),"stderr_slope",round(res.stderr,4))
resid=[mv[i]-(res.intercept+res.slope*pv[i]) for i in range(len(ids_q))]
sdr=st.pstdev(resid)
print("residual sd (population)",round(sdr,4))
# posterior risk: for each unqueried line, prob measured > 5.0 using calibrated mean and residual sd
mean_meas=st.mean(mv); sd_meas=st.pstdev(mv)
print("meas mean",round(mean_meas,3),"sd",round(sd_meas,3),"min",min(mv),"max",max(mv))
# use residual sd from regression; predictive distribution for unqueried line predicted p: mean=intercept+slope*p, sd=sdr
unq=[r["id"] for r in E["predictions"] if r["id"] not in meas]
rows=[]
for uid in unq:
    p=pred[uid]; mu=res.intercept+res.slope*p
    z=(5.0-mu)/sdr
    prob=1-stats.norm.cdf(z)
    rows.append((uid,p,mu,prob))
rows.sort(key=lambda t:-t[3])
print("n_unqueried",len(unq))
print("expected # unqueried >5.0:",round(sum(r[3] for r in rows),4))
print("P(no unqueried >5.0) =",round(stats.norm.cdf((5.0-(res.intercept+res.slope*max([pred[uid] for uid in unq])))/sdr)**0,4) if False else round(math.prod([(1-r[3]) for r in rows]),4))
print("top-risk unqueried:")
for r in rows[:8]: print("  ",r[0],"pred %.3f"%r[1],"mu %.3f"%r[2],"P>5 %.4f"%r[3])
# also a conservative approach: max predicted among unqueried
print("max pred unqueried", max(pred[uid] for uid in unq))
# model rank of 12254 and 12349
print("rank map:", {r["id"]:r["rank"] for r in E["predictions"] if r["id"] in ("IRIS_313.12254","IRIS_313.12349","IRIS_313.12344","IRIS_313.12242")})
json.dump({"spearman":sp.statistic,"pearson":pe.statistic,"slope":res.slope,"intercept":res.intercept,
 "resid_sd":sdr,"exp_unq_gt_max":sum(r[3] for r in rows),"p_no_unq_gt_max":math.prod([(1-r[3]) for r in rows]),
 "top_risk":rows[:8],"measured":meas,"queried":ids_q},open("analysis_b3/calib.json","w"),indent=1)
