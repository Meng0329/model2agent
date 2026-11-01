import json, numpy as np
ranked=json.load(open('ranked_e1.json'))
pred={r['id']:r['predicted'] for r in ranked}
e3={"IRIS_313.12254":5.0,"IRIS_313.12242":4.5,"IRIS_313.12344":4.6,"IRIS_313.12228":3.8,
"IRIS_313.11094":3.6,"IRIS_313.11623":3.3,"IRIS_313.12063":3.3,"IRIS_313.12352":3.1,
"IRIS_313.12262":3.4,"IRIS_313.12342":3.1,"IRIS_313.10679":3.6,"IRIS_313.12321":3.3,
"IRIS_313.10921":2.7,"IRIS_313.10089":3.5,"IRIS_313.8683":1.9,"IRIS_313.10569":3.0,
"IRIS_313.8567":2.6,"IRIS_313.9108":2.2,"IRIS_313.11734":2.8,"IRIS_313.10294":2.4,
"IRIS_313.12134":2.9,"IRIS_313.12349":4.7,"IRIS_313.12129":3.8,"IRIS_313.10653":3.4,
"IRIS_313.12227":3.3,"IRIS_313.10660":3.4,"IRIS_313.11845":3.3,"IRIS_313.12330":2.8,
"IRIS_313.11705":2.9,"IRIS_313.12251":2.5}
print("n measured:", len(e3))
# sort measured descending, tie-break by E1 prediction descending
items=sorted(e3.items(), key=lambda kv:(-kv[1], -pred[kv[0]]))
print("\nAll measured ranked (value, E1, id):")
for mid,v in items:
    print(f"  {v:.1f}  E1={pred[mid]:.3f}  {mid}")
top=[mid for mid,_ in items[:10]]
print("\nTOP 10:", top)
json.dump({"top_ids":top}, open('final_selection.json','w'), indent=1)

# ---- threshold estimation, two ways ----
# (A) calibration fit on all 30, simulate population quartile
x=np.array([pred[i] for i in e3]); y=np.array([e3[i] for i in e3])
b=np.cov(x,y)[0,1]/np.var(x); a=y.mean()-b*x.mean(); s=np.std(y-(a+b*x),ddof=2)
print(f"\ncalib(all30): y={a:.3f}+{b:.3f}x  resid_sd={s:.3f}")
allx=np.array([pred[r['id']] for r in ranked]); mu=a+b*allx
rng=np.random.default_rng(1); thrs=[]
for _ in range(600):
    thrs.append(np.quantile(rng.normal(mu,s),0.75))
print(f"(A) pop 75th pct est = {np.mean(thrs):.3f} +/- {np.std(thrs):.3f}")
# (B) nonparametric from stratified-control-ish sample: use the 30 as approximate? no.
# Robust check: what values do model top-20 measured span?
top20pred=[r['id'] for r in ranked[:20]]
measured_top=[(i, e3[i]) for i in top20pred if i in e3]
print("(B) measured among model top-20:", measured_top)
# distribution of all 30 measured
vals=np.array(list(e3.values()))
print("30 measured: mean %.3f sd %.3f min %.1f max %.1f"%(vals.mean(),vals.std(),vals.min(),vals.max()))
# probability each selected line exceeds plausible thresholds
for T in (3.0,3.1,3.2):
    print(f"  selected lines with value > {T}:", sum(1 for _,v in items[:10] if v>T),"/10")
