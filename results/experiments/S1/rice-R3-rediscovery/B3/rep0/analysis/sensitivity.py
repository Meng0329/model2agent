import json, math
import numpy as np
from scipy import stats
E1={r['id']:r['predicted'] for r in json.load(open('analysis/e1_full.json'))}
E3={"IRIS_313.12254":5.0,"IRIS_313.12242":4.5,"IRIS_313.12344":4.6,"IRIS_313.12228":3.8,"IRIS_313.11094":3.6,"IRIS_313.11623":3.3,"IRIS_313.12063":3.3,"IRIS_313.12352":3.1,"IRIS_313.12262":3.4,"IRIS_313.12342":3.1,"IRIS_313.10679":3.6,"IRIS_313.12321":3.3,"IRIS_313.12134":2.9,"IRIS_313.12349":4.7,"IRIS_313.12129":3.8,"IRIS_313.10653":3.4,"IRIS_313.12227":3.3,"IRIS_313.10660":3.4,"IRIS_313.11845":3.3,"IRIS_313.12330":2.8}
xs=np.array([E1[i] for i in E3]); ys=np.array([E3[i] for i in E3])
b,a=np.polyfit(xs,ys,1)
unq=[i for i in E1 if i not in E3]; pu=np.array([E1[i] for i in unq]); X=pu
print("Sensitivity of P(no unqueried line > 5.0) to residual-sd and slope assumptions")
print(f"{'slope':>6s} {'intercept':>9s} {'sd':>5s} {'E[N>5]':>7s} {'P(no exceed)':>12s}")
for bb,aa,lab in [(b,a,'OLS fit (anchored)'),(3.489,-8.100,'OLS'),(2.0,-3.5,'slope=2 (half)'),(1.0,1.34,'slope=1, anchored at top')]:
    for s in [0.465,0.6,0.8]:
        p=1-stats.norm.cdf((5.0-(aa+bb*X))/s)
        print(f"{bb:6.2f} {aa:9.2f} {s:5.2f} {p.sum():7.2f} {np.exp(np.log1p(-p).sum()):12.3f}  {lab if s==0.465 else ''}")
# probability the TRUE max lies among the measured-20 = coverage argument (Gaussian, monotone)
print()
# empirical: how far is the observed max above the model-implied mean of the next-best set?
print("Runner-up margin: 5.0 (12254) vs 4.7 (12349, predicted rank 14) = 0.3 g")
print("Measured sd of the 20 queried lines = %.3f"%ys.std(ddof=1))
print("Model rank-1 line holds the measured max:", max(E3,key=E3.get)=='IRIS_313.12254')
