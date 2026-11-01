import json
from scipy.stats import spearmanr
import numpy as np
s=json.load(open('scores.json'))['scores']
m={"T17K":0.39334607124328613,"F14K":-0.09433766454458237,"S37N":0.13703592121601105,
"H40K":-0.5783393979072571,"T17I":0.35440775752067566,"L9D":-2.4961514472961426,
"T17V":0.288845956325531,"T17L":0.10830256342887878,"T17R":0.48495471477508545,
"T17M":0.27186697721481323,"I29L":0.1046341210603714,"M19L":0.11650332808494568,
"N22D":0.13318341970443726,"S37K":0.17296814918518066,"F14Y":0.10313118249177933,
"H40N":-0.2638293206691742}
xs=[s[k] for k in m]; ys=list(m.values())
allrho=spearmanr(xs,ys)
pear=np.corrcoef(xs,ys)[0,1]
# excluding the extreme control L9D
ns=[k for k in m if k!="L9D"]
rho_ns=spearmanr([s[k] for k in ns],[m[k] for k in ns])
# ESM-only top5 vs measured top5
esm_top5=[k for k,_ in sorted(((k,s[k]) for k in s), key=lambda kv:-kv[1])[:5]]
meas_top5=[k for k,_ in sorted(m.items(), key=lambda kv:-kv[1])[:5]]
pos17=[(k,m[k]) for k in m if k.startswith("T17")]
pos17.sort(key=lambda kv:-kv[1])
res={"spearman_all16":round(allrho.statistic,3),"p_all16":round(allrho.pvalue,4),
 "pearson_all16":round(float(pear),3),
 "spearman_no_L9D":round(rho_ns.statistic,3),"p_no_L9D":round(rho_ns.pvalue,4),
 "esm_top5":esm_top5,"measured_top5":meas_top5,
 "overlap_esm_top5_vs_measured_top5":len(set(esm_top5)&set(meas_top5)),
 "pos17_measured":pos17,
 "frac_pos17_measured_above_0.25":round(sum(1 for k,v in pos17 if v>0.25)/len(pos17),3)}
json.dump(res,open('analysis.json','w'),indent=1)
print(json.dumps(res,indent=1))
